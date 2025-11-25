"""
Repository for symbol filter data
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from .base_repository import BaseRepository


class SymbolFilterRepository(BaseRepository):
    """Repository for symbol filter data access"""
    
    def find_all(self, filter_type: Optional[str] = None) -> List[Dict]:
        """Find all symbol filters, optionally filtered by type"""
        if filter_type:
            if filter_type not in ('whitelist', 'blacklist'):
                raise ValueError("filter_type must be 'whitelist' or 'blacklist'")
            
            query = """
                SELECT symbol, filter_type, created_at, updated_at
                FROM symbol_filters
                WHERE filter_type = :filter_type
                ORDER BY symbol
            """
            rows = self.execute_query(query, {"filter_type": filter_type})
        else:
            query = """
                SELECT symbol, filter_type, created_at, updated_at
                FROM symbol_filters
                ORDER BY filter_type, symbol
            """
            rows = self.execute_query(query)
        
        return [self._row_to_dict(row) for row in rows]
    
    def find_by_symbol(self, symbol: str) -> Optional[Dict]:
        """Find filter for a specific symbol"""
        query = """
            SELECT symbol, filter_type, created_at, updated_at
            FROM symbol_filters
            WHERE symbol = :symbol
        """
        rows = self.execute_query(query, {"symbol": symbol})
        if not rows:
            return None
        return self._row_to_dict(rows[0])
    
    def add_filter(self, symbol: str, filter_type: str) -> Dict:
        """Add or update a symbol filter"""
        if filter_type not in ('whitelist', 'blacklist'):
            raise ValueError("filter_type must be 'whitelist' or 'blacklist'")
        
        # Remove from opposite filter type
        self.db.execute(
            text("""
                DELETE FROM symbol_filters
                WHERE symbol = :symbol AND filter_type != :filter_type
            """),
            {"symbol": symbol, "filter_type": filter_type}
        )
        
        # Insert or update
        query = text("""
            INSERT INTO symbol_filters (symbol, filter_type, updated_at)
            VALUES (:symbol, :filter_type, NOW())
            ON CONFLICT (symbol, filter_type) 
            DO UPDATE SET updated_at = NOW()
            RETURNING symbol, filter_type, created_at, updated_at
        """)
        
        result = self.db.execute(query, {
            "symbol": symbol,
            "filter_type": filter_type
        }).fetchone()
        
        self.db.commit()
        return self._row_to_dict(result)
    
    def remove_filter(self, symbol: str) -> int:
        """Remove symbol from all filters, returns count of deleted rows"""
        query = text("""
            DELETE FROM symbol_filters
            WHERE symbol = :symbol
        """)
        result = self.db.execute(query, {"symbol": symbol})
        self.db.commit()
        return result.rowcount
    
    @staticmethod
    def _row_to_dict(row) -> Dict:
        """Convert database row to dictionary"""
        return {
            "symbol": row[0],
            "filter_type": row[1],
            "created_at": row[2],
            "updated_at": row[3]
        }

