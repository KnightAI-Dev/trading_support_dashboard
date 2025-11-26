"""Simple gap detection and backfill utilities"""
import sys
import os
import asyncio
from datetime import datetime, timezone
from typing import List, Set, Optional, Dict, Tuple
from decimal import Decimal
from sqlalchemy import text
import structlog
import aiohttp

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from shared.database import DatabaseManager

# Import from local modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database.repository import get_timeframe_id, get_or_create_symbol_record, get_ingestion_config_value

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
    
    # Exclude the latest candle as it may still be in progress (not closed yet)
    # Only process completed candles
    if len(candles) > 1:
        latest_candle = candles[-1]
        candles = candles[:-1]  # Remove the last candle
        logger.debug(
            "backfill_latest_candle_excluded",
            symbol=cleaned_symbol,
            timeframe=timeframe,
            excluded_timestamp=latest_candle.timestamp.isoformat(),
            processed_count=len(candles)
        )
    elif len(candles) == 1:
        # Only one candle - exclude it as it's likely incomplete
        logger.debug(
            "backfill_single_candle_excluded",
            symbol=cleaned_symbol,
            timeframe=timeframe,
            excluded_timestamp=candles[0].timestamp.isoformat()
        )
        candles = []
    
    if not candles:
        logger.info(
            "backfill_no_completed_candles",
            symbol=cleaned_symbol,
            timeframe=timeframe,
            message="All candles excluded (latest candle may be incomplete)"
        )
        return 0
    
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
        # Also fetch existing OHLCV data for validation
        candle_timestamps = [c.timestamp for c in candles]
        
        # Dictionary to store existing candle data: timestamp -> (open, high, low, close, volume)
        existing_candles_data: Dict[datetime, Tuple[float, float, float, float, float]] = {}
        existing_timestamps: Set[datetime] = set()
        
        if candle_timestamps:
            # Use a single efficient query with IN clause and explicit placeholders
            # Optimized: use larger chunks to reduce query count (400 candles = 1 query)
            chunk_size = 400  # Process all candles in one query (faster)
            
            # Process in chunks if we have more than chunk_size timestamps
            for chunk_idx in range(0, len(candle_timestamps), chunk_size):
                chunk_timestamps = candle_timestamps[chunk_idx:chunk_idx + chunk_size]
                
                # Build query to fetch both timestamp and OHLCV data for validation
                placeholders = ", ".join([f":ts{i}" for i in range(len(chunk_timestamps))])
                query = text(f"""
                    SELECT timestamp, open, high, low, close, volume
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
                    for row in result:
                        ts = row[0]
                        existing_timestamps.add(ts)
                        # Store OHLCV data for comparison
                        existing_candles_data[ts] = (
                            float(row[1]),  # open
                            float(row[2]),  # high
                            float(row[3]),  # low
                            float(row[4]),  # close
                            float(row[5])   # volume
                        )
                    
                    logger.debug(
                        "backfill_chunk_checked",
                        symbol=cleaned_symbol,
                        timeframe=timeframe,
                        chunk=chunk_idx // chunk_size + 1,
                        chunk_size=len(chunk_timestamps),
                        found=len(existing_timestamps)
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
        
        # Separate candles into missing and existing for validation
        missing_candles = []
        candles_to_validate = []
        
        for candle in candles:
            if candle.timestamp not in existing_timestamps:
                missing_candles.append(candle)
            else:
                candles_to_validate.append(candle)
        
        # Validate and update existing candles if OHLCV data differs
        # Use a small tolerance for floating point comparison (0.0001%)
        tolerance = 0.000001  # Very small tolerance for floating point comparison
        candles_to_update = []
        
        for candle in candles_to_validate:
            if candle.timestamp in existing_candles_data:
                existing_ohlcv = existing_candles_data[candle.timestamp]
                new_open = float(candle.open)
                new_high = float(candle.high)
                new_low = float(candle.low)
                new_close = float(candle.close)
                new_volume = float(candle.volume)
                
                # Compare each OHLCV value with tolerance
                open_diff = abs(new_open - existing_ohlcv[0])
                high_diff = abs(new_high - existing_ohlcv[1])
                low_diff = abs(new_low - existing_ohlcv[2])
                close_diff = abs(new_close - existing_ohlcv[3])
                volume_diff = abs(new_volume - existing_ohlcv[4])
                
                # Check if any value differs significantly (relative to the value)
                # Use relative comparison for better accuracy
                open_mismatch = new_open > 0 and (open_diff / new_open) > tolerance
                high_mismatch = new_high > 0 and (high_diff / new_high) > tolerance
                low_mismatch = new_low > 0 and (low_diff / new_low) > tolerance
                close_mismatch = new_close > 0 and (close_diff / new_close) > tolerance
                volume_mismatch = new_volume > 0 and (volume_diff / new_volume) > tolerance
                
                if open_mismatch or high_mismatch or low_mismatch or close_mismatch or volume_mismatch:
                    candles_to_update.append(candle)
                    logger.debug(
                        "backfill_candle_mismatch_detected",
                        symbol=cleaned_symbol,
                        timeframe=timeframe,
                        timestamp=candle.timestamp.isoformat(),
                        existing_ohlcv=existing_ohlcv,
                        new_ohlcv=(new_open, new_high, new_low, new_close, new_volume),
                        differences={
                            "open": open_diff,
                            "high": high_diff,
                            "low": low_diff,
                            "close": close_diff,
                            "volume": volume_diff
                        }
                    )
        
        # Update mismatched candles and insert missing candles in a single transaction
        # Both operations must succeed or both must fail to maintain data consistency
        # Track what was actually committed (not just attempted)
        committed_inserts = 0
        committed_updates = 0
        
        try:
            # Update mismatched candles
            if candles_to_update:
                update_stmt = text("""
                    UPDATE ohlcv_candles
                    SET open = :open,
                        high = :high,
                        low = :low,
                        close = :close,
                        volume = :volume
                    WHERE symbol_id = :symbol_id
                    AND timeframe_id = :timeframe_id
                    AND timestamp = :timestamp
                """)
                
                for candle in candles_to_update:
                    db.execute(update_stmt, {
                        "symbol_id": symbol_id,
                        "timeframe_id": timeframe_id,
                        "timestamp": candle.timestamp,
                        "open": Decimal(str(candle.open)),
                        "high": Decimal(str(candle.high)),
                        "low": Decimal(str(candle.low)),
                        "close": Decimal(str(candle.close)),
                        "volume": Decimal(str(candle.volume))
                    })
                
                logger.info(
                    "backfill_candles_updated",
                    symbol=cleaned_symbol,
                    timeframe=timeframe,
                    candles_updated=len(candles_to_update),
                    first_timestamp=candles_to_update[0].timestamp.isoformat() if candles_to_update else None,
                    last_timestamp=candles_to_update[-1].timestamp.isoformat() if candles_to_update else None
                )
            
            logger.info(
                "backfill_candles_checked",
                symbol=cleaned_symbol,
                timeframe=timeframe,
                total_candles=len(candles),
                existing_candles=len(existing_timestamps),
                missing_candles=len(missing_candles),
                candles_to_update=len(candles_to_update)
            )
            
            # Insert missing candles
            if missing_candles:
                binance_service.save_candles(db, missing_candles)
                
                logger.info(
                    "backfill_candles_inserted",
                    symbol=cleaned_symbol,
                    timeframe=timeframe,
                    candles_inserted=len(missing_candles),
                    first_timestamp=missing_candles[0].timestamp.isoformat() if missing_candles else None,
                    last_timestamp=missing_candles[-1].timestamp.isoformat() if missing_candles else None
                )
            
            # Commit all changes atomically (both UPDATE and INSERT)
            # Only set committed counts after successful commit
            if candles_to_update or missing_candles:
                db.commit()
                # Track what was actually committed
                committed_updates = len(candles_to_update) if candles_to_update else 0
                committed_inserts = len(missing_candles) if missing_candles else 0
                
                logger.debug(
                    "backfill_transaction_committed",
                    symbol=cleaned_symbol,
                    timeframe=timeframe,
                    updates=committed_updates,
                    inserts=committed_inserts
                )
                
        except Exception as e:
            # Rollback all changes if any operation fails
            logger.error(
                "backfill_transaction_failed",
                symbol=cleaned_symbol,
                timeframe=timeframe,
                candles_to_update=len(candles_to_update) if candles_to_update else 0,
                missing_candles=len(missing_candles) if missing_candles else 0,
                error=str(e),
                exc_info=True
            )
            db.rollback()
            # Ensure counts remain 0 - nothing was committed
            committed_inserts = 0
            committed_updates = 0
        
        # Return total count of candles processed (inserted + updated)
        # Only count operations that were successfully committed
        total_processed = committed_inserts + committed_updates
        
        if total_processed == 0:
            logger.debug(
                "backfill_no_changes",
                symbol=cleaned_symbol,
                timeframe=timeframe
            )
        
        return total_processed


async def backfill_all_symbols_timeframes(
    binance_service,
    symbols: List[str],
    timeframes: List[str],
    limit: Optional[int] = None,
    max_retries: int = 3,
    max_concurrent: int = 5
) -> int:
    """Backfill recent candles for multiple symbols and timeframes with parallel processing
    
    Args:
        binance_service: BinanceIngestionService instance
        symbols: List of trading symbols
        timeframes: List of timeframe strings
        limit: Number of recent candles to fetch per symbol/timeframe. If None, will be fetched from ingestion_config table.
        max_retries: Maximum retry attempts per API call
        max_concurrent: Maximum concurrent requests (default: 5)
    
    Returns:
        Total number of candles inserted across all symbols/timeframes
    """
    # Get limit from database if not provided
    if limit is None:
        with DatabaseManager() as db:
            limit_value = get_ingestion_config_value(db, "backfill_limit", default_value=400.0)
            limit = int(limit_value) if limit_value is not None else 400
            logger.info(
                "backfill_limit_from_config",
                limit=limit,
                config_key="backfill_limit"
            )
    
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
