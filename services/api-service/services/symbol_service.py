"""
Service for symbol business logic
"""
from typing import List, Dict, Optional
from repositories.symbol_repository import SymbolRepository
from exceptions import NotFoundError
from shared.redis_client import cache_get, cache_set
import json


class SymbolService:
    """Service for symbol operations"""
    
    def __init__(self, symbol_repo: SymbolRepository):
        self.symbol_repo = symbol_repo
    
    def get_symbols_with_prices(self) -> List[Dict]:
        """Get all symbols with prices (cached)"""
        cache_key = "symbols:prices"
        cached = cache_get(cache_key)
        if cached:
            return json.loads(cached)
        
        symbols = self.symbol_repo.find_all_with_prices()
        
        # Cache for 30 seconds
        cache_set(cache_key, json.dumps(symbols), ttl=30)
        return symbols
    
    def get_symbol_details(self, symbol: str) -> Dict:
        """Get symbol details"""
        details = self.symbol_repo.find_by_symbol(symbol)
        if not details:
            raise NotFoundError(f"Symbol {symbol} not found")
        return details

