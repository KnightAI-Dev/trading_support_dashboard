"""
Strategy Engine Service - Listens to candle updates and executes trading strategy
"""
import sys
import os
import asyncio
import signal
import json
from datetime import datetime
import pandas as pd
import structlog

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.database import init_db, DatabaseManager, SessionLocal
from shared.redis_client import get_redis
from shared.logger import setup_logger
from shared.storage import StorageService
from shared.config import STRATEGY_CANDLE_COUNT
from sqlalchemy import text

from strategy import RunStrategy

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

# Global shutdown flag
shutdown_event = asyncio.Event()


def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown"""
    def signal_handler(signum, frame):
        logger.info("shutdown_signal_received", signal=signum)
        shutdown_event.set()
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def get_candles_from_db(symbol: str, timeframe: str, limit: int = 200) -> pd.DataFrame:
    """
    Fetch candles from database and return as DataFrame.
    
    Args:
        symbol: Symbol name (e.g., "BTCUSDT")
        timeframe: Timeframe (e.g., "4h", "30m", "1h")
        limit: Number of candles to fetch
        
    Returns:
        DataFrame with columns: unix, open, high, low, close, volume
    """
    try:
        db = SessionLocal()
        try:
            query = text("""
                SELECT 
                    EXTRACT(EPOCH FROM oc.timestamp)::BIGINT as unix,
                    oc.open,
                    oc.high,
                    oc.low,
                    oc.close,
                    oc.volume
                FROM ohlcv_candles oc
                INNER JOIN symbols s ON oc.symbol_id = s.symbol_id
                INNER JOIN timeframe t ON oc.timeframe_id = t.timeframe_id
                WHERE s.symbol_name = :symbol
                AND t.tf_name = :timeframe
                ORDER BY oc.timestamp DESC
                LIMIT :limit
            """)
            
            result = db.execute(query, {"symbol": symbol, "timeframe": timeframe, "limit": limit})
            rows = result.fetchall()
            
            if not rows:
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(rows, columns=['unix', 'open', 'high', 'low', 'close', 'volume'])
            # Reverse to get chronological order (oldest first)
            df = df.iloc[::-1].reset_index(drop=True)
            
            return df
        finally:
            db.close()
    except Exception as e:
        logger.error("error_fetching_candles", symbol=symbol, timeframe=timeframe, error=str(e))
        return pd.DataFrame()


async def process_candle_update(candle_data: dict, strategy: RunStrategy):
    """
    Process a candle update event and execute strategy if needed.
    
    Args:
        candle_data: Dictionary with candle data from Redis event
        strategy: RunStrategy instance
    """
    try:
        symbol = candle_data.get("symbol")
        timeframe = candle_data.get("timeframe")
        closed = candle_data.get("closed", False)
        
        # Only process closed candles for 4h and 30m timeframes
        if not closed or timeframe not in ["4h", "30m"]:
            return
        
        logger.info("processing_candle_update", symbol=symbol, timeframe=timeframe)
        
        # Fetch candle data from database
        df_4h = get_candles_from_db(symbol, "4h", limit=STRATEGY_CANDLE_COUNT)
        df_30m = get_candles_from_db(symbol, "30m", limit=STRATEGY_CANDLE_COUNT)
        df_1h = get_candles_from_db(symbol, "1h", limit=STRATEGY_CANDLE_COUNT)  # Always fetch 1h for support/resistance
        
        # Execute strategy
        result = strategy.execute_strategy(
            df_4h=df_4h,
            df_30m=df_30m,
            df_1h=df_1h,
            asset_symbol=symbol
        )
        
        if result.get('executed'):
            logger.info(
                "strategy_executed",
                symbol=symbol,
                timeframe=timeframe,
                reason=result.get('reason'),
                alerts_4h=len(result.get('result', {}).get('alerts_4h', [])),
                alerts_30m=len(result.get('result', {}).get('alerts_30m', [])),
                saved_4h=result.get('db_summary', {}).get('4h', {}).get('saved', 0),
                saved_30m=result.get('db_summary', {}).get('30m', {}).get('saved', 0)
            )
        else:
            logger.debug("strategy_skipped", symbol=symbol, reason=result.get('reason'))
            
    except Exception as e:
        logger.error("error_processing_candle_update", error=str(e), exc_info=True)


async def initialize_strategy_alerts():
    """
    Initialize strategy alerts by scanning all symbols with candle data
    and detecting alerts in the latest candles.
    """
    logger.info("initializing_strategy_alerts")
    
    try:
        # Get all symbols that have candle data for 4h and 30m timeframes
        with StorageService() as storage:
            metadata = storage.get_market_metadata()
            symbols = metadata.get("symbols", [])
            symbol_timeframes = metadata.get("symbol_timeframes", {})
        
        if not symbols:
            logger.warning("no_symbols_found_for_initialization")
            return
        
        strategy = RunStrategy()
        processed_count = 0
        alert_count = 0
        
        # Process each symbol that has 4h or 30m data
        for symbol in symbols:
            try:
                # Check if symbol has 4h or 30m data
                timeframes = symbol_timeframes.get(symbol, [])
                has_4h = "4h" in timeframes
                has_30m = "30m" in timeframes
                
                if not (has_4h or has_30m):
                    continue
                
                logger.debug("processing_symbol_for_initialization", symbol=symbol)
                
                # Fetch candle data
                df_4h = get_candles_from_db(symbol, "4h", limit=STRATEGY_CANDLE_COUNT) if has_4h else None
                df_30m = get_candles_from_db(symbol, "30m", limit=STRATEGY_CANDLE_COUNT) if has_30m else None
                df_1h = get_candles_from_db(symbol, "1h", limit=STRATEGY_CANDLE_COUNT)  # Always fetch 1h for support/resistance
                
                # Validate we have required data
                # Need at least one of 4h or 30m, and 1h for support/resistance
                valid_4h = df_4h is not None and len(df_4h) > 0
                valid_30m = df_30m is not None and len(df_30m) > 0
                valid_1h = df_1h is not None and len(df_1h) > 0
                
                if not (valid_4h or valid_30m):
                    logger.debug("no_valid_4h_or_30m_data", symbol=symbol)
                    continue
                
                if not valid_1h:
                    logger.debug("no_valid_1h_data_for_support_resistance", symbol=symbol)
                    continue
                
                # Execute strategy - pass None for missing timeframes
                # Strategy will handle None values appropriately
                result = strategy.execute_strategy(
                    df_4h=df_4h if valid_4h else None,
                    df_30m=df_30m if valid_30m else None,
                    df_1h=df_1h if valid_1h else None,
                    asset_symbol=symbol
                )
                
                if result.get('executed'):
                    alerts_4h = result.get('result', {}).get('alerts_4h', [])
                    alerts_30m = result.get('result', {}).get('alerts_30m', [])
                    total_alerts = len(alerts_4h) + len(alerts_30m)
                    
                    if total_alerts > 0:
                        alert_count += total_alerts
                        logger.info(
                            "alerts_detected_during_initialization",
                            symbol=symbol,
                            alerts_4h=len(alerts_4h),
                            alerts_30m=len(alerts_30m)
                        )
                    
                    processed_count += 1
                    
            except Exception as e:
                logger.error(
                    "error_processing_symbol_initialization",
                    symbol=symbol,
                    error=str(e),
                    exc_info=True
                )
                continue
        
        logger.info(
            "initialization_complete",
            symbols_processed=processed_count,
            total_alerts_detected=alert_count
        )
        
    except Exception as e:
        logger.error("error_during_initialization", error=str(e), exc_info=True)


async def listen_to_candle_updates():
    """Listen to Redis candle_update events and process them"""
    redis_client = get_redis()
    if not redis_client:
        logger.error("redis_not_available")
        return
    
    strategy = RunStrategy()
    pubsub = redis_client.pubsub()
    pubsub.subscribe("candle_update")
    
    logger.info("strategy_engine_listener_started")
    
    try:
        while not shutdown_event.is_set():
            try:
                # Get message with timeout
                message = pubsub.get_message(timeout=1.0, ignore_subscribe_messages=True)
                
                if message and message.get("type") == "message":
                    try:
                        data = json.loads(message["data"])
                        await process_candle_update(data, strategy)
                    except json.JSONDecodeError as e:
                        logger.error("error_parsing_message", error=str(e))
                    except Exception as e:
                        logger.error("error_processing_message", error=str(e))
                
            except Exception as e:
                if not shutdown_event.is_set():
                    logger.error("error_in_listener_loop", error=str(e))
                    await asyncio.sleep(1)
    finally:
        pubsub.close()
        logger.info("strategy_engine_listener_stopped")


async def main():
    """Main entry point"""
    setup_signal_handlers()
    
    if not init_db():
        logger.error("database_initialization_failed")
        return
    
    logger.info("strategy_engine_service_started")
    
    # Initialize strategy alerts on startup
    try:
        await initialize_strategy_alerts()
    except Exception as e:
        logger.error("error_during_startup_initialization", error=str(e), exc_info=True)
        # Continue even if initialization fails
    
    # Start listening to candle updates
    try:
        await listen_to_candle_updates()
    except KeyboardInterrupt:
        logger.info("shutdown_requested")
    finally:
        logger.info("strategy_engine_service_stopped")


if __name__ == "__main__":
    asyncio.run(main())

