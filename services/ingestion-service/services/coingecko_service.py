"""
CoinGecko ingestion service for fetching market data from CoinGecko API
"""
import sys
import os
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
import aiohttp
from sqlalchemy.orm import Session
from sqlalchemy import text
import structlog

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from shared.database import DatabaseManager
from shared.redis_client import publish_event

# Import from local modules (relative to ingestion-service root)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.circuit_breaker import AsyncCircuitBreaker
from utils.rate_limiter import COINGECKO_RATE_LIMIT, COINGECKO_MINUTE_LIMIT
from config.settings import COINGECKO_API_URL
from database.repository import get_or_create_symbol_record
from services.binance_service import BinanceIngestionService

logger = structlog.get_logger(__name__)

class CoinGeckoIngestionService:
    """Service for ingesting market data from CoinGecko API"""
    
    def __init__(self):
        self.base_url = COINGECKO_API_URL
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
    
    async def _fetch_top_market_metrics_impl(self, limit: int = 200) -> List[Dict]:
        """Internal implementation of fetch_top_market_metrics"""
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
            
            async with COINGECKO_RATE_LIMIT:
                async with COINGECKO_MINUTE_LIMIT:
                    async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as response:
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
                            response.raise_for_status()
                            break
        
        # Limit to requested number
        return all_coins[:limit]
    
    async def fetch_top_market_metrics(self, limit: int = 200) -> List[Dict]:
        """Fetch top market metrics from CoinGecko with circuit breaker protection"""
        try:
            return await self.circuit_breaker.call(self._fetch_top_market_metrics_impl, limit)
        except Exception as e:
            logger.error("coingecko_market_metrics_error", error=str(e), exc_info=True)
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
    
    def get_symbol_id(self, db: Session, symbol: str) -> Optional[int]:
        """Get symbol_id for an existing symbol only (does not create new symbols)"""
        try:
            result = db.execute(
                text("SELECT symbol_id FROM symbols WHERE symbol_name = :symbol"),
                {"symbol": symbol}
            ).scalar()
            return result
        except Exception as e:
            logger.error(f"Error getting symbol_id for {symbol}: {e}")
            return None
    
    async def save_market_metrics(
        self, 
        db: Session, 
        coins_data: List[Dict], 
        binance_service: Optional[BinanceIngestionService] = None,
        create_symbols: bool = True
    ):
        """Save market metrics to database, using Binance ticker for price and volume_24h data
        
        Args:
            create_symbols: If True, creates new symbols if they don't exist.
                           If False, only updates existing symbols (skips new ones).
        """
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
                    
                    # Get symbol_id - create if allowed, otherwise only get existing
                    if create_symbols:
                        symbol_id = self.get_or_create_symbol_id(db, symbol, image_path=image_path)
                        if not symbol_id:
                            logger.warning(f"Could not get/create symbol_id for {symbol}")
                            skipped_count += 1
                            continue
                    else:
                        # Only update existing symbols, skip new ones
                        symbol_id = self.get_symbol_id(db, symbol)
                        if not symbol_id:
                            skipped_count += 1
                            continue  # Skip symbols that don't exist
                    
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
                    
                    # Publish marketcap_update event for real-time market cap and volume updates
                    # Note: Price is excluded - it comes from real-time Binance ticker streams
                    # Only market_cap and volume_24h are updated from periodic CoinGecko updates
                    try:
                        publish_event("marketcap_update", {
                            "symbol": symbol,
                            "marketcap": float(market_cap) if market_cap else None,
                            "volume_24h": float(volume_24h) if volume_24h else None,
                            # Price is NOT included - comes from real-time Binance WebSocket ticker streams
                            "timestamp": current_timestamp.isoformat()
                        })
                    except Exception as e:
                        logger.debug(f"Failed to publish marketcap_update event for {symbol}: {e}")
                    
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
    
    async def _fetch_market_data_by_symbols_impl(self, symbols: List[str]) -> List[Dict]:
        """Internal implementation of fetch_market_data_by_symbols"""
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
            
            async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as response:
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
                    response.raise_for_status()
                    break
        
        return all_coins
    
    async def fetch_market_data_by_symbols(self, symbols: List[str]) -> List[Dict]:
        """Fetch market data from CoinGecko for specific symbols with circuit breaker protection"""
        try:
            return await self.circuit_breaker.call(self._fetch_market_data_by_symbols_impl, symbols)
        except Exception as e:
            logger.error(f"Error fetching market data by symbols: {e}")
            return []
    
    async def update_market_data_for_symbols(self, symbols: List[str], binance_service: Optional[BinanceIngestionService] = None):
        """Update market data (price, market_cap, volume_24h) for existing symbols only"""
        logger.info(f"Updating market data for {len(symbols)} existing symbols")
        
        # Fetch market data from CoinGecko
        coins_data = await self.fetch_market_data_by_symbols(symbols)
        if not coins_data:
            logger.warning("No market data fetched from CoinGecko")
            return
        
        # Update database (create_symbols=False means only update existing symbols)
        with DatabaseManager() as db:
            await self.save_market_metrics(
                db, 
                coins_data, 
                binance_service=binance_service,
                create_symbols=False  # Only update existing symbols, don't create new ones
            )
            logger.info(f"Successfully updated market data for {len(coins_data)} symbols")
    
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
        with DatabaseManager() as db:
            await self.save_market_metrics(db, coins_data, binance_service=binance_service)

