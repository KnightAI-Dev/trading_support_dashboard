"""Simple gap detection and backfill utilities"""
import sys
import os
import asyncio
from datetime import datetime, timezone
from typing import List, Set, Optional
from sqlalchemy import text
import structlog
import aiohttp

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from shared.database import DatabaseManager

# Import from local modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database.repository import get_timeframe_id, get_or_create_symbol_record

logger = structlog.get_logger(__name__)


async def backfill_recent_candles(
    binance_service,
    symbol: str,
    timeframe: str,
    limit: int = 400,
    max_retries: int = 3
) -> int:
    """Backfill recent candles by fetching from Binance and inserting missing ones
    
    Simple logic:
    1. Fetch the most recent N candles from Binance
    2. Check which ones exist in database (batch check)
    3. Insert only the missing ones
    
    Args:
        binance_service: BinanceIngestionService instance
        symbol: Trading symbol (e.g., "BTCUSDT") - will be cleaned
        timeframe: Timeframe string (e.g., "1h", "1d")
        limit: Number of recent candles to fetch (default: 400)
        max_retries: Maximum retry attempts for API calls
    
    Returns:
        Number of candles inserted
    """
    # Clean symbol: remove @ prefix if present (from WebSocket stream names)
    cleaned_symbol = symbol.lstrip("@").upper()
    
    if cleaned_symbol != symbol:
        logger.warning(
            "backfill_symbol_cleaned",
            original=symbol,
            cleaned=cleaned_symbol
        )
    
    logger.info(
        "backfill_recent_candles_starting",
        symbol=cleaned_symbol,
        timeframe=timeframe,
        limit=limit
    )
    
    # Fetch recent candles from Binance
    klines = None
    retry_count = 0
    
    while retry_count <= max_retries:
        try:
            klines = await binance_service.fetch_klines(
                symbol=cleaned_symbol,
                interval=timeframe,
                limit=limit
            )
            break  # Success
            
        except aiohttp.ClientResponseError as e:
            # Handle rate limit errors (429 or -1003)
            is_rate_limit = (
                e.status == 429 or 
                (e.status == 400 and hasattr(e, 'message') and '-1003' in str(e.message))
            )
            
            if is_rate_limit:
                retry_count += 1
                if retry_count <= max_retries:
                    # Exponential backoff for rate limits: 5s, 10s, 20s
                    wait_time = 5 * (2 ** (retry_count - 1))
                    logger.warning(
                        "backfill_rate_limited",
                        symbol=cleaned_symbol,
                        timeframe=timeframe,
                        retry=retry_count,
                        max_retries=max_retries,
                        wait_seconds=wait_time,
                        status_code=e.status
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "backfill_rate_limit_exceeded",
                        symbol=cleaned_symbol,
                        timeframe=timeframe,
                        retries=retry_count,
                        status_code=e.status
                    )
                    return 0
            else:
                # Non-rate-limit error
                retry_count += 1
                if retry_count <= max_retries:
                    wait_time = retry_count * 2  # 2s, 4s, 6s
                    logger.warning(
                        "backfill_retry",
                        symbol=cleaned_symbol,
                        timeframe=timeframe,
                        retry=retry_count,
                        max_retries=max_retries,
                        wait_seconds=wait_time,
                        error=str(e),
                        status_code=e.status
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        "backfill_fetch_failed",
                        symbol=cleaned_symbol,
                        timeframe=timeframe,
                        retries=retry_count,
                        error=str(e),
                        status_code=e.status,
                        exc_info=True
                    )
                    return 0
                    
        except Exception as e:
            retry_count += 1
            if retry_count <= max_retries:
                wait_time = retry_count * 2  # 2s, 4s, 6s
                logger.warning(
                    "backfill_retry",
                    symbol=cleaned_symbol,
                    timeframe=timeframe,
                    retry=retry_count,
                    max_retries=max_retries,
                    wait_seconds=wait_time,
                    error=str(e)
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(
                    "backfill_fetch_failed",
                    symbol=cleaned_symbol,
                    timeframe=timeframe,
                    retries=retry_count,
                    error=str(e),
                    exc_info=True
                )
                return 0
    
    if not klines:
        logger.warning(
            "backfill_no_klines",
            symbol=cleaned_symbol,
            timeframe=timeframe
        )
        return 0
    
    # Parse klines into candle objects
    candles = binance_service.parse_klines(klines, cleaned_symbol, timeframe)
    
    if not candles:
        logger.warning(
            "backfill_no_candles_parsed",
            symbol=cleaned_symbol,
            timeframe=timeframe,
            klines_count=len(klines)
        )
        return 0
    
    logger.debug(
        "backfill_candles_parsed",
        symbol=cleaned_symbol,
        timeframe=timeframe,
        candles_count=len(candles),
        first_timestamp=candles[0].timestamp.isoformat() if candles else None,
        last_timestamp=candles[-1].timestamp.isoformat() if candles else None
    )
    
    # Batch check which candles already exist in database
    with DatabaseManager() as db:
        # Get symbol_id and timeframe_id (use cleaned symbol)
        symbol_id = get_or_create_symbol_record(db, cleaned_symbol)
        timeframe_id = get_timeframe_id(db, timeframe)
        
        if not symbol_id or not timeframe_id:
            logger.error(
                "backfill_id_resolution_failed",
                symbol=cleaned_symbol,
                timeframe=timeframe,
                symbol_id=symbol_id,
                timeframe_id=timeframe_id
            )
            return 0
        
        # Extract timestamps from candles and batch check which ones exist
        candle_timestamps = [c.timestamp for c in candles]
        
        if not candle_timestamps:
            existing_timestamps: Set[datetime] = set()
        else:
            # Use a single efficient query with IN clause and explicit placeholders
            # Optimized: use larger chunks to reduce query count (400 candles = 1 query)
            chunk_size = 400  # Process all candles in one query (faster)
            existing_timestamps: Set[datetime] = set()
            
            # Process in chunks if we have more than chunk_size timestamps
            for chunk_idx in range(0, len(candle_timestamps), chunk_size):
                chunk_timestamps = candle_timestamps[chunk_idx:chunk_idx + chunk_size]
                
                # Build query with explicit placeholders - most reliable with SQLAlchemy
                # Using bindparam approach for better performance
                placeholders = ", ".join([f":ts{i}" for i in range(len(chunk_timestamps))])
                query = text(f"""
                    SELECT timestamp
                    FROM ohlcv_candles
                    WHERE symbol_id = :symbol_id
                    AND timeframe_id = :timeframe_id
                    AND timestamp IN ({placeholders})
                """)
                
                # Build parameters dict efficiently
                params = {
                    "symbol_id": symbol_id,
                    "timeframe_id": timeframe_id,
                    **{f"ts{i}": ts for i, ts in enumerate(chunk_timestamps)}
                }
                
                try:
                    result = db.execute(query, params)
                    chunk_existing = {row[0] for row in result}
                    existing_timestamps.update(chunk_existing)
                    
                    logger.debug(
                        "backfill_chunk_checked",
                        symbol=cleaned_symbol,
                        timeframe=timeframe,
                        chunk=chunk_idx // chunk_size + 1,
                        chunk_size=len(chunk_timestamps),
                        found=len(chunk_existing)
                    )
                except Exception as e:
                    # Log error and continue with next chunk
                    logger.warning(
                        "backfill_chunk_query_error",
                        symbol=cleaned_symbol,
                        timeframe=timeframe,
                        chunk=chunk_idx // chunk_size + 1,
                        chunk_size=len(chunk_timestamps),
                        error=str(e)
                    )
                    # Rollback failed chunk and continue
                    try:
                        db.rollback()
                    except:
                        pass
                    continue
        
        # Filter candles to only include missing ones
        missing_candles = [
            c for c in candles
            if c.timestamp not in existing_timestamps
        ]
        
        logger.info(
            "backfill_candles_checked",
            symbol=cleaned_symbol,
            timeframe=timeframe,
            total_candles=len(candles),
            existing_candles=len(existing_timestamps),
            missing_candles=len(missing_candles)
        )
        
        # Insert missing candles
        if missing_candles:
            try:
                binance_service.save_candles(db, missing_candles)
                
                logger.info(
                    "backfill_candles_inserted",
                    symbol=cleaned_symbol,
                    timeframe=timeframe,
                    candles_inserted=len(missing_candles),
                    first_timestamp=missing_candles[0].timestamp.isoformat() if missing_candles else None,
                    last_timestamp=missing_candles[-1].timestamp.isoformat() if missing_candles else None
                )
                
                return len(missing_candles)
            except Exception as e:
                logger.error(
                    "backfill_insert_failed",
                    symbol=cleaned_symbol,
                    timeframe=timeframe,
                    candles_count=len(missing_candles),
                    error=str(e),
                    exc_info=True
                )
                return 0
        else:
            logger.debug(
                "backfill_no_missing_candles",
                symbol=cleaned_symbol,
                timeframe=timeframe
            )
            return 0


async def backfill_all_symbols_timeframes(
    binance_service,
    symbols: List[str],
    timeframes: List[str],
    limit: int = 400,
    max_retries: int = 3,
    max_concurrent: int = 5
) -> int:
    """Backfill recent candles for multiple symbols and timeframes with parallel processing
    
    Args:
        binance_service: BinanceIngestionService instance
        symbols: List of trading symbols
        timeframes: List of timeframe strings
        limit: Number of recent candles to fetch per symbol/timeframe
        max_retries: Maximum retry attempts per API call
        max_concurrent: Maximum concurrent requests (default: 5)
    
    Returns:
        Total number of candles inserted across all symbols/timeframes
    """
    total_inserted = 0
    
    logger.info(
        "backfill_all_starting",
        symbol_count=len(symbols),
        timeframe_count=len(timeframes),
        limit=limit,
        max_concurrent=max_concurrent
    )
    
    # Create semaphore to limit concurrent requests
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def backfill_with_semaphore(symbol: str, timeframe: str) -> int:
        """Wrapper to limit concurrent requests"""
        async with semaphore:
            try:
                return await backfill_recent_candles(
                    binance_service=binance_service,
                    symbol=symbol,
                    timeframe=timeframe,
                    limit=limit,
                    max_retries=max_retries
                )
            except Exception as e:
                logger.error(
                    "backfill_symbol_timeframe_error",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(e),
                    exc_info=True
                )
                return 0
    
    # Create all tasks
    tasks = [
        backfill_with_semaphore(symbol, timeframe)
        for symbol in symbols
        for timeframe in timeframes
    ]
    
    # Execute tasks in parallel (limited by semaphore)
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Sum results, handling exceptions
    for result in results:
        if isinstance(result, Exception):
            logger.error(
                "backfill_task_exception",
                error=str(result),
                exc_info=True
            )
        else:
            total_inserted += result
    
    logger.info(
        "backfill_all_completed",
        total_candles_inserted=total_inserted,
        symbol_count=len(symbols),
        timeframe_count=len(timeframes),
        total_tasks=len(tasks)
    )
    
    return total_inserted
