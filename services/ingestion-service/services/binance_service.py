"""
Binance ingestion service for fetching market data from Binance Futures API
"""
import sys
import os
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set
import aiohttp
from sqlalchemy.orm import Session
from sqlalchemy import text
import structlog

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from shared.database import DatabaseManager
from shared.models import OHLCVCandle
from shared.redis_client import publish_event

# Import from local modules (relative to ingestion-service root)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.circuit_breaker import AsyncCircuitBreaker
from utils.rate_limiter import BINANCE_RATE_LIMIT, BINANCE_BURST_LIMIT
from config.settings import BINANCE_API_URL, DEFAULT_TIMEFRAME, SYMBOL_LIMIT
from database.repository import get_or_create_symbol_record, get_timeframe_id

logger = structlog.get_logger(__name__)

class BinanceIngestionService:
    """Service for ingesting data from Binance Futures/Perpetual API (fapi/v1)"""
    
    def __init__(self):
        self.base_url = BINANCE_API_URL  # Should be https://fapi.binance.com for perpetual futures
        self.session: Optional[aiohttp.ClientSession] = None
        self.circuit_breaker = AsyncCircuitBreaker(
            failure_threshold=5,
            recovery_timeout=60,
            expected_exception=(aiohttp.ClientError, asyncio.TimeoutError, Exception)
        )
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def _fetch_klines_impl(
        self, 
        symbol: str, 
        interval: str = "1h", 
        limit: int = 500,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[List]:
        """Internal implementation of fetch_klines with rate limiting
        
        Args:
            symbol: Trading symbol
            interval: Timeframe interval
            limit: Maximum number of candles (max 1000)
            start_time: Optional start time for historical data
            end_time: Optional end time for historical data
        """
        url = f"{self.base_url}/fapi/v1/klines"
        params = {
            "symbol": symbol,
            "interval": interval,
            "limit": limit
        }
        
        # Add time range parameters if provided
        if start_time:
            # Convert datetime to milliseconds timestamp
            params["startTime"] = int(start_time.timestamp() * 1000)
        if end_time:
            params["endTime"] = int(end_time.timestamp() * 1000)
        
        # Apply rate limiting
        async with BINANCE_RATE_LIMIT:
            async with BINANCE_BURST_LIMIT:
                async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        data = await response.json()
                        logger.info(
                            "klines_fetched",
                            symbol=symbol,
                            interval=interval,
                            count=len(data),
                            limit=limit
                        )
                        return data
                    else:
                        logger.error(
                            "klines_fetch_failed",
                            symbol=symbol,
                            interval=interval,
                            status_code=response.status
                        )
                        response.raise_for_status()
                        return []
    
    async def fetch_klines(
        self, 
        symbol: str, 
        interval: str = "1h", 
        limit: int = 500,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[List]:
        """Fetch OHLCV klines from Binance with circuit breaker protection
        
        Args:
            symbol: Trading symbol (will be cleaned to remove any @ prefix)
            interval: Timeframe interval
            limit: Maximum number of candles (max 1000)
            start_time: Optional start time for historical data
            end_time: Optional end time for historical data
        """
        # Clean symbol: remove @ prefix if present (from WebSocket stream names)
        cleaned_symbol = symbol.lstrip("@").upper()
        
        if cleaned_symbol != symbol:
            logger.warning(
                "symbol_cleaned",
                original=symbol,
                cleaned=cleaned_symbol
            )
        
        try:
            return await self.circuit_breaker.call(
                self._fetch_klines_impl,
                cleaned_symbol,
                interval,
                limit,
                start_time,
                end_time
            )
        except Exception as e:
            logger.error(
                "klines_fetch_error",
                symbol=symbol,
                interval=interval,
                error=str(e),
                exc_info=True
            )
            return []
    
    async def _fetch_ticker_24h_impl(self, symbol: str) -> Optional[Dict]:
        """Internal implementation of fetch_ticker_24h with rate limiting"""
        url = f"{self.base_url}/fapi/v1/ticker/24hr"
        params = {"symbol": symbol}
        
        async with BINANCE_RATE_LIMIT:
            async with BINANCE_BURST_LIMIT:
                async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        return await response.json()
                    response.raise_for_status()
                    return None
    
    async def fetch_ticker_24h(self, symbol: str) -> Optional[Dict]:
        """Fetch 24h ticker data for a single symbol with circuit breaker protection"""
        try:
            return await self.circuit_breaker.call(self._fetch_ticker_24h_impl, symbol)
        except Exception as e:
            logger.error(
                "ticker_fetch_error",
                symbol=symbol,
                error=str(e),
                exc_info=True
            )
            return None
    
    async def _fetch_all_tickers_24h_impl(self) -> Dict[str, Dict]:
        """Internal implementation of fetch_all_tickers_24h with rate limiting"""
        url = f"{self.base_url}/fapi/v1/ticker/24hr"
        # No symbol parameter = get all tickers
        
        async with BINANCE_RATE_LIMIT:
            async with BINANCE_BURST_LIMIT:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
                    if response.status == 200:
                        tickers = await response.json()
                        # Convert list to dictionary keyed by symbol for fast lookup
                        ticker_dict = {ticker.get("symbol"): ticker for ticker in tickers if ticker.get("symbol")}
                        logger.info(
                            "all_tickers_fetched",
                            count=len(ticker_dict)
                        )
                        return ticker_dict
                    else:
                        logger.error(
                            "all_tickers_fetch_failed",
                            status_code=response.status
                        )
                        response.raise_for_status()
                        return {}
    
    async def fetch_all_tickers_24h(self) -> Dict[str, Dict]:
        """Fetch 24h ticker data for all symbols with circuit breaker protection"""
        try:
            return await self.circuit_breaker.call(self._fetch_all_tickers_24h_impl)
        except Exception as e:
            logger.error(
                "all_tickers_fetch_error",
                error=str(e),
                exc_info=True
            )
            return {}
    
    async def _fetch_exchange_info_impl(self) -> Optional[Dict]:
        """Internal implementation of fetch_exchange_info with rate limiting"""
        url = f"{self.base_url}/fapi/v1/exchangeInfo"
        async with BINANCE_RATE_LIMIT:
            async with BINANCE_BURST_LIMIT:
                async with self.session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        return await response.json()
                    response.raise_for_status()
                    return None
    
    async def fetch_exchange_info(self) -> Optional[Dict]:
        """Fetch exchange information with circuit breaker protection"""
        try:
            return await self.circuit_breaker.call(self._fetch_exchange_info_impl)
        except Exception as e:
            logger.error(
                "exchange_info_fetch_error",
                error=str(e),
                exc_info=True
            )
            return None
    
    async def get_available_perpetual_symbols(self) -> Set[str]:
        """Get set of available perpetual contract symbols from Binance Futures"""
        try:
            exchange_info = await self.fetch_exchange_info()
            if not exchange_info:
                logger.warning("exchange_info_fetch_failed")
                return set()
            
            # Filter for perpetual contracts (contractType: PERPETUAL)
            perpetual_symbols = set()
            for symbol_info in exchange_info.get("symbols", []):
                if symbol_info.get("contractType") == "PERPETUAL" and symbol_info.get("status") == "TRADING":
                    perpetual_symbols.add(symbol_info.get("symbol"))
            
            logger.info(
                "perpetual_symbols_found",
                count=len(perpetual_symbols)
            )
            return perpetual_symbols
        except Exception as e:
            logger.error(
                "perpetual_symbols_fetch_error",
                error=str(e),
                exc_info=True
            )
            return set()
    
    def parse_klines(self, klines: List[List], symbol: str, timeframe: str) -> List[OHLCVCandle]:
        """Parse klines data into OHLCVCandle objects"""
        candles = []
        for kline in klines:
            try:
                candle = OHLCVCandle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.fromtimestamp(kline[0] / 1000, tz=timezone.utc),
                    open=float(kline[1]),
                    high=float(kline[2]),
                    low=float(kline[3]),
                    close=float(kline[4]),
                    volume=float(kline[5])
                )
                candles.append(candle)
            except Exception as e:
                logger.error(
                    "kline_parse_error",
                    symbol=symbol,
                    error=str(e),
                    exc_info=True
                )
                continue
        return candles
    
    def save_candles(self, db: Session, candles: List[OHLCVCandle]):
        """Save candles to database with symbol/timeframe foreign keys (BATCH INSERT)
        
        Note: Does not commit - caller should commit at service boundary
        """
        if not candles:
            return
        
        try:
            first_candle = candles[0]
            symbol_id = get_or_create_symbol_record(db, first_candle.symbol)
            timeframe_id = get_timeframe_id(db, first_candle.timeframe)
            
            if not symbol_id or not timeframe_id:
                logger.error(
                    "symbol_timeframe_id_resolution_failed",
                    symbol=first_candle.symbol,
                    timeframe=first_candle.timeframe,
                    symbol_id=symbol_id,
                    timeframe_id=timeframe_id
                )
                return
            
            # Batch insert all candles in single execute
            params_list = []
            for candle in candles:
                params_list.append({
                    "symbol_id": symbol_id,
                    "timeframe_id": timeframe_id,
                    "timestamp": candle.timestamp,
                    "open": float(candle.open),
                    "high": float(candle.high),
                    "low": float(candle.low),
                    "close": float(candle.close),
                    "volume": float(candle.volume)
                })
            
            stmt = text("""
                INSERT INTO ohlcv_candles 
                (symbol_id, timeframe_id, timestamp, open, high, low, close, volume)
                VALUES (:symbol_id, :timeframe_id, :timestamp, :open, :high, :low, :close, :volume)
                ON CONFLICT (symbol_id, timeframe_id, timestamp) DO NOTHING
            """)
            
            # Single execute for all candles (more efficient)
            db.execute(stmt, params_list)
            
            # Note: No commit here - caller commits at service boundary
            logger.info(
                "candles_saved",
                symbol=first_candle.symbol,
                timeframe=first_candle.timeframe,
                count=len(candles)
            )
        except Exception as e:
            logger.error(
                "candles_save_error",
                symbol=first_candle.symbol,
                timeframe=first_candle.timeframe,
                count=len(candles),
                error=str(e),
                exc_info=True
            )
            raise
    
    async def ingest_symbol(self, symbol: str, timeframe: str = DEFAULT_TIMEFRAME):
        """Ingest data for a single symbol with error isolation"""
        try:
            logger.debug("ingestion_started", symbol=symbol, timeframe=timeframe)
            
            # Fetch klines
            klines = await self.fetch_klines(symbol, timeframe, limit=SYMBOL_LIMIT)
            if not klines:
                logger.warning("no_klines_fetched", symbol=symbol, timeframe=timeframe)
                return
            
            # Parse and save
            candles = self.parse_klines(klines, symbol, timeframe)
            if candles:
                with DatabaseManager() as db:
                    self.save_candles(db, candles)
                    db.commit()  # Commit at service boundary
                    # Publish event with full OHLCV data
                    latest_candle = candles[-1]
                    publish_event("candle_update", {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "timestamp": latest_candle.timestamp.isoformat(),
                        "open": float(latest_candle.open),
                        "high": float(latest_candle.high),
                        "low": float(latest_candle.low),
                        "close": float(latest_candle.close),
                        "volume": float(latest_candle.volume),
                        "closed": True
                    })
            
            # Note: market_data (price, market_cap, volume_24h) is updated hourly 
            # via the CoinGecko hourly update task, not here
        except Exception as e:
            # Isolate errors per symbol - log but don't abort the batch
            logger.error(
                "ingestion_error",
                symbol=symbol,
                timeframe=timeframe,
                error=str(e),
                exc_info=True
            )
    
    async def ingest_all_symbols(self, symbols: List[str], timeframe: str = DEFAULT_TIMEFRAME):
        """Ingest data for multiple symbols with error isolation"""
        tasks = [self.ingest_symbol(symbol, timeframe) for symbol in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count successes and failures
        # Exceptions are caught and logged in ingest_symbol, but we can still track them here
        success_count = sum(1 for r in results if r is None or not isinstance(r, Exception))
        failure_count = sum(1 for r in results if isinstance(r, Exception))
        
        if failure_count > 0:
            logger.warning(
                f"Timeframe {timeframe}: {success_count}/{len(symbols)} symbols succeeded, "
                f"{failure_count} symbols failed"
            )
        else:
            logger.debug(
                "ingestion_completed",
                timeframe=timeframe,
                symbol_count=len(symbols),
                success_count=success_count
            )
