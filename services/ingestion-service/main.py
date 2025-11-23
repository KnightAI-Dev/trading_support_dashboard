"""
Ingestion Service - Main entry point
Orchestrates ingestion from Binance and CoinGecko APIs
"""
import sys
import os
import asyncio
import signal
from datetime import datetime, timedelta, timezone
from typing import List
from sqlalchemy import text
import structlog

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.database import init_db, DatabaseManager
from shared.redis_client import publish_event, get_redis
import logging

# Configure standard logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s',
    stream=sys.stdout,
    force=True
)
# Configure structlog
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)

# Import from modules
from config.settings import (
    DEFAULT_SYMBOLS, DEFAULT_TIMEFRAME, MARKET_DATA_LIMIT
)
from services.binance_service import BinanceIngestionService
from services.coingecko_service import CoinGeckoIngestionService
from services.websocket_service import BinanceWebSocketService
from database.repository import get_qualified_symbols, get_ingestion_timeframes
from utils.gap_detection import backfill_all_symbols_timeframes

# Global shutdown flag
shutdown_event = asyncio.Event()

# Global variables for symbol management
current_symbols = []
symbols_lock = asyncio.Lock()
ws_service_instance = None  # Global reference to WebSocket service for dynamic updates


async def periodic_market_data_update():
    """Background task to update market data every 5 minutes with metrics"""
    logger.info("periodic_market_data_update_started")
    while True:
        try:                        
            start_time = datetime.now()
            await asyncio.sleep(300)  # Wait 5 minutes
            
            # Get all symbols from database that have market data
            with DatabaseManager() as db:
                result = db.execute(
                    text("""
                        SELECT DISTINCT s.symbol_name
                        FROM symbols s
                        INNER JOIN market_data md ON s.symbol_id = md.symbol_id
                        WHERE s.is_active = TRUE AND s.removed_at is NULL
                        ORDER BY s.symbol_name
                    """)
                ).fetchall()
                symbols = [row[0] for row in result]
            
            if symbols:
                logger.info("periodic_market_data_update_starting", symbol_count=len(symbols))
                # Create service instances for this update
                async with BinanceIngestionService() as binance_service:
                    async with CoinGeckoIngestionService() as coingecko_service:
                        await coingecko_service.update_market_data_for_symbols(
                            symbols, binance_service=binance_service
                        )
                
                # Calculate metrics
                duration = (datetime.now() - start_time).total_seconds()
                symbols_per_second = len(symbols) / duration if duration > 0 else 0
                
                logger.info(
                    "periodic_market_data_update_completed",
                    symbol_count=len(symbols),
                    duration_seconds=duration,
                    symbols_per_second=symbols_per_second
                )
            else:
                logger.warning("periodic_market_data_update_no_symbols")

        except asyncio.CancelledError:
            logger.info("periodic_market_data_update_cancelled")
            break
        except Exception as e:
            logger.error(
                "periodic_market_data_update_error",
                error=str(e),
                exc_info=True
            )
            await asyncio.sleep(60)  # Wait 1 minute before retrying


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info("shutdown_signal_received", signal=signum)
        shutdown_event.set()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


async def gap_detection_task(initial_symbols: list, timeframes: list):
    """Periodic task to backfill recent candles for all symbols and timeframes
    Uses current_symbols global variable to pick up config changes
    """
    while not shutdown_event.is_set():
        try:
            if shutdown_event.is_set():
                break
            
            logger.info("gap_detection_starting")
            
            # Use current_symbols if available, otherwise use initial_symbols
            async with symbols_lock:
                symbols_to_use = current_symbols if current_symbols else initial_symbols
            
            async with BinanceIngestionService() as binance_service:
                # Simple approach: fetch recent 400 candles and insert missing ones
                total_inserted = await backfill_all_symbols_timeframes(
                    binance_service=binance_service,
                    symbols=symbols_to_use,
                    timeframes=timeframes,
                    limit=400,
                    max_retries=3
                )
                
                logger.info(
                    "gap_detection_completed",
                    total_candles_inserted=total_inserted
                )
            
            # Sleep after gap detection (check every hour)
            await asyncio.sleep(3600)
            
        except asyncio.CancelledError:
            logger.info("gap_detection_cancelled")
            break
        except Exception as e:
            logger.error(
                "gap_detection_error",
                error=str(e),
                exc_info=True
            )
            await asyncio.sleep(300)  # Wait 5 minutes before retrying


async def backfill_reactivated_symbols(symbols: List[str]):
    """Backfill OHLCV data for newly reactivated symbols"""
    if not symbols:
        return
    
    try:
        logger.info(
            "backfilling_reactivated_symbols_starting",
            symbol_count=len(symbols),
            symbols=symbols[:10] if len(symbols) > 10 else symbols
        )
        
        with DatabaseManager() as db:
            timeframes = get_ingestion_timeframes(db)
        
        async with BinanceIngestionService() as binance_service:
            total_inserted = await backfill_all_symbols_timeframes(
                binance_service=binance_service,
                symbols=symbols,
                timeframes=timeframes,
                limit=400,  # Backfill recent 400 candles
                max_retries=3
            )
            
            logger.info(
                "reactivated_symbols_backfilled",
                symbol_count=len(symbols),
                total_candles_inserted=total_inserted
            )
    except Exception as e:
        logger.error(
            "error_backfilling_reactivated_symbols",
            error=str(e),
            exc_info=True
        )


async def listen_for_config_changes(shutdown_event: asyncio.Event):
    """Listen for ingestion config changes and reload qualified symbols"""
    redis_client = get_redis()
    if not redis_client:
        logger.warning("Redis not available, config change listener disabled")
        return
    
    pubsub = redis_client.pubsub()
    pubsub.subscribe("ingestion_config_changed")
    
    logger.info("config_change_listener_started")
    
    while not shutdown_event.is_set():
        try:
            # Use asyncio.to_thread for blocking Redis call
            message = await asyncio.to_thread(
                pubsub.get_message,
                ignore_subscribe_messages=True,
                timeout=1.0
            )
            
            if message and message.get("type") == "message":
                try:
                    import json
                    data = json.loads(message["data"])
                    logger.info(
                        "ingestion_config_changed_received",
                        timestamp=data.get("timestamp"),
                        message=data.get("message")
                    )
                    
                    # Reload qualified symbols with new config
                    with DatabaseManager() as db:
                        new_symbols, reactivated_symbols = get_qualified_symbols(db)
                        
                        async with symbols_lock:
                            global current_symbols
                            old_symbols = set(current_symbols)
                            new_symbols_set = set(new_symbols)
                            current_symbols = new_symbols
                            
                            added = new_symbols_set - old_symbols
                            removed = old_symbols - new_symbols_set
                            
                            logger.info(
                                "qualified_symbols_reloaded",
                                old_count=len(old_symbols),
                                new_count=len(new_symbols),
                                added_count=len(added),
                                removed_count=len(removed),
                                reactivated_count=len(reactivated_symbols),
                                added_symbols=list(added) if len(added) <= 10 else list(added)[:10],
                                removed_symbols=list(removed) if len(removed) <= 10 else list(removed)[:10],
                                reactivated_symbols=reactivated_symbols[:10] if len(reactivated_symbols) > 10 else reactivated_symbols
                            )
                            
                            # Backfill reactivated symbols immediately (don't block)
                            if reactivated_symbols:
                                logger.info(
                                    "backfilling_reactivated_symbols",
                                    count=len(reactivated_symbols),
                                    symbols=reactivated_symbols[:10] if len(reactivated_symbols) > 10 else reactivated_symbols
                                )
                                # Trigger backfill asynchronously
                                asyncio.create_task(backfill_reactivated_symbols(reactivated_symbols))
                            
                            if added or removed:
                                logger.info(
                                    "symbol_list_changed",
                                    message="Updating WebSocket subscriptions immediately"
                                )
                                
                                # Update WebSocket service immediately if available
                                global ws_service_instance
                                if ws_service_instance:
                                    try:
                                        # Get timeframes from database
                                        with DatabaseManager() as db:
                                            timeframes = get_ingestion_timeframes(db)
                                        
                                        await ws_service_instance.update_symbols(new_symbols, timeframes)
                                        logger.info(
                                            "websocket_subscriptions_updated",
                                            symbol_count=len(new_symbols),
                                            timeframe_count=len(timeframes)
                                        )
                                    except Exception as e:
                                        logger.error(
                                            "error_updating_websocket_subscriptions",
                                            error=str(e),
                                            exc_info=True
                                        )
                                else:
                                    logger.warning(
                                        "websocket_service_not_available",
                                        message="WebSocket service not yet initialized, will update on next reconnection"
                                    )
                                
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing config change message: {e}")
                except Exception as e:
                    logger.error(f"Error processing config change: {e}", exc_info=True)
                    
        except Exception as e:
            logger.error(f"Error in config change listener: {e}")
            await asyncio.sleep(1)
    
    logger.info("config_change_listener_stopped")
    pubsub.close()


async def main():
    """Main ingestion loop with graceful shutdown"""
    setup_signal_handlers()
    
    if not init_db():
        logger.error("database_initialization_failed")
        return
    
    # New ingestion flow: Start with Binance perpetual futures, enrich with CoinGecko
    async with BinanceIngestionService() as binance_service:
        async with CoinGeckoIngestionService() as coingecko_service:
            await coingecko_service.ingest_from_binance_perpetuals_and_save(
                binance_service=binance_service
            )
            logger.info("binance_perpetuals_ingestion_completed")
    
    # Start periodic market data update task (runs every 5 minutes, independently)
    update_task = asyncio.create_task(periodic_market_data_update())
    logger.info("periodic_market_data_update_task_started")
    
    try:
        # Get qualified symbols and timeframes from database
        with DatabaseManager() as db:
            timeframes = get_ingestion_timeframes(db)
            symbols, reactivated_symbols = get_qualified_symbols(db)
            if not symbols:
                logger.warning("no_qualified_symbols_using_defaults")
                symbols = DEFAULT_SYMBOLS
            
            # Backfill any reactivated symbols immediately
            if reactivated_symbols:
                logger.info(
                    "backfilling_initial_reactivated_symbols",
                    count=len(reactivated_symbols),
                    symbols=reactivated_symbols[:10] if len(reactivated_symbols) > 10 else reactivated_symbols
                )
                # Trigger backfill asynchronously (don't block startup)
                asyncio.create_task(backfill_reactivated_symbols(reactivated_symbols))
        
        # Store initial symbols globally
        async with symbols_lock:
            current_symbols = symbols
        
        logger.info(
            "websocket_ingestion_starting",
            symbol_count=len(symbols),
            timeframe_count=len(timeframes),
            timeframes=timeframes
        )
        
        # Start gap detection task (will use current_symbols which can be updated)
        gap_task = asyncio.create_task(gap_detection_task(symbols, timeframes))
        
        # Start config change listener
        config_listener_task = asyncio.create_task(listen_for_config_changes(shutdown_event))
        
        # Start WebSocket service for real-time OHLCV data
        # This replaces the REST polling loop
        async with BinanceWebSocketService() as ws_service:
            # Store global reference for config change listener
            global ws_service_instance
            ws_service_instance = ws_service
            # Start periodic metrics logging task
            async def log_metrics_periodically():
                while not shutdown_event.is_set():
                    try:
                        await asyncio.sleep(300)  # Log every 5 minutes
                        
                        if shutdown_event.is_set():
                            break
                        
                        metrics = ws_service.get_metrics()
                        messages_per_sec = (
                            metrics['messages_received'] / 300 
                            if metrics['messages_received'] > 0 else 0
                        )
                        logger.info(
                            "websocket_metrics",
                            messages_received=metrics['messages_received'],
                            messages_per_second=messages_per_sec,
                            parse_errors=metrics['parse_errors'],
                            reconnect_count=metrics['reconnect_count'],
                            is_connected=metrics['is_connected']
                        )
                    except asyncio.CancelledError:
                        break
            
            metrics_task = asyncio.create_task(log_metrics_periodically())
            
            try:
                # Start WebSocket service (runs indefinitely with reconnection)
                # Pass shutdown_event to allow graceful shutdown
                await ws_service.start(symbols, timeframes, shutdown_event=shutdown_event)
            finally:
                # Graceful shutdown: cancel tasks and flush pending data
                logger.info("shutdown_initiated")
                
                # Cancel metrics task
                metrics_task.cancel()
                try:
                    await metrics_task
                except asyncio.CancelledError:
                    pass
                
                # Cancel gap detection task
                gap_task.cancel()
                try:
                    await gap_task
                except asyncio.CancelledError:
                    pass
                
                # Cancel config listener task
                config_listener_task.cancel()
                try:
                    await config_listener_task
                except asyncio.CancelledError:
                    pass
                
                # Flush any pending batches in WebSocket service
                if ws_service.batch_buffer:
                    logger.info("flushing_pending_batches", count=len(ws_service.batch_buffer))
                    try:
                        with DatabaseManager() as db:
                            await ws_service.flush_batch(db)
                    except Exception as e:
                        logger.error("error_flushing_final_batch", error=str(e))
                
                logger.info("shutdown_completed")
                
                # Clear global reference
                ws_service_instance = None

    finally:
        # Cancel the hourly update task
        update_task.cancel()
        try:
            await update_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())

