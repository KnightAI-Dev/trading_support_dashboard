"""
CoinGecko ingestion service for fetching market data from CoinGecko API
"""
import sys
import os
import asyncio
import json
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set
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
from config.settings import COINGECKO_API_URL, COINGECKO_MIN_MARKET_CAP, COINGECKO_MIN_VOLUME_24H
from database.repository import (
    get_or_create_symbol_record, 
    get_ingestion_config_value, 
    split_symbol_components,
    should_ingest_symbol,
    normalize_symbol
)
from services.binance_service import BinanceIngestionService

logger = structlog.get_logger(__name__)

# Path to local mapping file
MAPPING_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'ticker_to_coingecko_mapping.json')
# Path to local blacklist file
BLACKLIST_FILE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'coingecko_blacklist.json')

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
        self._mapping_cache: Optional[Dict[str, str]] = None
        self._blacklist_cache: Optional[Set[str]] = None
    
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
        """Save market metrics to database using CoinGecko data
        
        Args:
            create_symbols: If True, creates new symbols if they don't exist.
                           If False, only updates existing symbols (skips new ones).
        """
        try:
            saved_count = 0
            skipped_count = 0
            current_timestamp = datetime.now()
            
            for coin in coins_data:
                try:
                    # Use Binance symbol if available (from new ingestion flow), otherwise map from coin data
                    symbol = coin.get("_binance_symbol")
                    if not symbol:
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
                    volume_24h = coin.get("total_volume")
                    circulating_supply = coin.get("circulating_supply")
                    price = coin.get("current_price")
                    
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
                    try:
                        publish_event("marketcap_update", {
                            "symbol": symbol,
                            "marketcap": float(market_cap) if market_cap else None,
                            "volume_24h": float(volume_24h) if volume_24h else None,
                            "timestamp": current_timestamp.isoformat()
                        })
                    except Exception as e:
                        logger.debug(f"Failed to publish marketcap_update event for {symbol}: {e}")
                    
                except Exception as e:
                    logger.error(f"Error saving market data for {coin.get('id', 'unknown')}: {e}")
                    skipped_count += 1
                    continue
            
            # Commit at service boundary (single commit for all symbols)
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
    
    async def _fetch_market_data_by_coin_ids_impl(self, coin_ids: List[str]) -> List[Dict]:
        """Internal implementation of fetch_market_data_by_coin_ids"""
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
            
            async with COINGECKO_RATE_LIMIT:
                async with COINGECKO_MINUTE_LIMIT:
                    async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=60)) as response:
                        if response.status == 200:
                            data = await response.json()
                            all_coins.extend(data)
                            logger.info(f"Fetched market data for {len(data)} coins by IDs")
                        else:
                            logger.error(f"Failed to fetch CoinGecko data: {response.status}")
                            if response.status == 429:
                                logger.warning("Rate limited by CoinGecko, waiting 60 seconds...")
                                await asyncio.sleep(60)
                                continue
                            response.raise_for_status()
                            break
        
        return all_coins
    
    async def fetch_market_data_by_coin_ids(self, coin_ids: List[str]) -> List[Dict]:
        """Fetch market data from CoinGecko for specific coin IDs with circuit breaker protection"""
        try:
            return await self.circuit_breaker.call(self._fetch_market_data_by_coin_ids_impl, coin_ids)
        except Exception as e:
            logger.error(f"Error fetching market data by coin IDs: {e}")
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
    
    def extract_base_asset(self, symbol: str) -> Optional[str]:
        """Extract base asset from Binance symbol (e.g., BTC from BTCUSDT)"""
        if symbol.endswith("USDT"):
            return symbol[:-4]
        return None
    
    def normalize_base_asset(self, base_asset: str) -> str:
        """Normalize base asset by removing common multiplier prefixes.
        
        Binance often uses multiplier prefixes (1000, 100, 10) for tokens with small unit prices.
        This function removes these prefixes to match with CoinGecko ticker symbols.
        
        Examples:
            "1000PEPE" -> "PEPE"
            "100SHIB" -> "SHIB"
            "10LUNC" -> "LUNC"
            "BTC" -> "BTC" (no change)
        
        Args:
            base_asset: Base asset string, may contain multiplier prefix
            
        Returns:
            Normalized base asset without multiplier prefix
        """
        base_upper = base_asset.upper()
        
        # Common multiplier prefixes used by Binance
        multipliers = ["1000000", "1000",  "10"]
        
        for multiplier in multipliers:
            if base_upper.startswith(multiplier):
                # Check if the rest is a valid ticker (at least 2 chars)
                remaining = base_upper[len(multiplier):]
                if len(remaining) >= 2:
                    return remaining
        
        return base_upper
    
    def load_ticker_mapping(self) -> Dict[str, str]:
        """Load ticker to CoinGecko coin ID mapping from local file"""
        if self._mapping_cache is not None:
            return self._mapping_cache
        
        try:
            if os.path.exists(MAPPING_FILE_PATH):
                with open(MAPPING_FILE_PATH, 'r') as f:
                    data = json.load(f)
                    self._mapping_cache = data.get("mappings", {})
                    return self._mapping_cache
            else:
                # Create empty mapping file if it doesn't exist
                os.makedirs(os.path.dirname(MAPPING_FILE_PATH), exist_ok=True)
                with open(MAPPING_FILE_PATH, 'w') as f:
                    json.dump({"mappings": {}}, f, indent=2)
                self._mapping_cache = {}
                return {}
        except Exception as e:
            logger.error(f"Error loading ticker mapping: {e}")
            self._mapping_cache = {}
            return {}
    
    def save_ticker_mapping(self, ticker: str, coin_id: str):
        """Save ticker to CoinGecko coin ID mapping to local file"""
        try:
            mapping = self.load_ticker_mapping()
            mapping[ticker.upper()] = coin_id
            self._mapping_cache = mapping
            
            os.makedirs(os.path.dirname(MAPPING_FILE_PATH), exist_ok=True)
            with open(MAPPING_FILE_PATH, 'w') as f:
                json.dump({"mappings": mapping}, f, indent=2)
            
            logger.info(f"Updated mapping: {ticker.upper()} -> {coin_id}")
        except Exception as e:
            logger.error(f"Error saving ticker mapping: {e}")
    
    def load_blacklist(self) -> Set[str]:
        """Load blacklist from local file
        
        Returns:
            Set of blacklisted coin IDs (all lowercase)
        """
        if self._blacklist_cache is not None:
            return self._blacklist_cache
        
        try:
            if os.path.exists(BLACKLIST_FILE_PATH):
                with open(BLACKLIST_FILE_PATH, 'r') as f:
                    data = json.load(f)
                    # Support both old format (list) and new format (dict with "blacklist" key)
                    if isinstance(data, list):
                        blacklist = set(item.lower() for item in data)
                    elif isinstance(data, dict) and "blacklist" in data:
                        blacklist = set(item.lower() for item in data["blacklist"])
                    else:
                        blacklist = set()
                    self._blacklist_cache = blacklist
                    return blacklist
            else:
                # Create empty blacklist file if it doesn't exist
                os.makedirs(os.path.dirname(BLACKLIST_FILE_PATH), exist_ok=True)
                with open(BLACKLIST_FILE_PATH, 'w') as f:
                    json.dump({"blacklist": []}, f, indent=2)
                self._blacklist_cache = set()
                return set()
        except Exception as e:
            logger.error(f"Error loading blacklist: {e}")
            self._blacklist_cache = set()
            return set()
    
    def is_blacklisted(self, coin_id: Optional[str] = None, coin_data: Optional[Dict] = None) -> bool:
        """Check if a coin is blacklisted
        
        Args:
            coin_id: CoinGecko coin ID (e.g., "wrapped-solana")
            coin_data: CoinGecko coin data dict (will extract id)
        
        Returns:
            True if the coin is blacklisted
        """
        blacklist = self.load_blacklist()
        if not blacklist:
            return False
        
        # Get coin ID from coin_data if provided
        if coin_data and not coin_id:
            coin_id = coin_data.get("id")
        
        if coin_id:
            return coin_id.lower() in blacklist
        
        return False
    
    async def _search_coin_by_ticker_impl(self, ticker: str) -> Optional[Dict]:
        """Search for coin by ticker using CoinGecko search endpoint"""
        url = f"{self.base_url}/search"
        params = {"query": ticker}
        
        try:
            async with COINGECKO_RATE_LIMIT:
                async with COINGECKO_MINUTE_LIMIT:
                    async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            data = await response.json()
                            coins = data.get("coins", [])
                            
                            # Try to find exact match by ticker (case-insensitive)
                            ticker_upper = ticker.upper()
                            for coin in coins:
                                if coin.get("symbol", "").upper() == ticker_upper:
                                    return coin
                            
                            # If no exact match, return first result if available
                            if coins:
                                return coins[0]
                            
                            return None
                        elif response.status == 429:
                            logger.warning("Rate limited by CoinGecko search, waiting 60 seconds...")
                            await asyncio.sleep(60)
                            return None
                        else:
                            logger.debug(f"CoinGecko search failed for {ticker}: {response.status}")
                            return None
        except Exception as e:
            logger.debug(f"Error searching CoinGecko for {ticker}: {e}")
            return None
    
    async def search_coin_by_ticker(self, ticker: str) -> Optional[Dict]:
        """Search for coin by ticker with circuit breaker protection"""
        try:
            return await self.circuit_breaker.call(self._search_coin_by_ticker_impl, ticker)
        except Exception as e:
            logger.debug(f"Error searching coin by ticker {ticker}: {e}")
            return None
    
    async def _fetch_coin_by_id_impl(self, coin_id: str) -> Optional[Dict]:
        """Fetch coin market data by CoinGecko ID"""
        url = f"{self.base_url}/coins/markets"
        params = {
            "vs_currency": "usd",
            "ids": coin_id,
            "sparkline": "false"
        }
        
        try:
            async with COINGECKO_RATE_LIMIT:
                async with COINGECKO_MINUTE_LIMIT:
                    async with self.session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            data = await response.json()
                            if data and len(data) > 0:
                                return data[0]
                            return None
                        elif response.status == 429:
                            logger.warning("Rate limited by CoinGecko, waiting 60 seconds...")
                            await asyncio.sleep(60)
                            return None
                        else:
                            logger.debug(f"CoinGecko fetch failed for {coin_id}: {response.status}")
                            return None
        except Exception as e:
            logger.debug(f"Error fetching coin by ID {coin_id}: {e}")
            return None
    
    async def fetch_coin_by_id(self, coin_id: str) -> Optional[Dict]:
        """Fetch coin market data by CoinGecko ID with circuit breaker protection"""
        try:
            return await self.circuit_breaker.call(self._fetch_coin_by_id_impl, coin_id)
        except Exception as e:
            logger.debug(f"Error fetching coin by ID {coin_id}: {e}")
            return None
    
    async def enrich_asset_with_coingecko(self, ticker: str) -> Optional[Dict]:
        """Enrich asset with CoinGecko data using multiple strategies:
        1. Use local mapping file (most reliable, already confirmed)
        2. Use CoinGecko search endpoint (comprehensive search)
        3. Try direct match by ticker (fallback, rarely works)
        4. If new mapping is confirmed from search, update mapping file
        """
        ticker_upper = ticker.upper()
        
        # Strategy 1: Use local mapping file (most reliable)
        mapping = self.load_ticker_mapping()
        coin_id_from_mapping = mapping.get(ticker_upper)
        if coin_id_from_mapping:
            coin_data = await self.fetch_coin_by_id(coin_id_from_mapping)
            if coin_data:
                # Verify the symbol matches
                if coin_data.get("symbol", "").upper() == ticker_upper:
                    logger.debug(f"Mapping match found for {ticker}: {coin_id_from_mapping}")
                    return coin_data
        
        # Strategy 2: Use CoinGecko search endpoint
        search_result = await self.search_coin_by_ticker(ticker)
        if search_result:
            # Fetch full market data using the coin ID from search
            coin_id_from_search = search_result.get("id")
            if coin_id_from_search:
                coin_data = await self.fetch_coin_by_id(coin_id_from_search)
                if coin_data:
                    # Verify the symbol matches
                    if coin_data.get("symbol", "").upper() == ticker_upper:
                        logger.debug(f"Search match found for {ticker}: {coin_id_from_search}")
                        # Update mapping file with confirmed mapping
                        self.save_ticker_mapping(ticker, coin_id_from_search)
                        return coin_data
        
        # Strategy 3: Try direct match by ticker (coin ID is usually lowercase ticker, rarely works)
        coin_id_direct = ticker_upper.lower()
        coin_data = await self.fetch_coin_by_id(coin_id_direct)
        if coin_data:
            # Verify the symbol matches
            if coin_data.get("symbol", "").upper() == ticker_upper:
                logger.debug(f"Direct match found for {ticker}: {coin_id_direct}")
                # Update mapping file with confirmed mapping
                self.save_ticker_mapping(ticker, coin_id_direct)
                return coin_data
        
        logger.debug(f"No CoinGecko data found for {ticker}")
        return None
    
    async def ingest_from_binance_perpetuals(
        self, 
        binance_service: BinanceIngestionService,
        min_binance_volume: Optional[float] = None,
        min_market_cap: Optional[float] = None
    ) -> List[Dict]:
        logger.info("Starting new ingestion flow: Binance perpetuals -> CoinGecko enrichment")
        
        # Get filter thresholds and limits from database if not provided
        with DatabaseManager() as db:
            if min_binance_volume is None:
                db_value = get_ingestion_config_value(
                    db, 
                    "limit_volume_up", 
                    default_value=COINGECKO_MIN_VOLUME_24H
                )
                min_binance_volume = db_value if db_value is not None else COINGECKO_MIN_VOLUME_24H
                logger.info(f"Loaded min_binance_volume from ingestion_config: {min_binance_volume}")
            
            if min_market_cap is None:
                db_value = get_ingestion_config_value(
                    db,
                    "limit_market_cap",
                    default_value=COINGECKO_MIN_MARKET_CAP
                )
                min_market_cap = db_value if db_value is not None else COINGECKO_MIN_MARKET_CAP
                logger.info(f"Loaded min_market_cap from ingestion_config: {min_market_cap}")
            
            # Get CoinGecko limit from database
            db_value = get_ingestion_config_value(
                db,
                "coingecko_limit",
                default_value=250.0
            )
            coingecko_limit = int(db_value) if db_value is not None else 250
            logger.info(f"Loaded coingecko_limit from ingestion_config: {coingecko_limit}")
        
        # Step 1: Fetch Binance USDT perpetual futures
        perpetual_symbols = await binance_service.get_available_perpetual_symbols()
        if not perpetual_symbols:
            logger.warning("No Binance perpetual symbols found")
            return []
        
        # Filter to only USDT pairs
        usdt_symbols = [s for s in perpetual_symbols if s.endswith("USDT")]
        logger.info(f"Found {len(usdt_symbols)} USDT perpetual symbols on Binance")
        
        # Save usdt_symbols to symbols table
        if usdt_symbols:
            with DatabaseManager() as db:
                try:
                    insert_sql = text("""
                        INSERT INTO symbols (symbol_name, base_asset, quote_asset, is_active, removed_at)
                        VALUES (:symbol_name, :base_asset, :quote_asset, FALSE, NOW())
                        ON CONFLICT (symbol_name) 
                        DO NOTHING
                    """)
                    
                    inserted_count = 0
                    for symbol in usdt_symbols:
                        try:
                            # Extract base and quote assets using repository function
                            base_asset, quote_asset = split_symbol_components(symbol)
                            
                            db.execute(insert_sql, {
                                "symbol_name": symbol,
                                "base_asset": base_asset,
                                "quote_asset": quote_asset
                            })
                            inserted_count += 1
                        except Exception as e:
                            logger.error(f"Error inserting symbol {symbol}: {e}")
                            continue
                    
                    db.commit()
                    logger.info(f"Saved {inserted_count} symbols to symbols table")
                except Exception as e:
                    logger.error(f"Error saving symbols to database: {e}")
                    db.rollback()
        
        # Step 2: Fetch Binance ticker data for volume filtering
        binance_tickers = await binance_service.fetch_all_tickers_24h()
        logger.info(f"Retrieved {len(binance_tickers)} tickers from Binance")
        
        # Step 3: Combine perpetual_symbols and binance_tickers, filter by volume
        # Create a combined structure with symbols that exist in both perpetuals and tickers
        combined_symbols_data = {}
        filtered_by_volume = 0
        for symbol in usdt_symbols:
            if symbol in binance_tickers:
                ticker_data = binance_tickers[symbol]
                # Filter by min_binance_volume
                quote_volume = ticker_data.get("quoteVolume")
                if quote_volume is not None and float(quote_volume) >= min_binance_volume:
                    combined_symbols_data[symbol] = ticker_data
                else:
                    filtered_by_volume += 1
        logger.info(f"Combined {len(combined_symbols_data)} symbols with ticker data, filtered {filtered_by_volume} by min_binance_volume ({min_binance_volume})")
        
        # Step 3b: Get existing CoinGecko IDs from database and identify new symbols
        symbols_list = list(combined_symbols_data.keys())
        symbol_to_coingecko_id = {}
        new_symbols = set()
        
        if symbols_list:
            with DatabaseManager() as db:
                try:
                    # Get CoinGecko IDs for all symbols in combined_symbols_data in one query
                    query = text("""
                        SELECT binance_symbol, coingecko_id 
                        FROM binance_coingecko_matching 
                        WHERE binance_symbol = ANY(:symbols)
                    """)
                    result = db.execute(query, {"symbols": symbols_list}).fetchall()
                    symbol_to_coingecko_id = {row[0]: row[1] for row in result if row[1]}
                    
                    # Find new symbols that are not in the database
                    existing_symbols = set(symbol_to_coingecko_id.keys())
                    new_symbols = set(symbols_list) - existing_symbols
                    
                    logger.info(
                        f"Found {len(symbol_to_coingecko_id)} existing CoinGecko IDs, "
                        f"{len(new_symbols)} new symbols to process"
                    )
                except Exception as e:
                    logger.error(f"Error querying CoinGecko IDs from database: {e}")
                    new_symbols = set(symbols_list)
        
        # Step 4: Process new symbols - search CoinGecko and insert into database
        if new_symbols:
            logger.info(f"Processing {len(new_symbols)} new symbols, searching CoinGecko")
            inserted_new_count = 0
            
            insert_sql = text("""
                INSERT INTO binance_coingecko_matching 
                (binance_symbol, coingecko_id, base_asset, normalized_base, 
                 coingecko_symbol, updated_at)
                VALUES 
                (:binance_symbol, :coingecko_id, :base_asset, :normalized_base,
                 :coingecko_symbol, NOW())
                ON CONFLICT (binance_symbol) 
                DO NOTHING
            """)
            
            with DatabaseManager() as db:
                for binance_symbol in new_symbols:
                    try:
                        # Extract and normalize base asset
                        base_asset = self.extract_base_asset(binance_symbol)
                        if not base_asset:
                            continue
                        
                        normalized_base = self.normalize_base_asset(base_asset)
                        
                        # Search CoinGecko for this symbol
                        coin_data = await self.enrich_asset_with_coingecko(normalized_base)
                        if not coin_data and normalized_base != base_asset.upper():
                            coin_data = await self.enrich_asset_with_coingecko(base_asset.upper())
                        
                        if coin_data:
                            coingecko_id = coin_data.get("id", "")
                            coingecko_symbol = coin_data.get("symbol", "").upper()
                            
                            # Insert into database
                            db.execute(insert_sql, {
                                "binance_symbol": binance_symbol,
                                "coingecko_id": coingecko_id,
                                "base_asset": base_asset,
                                "normalized_base": normalized_base,
                                "coingecko_symbol": coingecko_symbol
                            })
                            
                            # Add to mapping for later use
                            symbol_to_coingecko_id[binance_symbol] = coingecko_id
                            inserted_new_count += 1
                            logger.debug(f"Found and inserted CoinGecko data for {binance_symbol}")
                    except Exception as e:
                        logger.error(f"Error processing new symbol {binance_symbol}: {e}")
                        continue
                
                db.commit()
                logger.info(f"Inserted {inserted_new_count} new symbols into database")
        
        # Step 5: Fetch market data from CoinGecko and build enriched assets
        if not symbol_to_coingecko_id:
            logger.warning("No CoinGecko IDs found, cannot fetch market data")
            return []
        
        # Fetch market data for all CoinGecko IDs
        coingecko_ids = list(symbol_to_coingecko_id.values())
        logger.info(f"Fetching market data for {len(coingecko_ids)} CoinGecko IDs")
        coingecko_market_data = await self.fetch_market_data_by_coin_ids(coingecko_ids)
        
        if not coingecko_market_data:
            logger.warning("No market data fetched from CoinGecko")
            return []
        
        # Create a mapping from coingecko_id to market data
        id_to_market_data = {coin.get("id"): coin for coin in coingecko_market_data if coin.get("id")}
        
        logger.info(
            "coingecko_market_data_fetched",
            count=len(id_to_market_data),
            requested=len(coingecko_ids),
        )

        # Build enriched assets with filters applied
        # First, load whitelist/blacklist filters from database
        whitelisted_symbols = set()
        blacklisted_symbols = set()
        
        with DatabaseManager() as db:
            from database.repository import get_symbol_filters
            filter_results = get_symbol_filters(db)
            for filter_item in filter_results:
                symbol = filter_item["symbol"]
                filter_type = filter_item["filter_type"]
                if filter_type == "whitelist":
                    whitelisted_symbols.add(symbol)
                elif filter_type == "blacklist":
                    blacklisted_symbols.add(symbol)
        
        logger.info(
            "symbol_filters_loaded_for_ingestion",
            whitelist_count=len(whitelisted_symbols),
            blacklist_count=len(blacklisted_symbols)
        )
        
        enriched_assets = []
        skipped_no_coingecko_id = 0
        skipped_market_cap_filter = 0
        skipped_blacklist = 0
        included_whitelist = 0
        
        for binance_symbol, ticker_data in combined_symbols_data.items():
            try:
                normalized_symbol = normalize_symbol(binance_symbol)
                
                # Apply whitelist/blacklist filters FIRST (before market cap/volume)
                if normalized_symbol in blacklisted_symbols:
                    skipped_blacklist += 1
                    logger.debug(f"Symbol {binance_symbol} skipped - blacklisted")
                    continue
                
                # Check if whitelisted (will skip market cap/volume checks if so)
                is_whitelisted = normalized_symbol in whitelisted_symbols
                
                coingecko_id = symbol_to_coingecko_id.get(binance_symbol)
                if not coingecko_id:
                    skipped_no_coingecko_id += 1
                    continue
                
                coin_data = id_to_market_data.get(coingecko_id)
                if not coin_data:
                    skipped_no_coingecko_id += 1
                    continue
                
                # Apply CoinGecko market cap filter (skip if whitelisted)
                if not is_whitelisted:
                    market_cap = coin_data.get("market_cap")
                    if market_cap is None or float(market_cap) < min_market_cap:
                        skipped_market_cap_filter += 1
                        continue
                else:
                    included_whitelist += 1
                    logger.debug(f"Symbol {binance_symbol} included - whitelisted (skipping market cap check)")
                
                # Build enriched asset
                coin_data_copy = coin_data.copy()
                coin_data_copy["_binance_symbol"] = binance_symbol
                coin_data_copy["_base_asset"] = coin_data.get("symbol", "").upper()
                enriched_assets.append(coin_data_copy)
                
            except Exception as e:
                logger.error(f"Error processing symbol {binance_symbol}: {e}")
                continue
        
        logger.info(
            "ingestion_completed",
            total_binance_symbols=len(usdt_symbols),
            combined_symbols=len(combined_symbols_data),
            symbols_with_coingecko_id=len(symbol_to_coingecko_id),
            enriched_count=len(enriched_assets),
            skipped_no_coingecko_id=skipped_no_coingecko_id,
            skipped_market_cap_filter=skipped_market_cap_filter,
            skipped_blacklist=skipped_blacklist,
            included_whitelist=included_whitelist
        )
        
        return enriched_assets
    
    async def ingest_from_binance_perpetuals_and_save(
        self,
        binance_service: BinanceIngestionService,
        min_binance_volume: Optional[float] = None,
        min_market_cap: Optional[float] = None
    ) -> Dict[str, List[str]]:
        """Ingest from Binance perpetuals, enrich with CoinGecko, and save to database.
        
        Returns:
            Dict containing metadata about the ingestion run, including any newly
            activated symbols that now qualify for backfilling.
        """
        logger.info("Starting new ingestion flow with database save")
        
        # Get enriched assets
        enriched_assets = await self.ingest_from_binance_perpetuals(
            binance_service=binance_service,
            min_binance_volume=min_binance_volume,
            min_market_cap=min_market_cap
        )
        
        if not enriched_assets:
            logger.warning("No enriched assets to save")
            return {"newly_activated_symbols": []}
        
        # Save to database
        with DatabaseManager() as db:
            def fetch_active_symbol_set() -> Set[str]:
                result = db.execute(
                    text("SELECT symbol_name FROM symbols WHERE is_active = TRUE")
                ).fetchall()
                cleaned = set()
                for row in result:
                    symbol_name = row[0]
                    if symbol_name:
                        cleaned.add(symbol_name.lstrip("@").upper())
                return cleaned
            
            active_symbols_before = fetch_active_symbol_set()
            
            await self.save_market_metrics(
                db,
                enriched_assets,
                binance_service=binance_service,
                create_symbols=True,
            )
            
            active_symbols_after = fetch_active_symbol_set()
            
            # Extract symbols from enriched assets for deactivation check
            enriched_symbols = {
                (asset.get("_binance_symbol") or "").lstrip("@").upper()
                for asset in enriched_assets
                if asset.get("_binance_symbol")
            }
            
            # Find symbols in database that are not in enriched assets
            symbols_to_deactivate = {
                symbol for symbol in active_symbols_after if symbol not in enriched_symbols
            }
            
            # Use SymbolLifecycleService for deactivation (proper service boundary)
            if symbols_to_deactivate:
                from core.symbol_lifecycle_service import SymbolLifecycleService
                lifecycle_service = SymbolLifecycleService()
                deactivated_count = await lifecycle_service.deactivate_symbols(
                    db, list(symbols_to_deactivate)
                )
                db.commit()
                logger.info(
                    "inactive_symbols_marked",
                    deactivated_count=deactivated_count,
                )
            else:
                logger.info("All active symbols are present in enriched assets, no deactivation needed")
        
        newly_activated_symbols = list(active_symbols_after - active_symbols_before)
        logger.info(
            "binance_ingestion_save_completed",
            saved_assets=len(enriched_assets),
            newly_activated=len(newly_activated_symbols),
            deactivated=len(symbols_to_deactivate),
        )
        return {"newly_activated_symbols": newly_activated_symbols}

