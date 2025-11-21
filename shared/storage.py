"""
Storage - Database operations and data access layer
"""
import os
from typing import List, Optional, Dict
from collections import defaultdict
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, text

from shared.database import SessionLocal
from shared.models import (
    OHLCVCandle, StrategyAlert
)
from shared.logger import setup_logger

logger = setup_logger(__name__)

DEFAULT_SYMBOLS = [
    symbol.strip()
    for symbol in os.getenv("DEFAULT_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")
    if symbol.strip()
]

DEFAULT_TIMEFRAMES = [
    tf.strip()
    for tf in os.getenv("DEFAULT_TIMEFRAMES", "1m,5m,15m,1h,4h").split(",")
    if tf.strip()
]


class StorageService:
    """Service for database operations"""
    
    def __init__(self):
        self.db: Optional[Session] = None
    
    def __enter__(self):
        self.db = SessionLocal()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.db:
            self.db.close()
    
    def get_strategy_alerts(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get strategy alerts with filters from database"""
        try:
            # Build query using raw SQL to join with symbols and timeframe tables
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
                WHERE 1=1
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
            
            base_query += " ORDER BY sa.timestamp DESC LIMIT :limit"
            params["limit"] = limit
            
            query = text(base_query)
            result = self.db.execute(query, params)
            rows = result.fetchall()
            
            # Convert to list of dictionaries
            alerts = []
            for row in rows:
                alerts.append({
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
                })
            
            return alerts
        except Exception as e:
            logger.error(f"Error getting strategy alerts: {e}")
            return []
    
    def get_latest_strategy_alert(self, symbol: str, timeframe: Optional[str] = None) -> Optional[Dict]:
        """Get latest strategy alert for a symbol from database"""
        try:
            # Query using raw SQL to join with symbols and timeframe tables
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
            """
            
            params = {"symbol": symbol}
            
            if timeframe:
                base_query += " AND t.tf_name = :timeframe"
                params["timeframe"] = timeframe
            
            base_query += " ORDER BY sa.timestamp DESC LIMIT 1"
            
            query = text(base_query)
            result = self.db.execute(query, params)
            row = result.fetchone()
            
            if not row:
                return None
            
            # Convert to dictionary
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
        except Exception as e:
            logger.error(f"Error getting latest strategy alert: {e}")
            return None
    
    def get_latest_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
        before: Optional[str] = None
    ) -> List[Dict]:
        """Get latest candles for a symbol from database, optionally before a timestamp"""
        try:
            # Query using raw SQL to join with symbols and timeframe tables
            # The database schema uses symbol_id and timeframe_id as foreign keys
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
            
            # Add before timestamp filter if provided
            if before:
                base_query += " AND oc.timestamp < :before"
                params["before"] = before
            
            base_query += " ORDER BY oc.timestamp DESC LIMIT :limit"
            
            query = text(base_query)
            
            result = self.db.execute(query, params)
            rows = result.fetchall()
            
            # Convert to list of dictionaries matching frontend interface
            candles = []
            for row in rows:
                candles.append({
                    "id": row[0],
                    "symbol": row[1],
                    "timeframe": row[2],
                    "timestamp": row[3].isoformat() if hasattr(row[3], 'isoformat') else str(row[3]),
                    "open": float(row[4]),
                    "high": float(row[5]),
                    "low": float(row[6]),
                    "close": float(row[7]),
                    "volume": float(row[8])
                })
            
            logger.debug(f"Retrieved {len(candles)} candles for {symbol} {timeframe}")
            return candles
        except Exception as e:
            logger.error(f"Error getting candles: {e}")
            return []
    

    def get_market_metadata(self) -> Dict[str, List[str]]:
        """Get available symbols and timeframes from database (ohlcv_candles table)"""
        try:
            # Query database using raw SQL to join with symbols and timeframe tables
            # The database schema uses symbol_id and timeframe_id as foreign keys
            query = """
                SELECT DISTINCT 
                    s.symbol_name,
                    t.tf_name
                FROM ohlcv_candles oc
                INNER JOIN symbols s ON oc.symbol_id = s.symbol_id
                INNER JOIN timeframe t ON oc.timeframe_id = t.timeframe_id
                ORDER BY s.symbol_name, t.tf_name
            """
            
            result = self.db.execute(text(query))
            rows = result.fetchall()

            logger.debug(f"Found {len(rows)} symbol/timeframe combinations in database")

            # If database is empty, return defaults
            if not rows:
                logger.info("No candles found in database, returning default symbols/timeframes")
                return {
                    "symbols": DEFAULT_SYMBOLS,
                    "timeframes": DEFAULT_TIMEFRAMES,
                    "symbol_timeframes": {
                        symbol: DEFAULT_TIMEFRAMES for symbol in DEFAULT_SYMBOLS
                    },
                }

            # Process database results
            symbol_timeframes = defaultdict(set)
            for row in rows:
                symbol_name = row[0]  # symbol_name from symbols table
                tf_name = row[1]      # tf_name from timeframe table
                if symbol_name and tf_name:
                    symbol_timeframes[symbol_name].add(tf_name)

            # Extract unique symbols and timeframes from database
            symbols = sorted(symbol_timeframes.keys())
            all_timeframes = sorted(
                {tf for tfs in symbol_timeframes.values() for tf in tfs}
            )

            logger.info(f"Found {len(symbols)} symbols and {len(all_timeframes)} timeframes in database")

            # Return database results (never use defaults if we have database data)
            return {
                "symbols": symbols,
                "timeframes": all_timeframes,
                "symbol_timeframes": {
                    symbol: sorted(list(timeframes))
                    for symbol, timeframes in symbol_timeframes.items()
                },
            }
        except Exception as e:
            logger.error(f"Error querying market metadata from database: {e}")
            # Only return defaults on database errors
            return {
                "symbols": DEFAULT_SYMBOLS,
                "timeframes": DEFAULT_TIMEFRAMES,
                "symbol_timeframes": {
                    symbol: DEFAULT_TIMEFRAMES for symbol in DEFAULT_SYMBOLS
                },
            }

    def get_symbols_with_prices(self) -> List[Dict]:
        """Get all symbols with latest prices and 24h change from database"""
        try:
            # Get all unique symbols from ohlcv_candles
            # For each symbol, get latest close price and close price from 24h ago
            query = text("""
                WITH latest_prices AS (
                    SELECT DISTINCT ON (s.symbol_name)
                        s.symbol_name as symbol,
                        oc.close as current_price,
                        oc.timestamp as current_timestamp
                    FROM ohlcv_candles oc
                    INNER JOIN symbols s ON oc.symbol_id = s.symbol_id
                    INNER JOIN timeframe t ON oc.timeframe_id = t.timeframe_id
                    WHERE t.tf_name = '1h'  -- Use 1h timeframe for price data
                    ORDER BY s.symbol_name, oc.timestamp DESC
                ),
                prices_24h_ago AS (
                    SELECT DISTINCT ON (s.symbol_name)
                        s.symbol_name as symbol,
                        oc.close as price_24h_ago
                    FROM ohlcv_candles oc
                    INNER JOIN symbols s ON oc.symbol_id = s.symbol_id
                    INNER JOIN timeframe t ON oc.timeframe_id = t.timeframe_id
                    WHERE t.tf_name = '1h'
                    AND oc.timestamp <= NOW() - INTERVAL '24 hours'
                    ORDER BY s.symbol_name, oc.timestamp DESC
                )
                SELECT 
                    lp.symbol,
                    s.base_asset as base,
                    s.quote_asset as quote,
                    s.image_path as image_url,
                    COALESCE(md.market_cap, 0) as marketcap,
                    COALESCE(md.volume_24h, 0) as volume_24h,
                    COALESCE(lp.current_price, 0) as price,
                    CASE 
                        WHEN p24.price_24h_ago > 0 THEN 
                            ((lp.current_price - p24.price_24h_ago) / p24.price_24h_ago) * 100
                        ELSE 0
                    END as change24h
                FROM latest_prices lp
                INNER JOIN symbols s ON lp.symbol = s.symbol_name
                LEFT JOIN prices_24h_ago p24 ON lp.symbol = p24.symbol
                LEFT JOIN LATERAL (
                    SELECT market_cap, volume_24h
                    FROM market_data md2
                    WHERE md2.symbol_id = s.symbol_id
                    ORDER BY md2.timestamp DESC
                    LIMIT 1
                ) md ON true
                ORDER BY lp.symbol
            """)
            
            result = self.db.execute(query)
            rows = result.fetchall()
            
            symbols = []
            for row in rows:
                # Parse symbol to get base and quote if not available
                symbol = row[0]
                base = row[1] if row[1] else symbol.replace("USDT", "").replace("USD", "")
                quote = row[2] if row[2] else "USDT"
                
                symbols.append({
                    "symbol": symbol,
                    "base": base,
                    "quote": quote,
                    "image_url": row[3] if row[3] else None,
                    "marketcap": float(row[4]) if row[4] else 0,
                    "volume_24h": float(row[5]) if row[5] else 0,
                    "price": float(row[6]) if row[6] else 0,
                    "change24h": float(row[7]) if row[7] is not None else 0,
                })
            
            logger.debug(f"Retrieved {len(symbols)} symbols with price data")
            return symbols
        except Exception as e:
            logger.error(f"Error getting symbols with prices: {e}")
            return []



