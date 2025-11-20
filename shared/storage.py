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
    OHLCVCandle, TradingSignal, SwingPoint,
    SupportResistance
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
    
    def save_trading_signal(self, signal_data: Dict) -> Optional[TradingSignal]:
        """Save trading signal to database"""
        try:
            signal = TradingSignal(
                symbol=signal_data["symbol"],
                timestamp=signal_data.get("timestamp", datetime.now()),
                market_score=signal_data["market_score"],
                direction=signal_data["direction"],
                price=signal_data["price"],
                entry1=signal_data.get("entry1"),
                entry2=signal_data.get("entry2"),
                sl=signal_data.get("sl"),
                tp1=signal_data.get("tp1"),
                tp2=signal_data.get("tp2"),
                tp3=signal_data.get("tp3"),
                swing_high=signal_data.get("swing_high"),
                swing_low=signal_data.get("swing_low"),
                support_level=signal_data.get("support_level"),
                resistance_level=signal_data.get("resistance_level"),
                confluence=signal_data.get("confluence"),
                risk_reward_ratio=signal_data.get("risk_reward_ratio"),
                pullback_detected=signal_data.get("pullback_detected", False),
                pullback_start_level=signal_data.get("pullback_start_level"),
                approaching_fib_level=signal_data.get("approaching_fib_level"),
                confidence_score=signal_data.get("confidence_score")
            )
            
            # Use merge to handle conflicts
            self.db.merge(signal)
            self.db.commit()
            
            logger.info(f"Saved trading signal for {signal_data['symbol']}")
            return signal
        except Exception as e:
            logger.error(f"Error saving trading signal: {e}")
            self.db.rollback()
            return None
    
    def get_latest_signal(self, symbol: str) -> Optional[Dict]:
        """Get latest trading signal for a symbol from database"""
        try:
            # Query using raw SQL to join with symbols table
            # The database schema uses symbol_id as a foreign key
            query = text("""
                SELECT 
                    ts.id,
                    s.symbol_name as symbol,
                    ts.timestamp,
                    ts.market_score,
                    ts.direction,
                    ts.price,
                    ts.entry1,
                    ts.entry2,
                    ts.sl,
                    ts.tp1,
                    ts.tp2,
                    ts.tp3,
                    ts.swing_high,
                    ts.swing_low,
                    ts.support_level,
                    ts.resistance_level,
                    ts.confluence,
                    ts.risk_reward_ratio,
                    ts.pullback_detected,
                    ts.pullback_start_level,
                    ts.approaching_fib_level,
                    ts.confidence_score
                FROM trading_signals ts
                INNER JOIN symbols s ON ts.symbol_id = s.symbol_id
                WHERE s.symbol_name = :symbol
                ORDER BY ts.timestamp DESC
                LIMIT 1
            """)
            
            result = self.db.execute(query, {"symbol": symbol})
            row = result.fetchone()
            
            if not row:
                return None
            
            # Convert to dictionary matching frontend interface
            return {
                "id": row[0],
                "symbol": row[1],
                "timestamp": row[2].isoformat() if hasattr(row[2], 'isoformat') else str(row[2]),
                "market_score": int(row[3]),
                "direction": row[4],
                "price": float(row[5]),
                "entry1": float(row[6]) if row[6] is not None else None,
                "entry2": float(row[7]) if row[7] is not None else None,
                "sl": float(row[8]) if row[8] is not None else None,
                "tp1": float(row[9]) if row[9] is not None else None,
                "tp2": float(row[10]) if row[10] is not None else None,
                "tp3": float(row[11]) if row[11] is not None else None,
                "swing_high": float(row[12]) if row[12] is not None else None,
                "swing_low": float(row[13]) if row[13] is not None else None,
                "support_level": float(row[14]) if row[14] is not None else None,
                "resistance_level": float(row[15]) if row[15] is not None else None,
                "confluence": row[16],
                "risk_reward_ratio": float(row[17]) if row[17] is not None else None,
                "pullback_detected": bool(row[18]) if row[18] is not None else False,
                "pullback_start_level": float(row[19]) if row[19] is not None else None,
                "approaching_fib_level": float(row[20]) if row[20] is not None else None,
                "confidence_score": float(row[21]) if row[21] is not None else None,
            }
        except Exception as e:
            logger.error(f"Error getting latest signal: {e}")
            return None
    
    def get_signals(
        self,
        symbol: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get trading signals with filters from database"""
        try:
            # Build query using raw SQL to join with symbols table
            base_query = """
                SELECT 
                    ts.id,
                    s.symbol_name as symbol,
                    ts.timestamp,
                    ts.market_score,
                    ts.direction,
                    ts.price,
                    ts.entry1,
                    ts.entry2,
                    ts.sl,
                    ts.tp1,
                    ts.tp2,
                    ts.tp3,
                    ts.swing_high,
                    ts.swing_low,
                    ts.support_level,
                    ts.resistance_level,
                    ts.confluence,
                    ts.risk_reward_ratio,
                    ts.pullback_detected,
                    ts.pullback_start_level,
                    ts.approaching_fib_level,
                    ts.confidence_score
                FROM trading_signals ts
                INNER JOIN symbols s ON ts.symbol_id = s.symbol_id
                WHERE 1=1
            """
            
            params = {}
            
            if symbol:
                base_query += " AND s.symbol_name = :symbol"
                params["symbol"] = symbol
            
            if direction:
                base_query += " AND ts.direction = :direction"
                params["direction"] = direction
            
            base_query += " ORDER BY ts.timestamp DESC LIMIT :limit"
            params["limit"] = limit
            
            query = text(base_query)
            result = self.db.execute(query, params)
            rows = result.fetchall()
            
            # Convert to list of dictionaries matching frontend interface
            signals = []
            for row in rows:
                signals.append({
                    "id": row[0],
                    "symbol": row[1],
                    "timestamp": row[2].isoformat() if hasattr(row[2], 'isoformat') else str(row[2]),
                    "market_score": int(row[3]),
                    "direction": row[4],
                    "price": float(row[5]),
                    "entry1": float(row[6]) if row[6] is not None else None,
                    "entry2": float(row[7]) if row[7] is not None else None,
                    "sl": float(row[8]) if row[8] is not None else None,
                    "tp1": float(row[9]) if row[9] is not None else None,
                    "tp2": float(row[10]) if row[10] is not None else None,
                    "tp3": float(row[11]) if row[11] is not None else None,
                    "swing_high": float(row[12]) if row[12] is not None else None,
                    "swing_low": float(row[13]) if row[13] is not None else None,
                    "support_level": float(row[14]) if row[14] is not None else None,
                    "resistance_level": float(row[15]) if row[15] is not None else None,
                    "confluence": row[16],
                    "risk_reward_ratio": float(row[17]) if row[17] is not None else None,
                    "pullback_detected": bool(row[18]) if row[18] is not None else False,
                    "pullback_start_level": float(row[19]) if row[19] is not None else None,
                    "approaching_fib_level": float(row[20]) if row[20] is not None else None,
                    "confidence_score": float(row[21]) if row[21] is not None else None,
                })
            
            return signals
        except Exception as e:
            logger.error(f"Error getting signals: {e}")
            return []
    
    def get_latest_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100
    ) -> List[Dict]:
        """Get latest candles for a symbol from database"""
        try:
            # Query using raw SQL to join with symbols and timeframe tables
            # The database schema uses symbol_id and timeframe_id as foreign keys
            query = text("""
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
                ORDER BY oc.timestamp DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(
                query,
                {"symbol": symbol, "timeframe": timeframe, "limit": limit}
            )
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
    
    def get_active_sr_levels(
        self,
        symbol: str,
        timeframe: str
    ) -> Dict[str, List[float]]:
        """Get active support and resistance levels"""
        try:
            support = self.db.query(SupportResistance).filter(
                and_(
                    SupportResistance.symbol == symbol,
                    SupportResistance.timeframe == timeframe,
                    SupportResistance.type == "support",
                    SupportResistance.is_active == True
                )
            ).all()
            
            resistance = self.db.query(SupportResistance).filter(
                and_(
                    SupportResistance.symbol == symbol,
                    SupportResistance.timeframe == timeframe,
                    SupportResistance.type == "resistance",
                    SupportResistance.is_active == True
                )
            ).all()
            
            return {
                "support": [float(s.level) for s in support],
                "resistance": [float(r.level) for r in resistance]
            }
        except Exception as e:
            logger.error(f"Error getting S/R levels: {e}")
            return {"support": [], "resistance": []}
    
    def get_latest_swings(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100
    ) -> List[Dict]:
        """Get latest swing points (highs and lows) from database"""
        try:
            # Query using raw SQL to join with symbols and timeframe tables
            # The database schema uses symbol_id and timeframe_id as foreign keys
            query = text("""
                SELECT 
                    sp.id,
                    s.symbol_name as symbol,
                    t.tf_name as timeframe,
                    sp.timestamp,
                    sp.price,
                    sp.type,
                    sp.strength
                FROM swing_points sp
                INNER JOIN symbols s ON sp.symbol_id = s.symbol_id
                INNER JOIN timeframe t ON sp.timeframe_id = t.timeframe_id
                WHERE s.symbol_name = :symbol
                AND t.tf_name = :timeframe
                ORDER BY sp.timestamp DESC
                LIMIT :limit
            """)
            
            result = self.db.execute(
                query,
                {"symbol": symbol, "timeframe": timeframe, "limit": limit}
            )
            rows = result.fetchall()
            
            # Convert to list of dictionaries matching frontend interface
            swings = []
            for row in rows:
                swing_type = row[5]  # type column
                # Convert 'swing_high' to 'high' and 'swing_low' to 'low' for frontend
                type_mapping = {"swing_high": "high", "swing_low": "low"}
                
                swings.append({
                    "id": row[0],
                    "symbol": row[1],
                    "timeframe": row[2],
                    "timestamp": row[3].isoformat() if hasattr(row[3], 'isoformat') else str(row[3]),
                    "price": float(row[4]),
                    "type": type_mapping.get(swing_type, swing_type.replace("swing_", "")),
                    "strength": row[6] if len(row) > 6 else 1
                })
            
            return swings
        except Exception as e:
            logger.error(f"Error getting swings: {e}")
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


def save_signal(signal_data: Dict) -> Optional[TradingSignal]:
    """Save trading signal - convenience function"""
    with StorageService() as storage:
        return storage.save_trading_signal(signal_data)


def get_latest_signal(symbol: str) -> Optional[TradingSignal]:
    """Get latest signal - convenience function"""
    with StorageService() as storage:
        return storage.get_latest_signal(symbol)

