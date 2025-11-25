"""
Base repository with common functionality
"""
from typing import TypeVar, Generic, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text

T = TypeVar('T')


class BaseRepository(Generic[T]):
    """Base repository with common query patterns"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def execute_query(self, query: str, params: Optional[dict] = None) -> list:
        """Execute raw SQL query and return results"""
        result = self.db.execute(text(query), params or {})
        return result.fetchall()
    
    def execute_scalar(self, query: str, params: Optional[dict] = None):
        """Execute query and return single scalar value"""
        result = self.db.execute(text(query), params or {})
        row = result.fetchone()
        return row[0] if row else None

