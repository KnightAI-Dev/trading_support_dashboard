"""
Ingestion Service - Fetches market data from Binance
"""
import asyncio
import sys
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple, Set
import aiohttp
from sqlalchemy.orm import Session
from sqlalchemy import text

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.database import SessionLocal, init_db
from shared.models import OHLCVCandle
from shared.logger import setup_logger
from shared.config import (
    BINANCE_API_URL, COINGECKO_API_URL, COINGECKO_MIN_MARKET_CAP, COINGECKO_MIN_VOLUME_24H, MARKET_DATA_LIMIT, SYMBOL_LIMIT,
    DEFAULT_SYMBOLS, DEFAULT_TIMEFRAME
)
from shared.redis_client import publish_event, cache_get, cache_set

logger = setup_logger(__name__)


class BinanceIngestionService:
    """Service for ingesting data from Binance Futures/Perpetual API (fapi/v1)"""
    
    def __init__(self):
        self.base_url = BINANCE_API_URL  # Should be https://fapi.binance.com for perpetual futures
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_klines(
        self, 
        symbol: str, 
        interval: str = "1h", 
        limit: int = 500
    ) -> List[List]:
        """Fetch OHLCV klines from Binance"""
        try:
            url = f"{self.base_url}/fapi/v1/klines"
            params = {
                "symbol": symbol,
                "interval": interval,
                "limit": limit
            }
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    logger.info(f"Fetched {len(data)} klines for {symbol}")
                    return data
                else:
                    logger.error(f"Failed to fetch klines: {response.status}")
                    return []
        except Exception as e:
            logger.error(f"Error fetching klines for {symbol}: {e}")
            return []
    
    async def fetch_ticker_24h(self, symbol: str) -> Optional[Dict]:
        """Fetch 24h ticker data for a single symbol"""
        try:
            url = f"{self.base_url}/fapi/v1/ticker/24hr"
            params = {"symbol": symbol}
            
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching ticker for {symbol}: {e}")
            return None
    
    async def fetch_all_tickers_24h(self) -> Dict[str, Dict]:
        """Fetch 24h ticker data for all symbols and return as dictionary keyed by symbol"""
        try:
            url = f"{self.base_url}/fapi/v1/ticker/24hr"
            # No symbol parameter = get all tickers
            
            async with self.session.get(url) as response:
                if response.status == 200:
                    tickers = await response.json()
                    # Convert list to dictionary keyed by symbol for fast lookup
                    ticker_dict = {ticker.get("symbol"): ticker for ticker in tickers if ticker.get("symbol")}
                    logger.info(f"Fetched {len(ticker_dict)} tickers from Binance")
                    return ticker_dict
                else:
                    logger.error(f"Failed to fetch all tickers: {response.status}")
                    return {}
        except Exception as e:
            logger.error(f"Error fetching all tickers: {e}")
            return {}
    
    async def fetch_exchange_info(self) -> Optional[Dict]:
        """Fetch exchange information"""
        try:
            url = f"{self.base_url}/fapi/v1/exchangeInfo"
            async with self.session.get(url) as response:
                if response.status == 200:
                    return await response.json()
                return None
        except Exception as e:
            logger.error(f"Error fetching exchange info: {e}")
            return None
    
    async def get_available_perpetual_symbols(self) -> Set[str]:
        """Get set of available perpetual contract symbols from Binance Futures"""
        try:
            exchange_info = await self.fetch_exchange_info()
            if not exchange_info:
                logger.warning("Could not fetch Binance exchange info")
                return set()
            
            # Filter for perpetual contracts (contractType: PERPETUAL)
            perpetual_symbols = set()
            for symbol_info in exchange_info.get("symbols", []):
                if symbol_info.get("contractType") == "PERPETUAL" and symbol_info.get("status") == "TRADING":
                    perpetual_symbols.add(symbol_info.get("symbol"))
            
            logger.info(f"Found {len(perpetual_symbols)} available perpetual contracts on Binance")
            return perpetual_symbols
        except Exception as e:
            logger.error(f"Error fetching available perpetual symbols: {e}")
            return set()
    
    def parse_klines(self, klines: List[List], symbol: str, timeframe: str) -> List[OHLCVCandle]:
        """Parse klines data into OHLCVCandle objects"""
        candles = []
        for kline in klines:
            try:
                candle = OHLCVCandle(
                    symbol=symbol,
                    timeframe=timeframe,
                    timestamp=datetime.fromtimestamp(kline[0] / 1000),
                    open=float(kline[1]),
                    high=float(kline[2]),
                    low=float(kline[3]),
                    close=float(kline[4]),
                    volume=float(kline[5])
                )
                candles.append(candle)
            except Exception as e:
                logger.error(f"Error parsing kline: {e}")
                continue
        return candles
    
    def save_candles(self, db: Session, candles: List[OHLCVCandle]):
        """Save candles to database with symbol/timeframe foreign keys"""
        if not candles:
            return
        
        try:
            first_candle = candles[0]
            symbol_id = get_or_create_symbol_record(db, first_candle.symbol)
            timeframe_id = get_timeframe_id(db, first_candle.timeframe)
            
            if not symbol_id or not timeframe_id:
                logger.error(
                    f"Unable to resolve IDs for symbol {first_candle.symbol} "
                    f"and timeframe {first_candle.timeframe}"
                )
                return
            
            stmt = text("""
                INSERT INTO ohlcv_candles 
                (symbol_id, timeframe_id, timestamp, open, high, low, close, volume)
                VALUES (:symbol_id, :timeframe_id, :timestamp, :open, :high, :low, :close, :volume)
                ON CONFLICT (symbol_id, timeframe_id, timestamp) DO NOTHING
            """)
            
            for candle in candles:
                db.execute(stmt, {
                    "symbol_id": symbol_id,
                    "timeframe_id": timeframe_id,
                    "timestamp": candle.timestamp,
                    "open": float(candle.open),
                    "high": float(candle.high),
                    "low": float(candle.low),
                    "close": float(candle.close),
                    "volume": float(candle.volume)
                })
            
            db.commit()
            logger.info(f"Saved {len(candles)} candles for {first_candle.symbol} {first_candle.timeframe}")
        except Exception as e:
            logger.error(f"Error saving candles: {e}")
            db.rollback()
            raise
    
    async def ingest_symbol(self, symbol: str, timeframe: str = DEFAULT_TIMEFRAME):
        """Ingest data for a single symbol with error isolation"""
        try:
            logger.debug(f"Starting ingestion for {symbol} ({timeframe})")
            
            # Fetch klines
            klines = await self.fetch_klines(symbol, timeframe, limit=SYMBOL_LIMIT)
            if not klines:
                logger.warning(f"No klines fetched for {symbol} ({timeframe})")
                return
            
            # Parse and save
            candles = self.parse_klines(klines, symbol, timeframe)
            if candles:
                db = SessionLocal()
                try:
                    self.save_candles(db, candles)
                    # Publish event
                    publish_event("candle_update", {
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "timestamp": candles[-1].timestamp.isoformat()
                    })
                finally:
                    db.close()
            
            # Note: market_data (price, market_cap, volume_24h) is updated hourly 
            # via the CoinGecko hourly update task, not here
        except Exception as e:
            # Isolate errors per symbol - log but don't abort the batch
            logger.error(f"Error ingesting {symbol} ({timeframe}): {e}", exc_info=True)
    
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
            logger.debug(f"Timeframe {timeframe}: All {len(symbols)} symbols ingested successfully")


async def main():
    """Main ingestion loop"""
    if not init_db():
        logger.error("Database initialization failed")
        return
    
    symbols = DEFAULT_SYMBOLS
    timeframe = DEFAULT_TIMEFRAME
    
    logger.info(f"Starting ingestion service for symbols: {symbols}")
    
    async with BinanceIngestionService() as service:
        while True:
            try:
                await service.ingest_all_symbols(symbols, timeframe)
                logger.info("Ingestion cycle completed")
                await asyncio.sleep(60)  # Wait 1 minute before next cycle
            except KeyboardInterrupt:
                logger.info("Ingestion service stopped")
                break
            except Exception as e:
                logger.error(f"Error in ingestion loop: {e}")
                await asyncio.sleep(60)


class CoinGeckoIngestionService:
    """Service for ingesting market data from CoinGecko API"""
    
    def __init__(self):
        self.base_url = COINGECKO_API_URL
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_top_market_metrics(self, limit: int = 200) -> List[Dict]:
        """Fetch top market metrics from CoinGecko"""
        try:
            # Calculate pages needed (CoinGecko allows max 250 per page)
            per_page = min(limit, 250)
            pages_needed = (limit + per_page - 1) // per_page
            
            all_coins = []
            for page in range(1, pages_needed + 1):
                url = f"{self.base_url}/coins/markets"
                params = {
                    "vs_currency": "usd",
                    "order": "market_cap_desc",
                    "per_page": per_page,
                    "page": page,
                    "sparkline": "false"
                }
                
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        all_coins.extend(data)
                        logger.info(f"Fetched page {page}: {len(data)} coins")
                    else:
                        logger.error(f"Failed to fetch CoinGecko data: {response.status}")
                        if response.status == 429:
                            logger.warning("Rate limited by CoinGecko, waiting 60 seconds...")
                            await asyncio.sleep(60)
                            continue
                        break
            
            # Limit to requested number
            return all_coins[:limit]
        except Exception as e:
            logger.error(f"Error fetching CoinGecko market metrics: {e}")
            return []
    
    def map_coin_to_symbol(self, coin_data: Dict) -> Optional[str]:
        """Map CoinGecko coin data to trading symbol (e.g., BTCUSDT)"""
        try:
            symbol = coin_data.get("symbol", "").upper()
            if symbol:
                return f"{symbol}USDT"
            return None
        except Exception as e:
            logger.error(f"Error mapping coin to symbol: {e}")
            return None
    
    def get_or_create_symbol_id(self, db: Session, symbol: str, image_path: Optional[str] = None) -> Optional[int]:
        """Get or create symbol_id for a given symbol with optional image path"""
        return get_or_create_symbol_record(db, symbol, image_path=image_path)
    
    async def save_market_metrics(self, db: Session, coins_data: List[Dict], binance_service: Optional[BinanceIngestionService] = None):
        """Save market metrics to database, using Binance ticker for price and volume_24h data"""
        try:
            saved_count = 0
            skipped_count = 0
            current_timestamp = datetime.now()
            
            # Fetch all ticker data from Binance once (much faster than individual requests)
            binance_tickers = {}
            if binance_service:
                logger.info("Fetching all ticker data from Binance...")
                binance_tickers = await binance_service.fetch_all_tickers_24h()
                logger.info(f"Retrieved {len(binance_tickers)} tickers from Binance")
            
            for coin in coins_data:
                try:
                    symbol = self.map_coin_to_symbol(coin)
                    if not symbol:
                        skipped_count += 1
                        continue
                    
                    # Extract image path from CoinGecko data
                    image_path = coin.get("image")
                    
                    # Get or create symbol_id with image path
                    symbol_id = self.get_or_create_symbol_id(db, symbol, image_path=image_path)
                    if not symbol_id:
                        logger.warning(f"Could not get/create symbol_id for {symbol}")
                        skipped_count += 1
                        continue
                    
                    # Extract market data from CoinGecko
                    market_cap = coin.get("market_cap")
                    volume_24h = coin.get("total_volume")  # Fallback to CoinGecko volume
                    circulating_supply = coin.get("circulating_supply")
                    price = coin.get("current_price")  # Fallback to CoinGecko price
                    
                    # Get price and volume from Binance ticker data (already fetched, just lookup)
                    if binance_service and symbol in binance_tickers:
                        ticker = binance_tickers[symbol]
                        # Use Binance price (lastPrice)
                        if ticker.get("lastPrice"):
                            price = float(ticker.get("lastPrice"))
                            logger.debug(f"Using Binance price for {symbol}: {price}")
                        
                        # Use Binance volume (quoteVolume is in USDT, volume is in base asset)
                        # Prefer quoteVolume as it's in USDT which matches our volume_24h field
                        if ticker.get("quoteVolume"):
                            volume_24h = float(ticker.get("quoteVolume"))
                            logger.debug(f"Using Binance volume_24h for {symbol}: {volume_24h}")
                    
                    # Skip if essential data is missing
                    if market_cap is None and volume_24h is None and circulating_supply is None and price is None:
                        skipped_count += 1
                        continue
                    
                    # Use INSERT ... ON CONFLICT DO UPDATE for upsert
                    stmt = text("""
                        INSERT INTO market_data 
                        (symbol_id, timestamp, market_cap, volume_24h, circulating_supply, price)
                        VALUES (:symbol_id, :timestamp, :market_cap, :volume_24h, :circulating_supply, :price)
                        ON CONFLICT (symbol_id, timestamp) 
                        DO UPDATE SET
                            market_cap = EXCLUDED.market_cap,
                            volume_24h = EXCLUDED.volume_24h,
                            circulating_supply = EXCLUDED.circulating_supply,
                            price = EXCLUDED.price
                    """)
                    db.execute(stmt, {
                        "symbol_id": symbol_id,
                        "timestamp": current_timestamp,
                        "market_cap": float(market_cap) if market_cap else None,
                        "volume_24h": float(volume_24h) if volume_24h else None,
                        "circulating_supply": float(circulating_supply) if circulating_supply else None,
                        "price": float(price) if price else None
                    })
                    saved_count += 1
                    
                except Exception as e:
                    logger.error(f"Error saving market data for {coin.get('id', 'unknown')}: {e}")
                    skipped_count += 1
                    continue
            
            db.commit()
            logger.info(f"Saved {saved_count} market metrics, skipped {skipped_count}")
            
            # Publish event
            if saved_count > 0:
                publish_event("market_metrics_update", {
                    "count": saved_count,
                    "timestamp": current_timestamp.isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error saving market metrics: {e}")
            db.rollback()
            raise
    
    async def fetch_market_data_by_symbols(self, symbols: List[str]) -> List[Dict]:
        """Fetch market data from CoinGecko for specific symbols"""
        try:
            # Convert symbols to coin IDs (remove USDT suffix and lowercase)
            coin_ids = []
            symbol_to_coin_id = {}
            for symbol in symbols:
                if symbol.endswith("USDT"):
                    coin_id = symbol[:-4].lower()
                    coin_ids.append(coin_id)
                    symbol_to_coin_id[symbol] = coin_id
            
            if not coin_ids:
                return []
            
            # CoinGecko API allows up to 250 coin IDs per request
            all_coins = []
            batch_size = 250
            for i in range(0, len(coin_ids), batch_size):
                batch = coin_ids[i:i + batch_size]
                coin_ids_str = ",".join(batch)
                
                url = f"{self.base_url}/coins/markets"
                params = {
                    "vs_currency": "usd",
                    "ids": coin_ids_str,
                    "order": "market_cap_desc",
                    "per_page": len(batch),
                    "page": 1,
                    "sparkline": "false"
                }
                print(params)
                
                async with self.session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        all_coins.extend(data)
                        logger.info(f"Fetched market data for {len(data)} coins")
                    else:
                        logger.error(f"Failed to fetch CoinGecko data: {response.status}")
                        if response.status == 429:
                            logger.warning("Rate limited by CoinGecko, waiting 60 seconds...")
                            await asyncio.sleep(60)
                            continue
                        break
            
            return all_coins
        except Exception as e:
            logger.error(f"Error fetching market data by symbols: {e}")
            return []
    
    async def update_market_data_for_symbols(self, symbols: List[str], binance_service: Optional[BinanceIngestionService] = None):
        """Update market data (price, market_cap, volume_24h) for existing symbols"""
        logger.info(f"Updating market data for {len(symbols)} symbols")
        
        # Fetch market data from CoinGecko
        coins_data = await self.fetch_market_data_by_symbols(symbols)
        if not coins_data:
            logger.warning("No market data fetched from CoinGecko")
            return
        
        # Update database
        db = SessionLocal()
        try:
            await self.save_market_metrics(db, coins_data, binance_service=binance_service)
            logger.info(f"Successfully updated market data for {len(coins_data)} symbols")
        finally:
            db.close()
    
    async def ingest_top_market_metrics(self, limit: int = 200, binance_service: Optional[BinanceIngestionService] = None):
        """Ingest top market metrics from CoinGecko, filtered to only Binance perpetual contracts"""
        logger.info(f"Starting CoinGecko ingestion for top {limit} coins")
        
        # Fetch market metrics
        coins_data = await self.fetch_top_market_metrics(limit)
        if not coins_data:
            logger.warning("No market metrics fetched from CoinGecko")
            return
        
        # Filter to only include symbols available on Binance perpetual contracts
        if binance_service:
            available_symbols = await binance_service.get_available_perpetual_symbols()
            if available_symbols:
                filtered_coins = []
                for coin in coins_data:
                    symbol = self.map_coin_to_symbol(coin)
                    if symbol and symbol in available_symbols:
                        filtered_coins.append(coin)
                    else:
                        logger.debug(f"Filtered out {coin.get('id', 'unknown')} - not available as perpetual on Binance")
                
                coins_data = filtered_coins
                logger.info(f"Filtered to {len(coins_data)} coins available as Binance perpetual contracts")
            else:
                logger.warning("Could not fetch Binance perpetual symbols, saving all CoinGecko data")
        
        # Save to database
        db = SessionLocal()
        try:
            await self.save_market_metrics(db, coins_data, binance_service=binance_service)
        finally:
            db.close()


def get_qualified_symbols(db: Session) -> List[str]:
    """Get symbols from database that meet market cap and volume criteria"""
    try:
        # Query symbols with latest market_data that meet criteria
        result = db.execute(
            text("""
                SELECT s.symbol_name
                FROM symbols s
                INNER JOIN (
                    SELECT DISTINCT ON (symbol_id)
                        symbol_id, market_cap, volume_24h
                    FROM market_data
                    WHERE market_cap IS NOT NULL
                    AND volume_24h IS NOT NULL
                    ORDER BY symbol_id, timestamp DESC
                ) md ON s.symbol_id = md.symbol_id
                ORDER BY md.market_cap DESC, s.symbol_name;
            """)
        ).fetchall()
        
        symbols = [row[0] for row in result]
        logger.info(f"Found {len(symbols)} qualified symbols from database")
        return symbols
    except Exception as e:
        logger.error(f"Error fetching qualified symbols: {e}")
        return DEFAULT_SYMBOLS


def get_ingestion_timeframes(db: Session) -> List[str]:
    """Get ingestion timeframes from timeframe table, fallback to DEFAULT_TIMEFRAME list"""
    try:
        results = db.execute(
            text("SELECT tf_name FROM timeframe ORDER BY seconds ASC")
        ).fetchall()
        timeframes = [row[0] for row in results]
        if timeframes:
            logger.info(f"Using {len(timeframes)} timeframes from database: {timeframes}")
            return timeframes
    except Exception as e:
        logger.error(f"Error fetching timeframes from database: {e}")
    
    logger.warning(f"Falling back to DEFAULT_TIMEFRAME only: {DEFAULT_TIMEFRAME}")
    return [DEFAULT_TIMEFRAME]


KNOWN_QUOTE_ASSETS = ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB", "USD", "EUR", "TRY", "BIDR"]


def split_symbol_components(symbol: str) -> Tuple[str, str]:
    """Best-effort parsing of base/quote assets from a trading symbol"""
    for quote in KNOWN_QUOTE_ASSETS:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[:-len(quote)], quote
    # Fallback: treat entire symbol as base and default quote to USD
    return symbol, "USD"


def get_or_create_symbol_record(db: Session, symbol: str, image_path: Optional[str] = None) -> Optional[int]:
    """Ensure symbol exists in symbols table and return symbol_id"""
    try:
        result = db.execute(
            text("SELECT symbol_id FROM symbols WHERE symbol_name = :symbol"),
            {"symbol": symbol}
        ).scalar()
        if result:
            symbol_id = result
            if image_path:
                db.execute(
                    text("""
                        UPDATE symbols
                        SET image_path = :image_path, updated_at = NOW()
                        WHERE symbol_id = :symbol_id AND (image_path IS NULL OR image_path != :image_path)
                    """),
                    {"symbol_id": symbol_id, "image_path": image_path}
                )
            return symbol_id
        
        base_asset, quote_asset = split_symbol_components(symbol)
        result = db.execute(
            text("""
                INSERT INTO symbols (symbol_name, base_asset, quote_asset, image_path)
                VALUES (:symbol, :base_asset, :quote_asset, :image_path)
                ON CONFLICT (symbol_name) DO UPDATE SET
                    image_path = COALESCE(EXCLUDED.image_path, symbols.image_path),
                    updated_at = NOW()
                RETURNING symbol_id
            """),
            {
                "symbol": symbol,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "image_path": image_path
            }
        ).scalar()
        return result
    except Exception as e:
        logger.error(f"Error ensuring symbol record for {symbol}: {e}")
        return None


def get_timeframe_id(db: Session, timeframe: str) -> Optional[int]:
    """Get timeframe_id for given timeframe string"""
    try:
        return db.execute(
            text("SELECT timeframe_id FROM timeframe WHERE tf_name = :tf LIMIT 1"),
            {"tf": timeframe}
        ).scalar()
    except Exception as e:
        logger.error(f"Error fetching timeframe_id for {timeframe}: {e}")
        return None


async def hourly_market_data_update():
    """Background task to update market data every hour with metrics"""
    logger.info("Hourly market data update task started")
    while True:
        try:            
            await asyncio.sleep(3600)  # Wait 1 hour
            
            start_time = datetime.now()
            
            # Get all symbols from database that have market data
            db = SessionLocal()
            try:
                result = db.execute(
                    text("""
                        SELECT DISTINCT s.symbol_name
                        FROM symbols s
                        INNER JOIN market_data md ON s.symbol_id = md.symbol_id
                        ORDER BY s.symbol_name
                    """)
                ).fetchall()
                symbols = [row[0] for row in result]
            finally:
                db.close()
            
            if symbols:
                logger.info(f"Starting hourly market data update for {len(symbols)} symbols")
                # Create service instances for this update
                async with BinanceIngestionService() as binance_service:
                    async with CoinGeckoIngestionService() as coingecko_service:
                        await coingecko_service.update_market_data_for_symbols(symbols, binance_service=binance_service)
                
                # Calculate metrics
                duration = (datetime.now() - start_time).total_seconds()
                symbols_per_second = len(symbols) / duration if duration > 0 else 0
                
                logger.info(
                    f"Hourly market data update completed: {len(symbols)} symbols updated "
                    f"in {duration:.2f}s ({symbols_per_second:.2f} symbols/sec)"
                )
            else:
                logger.warning("No symbols found for hourly market data update")

        except asyncio.CancelledError:
            logger.info("Hourly market data update task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in hourly market data update: {e}", exc_info=True)
            await asyncio.sleep(60)  # Wait 1 minute before retrying


async def main():
    """Main ingestion loop"""
    if not init_db():
        logger.error("Database initialization failed")
        return
    
    # Ingest CoinGecko market metrics first, filtered to Binance perpetual contracts
    async with BinanceIngestionService() as binance_service:
        async with CoinGeckoIngestionService() as coingecko_service:
            await coingecko_service.ingest_top_market_metrics(limit=MARKET_DATA_LIMIT, binance_service=binance_service)
            logger.info("CoinGecko market metrics ingestion completed (filtered to Binance perpetuals)")
    
    # Start hourly market data update task (runs independently)
    update_task = asyncio.create_task(hourly_market_data_update())
    logger.info("Started hourly market data update task")
    
    try:
        # Get qualified symbols and timeframes from database
        db = SessionLocal()
        try:
            timeframes = get_ingestion_timeframes(db)
            symbols = get_qualified_symbols(db)
            if not symbols:
                logger.warning("No qualified symbols found, using default symbols")
                symbols = DEFAULT_SYMBOLS
        finally:
            db.close()
        
        logger.info(
            f"Starting Binance ingestion for {len(symbols)} symbols "
            f"across {len(timeframes)} timeframes: {timeframes}"
        )
        
        # Continue with Binance ingestion
        cycle_count = 0
        async with BinanceIngestionService() as service:
            while True:
                try:
                    # Refresh symbols list every 10 cycles (~10 minutes)
                    # This ensures we pick up newly qualified symbols
                    if cycle_count % 10 == 0:
                        db = SessionLocal()
                        try:
                            new_symbols = get_qualified_symbols(db)
                            if new_symbols:
                                symbols = new_symbols
                                logger.info(f"Refreshed symbols list: {len(symbols)} qualified symbols")
                            new_timeframes = get_ingestion_timeframes(db)
                            if new_timeframes:
                                timeframes = new_timeframes
                                logger.info(f"Refreshed timeframe list: {timeframes}")
                        finally:
                            db.close()
                    
                    # Ingest all timeframes in parallel
                    timeframe_tasks = [
                        service.ingest_all_symbols(symbols, timeframe) 
                        for timeframe in timeframes
                    ]
                    await asyncio.gather(*timeframe_tasks, return_exceptions=True)
                    logger.info(f"Ingestion cycle completed for all {len(timeframes)} timeframes")
                    
                    cycle_count += 1
                    await asyncio.sleep(60)  # Wait 1 minute before next cycle
                except KeyboardInterrupt:
                    logger.info("Ingestion service stopped")
                    break
                except Exception as e:
                    logger.error(f"Error in ingestion loop: {e}")
                    await asyncio.sleep(60)
    finally:
        # Cancel the hourly update task
        update_task.cancel()
        try:
            await update_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    asyncio.run(main())

