"""
Binance WebSocket service for real-time OHLCV data
"""
import sys
import os
import asyncio
import json
import time
from datetime import datetime, timezone
from typing import List, Dict, Optional, Tuple
import websockets
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, WebSocketException
from sqlalchemy.orm import Session
from sqlalchemy import text
from decimal import Decimal
import structlog

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from shared.database import DatabaseManager
from shared.redis_client import publish_event, get_redis

# Import from local modules (relative to ingestion-service root)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.types import KlineData
from utils.circuit_breaker import AsyncCircuitBreaker
from config.settings import WS_BATCH_SIZE, WS_BATCH_TIMEOUT, WS_MAX_RECONNECT_DELAY, WS_PING_INTERVAL, WS_PING_TIMEOUT
from database.repository import get_or_create_symbol_record, get_timeframe_id

logger = structlog.get_logger(__name__)

class BinanceWebSocketService:
    """WebSocket service for real-time OHLCV data from Binance Futures"""
    
    def __init__(self):
        self.ws_url = "wss://fstream.binance.com/ws"
        self.ws_stream_url = "wss://fstream.binance.com/stream"  # For multi-stream
        self.websocket = None
        self.websockets = []  # List of WebSocket connections for multiple batches
        self.reconnect_delay = 1  # Start with 1 second
        self.max_reconnect_delay = WS_MAX_RECONNECT_DELAY
        self.is_connected = False
        self.messages_received = 0
        self.parse_errors = 0
        self.reconnect_count = 0
        self.last_message_time = None
        self.batch_buffer = []  # Buffer for batch inserts
        self._batch_lock = asyncio.Lock()  # Lock for thread-safe batch buffer access
        self.last_batch_flush = time.time()  # Initialize to current time
        self.batch_size = WS_BATCH_SIZE
        self.batch_timeout = WS_BATCH_TIMEOUT
        self.total_batches_flushed = 0
        self.total_candles_batched = 0
        self.max_url_length = 2000  # Maximum URL length (leaving room for base URL)
        self.current_symbols = []  # Store current symbols for dynamic updates
        self.current_timeframes = []  # Store current timeframes for dynamic updates
        self._symbols_lock = asyncio.Lock()  # Lock for thread-safe symbol updates
        self._redis_client = get_redis()  # Redis client for batch persistence
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def update_symbols(self, new_symbols: List[str], new_timeframes: List[str]):
        """Update symbols and timeframes, triggering immediate reconnection with new subscriptions
        
        Args:
            new_symbols: New list of symbols to subscribe to
            new_timeframes: New list of timeframes to subscribe to
        """
        async with self._symbols_lock:
            old_symbols = set(self.current_symbols)
            new_symbols_set = set(new_symbols)
            
            self.current_symbols = new_symbols
            self.current_timeframes = new_timeframes
            
            added = new_symbols_set - old_symbols
            removed = old_symbols - new_symbols_set
            
            if added or removed:
                logger.info(
                    "websocket_symbols_updating",
                    old_count=len(old_symbols),
                    new_count=len(new_symbols),
                    added_count=len(added),
                    removed_count=len(removed),
                    added_symbols=list(added) if len(added) <= 10 else list(added)[:10],
                    removed_symbols=list(removed) if len(removed) <= 10 else list(removed)[:10]
                )
                
                # Close current connections to trigger reconnection with new symbols
                await self.close()
                logger.info("websocket_connections_closed_for_symbol_update")
    
    async def _persist_batch_buffer(self):
        """Persist batch buffer to Redis before clearing to prevent data loss"""
        if not self.batch_buffer or not self._redis_client:
            return
        
        async with self._batch_lock:
            try:
                key = f"websocket:batch_buffer:{id(self)}"
                # Serialize batch buffer
                data = json.dumps([
                    {
                        "symbol": c.get("symbol"),
                        "timeframe": c.get("timeframe"),
                        "timestamp": c.get("timestamp").isoformat() if hasattr(c.get("timestamp"), 'isoformat') else str(c.get("timestamp")),
                        "open": float(c.get("open", 0)),
                        "high": float(c.get("high", 0)),
                        "low": float(c.get("low", 0)),
                        "close": float(c.get("close", 0)),
                        "volume": float(c.get("volume", 0)),
                        "is_closed": c.get("is_closed", False),
                        "open_ts": c.get("open_ts"),
                        "close_ts": c.get("close_ts")
                    }
                    for c in self.batch_buffer
                ])
                await asyncio.to_thread(
                    self._redis_client.setex,
                    key,
                    3600,  # 1 hour TTL
                    data
                )
                logger.info("batch_buffer_persisted", count=len(self.batch_buffer))
            except Exception as e:
                logger.error("batch_persistence_error", error=str(e), exc_info=True)
    
    async def _restore_batch_buffer(self):
        """Restore batch buffer from Redis after reconnection"""
        if not self._redis_client:
            return
        
        async with self._batch_lock:
            try:
                key = f"websocket:batch_buffer:{id(self)}"
                data = await asyncio.to_thread(self._redis_client.get, key)
                if data:
                    batch_data = json.loads(data)
                    # Convert back to candle format
                    restored = []
                    for c in batch_data:
                        restored.append({
                            "symbol": c["symbol"],
                            "timeframe": c["timeframe"],
                            "timestamp": datetime.fromisoformat(c["timestamp"]),
                            "open": c["open"],
                            "high": c["high"],
                            "low": c["low"],
                            "close": c["close"],
                            "volume": c["volume"],
                            "is_closed": c["is_closed"],
                            "open_ts": c.get("open_ts"),
                            "close_ts": c.get("close_ts")
                        })
                    self.batch_buffer.extend(restored)
                    # Delete after restore
                    await asyncio.to_thread(self._redis_client.delete, key)
                    logger.info("batch_buffer_restored", count=len(restored))
            except Exception as e:
                logger.error("batch_restore_error", error=str(e), exc_info=True)
    
    async def close(self):
        """Close all WebSocket connections and persist batch buffer"""
        # Persist batch buffer before closing to prevent data loss
        await self._persist_batch_buffer()
        
        # Close single connection if it exists
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket: {e}")
            self.websocket = None
        
        # Close all batch connections
        for ws in self.websockets:
            try:
                await ws.close()
            except Exception as e:
                logger.debug(f"Error closing WebSocket batch connection: {e}")
        
        self.websockets = []
        self.is_connected = False
        logger.info("All WebSocket connections closed")
    
    def map_timeframe_to_binance_interval(self, timeframe: str) -> str:
        """Map our timeframe format to Binance interval format
        
        Binance supports: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
        Returns the mapped interval or the original if not found (will fail at connection time)
        """
        # Normalize input (lowercase except for month)
        normalized = timeframe.lower() if timeframe != "1M" else "1M"
        
        timeframe_map = {
            "1m": "1m",
            "3m": "3m",
            "5m": "5m",
            "15m": "15m",
            "30m": "30m",
            "1h": "1h",
            "2h": "2h",
            "4h": "4h",
            "6h": "6h",
            "8h": "8h",
            "12h": "12h",
            "1d": "1d",
            "3d": "3d",
            "1w": "1w",
            "1M": "1M"  # Month (uppercase)
        }
        
        mapped = timeframe_map.get(normalized, timeframe)
        if mapped != timeframe:
            logger.debug(f"Mapped timeframe {timeframe} -> {mapped}")
        return mapped
    
    def build_stream_name(self, symbol: str, interval: str) -> str:
        """Build stream name for kline: symbol@kline_interval"""
        # Map timeframe to Binance interval format
        binance_interval = self.map_timeframe_to_binance_interval(interval)
        return f"{symbol.lower()}@kline_{binance_interval}"
    
    def build_ticker_stream_name(self, symbol: str) -> str:
        """Build stream name for ticker: symbol@ticker"""
        return f"{symbol.lower()}@ticker"
    
    def build_multi_stream_url(self, symbols: List[str], timeframes: List[str]) -> str:
        """Build multi-stream URL for multiple symbols and timeframes, including ticker streams"""
        streams = []
        # Add kline streams
        for symbol in symbols:
            for timeframe in timeframes:
                stream_name = self.build_stream_name(symbol, timeframe)
                streams.append(stream_name)
        # Add ticker streams (one per symbol for real-time price/volume updates)
        for symbol in symbols:
            ticker_stream = self.build_ticker_stream_name(symbol)
            streams.append(ticker_stream)
        
        # Multi-stream format: ?streams=stream1/stream2/stream3
        streams_str = "/".join(streams)
        return f"{self.ws_stream_url}?streams={streams_str}"
    
    def build_stream_batches(self, symbols: List[str], timeframes: List[str]) -> List[Tuple[List[str], List[str]]]:
        """
        Split symbols into batches that fit within URL length limit.
        
        Calculates actual URL length for each batch to ensure it stays within limits.
        
        Args:
            symbols: List of symbols to subscribe to
            timeframes: List of timeframes to subscribe to
            
        Returns:
            List of tuples (symbol_batch, timeframe_list) where each batch fits in URL length limit
        """
        batches = []
        base_url_length = len(self.ws_stream_url) + len("?streams=")
        
        current_batch_symbols = []
        
        for symbol in symbols:
            # Try adding this symbol to current batch
            test_symbols = current_batch_symbols + [symbol]
            
            # Build streams for test batch
            test_streams = []
            for s in test_symbols:
                # Add kline streams for this symbol
                for timeframe in timeframes:
                    test_streams.append(self.build_stream_name(s, timeframe))
                # Add ticker stream for this symbol
                test_streams.append(self.build_ticker_stream_name(s))
            
            # Build test URL
            streams_str = "/".join(test_streams)
            test_url = f"{self.ws_stream_url}?streams={streams_str}"
            test_url_length = len(test_url)
            
            # Check if test URL exceeds limit
            if test_url_length > self.max_url_length and current_batch_symbols:
                # Current batch is full, save it and start new one
                batches.append((current_batch_symbols.copy(), timeframes))
                current_batch_symbols = [symbol]
            else:
                # Add symbol to current batch
                current_batch_symbols.append(symbol)
        
        # Add the last batch if it has symbols
        if current_batch_symbols:
            batches.append((current_batch_symbols, timeframes))
        
        return batches if batches else [([], timeframes)]
    
    def parse_kline_message(self, message: Dict) -> Optional[KlineData]:
        """Parse kline WebSocket message into canonical OHLCV format
        
        Handles both single-stream and multi-stream formats:
        - Single: {"e":"kline","E":...,"s":"BTCUSDT","k":{...}}
        - Multi: {"stream":"btcusdt@kline_1m","data":{"e":"kline",...}}
        """
        try:
            # Handle multi-stream format
            if "stream" in message and "data" in message:
                data = message["data"]
            # Handle single-stream format
            elif "e" in message and message.get("e") == "kline":
                data = message
            else:
                return None
            
            if data.get("e") != "kline":
                return None
            
            k = data.get("k", {})
            if not k:
                return None
            
            # Extract OHLCV data
            symbol = k.get("s")  # Symbol
            interval = k.get("i")  # Interval
            is_closed = k.get("x", False)  # True if candle is closed
            
            # Timestamps (ms since epoch)
            open_ts = k.get("t")  # Open time
            close_ts = k.get("T")  # Close time
            
            # Validate timestamps
            if not open_ts:
                logger.warning("Missing open timestamp in kline data")
                return None
            
            # Create timezone-aware timestamp (UTC)
            timestamp = datetime.fromtimestamp(open_ts / 1000, tz=timezone.utc)
            
            # OHLCV values - validate and convert
            open_price = float(k.get("o", 0))
            high_price = float(k.get("h", 0))
            low_price = float(k.get("l", 0))
            close_price = float(k.get("c", 0))
            volume = float(k.get("v", 0))
            
            # Validate OHLCV data
            if not all([open_price > 0, high_price > 0, low_price > 0, close_price > 0]):
                logger.warning(
                    "kline_invalid_prices",
                    symbol=symbol,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price
                )
                return None
            
            if high_price < low_price:
                logger.warning(
                    "kline_invalid_high_low",
                    symbol=symbol,
                    high=high_price,
                    low=low_price
                )
                return None
            
            return {
                "symbol": symbol,
                "timeframe": interval,
                "open_ts": open_ts,
                "close_ts": close_ts,
                "open": open_price,
                "high": high_price,
                "low": low_price,
                "close": close_price,
                "volume": volume,
                "is_closed": is_closed,
                "timestamp": timestamp
            }
        except Exception as e:
            self.parse_errors += 1
            logger.error(
                "kline_parse_error",
                error=str(e),
                exc_info=True
            )
            return None
    
    def parse_ticker_message(self, message: Dict) -> Optional[Dict]:
        """Parse ticker WebSocket message for real-time price and volume updates
        
        Handles both single-stream and multi-stream formats:
        - Single: {"e":"24hrTicker","E":...,"s":"BTCUSDT","c":"50000.00","q":"1000000.00",...}
        - Multi: {"stream":"btcusdt@ticker","data":{"e":"24hrTicker",...}}
        
        Returns:
            Dict with symbol, price, volume_24h, and change24h, or None if invalid
        """
        try:
            # Handle multi-stream format
            if "stream" in message and "data" in message:
                data = message["data"]
            # Handle single-stream format
            elif "e" in message and message.get("e") == "24hrTicker":
                data = message
            else:
                return None
            
            if data.get("e") != "24hrTicker":
                return None
            
            symbol = data.get("s")  # Symbol
            if not symbol:
                return None
            
            # Extract price and volume data
            last_price = data.get("c")  # Last price (string)
            quote_volume = data.get("q")  # Quote volume (24h volume in quote currency, string)
            price_change_percent = data.get("P")  # Price change percent (24h, string)
            
            # Convert to float, handling None/empty strings
            try:
                price = float(last_price) if last_price else None
                volume_24h = float(quote_volume) if quote_volume else None
                change24h = float(price_change_percent) if price_change_percent else None
            except (ValueError, TypeError):
                logger.debug(f"Failed to convert ticker values for {symbol}: price={last_price}, volume={quote_volume}, change={price_change_percent}")
                return None
            
            if price is None or price <= 0:
                return None
            
            return {
                "symbol": symbol,
                "price": price,
                "volume_24h": volume_24h,
                "change24h": change24h
            }
        except Exception as e:
            logger.debug(f"Error parsing ticker message: {e}")
            return None
    
    async def flush_batch(self) -> Tuple[int, int]:
        """Flush batched candles to database using DatabaseManager
        
        Only saves closed candles to database. In-progress candles are published
        via WebSocket for real-time display but not persisted.
        
        Returns:
            Tuple[int, int]: (saved_count, failed_count)
        """
        async with self._batch_lock:
            if not self.batch_buffer:
                return 0, 0
            
            batch = self.batch_buffer.copy()
            self.batch_buffer.clear()
        
        saved_count = 0
        failed_count = 0
        
        try:
            # Separate closed and in-progress candles
            closed_candles = [c for c in batch if c.get("is_closed", False)]
            in_progress_candles = [c for c in batch if not c.get("is_closed", False)]
            
            # Only save closed candles to database using DatabaseManager
            if closed_candles:
                try:
                    with DatabaseManager() as db:
                        saved, failed = await self._batch_insert_candles(db, closed_candles, is_closed=True)
                        saved_count += saved
                        failed_count += failed
                        db.commit()
                except Exception as e:
                    logger.error("batch_flush_db_error", error=str(e), exc_info=True)
                    # Restore batch on error for retry
                    async with self._batch_lock:
                        self.batch_buffer.extend(batch)
                    return 0, len(batch)
            
            # Publish WebSocket events for ALL candles (closed and in-progress) for real-time display
            # Closed candles are published in _batch_insert_candles, so publish in-progress here
            for kline_data in in_progress_candles:
                try:
                    timestamp = kline_data.get("timestamp")
                    publish_event("candle_update", {
                        "symbol": kline_data.get("symbol"),
                        "timeframe": kline_data.get("timeframe"),
                        "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                        "open": float(kline_data.get("open", 0)),
                        "high": float(kline_data.get("high", 0)),
                        "low": float(kline_data.get("low", 0)),
                        "close": float(kline_data.get("close", 0)),
                        "volume": float(kline_data.get("volume", 0)),
                        "closed": False  # Indicates this is an in-progress candle
                    })
                except Exception as e:
                    logger.debug(f"Failed to publish in-progress candle event: {e}")
            
            if saved_count > 0:
                self.total_batches_flushed += 1
                self.total_candles_batched += saved_count
                logger.debug(
                    f"Flushed batch: {saved_count} closed candles saved to DB, "
                    f"{len(in_progress_candles)} in-progress candles published via WebSocket only "
                    f"(total batches: {self.total_batches_flushed})"
                )
            
            return saved_count, failed_count
        except Exception as e:
            logger.error(f"Error flushing batch: {e}", exc_info=True)
            # Restore batch on error for retry
            async with self._batch_lock:
                self.batch_buffer.extend(batch)
            return 0, len(batch)
    
    async def _batch_insert_candles(self, db: Session, candles: List[Dict], is_closed: bool) -> Tuple[int, int]:
        """Insert a batch of closed candles to database
        
        Note: This method should only be called with closed candles (is_closed=True).
        In-progress candles are handled separately and only published via WebSocket.
        """
        if not candles:
            return 0, 0
        
        saved_count = 0
        failed_count = 0
        
        # Build parameter lists for bulk insert
        params_list = []
        symbol_timeframe_map = {}  # Cache symbol_id and timeframe_id lookups
        
        for kline_data in candles:
            try:
                symbol = kline_data.get("symbol")
                timeframe = kline_data.get("timeframe")
                timestamp = kline_data.get("timestamp")
                
                if not all([symbol, timeframe, timestamp]):
                    failed_count += 1
                    continue
                
                # Get or cache symbol_id and timeframe_id
                cache_key = (symbol, timeframe)
                if cache_key not in symbol_timeframe_map:
                    symbol_id = get_or_create_symbol_record(db, symbol)
                    timeframe_id = get_timeframe_id(db, timeframe)
                    if not symbol_id or not timeframe_id:
                        failed_count += 1
                        continue
                    symbol_timeframe_map[cache_key] = (symbol_id, timeframe_id)
                else:
                    symbol_id, timeframe_id = symbol_timeframe_map[cache_key]
                
                params_list.append({
                    "symbol_id": symbol_id,
                    "timeframe_id": timeframe_id,
                    "timestamp": timestamp,
                    "open": Decimal(str(kline_data["open"])),
                    "high": Decimal(str(kline_data["high"])),
                    "low": Decimal(str(kline_data["low"])),
                    "close": Decimal(str(kline_data["close"])),
                    "volume": Decimal(str(kline_data["volume"]))
                })
            except Exception as e:
                logger.error(f"Error preparing batch insert for candle: {e}")
                failed_count += 1
        
        if not params_list:
            return 0, failed_count
        
        # Only build SQL statement for closed candles
        # In-progress candles should not reach this method (filtered in flush_batch)
        if not is_closed:
            # This should never happen, but log a warning if it does
            logger.warning("Attempted to insert in-progress candles to database - this should not happen")
            return 0, len(candles)
        
        # SQL statement for closed candles only - full upsert
        stmt = text("""
            INSERT INTO ohlcv_candles 
            (symbol_id, timeframe_id, timestamp, open, high, low, close, volume)
            VALUES (:symbol_id, :timeframe_id, :timestamp, :open, :high, :low, :close, :volume)
            ON CONFLICT (symbol_id, timeframe_id, timestamp) 
            DO UPDATE SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume
        """)
        
        try:
            # Execute batch insert
            db.execute(stmt, params_list)
            db.flush()
            saved_count = len(params_list)
            
            # Publish events for closed candles with full OHLCV data
            # All candles in this method are closed (in-progress are filtered out earlier)
            for kline_data in candles:
                try:
                    timestamp = kline_data.get("timestamp")
                    publish_event("candle_update", {
                        "symbol": kline_data.get("symbol"),
                        "timeframe": kline_data.get("timeframe"),
                        "timestamp": timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp),
                        "open": float(kline_data.get("open", 0)),
                        "high": float(kline_data.get("high", 0)),
                        "low": float(kline_data.get("low", 0)),
                        "close": float(kline_data.get("close", 0)),
                        "volume": float(kline_data.get("volume", 0)),
                        "closed": True
                    })
                except Exception as e:
                    logger.debug(f"Failed to publish closed candle event: {e}")
        except Exception as e:
            logger.error(f"Error in batch insert: {e}", exc_info=True)
            failed_count += len(params_list)
            saved_count = 0
        
        return saved_count, failed_count
    
    async def save_candle_from_websocket(self, kline_data: Dict) -> bool:
        """Add candle to batch buffer for later batch insert (thread-safe)
        
        Returns:
            bool: True if added to batch, False if validation failed
        """
        symbol = kline_data.get("symbol")
        timeframe = kline_data.get("timeframe")
        timestamp = kline_data.get("timestamp")
        
        # Validate required fields
        if not all([symbol, timeframe, timestamp]):
            logger.error(f"Missing required fields in kline_data: symbol={symbol}, timeframe={timeframe}, timestamp={timestamp}")
            return False
        
        # Validate timestamp is timezone-aware
        if timestamp.tzinfo is None:
            logger.error(f"Timestamp is not timezone-aware for {symbol} {timeframe}")
            return False
        
        # Add to batch buffer with lock
        async with self._batch_lock:
            self.batch_buffer.append(kline_data)
        return True
    
    async def connect_and_subscribe(self, symbols: List[str], timeframes: List[str]):
        """Connect to WebSocket(s) and subscribe to kline streams, splitting into batches if needed"""
        # Restore batch buffer from Redis after reconnection
        await self._restore_batch_buffer()
        
        if not symbols or not timeframes:
            logger.error("Cannot connect: empty symbols or timeframes list")
            return False
        
        # Validate timeframes are supported by Binance
        for tf in timeframes:
            mapped = self.map_timeframe_to_binance_interval(tf)
            valid_intervals = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]
            if mapped not in valid_intervals:
                logger.warning(f"Timeframe {tf} (mapped to {mapped}) may not be supported by Binance")
        
        # Close existing connections
        await self.close()
        self.websockets = []
        
        # Split symbols into batches that fit within URL length limit
        batches = self.build_stream_batches(symbols, timeframes)
        
        if len(batches) > 1:
            logger.info(
                f"Splitting {len(symbols)} symbols into {len(batches)} WebSocket connections "
                f"to avoid URL length limit"
            )
        
        # Connect to each batch
        connected_count = 0
        for batch_idx, (batch_symbols, batch_timeframes) in enumerate(batches):
            if not batch_symbols:
                continue
            
            # Build URL for this batch
            url = self.build_multi_stream_url(batch_symbols, batch_timeframes)
            url_length = len(url)
            total_kline_streams = len(batch_symbols) * len(batch_timeframes)
            total_ticker_streams = len(batch_symbols)
            total_streams = total_kline_streams + total_ticker_streams
            
            logger.info(
                f"Connecting to WebSocket batch {batch_idx + 1}/{len(batches)}: "
                f"{len(batch_symbols)} symbols x {len(batch_timeframes)} timeframes = "
                f"{total_kline_streams} kline streams + {total_ticker_streams} ticker streams = "
                f"{total_streams} total streams (URL length: {url_length})"
            )
            
            try:
                # Connect with timeout
                ws = await asyncio.wait_for(
                    websockets.connect(
                        url, 
                        ping_interval=WS_PING_INTERVAL, 
                        ping_timeout=WS_PING_TIMEOUT
                    ),
                    timeout=10.0
                )
                self.websockets.append(ws)
                connected_count += 1
                logger.info(f"WebSocket batch {batch_idx + 1} connected successfully (URL length: {url_length})")
            except asyncio.TimeoutError:
                logger.error(f"WebSocket batch {batch_idx + 1} connection timeout after 10s")
            except Exception as e:
                error_msg = str(e)
                if "414" in error_msg or "URI Too Long" in error_msg:
                    logger.error(
                        f"WebSocket batch {batch_idx + 1} rejected: URL too long ({url_length} chars). "
                        f"This batch still exceeds limit - need smaller batches."
                    )
                else:
                    logger.error(f"Failed to connect WebSocket batch {batch_idx + 1}: {e}")
        
        # Update connection status
        if connected_count > 0:
            self.is_connected = True
            self.reconnect_delay = 1  # Reset delay on successful connection
            # For backward compatibility, set self.websocket to first connection
            if self.websockets:
                self.websocket = self.websockets[0]
            logger.info(f"Connected {connected_count}/{len(batches)} WebSocket batches successfully")
            return True
        else:
            self.is_connected = False
            logger.error(f"Failed to connect any WebSocket batches ({len(batches)} attempted)")
            return False
    
    async def listen_and_process(self, symbols: List[str], timeframes: List[str], shutdown_event=None):
        """Listen to WebSocket messages and process kline data with improved error handling"""
        candles_saved = 0
        candles_failed = 0
        
        # Test database connection on startup
        try:
            with DatabaseManager() as test_db:
                test_db.execute(text("SELECT 1"))
            logger.info("Database connection test successful")
        except Exception as e:
            logger.error(f"Database connection test failed: {e}", exc_info=True)
        
        try:
            while shutdown_event is None or not shutdown_event.is_set():
                try:
                    if not self.is_connected or not self.websockets:
                        # Reconnect with exponential backoff
                        await asyncio.sleep(self.reconnect_delay)
                        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                        
                        # Get current symbols/timeframes (may have been updated)
                        async with self._symbols_lock:
                            current_symbols = self.current_symbols
                            current_timeframes = self.current_timeframes
                        
                        success = await self.connect_and_subscribe(current_symbols, current_timeframes)
                        if not success:
                            continue
                    
                    # Receive message from any connected WebSocket (with shutdown check)
                    if not self.websockets:
                        # No active connections, try to reconnect
                        await asyncio.sleep(self.reconnect_delay)
                        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
                        success = await self.connect_and_subscribe(symbols, timeframes)
                        if not success:
                            continue
                        continue
                    
                    # Use asyncio.wait to receive from any of the WebSocket connections
                    try:
                        # Create tasks from coroutines (required by asyncio.wait)
                        recv_tasks = [asyncio.create_task(ws.recv()) for ws in self.websockets]
                        
                        done, pending = await asyncio.wait(
                            recv_tasks,
                            timeout=30.0,
                            return_when=asyncio.FIRST_COMPLETED
                        )
                        
                        if shutdown_event and shutdown_event.is_set():
                            # Cancel all tasks if shutting down
                            for task in pending:
                                task.cancel()
                            break
                        
                        if not done:
                            # Timeout - cancel all tasks and check shutdown
                            for task in recv_tasks:
                                task.cancel()
                                try:
                                    await task
                                except (asyncio.CancelledError, Exception):
                                    pass
                            if shutdown_event and shutdown_event.is_set():
                                break
                            continue
                        
                        # Get message from the first completed connection
                        message_task = done.pop()
                        try:
                            message_str = await message_task
                        except ConnectionClosedOK:
                            # Normal closure - connection was closed intentionally
                            logger.debug("WebSocket connection closed normally during message receive")
                            # Cancel pending tasks
                            for task in pending:
                                task.cancel()
                                try:
                                    await task
                                except (asyncio.CancelledError, ConnectionClosedOK):
                                    pass
                            # Close and reconnect
                            await self.close()
                            await asyncio.sleep(self.reconnect_delay)
                            continue
                        
                        # Cancel pending tasks (we only process one message at a time)
                        for task in pending:
                            task.cancel()
                            try:
                                await task
                            except (asyncio.CancelledError, ConnectionClosedOK):
                                pass
                    except asyncio.TimeoutError:
                        # Check shutdown on timeout
                        if shutdown_event and shutdown_event.is_set():
                            break
                        continue
                    except ConnectionClosedOK:
                        # Normal WebSocket closure (status 1000) - not an error
                        # This happens when connections are closed intentionally (e.g., during symbol updates)
                        logger.debug("WebSocket connection closed normally, will reconnect")
                        await self.close()
                        await asyncio.sleep(self.reconnect_delay)
                        continue
                    except (ConnectionClosed, WebSocketException) as e:
                        # Abnormal WebSocket closure or error
                        logger.warning(f"WebSocket connection closed abnormally: {e}")
                        await self.close()
                        await asyncio.sleep(self.reconnect_delay)
                        continue
                    except Exception as e:
                        logger.error(f"Error receiving WebSocket message: {e}", exc_info=True)
                        # Reconnect on error
                        await self.close()
                        await asyncio.sleep(self.reconnect_delay)
                        continue
                    
                    if shutdown_event and shutdown_event.is_set():
                        break
                    
                    self.messages_received += 1
                    self.last_message_time = time.time()
                    
                    # Log metrics periodically (every 1000 messages)
                    if self.messages_received % 1000 == 0:
                        metrics = self.get_metrics()
                        logger.info(
                            f"WebSocket metrics: {metrics['messages_received']} messages received, "
                            f"{metrics['parse_errors']} parse errors, "
                            f"{metrics['reconnect_count']} reconnects, "
                            f"{candles_saved} candles saved, {candles_failed} failed, "
                            f"batch_buffer={metrics['batch_buffer_size']}/{metrics['batch_size']}, "
                            f"batches_flushed={self.total_batches_flushed}, "
                            f"connected: {metrics['is_connected']}"
                        )
                    
                    # Parse message
                    try:
                        message = json.loads(message_str)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse JSON message: {e}, message: {message_str[:200]}")
                        continue
                    
                    # Check if this is a ticker message (for real-time price/volume updates)
                    ticker_data = self.parse_ticker_message(message)
                    if ticker_data:
                        try:
                            # Publish real-time price/volume update
                            publish_event("symbol_update", {
                                "symbol": ticker_data.get("symbol"),
                                "price": ticker_data.get("price"),
                                "volume_24h": ticker_data.get("volume_24h"),
                                "change24h": ticker_data.get("change24h"),
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            })
                        except Exception as e:
                            logger.debug(f"Failed to publish ticker update for {ticker_data.get('symbol')}: {e}")
                        # Continue processing (ticker messages don't need database operations)
                        continue
                    
                    # Check if this is a kline message (for candle data)
                    kline_data = self.parse_kline_message(message)
                    
                    if kline_data:
                        try:
                            # Add to batch buffer (thread-safe)
                            success = await self.save_candle_from_websocket(kline_data)
                            
                            # Check if we should flush the batch
                            async with self._batch_lock:
                                batch_size = len(self.batch_buffer)
                                should_flush = (
                                    batch_size >= self.batch_size or
                                    (time.time() - self.last_batch_flush) >= self.batch_timeout
                                )
                            
                            if should_flush:
                                batch_saved, batch_failed = await self.flush_batch()
                                candles_saved += batch_saved
                                candles_failed += batch_failed
                                self.last_batch_flush = time.time()
                            
                            if not success:
                                candles_failed += 1
                                logger.warning(
                                    f"Failed to add candle to batch: "
                                    f"{kline_data.get('symbol', 'unknown')} {kline_data.get('timeframe', 'unknown')}"
                                )
                        except Exception as save_error:
                            candles_failed += 1
                            logger.error(f"Failed to process candle (exception): {save_error}", exc_info=True)
                    
                except (ConnectionClosed, WebSocketException) as e:
                    logger.warning(
                        f"WebSocket connection closed: {e}. "
                        f"Reconnect attempt {self.reconnect_count + 1}, "
                        f"delay: {self.reconnect_delay}s"
                    )
                    self.is_connected = False
                    self.reconnect_count += 1
                    
                    # Try to flush any pending batch before closing (batch will be persisted in close())
                    async with self._batch_lock:
                        if self.batch_buffer:
                            try:
                                await self.flush_batch()
                            except Exception as flush_error:
                                logger.error("error_flushing_before_close", error=str(flush_error))
                    
                    # Close all connections (this will persist batch buffer)
                    await self.close()
                except Exception as e:
                    logger.error(f"Error processing WebSocket message: {e}", exc_info=True)
                    await asyncio.sleep(1)
        finally:
            # Flush any remaining batch items (batch will be persisted in close() if flush fails)
            async with self._batch_lock:
                if self.batch_buffer:
                    try:
                        batch_saved, batch_failed = await self.flush_batch()
                        candles_saved += batch_saved
                        candles_failed += batch_failed
                        logger.info(f"Flushed final batch: {batch_saved} saved, {batch_failed} failed")
                    except Exception as e:
                        logger.error(f"Error flushing final batch: {e}")
                        # Batch will be persisted by close() if available
            
            logger.info(f"WebSocket listener stopped. Total: {candles_saved} saved, {candles_failed} failed")
    
    async def start(self, symbols: List[str], timeframes: List[str], shutdown_event=None):
        """Start WebSocket service with reconnection logic and fallback to REST API
        
        Args:
            symbols: List of symbols to subscribe to
            timeframes: List of timeframes to subscribe to
            shutdown_event: Optional asyncio.Event to signal shutdown
        """
        # Store initial symbols and timeframes
        async with self._symbols_lock:
            self.current_symbols = symbols
            self.current_timeframes = timeframes
        
        logger.info(f"Starting WebSocket service for {len(symbols)} symbols, {len(timeframes)} timeframes")
        
        consecutive_failures = 0
        max_consecutive_failures = 5  # After 5 failures, fallback to REST
        
        while shutdown_event is None or not shutdown_event.is_set():
            try:
                # Get current symbols/timeframes (may have been updated)
                async with self._symbols_lock:
                    current_symbols = self.current_symbols
                    current_timeframes = self.current_timeframes
                
                if await self.connect_and_subscribe(current_symbols, current_timeframes):
                    consecutive_failures = 0  # Reset on successful connection
                    await self.listen_and_process(current_symbols, current_timeframes, shutdown_event)
                else:
                    consecutive_failures += 1
            except KeyboardInterrupt:
                logger.info("WebSocket service stopped by user")
                break
            except Exception as e:
                consecutive_failures += 1
                logger.error(f"WebSocket service error: {e}", exc_info=True)
                
                # If too many consecutive failures, fallback to REST API
                if consecutive_failures >= max_consecutive_failures:
                    logger.warning(
                        "websocket_fallback_to_rest",
                        consecutive_failures=consecutive_failures,
                        max_failures=max_consecutive_failures
                    )
                    await self._fallback_to_rest_api(symbols, timeframes, shutdown_event)
                    consecutive_failures = 0  # Reset after fallback attempt
                
                if shutdown_event and shutdown_event.is_set():
                    break
                
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
    
    async def _fallback_to_rest_api(self, symbols: List[str], timeframes: List[str], shutdown_event=None):
        """Fallback to REST API polling when WebSocket fails"""
        logger.info("fallback_rest_api_starting", symbol_count=len(symbols), timeframe_count=len(timeframes))
        
        from services.binance_service import BinanceIngestionService
        
        async with BinanceIngestionService() as binance_service:
            poll_interval = 60  # Poll every 60 seconds
            
            while shutdown_event is None or not shutdown_event.is_set():
                try:
                    for symbol in symbols:
                        if shutdown_event and shutdown_event.is_set():
                            break
                        
                        for timeframe in timeframes:
                            if shutdown_event and shutdown_event.is_set():
                                break
                            
                            try:
                                # Fetch latest candles
                                klines = await binance_service.fetch_klines(symbol, timeframe, limit=1)
                                if klines:
                                    candles = binance_service.parse_klines(klines, symbol, timeframe)
                                    if candles:
                                        with DatabaseManager() as db:
                                            binance_service.save_candles(db, candles)
                                        
                                        logger.debug(
                                            "rest_api_poll_success",
                                            symbol=symbol,
                                            timeframe=timeframe
                                        )
                            except Exception as e:
                                logger.error(
                                    "rest_api_poll_error",
                                    symbol=symbol,
                                    timeframe=timeframe,
                                    error=str(e)
                                )
                    
                    # Wait before next poll
                    await asyncio.sleep(poll_interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Fallback REST API error: {e}", exc_info=True)
                    await asyncio.sleep(poll_interval)
        
        logger.info("fallback_rest_api_stopped")
    
    def get_metrics(self) -> Dict:
        """Get WebSocket connection metrics"""
        return {
            "is_connected": self.is_connected,
            "messages_received": self.messages_received,
            "parse_errors": self.parse_errors,
            "reconnect_count": self.reconnect_count,
            "last_message_time": self.last_message_time,
            "reconnect_delay": self.reconnect_delay,
            "batch_buffer_size": len(self.batch_buffer),
            "batch_size": self.batch_size,
            "time_since_last_flush": time.time() - self.last_batch_flush if self.last_batch_flush else 0,
            "total_batches_flushed": self.total_batches_flushed,
            "total_candles_batched": self.total_candles_batched
        }

