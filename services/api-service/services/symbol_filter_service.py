"""
Service for symbol filter business logic
"""
from typing import List, Dict, Optional
from repositories.symbol_filter_repository import SymbolFilterRepository
from exceptions import NotFoundError, ValidationError


class SymbolFilterService:
    """Service for symbol filter operations"""
    
    def __init__(self, filter_repo: SymbolFilterRepository):
        self.filter_repo = filter_repo
    
    def get_filters(self, filter_type: Optional[str] = None) -> List[Dict]:
        """Get all symbol filters"""
        try:
            return self.filter_repo.find_all(filter_type)
        except ValueError as e:
            raise ValidationError(str(e)) from e
    
    def get_filter_by_symbol(self, symbol: str) -> Dict:
        """Get filter status for a symbol"""
        symbol_normalized = symbol.lstrip("@").upper().strip()
        if not symbol_normalized:
            raise ValidationError("Invalid symbol")
        
        filter_data = self.filter_repo.find_by_symbol(symbol_normalized)
        if filter_data:
            return {
                "symbol": symbol_normalized,
                "is_whitelisted": filter_data["filter_type"] == "whitelist",
                "is_blacklisted": filter_data["filter_type"] == "blacklist",
                "filter_type": filter_data["filter_type"]
            }
        else:
            return {
                "symbol": symbol_normalized,
                "is_whitelisted": False,
                "is_blacklisted": False,
                "filter_type": None
            }
    
    def add_filter(self, symbol: str, filter_type: str) -> Dict:
        """Add symbol to whitelist or blacklist"""
        symbol_normalized = symbol.lstrip("@").upper().strip()
        if not symbol_normalized:
            raise ValidationError("Invalid symbol")
        
        try:
            return self.filter_repo.add_filter(symbol_normalized, filter_type)
        except ValueError as e:
            raise ValidationError(str(e)) from e
    
    def remove_filter(self, symbol: str) -> bool:
        """Remove symbol from all filters"""
        symbol_normalized = symbol.lstrip("@").upper().strip()
        if not symbol_normalized:
            raise ValidationError("Invalid symbol")
        
        deleted_count = self.filter_repo.remove_filter(symbol_normalized)
        if deleted_count == 0:
            raise NotFoundError(f"Symbol {symbol_normalized} not found in filters")
        return True

