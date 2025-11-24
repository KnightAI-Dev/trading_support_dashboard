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
    OHLCVCandle, StrategyAlert, StrategyConfig
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
                WHERE s.is_active = TRUE
                AND s.removed_at IS NULL
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
                WHERE s.is_active = TRUE
                AND s.removed_at IS NULL
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
    
    def get_symbol_details(self, symbol: str) -> Optional[Dict]:
        """Get detailed symbol information including market data"""
        try:
            query = text("""
                SELECT 
                    s.symbol_name,
                    s.base_asset,
                    s.quote_asset,
                    s.image_path,
                    md.price,
                    md.volume_24h,
                    md.market_cap,
                    md.circulating_supply,
                    md.timestamp
                FROM symbols s
                LEFT JOIN LATERAL (
                    SELECT price, volume_24h, market_cap, circulating_supply, timestamp
                    FROM market_data md2
                    WHERE md2.symbol_id = s.symbol_id
                    ORDER BY md2.timestamp DESC
                    LIMIT 1
                ) md ON true
                WHERE s.symbol_name = :symbol
                AND s.is_active = TRUE
                AND s.removed_at IS NULL
            """)
            
            result = self.db.execute(query, {"symbol": symbol})
            row = result.fetchone()
            
            if not row:
                return None
            
            return {
                "symbol_name": row[0],
                "base_asset": row[1],
                "quote_asset": row[2],
                "image_path": row[3],
                "price": float(row[4]) if row[4] is not None else None,
                "volume_24h": float(row[5]) if row[5] is not None else None,
                "market_cap": float(row[6]) if row[6] is not None else None,
                "circulating_supply": float(row[7]) if row[7] is not None else None,
                "timestamp": row[8].isoformat() if row[8] and hasattr(row[8], 'isoformat') else None,
            }
        except Exception as e:
            logger.error(f"Error getting symbol details for {symbol}: {e}")
            return None
    
    def get_strategy_config(self, config_key: Optional[str] = None) -> Dict:
        """Get strategy configuration values from database"""
        try:
            if config_key:
                # Get single config value
                config = self.db.query(StrategyConfig).filter(StrategyConfig.config_key == config_key).first()
                if not config:
                    return {}
                
                # Parse value based on type
                value = config.config_value
                if config.config_type == 'number':
                    # Try to parse as float first, then int
                    try:
                        if '.' in value:
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass
                elif config.config_type == 'json':
                    import json
                    value = json.loads(value)
                
                return {config_key: value}
            else:
                # Get all config values
                configs = self.db.query(StrategyConfig).all()
                result = {}
                for config in configs:
                    value = config.config_value
                    if config.config_type == 'number':
                        try:
                            if '.' in value:
                                value = float(value)
                            else:
                                value = int(value)
                        except ValueError:
                            pass
                    elif config.config_type == 'json':
                        import json
                        value = json.loads(value)
                    result[config.config_key] = value
                return result
        except Exception as e:
            logger.error(f"Error getting strategy config: {e}")
            return {}

    def update_strategy_config(self, config_key: str, config_value: str, updated_by: Optional[str] = None) -> bool:
        """Update a strategy configuration value"""
        try:
            config = self.db.query(StrategyConfig).filter(StrategyConfig.config_key == config_key).first()
            if config:
                config.config_value = str(config_value)
                config.updated_by = updated_by
                config.updated_at = datetime.utcnow()
            else:
                # Create new config entry
                config = StrategyConfig(
                    config_key=config_key,
                    config_value=str(config_value),
                    config_type='string',
                    updated_by=updated_by
                )
                self.db.add(config)
            
            self.db.commit()
            logger.info(f"Updated strategy config: {config_key} = {config_value}")
            return True
        except Exception as e:
            logger.error(f"Error updating strategy config: {e}")
            self.db.rollback()
            return False

    def update_strategy_configs(self, configs: Dict[str, str], updated_by: Optional[str] = None) -> bool:
        """Update multiple strategy configuration values"""
        try:
            for config_key, config_value in configs.items():
                config = self.db.query(StrategyConfig).filter(StrategyConfig.config_key == config_key).first()
                if config:
                    config.config_value = str(config_value)
                    config.updated_by = updated_by
                    config.updated_at = datetime.utcnow()
                else:
                    # Create new config entry
                    config = StrategyConfig(
                        config_key=config_key,
                        config_value=str(config_value),
                        config_type='string',
                        updated_by=updated_by
                    )
                    self.db.add(config)
            
            self.db.commit()
            logger.info(f"Updated {len(configs)} strategy configs")
            return True
        except Exception as e:
            logger.error(f"Error updating strategy configs: {e}")
            self.db.rollback()
            return False

    def get_ingestion_config(self, config_key: Optional[str] = None) -> Dict:
        """Get ingestion configuration values from database"""
        try:
            if config_key:
                # Get single config value
                result = self.db.execute(
                    text("""
                        SELECT config_key, config_value, config_type, description, updated_at, updated_by
                        FROM ingestion_config
                        WHERE config_key = :config_key
                    """),
                    {"config_key": config_key}
                ).fetchone()
                
                if not result:
                    return {}
                
                # Parse value based on type
                value = result[1]  # config_value
                if result[2] == 'number':  # config_type
                    try:
                        if '.' in str(value):
                            value = float(value)
                        else:
                            value = int(value)
                    except ValueError:
                        pass
                elif result[2] == 'json':
                    import json
                    value = json.loads(value)
                
                return {config_key: value}
            else:
                # Get all config values
                results = self.db.execute(
                    text("""
                        SELECT config_key, config_value, config_type, description, updated_at, updated_by
                        FROM ingestion_config
                        ORDER BY config_key
                    """)
                ).fetchall()
                
                result = {}
                for row in results:
                    config_key, config_value, config_type, description, updated_at, updated_by = row
                    value = config_value
                    if config_type == 'number':
                        try:
                            if '.' in str(value):
                                value = float(value)
                            else:
                                value = int(value)
                        except ValueError:
                            pass
                    elif config_type == 'json':
                        import json
                        value = json.loads(value)
                    result[config_key] = value
                return result
        except Exception as e:
            logger.error(f"Error getting ingestion config: {e}")
            return {}

    def update_ingestion_config(self, config_key: str, config_value: str, updated_by: Optional[str] = None) -> bool:
        """Update an ingestion configuration value"""
        try:
            # Check if config exists
            existing = self.db.execute(
                text("""
                    SELECT config_type FROM ingestion_config WHERE config_key = :config_key
                """),
                {"config_key": config_key}
            ).fetchone()
            
            config_type = 'number'  # Default type
            if existing:
                config_type = existing[0]
            
            # Update or insert
            self.db.execute(
                text("""
                    INSERT INTO ingestion_config (config_key, config_value, config_type, updated_at, updated_by)
                    VALUES (:config_key, :config_value, :config_type, NOW(), :updated_by)
                    ON CONFLICT (config_key) DO UPDATE SET
                        config_value = EXCLUDED.config_value,
                        updated_at = NOW(),
                        updated_by = EXCLUDED.updated_by
                """),
                {
                    "config_key": config_key,
                    "config_value": str(config_value),
                    "config_type": config_type,
                    "updated_by": updated_by or "api-service"
                }
            )
            
            self.db.commit()
            logger.info(f"Updated ingestion config: {config_key} = {config_value}")
            return True
        except Exception as e:
            logger.error(f"Error updating ingestion config: {e}")
            self.db.rollback()
            return False

    def update_ingestion_configs(self, configs: Dict[str, str], updated_by: Optional[str] = None) -> bool:
        """Update multiple ingestion configuration values"""
        try:
            for config_key, config_value in configs.items():
                # Check if config exists to get its type
                existing = self.db.execute(
                    text("""
                        SELECT config_type FROM ingestion_config WHERE config_key = :config_key
                    """),
                    {"config_key": config_key}
                ).fetchone()
                
                config_type = 'number'  # Default type
                if existing:
                    config_type = existing[0]
                
                # Update or insert
                self.db.execute(
                    text("""
                        INSERT INTO ingestion_config (config_key, config_value, config_type, updated_at, updated_by)
                        VALUES (:config_key, :config_value, :config_type, NOW(), :updated_by)
                        ON CONFLICT (config_key) DO UPDATE SET
                            config_value = EXCLUDED.config_value,
                            updated_at = NOW(),
                            updated_by = EXCLUDED.updated_by
                    """),
                    {
                        "config_key": config_key,
                        "config_value": str(config_value),
                        "config_type": config_type,
                        "updated_by": updated_by or "api-service"
                    }
                )
            
            self.db.commit()
            logger.info(f"Updated {len(configs)} ingestion configs")
            return True
        except Exception as e:
            logger.error(f"Error updating ingestion configs: {e}")
            self.db.rollback()
            return False



