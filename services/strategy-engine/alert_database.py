"""
Database Manager for Trading Alerts

This module handles all database operations for storing and retrieving trading alerts.
It uses PostgreSQL and stores alerts in the strategy_alerts table.
"""

import sys
import os
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from sqlalchemy import text

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.database import SessionLocal
from shared.logger import setup_logger
from shared.redis_client import publish_event

logger = setup_logger(__name__)


class AlertDatabase:
    """
    Manages database operations for trading alerts.
    Handles storage, retrieval, and duplicate detection for swing high/low pairs.
    Uses PostgreSQL with the strategy_alerts table.
    """
    
    def __init__(self):
        """Initialize the database manager."""
        self._init_candle_timestamps_table()
    
    def _init_candle_timestamps_table(self):
        """Initialize the candle_timestamps table if it doesn't exist."""
        try:
            db = SessionLocal()
            try:
                db.execute(text("""
                    CREATE TABLE IF NOT EXISTS candle_timestamps (
                        id SERIAL PRIMARY KEY,
                        symbol_id INTEGER NOT NULL,
                        timeframe_id INTEGER NOT NULL,
                        last_candle_timestamp BIGINT NOT NULL,
                        updated_at TIMESTAMPTZ DEFAULT NOW(),
                        UNIQUE(symbol_id, timeframe_id),
                        FOREIGN KEY (symbol_id) REFERENCES symbols(symbol_id),
                        FOREIGN KEY (timeframe_id) REFERENCES timeframe(timeframe_id)
                    )
                """))
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"Table candle_timestamps may already exist: {e}")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error initializing candle_timestamps table: {e}")
    
    def _get_symbol_id(self, db, symbol: str) -> Optional[int]:
        """Get symbol_id from symbol name."""
        try:
            result = db.execute(
                text("SELECT symbol_id FROM symbols WHERE symbol_name = :symbol"),
                {"symbol": symbol}
            )
            row = result.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Error getting symbol_id for {symbol}: {e}")
            return None
    
    def _get_timeframe_id(self, db, timeframe: str) -> Optional[int]:
        """Get timeframe_id from timeframe name."""
        try:
            result = db.execute(
                text("SELECT timeframe_id FROM timeframe WHERE tf_name = :timeframe"),
                {"timeframe": timeframe}
            )
            row = result.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"Error getting timeframe_id for {timeframe}: {e}")
            return None
    
    def swing_pair_exists(self, asset: str, timeframe: str, swing_low: Tuple, swing_high: Tuple) -> bool:
        """
        Check if a swing high/low pair already exists in the database.
        
        Args:
            asset: Asset symbol (e.g., "BTCUSDT")
            timeframe: Timeframe string (e.g., "4h", "30m")
            swing_low: Tuple of (index, price) for swing low
            swing_high: Tuple of (index, price) for swing high
            
        Returns:
            True if the pair exists, False otherwise
        """
        if swing_low is None or swing_high is None:
            return False
        
        try:
            low_price = swing_low[1]
            high_price = swing_high[1]
        except (IndexError, TypeError):
            return False
        
        db = SessionLocal()
        try:
            symbol_id = self._get_symbol_id(db, asset)
            timeframe_id = self._get_timeframe_id(db, timeframe)
            
            if not symbol_id or not timeframe_id:
                return False
            
            result = db.execute(
                text("""
                    SELECT COUNT(*) FROM strategy_alerts
                    WHERE symbol_id = :symbol_id
                    AND timeframe_id = :timeframe_id
                    AND ABS(swing_low_price - :low_price) < 0.01
                    AND ABS(swing_high_price - :high_price) < 0.01
                """),
                {
                    "symbol_id": symbol_id,
                    "timeframe_id": timeframe_id,
                    "low_price": float(low_price),
                    "high_price": float(high_price)
                }
            )
            
            count = result.fetchone()[0]
            return count > 0
        except Exception as e:
            logger.error(f"Error checking swing pair existence: {e}")
            return False
        finally:
            db.close()
    
    def _unix_to_timestamp(self, unix_timestamp: int) -> datetime:
        """Convert Unix timestamp to datetime."""
        return datetime.fromtimestamp(unix_timestamp)
    
    def save_alerts(self, alerts: List[Dict], asset_symbol: str) -> Dict[str, int]:
        """
        Save alerts to database, skipping those that already exist.
        
        Args:
            alerts: List of alert dictionaries from _generate_alerts
            asset_symbol: Asset symbol (e.g., "BTCUSDT")
            
        Returns:
            Dictionary with counts: {'saved': int, 'skipped': int, 'errors': int}
        """
        if not alerts:
            return {'saved': 0, 'skipped': 0, 'errors': 0}
        
        saved_count = 0
        skipped_count = 0
        error_count = 0
        
        db = SessionLocal()
        try:
            symbol_id = self._get_symbol_id(db, asset_symbol)
            if not symbol_id:
                logger.error(f"Symbol {asset_symbol} not found in database")
                return {'saved': 0, 'skipped': 0, 'errors': len(alerts)}
            
            for alert in alerts:
                try:
                    timeframe = alert.get('timeframe', 'unknown')
                    swing_low = alert.get('swing_low')
                    swing_high = alert.get('swing_high')
                    
                    # Check if pair already exists
                    if self.swing_pair_exists(asset_symbol, timeframe, swing_low, swing_high):
                        skipped_count += 1
                        continue
                    
                    # Extract swing low/high data
                    if swing_low is None or swing_high is None:
                        error_count += 1
                        continue
                    
                    low_price = swing_low[1]
                    high_price = swing_high[1]
                    
                    # Get swing timestamps from alert or use current timestamp
                    # The alert should contain timestamps, but if not, use current time
                    swing_low_timestamp = alert.get('swing_low_timestamp')
                    swing_high_timestamp = alert.get('swing_high_timestamp')
                    
                    # If timestamps are in unix format, convert them
                    if isinstance(swing_low_timestamp, (int, float)):
                        swing_low_timestamp = self._unix_to_timestamp(int(swing_low_timestamp))
                    elif swing_low_timestamp is None:
                        swing_low_timestamp = datetime.now()
                    
                    if isinstance(swing_high_timestamp, (int, float)):
                        swing_high_timestamp = self._unix_to_timestamp(int(swing_high_timestamp))
                    elif swing_high_timestamp is None:
                        swing_high_timestamp = datetime.now()
                    
                    timeframe_id = self._get_timeframe_id(db, timeframe)
                    if not timeframe_id:
                        logger.warning(f"Timeframe {timeframe} not found, skipping alert")
                        error_count += 1
                        continue
                    
                    # Get alert timestamp (when the alert was generated)
                    alert_timestamp = alert.get('timestamp')
                    if isinstance(alert_timestamp, (int, float)):
                        alert_timestamp = self._unix_to_timestamp(int(alert_timestamp))
                    elif alert_timestamp is None:
                        alert_timestamp = datetime.now()
                    
                    # Insert alert and get the inserted ID
                    result = db.execute(
                        text("""
                            INSERT INTO strategy_alerts (
                                symbol_id, timeframe_id, timestamp,
                                entry_price, stop_loss, take_profit_1, take_profit_2, take_profit_3,
                                risk_score, swing_low_price, swing_low_timestamp,
                                swing_high_price, swing_high_timestamp, direction
                            ) VALUES (
                                :symbol_id, :timeframe_id, :timestamp,
                                :entry_price, :stop_loss, :take_profit_1, :take_profit_2, :take_profit_3,
                                :risk_score, :swing_low_price, :swing_low_timestamp,
                                :swing_high_price, :swing_high_timestamp, :direction
                            )
                            ON CONFLICT (symbol_id, timeframe_id, swing_low_price, swing_high_price, timestamp)
                            DO NOTHING
                            RETURNING id
                        """),
                        {
                            "symbol_id": symbol_id,
                            "timeframe_id": timeframe_id,
                            "timestamp": alert_timestamp,
                            "entry_price": float(alert.get('entry_level', 0)),
                            "stop_loss": float(alert.get('sl', 0)),
                            "take_profit_1": float(alert.get('tp1', 0)),
                            "take_profit_2": float(alert.get('tp2')) if alert.get('tp2') is not None else None,
                            "take_profit_3": float(alert.get('tp3')) if alert.get('tp3') is not None else None,
                            "risk_score": str(alert.get('risk_score', 'none')),
                            "swing_low_price": float(low_price),
                            "swing_low_timestamp": swing_low_timestamp,
                            "swing_high_price": float(high_price),
                            "swing_high_timestamp": swing_high_timestamp,
                            "direction": alert.get('trend_type')  # 'long' or 'short'
                        }
                    )
                    
                    inserted_row = result.fetchone()
                    if inserted_row:  # Alert was actually inserted (not skipped due to conflict)
                        alert_id = inserted_row[0]
                        # Publish event to Redis for API service to broadcast
                        try:
                            # Ensure timestamp is in ISO format string
                            timestamp_str = alert_timestamp.isoformat() if hasattr(alert_timestamp, 'isoformat') else str(alert_timestamp)
                            
                            alert_event = {
                                "id": alert_id,
                                "symbol": asset_symbol,
                                "timeframe": timeframe,
                                "timestamp": timestamp_str,
                                "entry_price": float(alert.get('entry_level', 0)),
                                "stop_loss": float(alert.get('sl', 0)),
                                "take_profit_1": float(alert.get('tp1', 0)),
                                "take_profit_2": float(alert.get('tp2')) if alert.get('tp2') is not None else None,
                                "take_profit_3": float(alert.get('tp3')) if alert.get('tp3') is not None else None,
                                "risk_score": str(alert.get('risk_score', 'none')),
                                "swing_low_price": float(low_price),
                                "swing_high_price": float(high_price),
                                "direction": alert.get('trend_type')
                            }
                            
                            publish_event("strategy_alert", alert_event)
                            logger.info(
                                f"Published strategy_alert event to Redis",
                                extra={
                                    "alert_id": alert_id,
                                    "symbol": asset_symbol,
                                    "timeframe": timeframe,
                                    "direction": alert.get('trend_type')
                                }
                            )
                        except Exception as e:
                            logger.error(f"Failed to publish strategy_alert event: {e}", exc_info=True)
                    
                    saved_count += 1
                    
                except Exception as e:
                    error_count += 1
                    logger.error(f"Error saving alert to database: {e}")
                    continue
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error in save_alerts: {e}")
        finally:
            db.close()
        
        return {
            'saved': saved_count,
            'skipped': skipped_count,
            'errors': error_count
        }
    
    def update_candle_timestamp(self, asset: str, timeframe: str, candle_timestamp: int) -> bool:
        """
        Update the last processed candle timestamp for a given asset and timeframe.
        
        Args:
            asset: Asset symbol (e.g., "BTCUSDT")
            timeframe: Timeframe string (e.g., "4h", "30m")
            candle_timestamp: Unix timestamp of the candle
            
        Returns:
            True if updated successfully, False otherwise
        """
        try:
            db = SessionLocal()
            try:
                symbol_id = self._get_symbol_id(db, asset)
                timeframe_id = self._get_timeframe_id(db, timeframe)
                
                if not symbol_id or not timeframe_id:
                    return False
                
                db.execute(
                    text("""
                        INSERT INTO candle_timestamps 
                        (symbol_id, timeframe_id, last_candle_timestamp, updated_at)
                        VALUES (:symbol_id, :timeframe_id, :timestamp, NOW())
                        ON CONFLICT (symbol_id, timeframe_id)
                        DO UPDATE SET 
                            last_candle_timestamp = EXCLUDED.last_candle_timestamp,
                            updated_at = NOW()
                    """),
                    {
                        "symbol_id": symbol_id,
                        "timeframe_id": timeframe_id,
                        "timestamp": candle_timestamp
                    }
                )
                
                db.commit()
                return True
            except Exception as e:
                db.rollback()
                logger.error(f"Error updating candle timestamp: {e}")
                return False
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error in update_candle_timestamp: {e}")
            return False
    
    def get_last_candle_timestamp(self, asset: str, timeframe: str) -> Optional[int]:
        """
        Get the last processed candle timestamp for a given asset and timeframe.
        
        Args:
            asset: Asset symbol (e.g., "BTCUSDT")
            timeframe: Timeframe string (e.g., "4h", "30m")
            
        Returns:
            Unix timestamp of last processed candle, or None if not found
        """
        try:
            db = SessionLocal()
            try:
                symbol_id = self._get_symbol_id(db, asset)
                timeframe_id = self._get_timeframe_id(db, timeframe)
                
                if not symbol_id or not timeframe_id:
                    return None
                
                result = db.execute(
                    text("""
                        SELECT last_candle_timestamp 
                        FROM candle_timestamps
                        WHERE symbol_id = :symbol_id AND timeframe_id = :timeframe_id
                    """),
                    {"symbol_id": symbol_id, "timeframe_id": timeframe_id}
                )
                
                row = result.fetchone()
                return row[0] if row else None
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Error getting candle timestamp: {e}")
            return None
    
    def is_new_candle(self, asset: str, timeframe: str, current_candle_timestamp: int) -> bool:
        """
        Check if the current candle is new (hasn't been processed yet).
        
        Args:
            asset: Asset symbol (e.g., "BTCUSDT")
            timeframe: Timeframe string (e.g., "4h", "30m")
            current_candle_timestamp: Unix timestamp of the current candle
            
        Returns:
            True if this is a new candle, False otherwise
        """
        last_timestamp = self.get_last_candle_timestamp(asset, timeframe)
        
        if last_timestamp is None:
            return True  # First time processing, consider it new
        
        return current_candle_timestamp > last_timestamp
    
    def save_strategy_results(self, result: Dict, asset_symbol: str, 
                             df_4h=None, df_30m=None) -> Dict[str, Dict[str, int]]:
        """
        Save strategy results (alerts) to database, checking for new candles and existing pairs.
        This is the main function to call after executing the strategy.
        
        Args:
            result: Result dictionary from execute_strategy containing 'alerts_4h' and 'alerts_30m'
            asset_symbol: Asset symbol (e.g., "BTCUSDT")
            df_4h: Optional DataFrame with 4H candles (to extract latest timestamp)
            df_30m: Optional DataFrame with 30M candles (to extract latest timestamp)
            
        Returns:
            Dictionary with summary: {
                '4h': {'saved': int, 'skipped': int, 'errors': int},
                '30m': {'saved': int, 'skipped': int, 'errors': int}
            }
        """
        summary = {
            '4h': {'saved': 0, 'skipped': 0, 'errors': 0},
            '30m': {'saved': 0, 'skipped': 0, 'errors': 0}
        }
        
        # Process 4H alerts
        alerts_4h = result.get('alerts_4h', [])
        if alerts_4h:
            # Check if we have a new 4H candle
            should_process_4h = True
            if df_4h is not None and len(df_4h) > 0:
                try:
                    # Get the latest candle timestamp (after get_candle, latest is at iloc[-1])
                    latest_4h_timestamp = int(df_4h.iloc[-1]['unix'])
                    should_process_4h = self.is_new_candle(asset_symbol, '4h', latest_4h_timestamp)
                    
                    if should_process_4h:
                        self.update_candle_timestamp(asset_symbol, '4h', latest_4h_timestamp)
                except (KeyError, IndexError, ValueError) as e:
                    logger.warning(f"Could not extract 4H candle timestamp: {e}")
            
            if should_process_4h:
                summary['4h'] = self.save_alerts(alerts_4h, asset_symbol)
            else:
                summary['4h'] = {'saved': 0, 'skipped': len(alerts_4h), 'errors': 0}
        
        # Process 30M alerts
        alerts_30m = result.get('alerts_30m', [])
        if alerts_30m:
            # Check if we have a new 30M candle
            should_process_30m = True
            if df_30m is not None and len(df_30m) > 0:
                try:
                    # Get the latest candle timestamp (after get_candle, latest is at iloc[-1])
                    latest_30m_timestamp = int(df_30m.iloc[-1]['unix'])
                    should_process_30m = self.is_new_candle(asset_symbol, '30m', latest_30m_timestamp)
                    
                    if should_process_30m:
                        self.update_candle_timestamp(asset_symbol, '30m', latest_30m_timestamp)
                except (KeyError, IndexError, ValueError) as e:
                    logger.warning(f"Could not extract 30M candle timestamp: {e}")
            
            if should_process_30m:
                summary['30m'] = self.save_alerts(alerts_30m, asset_symbol)
            else:
                summary['30m'] = {'saved': 0, 'skipped': len(alerts_30m), 'errors': 0}
        
        return summary
