"""
Service for candle business logic
"""
from typing import List, Dict, Optional
from repositories.candle_repository import CandleRepository
from exceptions import ValidationError
from shared.redis_client import cache_get, cache_set
import json
import os


class CandleService:
    """Service for candle operations"""
    
    def __init__(self, candle_repo: CandleRepository):
        self.candle_repo = candle_repo
        self.default_symbols = [
            s.strip() for s in os.getenv("DEFAULT_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")
            if s.strip()
        ]
        self.default_timeframes = [
            tf.strip() for tf in os.getenv("DEFAULT_TIMEFRAMES", "1m,5m,15m,1h,4h").split(",")
            if tf.strip()
        ]
    
    def get_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        before: Optional[str] = None
    ) -> List[Dict]:
        """Get candles for symbol/timeframe"""
        return self.candle_repo.find_latest(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            before=before
        )
    
    def get_market_metadata(self) -> Dict[str, List[str]]:
        """Get market metadata with caching"""
        cache_key = "market:metadata"
        cached = cache_get(cache_key)
        if cached:
            return json.loads(cached)
        
        metadata = self.candle_repo.get_market_metadata()
        
        # Fallback to defaults if empty
        if not metadata.get("symbols"):
            metadata = {
                "symbols": self.default_symbols,
                "timeframes": self.default_timeframes,
                "symbol_timeframes": {
                    symbol: self.default_timeframes
                    for symbol in self.default_symbols
                },
            }
        
        # Cache for 5 minutes
        cache_set(cache_key, json.dumps(metadata), ttl=300)
        return metadata

