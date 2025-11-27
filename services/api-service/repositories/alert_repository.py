"""
Repository for strategy alerts
"""
from typing import List, Optional, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from .base_repository import BaseRepository


class AlertRepository(BaseRepository):
    """Repository for strategy alert data access"""
    
    def find_all(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Find alerts with optional filters"""
        # Use CTE with window function to limit each symbol to max 50 signals
        base_query = """
            WITH ranked_alerts AS (
                SELECT 
                    sa.id,
                    s.symbol_name as symbol,
                    t.tf_name as timeframe,
                    sa.timestamp,
                    sa.entry_price,
                    sa.stop_loss,
                    sa.take_profit_1,
                    sa.take_profit_2,
                    sa.take_profit_3,
                    sa.risk_score,
                    sa.swing_low_price,
                    sa.swing_low_timestamp,
                    sa.swing_high_price,
                    sa.swing_high_timestamp,
                    sa.direction,
                    sa.created_at,
                    ROW_NUMBER() OVER (PARTITION BY s.symbol_name ORDER BY sa.created_at DESC) as rn
                FROM strategy_alerts sa
                INNER JOIN symbols s ON sa.symbol_id = s.symbol_id
                INNER JOIN timeframe t ON sa.timeframe_id = t.timeframe_id
                WHERE s.is_active = TRUE AND s.removed_at IS NULL
        """
        
        params = {}
        
        if symbol:
            base_query += " AND s.symbol_name = :symbol"
            params["symbol"] = symbol
        
        if timeframe:
            base_query += " AND t.tf_name = :timeframe"
            params["timeframe"] = timeframe
        
        if direction:
            base_query += " AND sa.direction = :direction"
            params["direction"] = direction
        
        # Filter to max 50 per symbol, then apply overall limit
        base_query += """
            )
            SELECT 
                id, symbol, timeframe, timestamp, entry_price, stop_loss,
                take_profit_1, take_profit_2, take_profit_3, risk_score,
                swing_low_price, swing_low_timestamp, swing_high_price,
                swing_high_timestamp, direction, created_at
            FROM ranked_alerts
            WHERE rn <= 50
            ORDER BY created_at DESC
            LIMIT :limit
        """
        params["limit"] = limit
        
        rows = self.execute_query(base_query, params)
        return [self._row_to_dict(row) for row in rows]
    
    def find_latest(self, symbol: str, timeframe: Optional[str] = None) -> Optional[Dict]:
        """Find latest alert for a symbol"""
        base_query = """
            SELECT 
                sa.id,
                s.symbol_name as symbol,
                t.tf_name as timeframe,
                sa.timestamp,
                sa.entry_price,
                sa.stop_loss,
                sa.take_profit_1,
                sa.take_profit_2,
                sa.take_profit_3,
                sa.risk_score,
                sa.swing_low_price,
                sa.swing_low_timestamp,
                sa.swing_high_price,
                sa.swing_high_timestamp,
                sa.direction,
                sa.created_at
            FROM strategy_alerts sa
            INNER JOIN symbols s ON sa.symbol_id = s.symbol_id
            INNER JOIN timeframe t ON sa.timeframe_id = t.timeframe_id
            WHERE s.symbol_name = :symbol
            AND s.is_active = TRUE AND s.removed_at IS NULL
        """
        
        params = {"symbol": symbol}
        
        if timeframe:
            base_query += " AND t.tf_name = :timeframe"
            params["timeframe"] = timeframe
        
        base_query += " ORDER BY sa.timestamp DESC LIMIT 1"
        
        rows = self.execute_query(base_query, params)
        if not rows:
            return None
        return self._row_to_dict(rows[0])
    
    def find_summary(self, limit: int = 1000) -> List[Dict]:
        """Find latest alert for each symbol/timeframe combination"""
        # Use window function for efficiency
        query = """
            WITH ranked_alerts AS (
                SELECT 
                    sa.id,
                    s.symbol_name as symbol,
                    t.tf_name as timeframe,
                    sa.timestamp,
                    sa.entry_price,
                    sa.stop_loss,
                    sa.take_profit_1,
                    sa.take_profit_2,
                    sa.take_profit_3,
                    sa.risk_score,
                    sa.swing_low_price,
                    sa.swing_low_timestamp,
                    sa.swing_high_price,
                    sa.swing_high_timestamp,
                    sa.direction,
                    sa.created_at,
                    ROW_NUMBER() OVER (PARTITION BY s.symbol_name, t.tf_name ORDER BY sa.timestamp DESC) as rn
                FROM strategy_alerts sa
                INNER JOIN symbols s ON sa.symbol_id = s.symbol_id
                INNER JOIN timeframe t ON sa.timeframe_id = t.timeframe_id
                WHERE s.is_active = TRUE AND s.removed_at IS NULL
            )
            SELECT * FROM ranked_alerts WHERE rn = 1
            ORDER BY timestamp DESC
            LIMIT :limit
        """
        
        rows = self.execute_query(query, {"limit": limit})
        return [self._row_to_dict(row) for row in rows]
    
    @staticmethod
    def _row_to_dict(row) -> Dict:
        """Convert database row to dictionary"""
        return {
            "id": row[0],
            "symbol": row[1],
            "timeframe": row[2],
            "timestamp": row[3].isoformat() if hasattr(row[3], 'isoformat') else str(row[3]),
            "entry_price": float(row[4]),
            "stop_loss": float(row[5]),
            "take_profit_1": float(row[6]),
            "take_profit_2": float(row[7]) if row[7] is not None else None,
            "take_profit_3": float(row[8]) if row[8] is not None else None,
            "risk_score": row[9],
            "swing_low_price": float(row[10]),
            "swing_low_timestamp": row[11].isoformat() if hasattr(row[11], 'isoformat') else str(row[11]),
            "swing_high_price": float(row[12]),
            "swing_high_timestamp": row[13].isoformat() if hasattr(row[13], 'isoformat') else str(row[13]),
            "direction": row[14],
            "created_at": row[15].isoformat() if hasattr(row[15], 'isoformat') else str(row[15]),
        }

