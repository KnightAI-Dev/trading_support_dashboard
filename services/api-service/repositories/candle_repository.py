"""
Repository for OHLCV candles
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from .base_repository import BaseRepository


class CandleRepository(BaseRepository):
    """Repository for OHLCV candle data access"""
    
    def find_latest(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        before: Optional[str] = None
    ) -> List[Dict]:
        """Find latest candles for symbol/timeframe"""
        base_query = """
            SELECT 
                oc.id,
                s.symbol_name as symbol,
                t.tf_name as timeframe,
                oc.timestamp,
                oc.open,
                oc.high,
                oc.low,
                oc.close,
                oc.volume
            FROM ohlcv_candles oc
            INNER JOIN symbols s ON oc.symbol_id = s.symbol_id
            INNER JOIN timeframe t ON oc.timeframe_id = t.timeframe_id
            WHERE s.symbol_name = :symbol
            AND t.tf_name = :timeframe
        """
        
        params = {"symbol": symbol, "timeframe": timeframe, "limit": limit}
        
        if before:
            base_query += " AND oc.timestamp < :before"
            params["before"] = before
        
        base_query += " ORDER BY oc.timestamp DESC LIMIT :limit"
        
        rows = self.execute_query(base_query, params)
        return [self._row_to_dict(row) for row in rows]
    
    def get_market_metadata(self) -> Dict[str, List[str]]:
        """Get available symbols and timeframes"""
        query = """
            SELECT DISTINCT 
                s.symbol_name,
                t.tf_name
            FROM ohlcv_candles oc
            INNER JOIN symbols s ON oc.symbol_id = s.symbol_id
            INNER JOIN timeframe t ON oc.timeframe_id = t.timeframe_id
            WHERE s.is_active = TRUE
            AND s.removed_at IS NULL
            ORDER BY s.symbol_name, t.tf_name
        """
        
        rows = self.execute_query(query)
        
        if not rows:
            return {
                "symbols": [],
                "timeframes": [],
                "symbol_timeframes": {},
            }
        
        from collections import defaultdict
        symbol_timeframes = defaultdict(set)
        for row in rows:
            symbol_name, tf_name = row[0], row[1]
            if symbol_name and tf_name:
                symbol_timeframes[symbol_name].add(tf_name)
        
        symbols = sorted(symbol_timeframes.keys())
        all_timeframes = sorted({tf for tfs in symbol_timeframes.values() for tf in tfs})
        
        return {
            "symbols": symbols,
            "timeframes": all_timeframes,
            "symbol_timeframes": {
                symbol: sorted(list(timeframes))
                for symbol, timeframes in symbol_timeframes.items()
            },
        }
    
    @staticmethod
    def _row_to_dict(row) -> Dict:
        """Convert database row to dictionary"""
        return {
            "id": row[0],
            "symbol": row[1],
            "timeframe": row[2],
            "timestamp": row[3].isoformat() if hasattr(row[3], 'isoformat') else str(row[3]),
            "open": float(row[4]),
            "high": float(row[5]),
            "low": float(row[6]),
            "close": float(row[7]),
            "volume": float(row[8])
        }

