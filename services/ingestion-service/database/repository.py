"""Database repository functions for ingestion service"""
import sys
import os
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
import structlog

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from config.settings import DEFAULT_SYMBOLS, DEFAULT_TIMEFRAME

logger = structlog.get_logger(__name__)

KNOWN_QUOTE_ASSETS = ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB", "USD", "EUR", "TRY", "BIDR"]


def split_symbol_components(symbol: str) -> Tuple[str, str]:
    """Best-effort parsing of base/quote assets from a trading symbol"""
    for quote in KNOWN_QUOTE_ASSETS:
        if symbol.endswith(quote) and len(symbol) > len(quote):
            return symbol[:-len(quote)], quote
    # Fallback: treat entire symbol as base and default quote to USD
    return symbol, "USD"


def get_or_create_symbol_record(db: Session, symbol: str, image_path: Optional[str] = None) -> Optional[int]:
    """Ensure symbol exists in symbols table and return symbol_id.
    
    If symbol exists but is inactive, it will be reactivated (is_active=True, removed_at=NULL).
    """
    try:
        result = db.execute(
            text("SELECT symbol_id, is_active FROM symbols WHERE symbol_name = :symbol"),
            {"symbol": symbol}
        ).fetchone()
        
        if result:
            symbol_id, is_active = result
            # Reactivate if inactive, update image_path if provided
            if not is_active:
                db.execute(
                    text("""
                        UPDATE symbols
                        SET is_active = TRUE,
                            removed_at = NULL,
                            updated_at = NOW()
                        WHERE symbol_id = :symbol_id
                    """),
                    {"symbol_id": symbol_id}
                )
                logger.debug("symbol_reactivated_during_creation", symbol=symbol)
            return symbol_id
        
        # Create new symbol (automatically active)
        base_asset, quote_asset = split_symbol_components(symbol)
        result = db.execute(
            text("""
                INSERT INTO symbols (symbol_name, base_asset, quote_asset, image_path, is_active, removed_at)
                VALUES (:symbol, :base_asset, :quote_asset, :image_path, TRUE, NULL)
                ON CONFLICT (symbol_name) DO UPDATE SET
                    image_path = COALESCE(EXCLUDED.image_path, symbols.image_path),
                    is_active = TRUE,
                    removed_at = NULL,
                    updated_at = NOW()
                RETURNING symbol_id
            """),
            {
                "symbol": symbol,
                "base_asset": base_asset,
                "quote_asset": quote_asset,
                "image_path": image_path
            }
        ).scalar()
        return result
    except Exception as e:
        logger.error(
            "symbol_record_error",
            symbol=symbol,
            error=str(e),
            exc_info=True
        )
        return None


def get_timeframe_id(db: Session, timeframe: str) -> Optional[int]:
    """Get timeframe_id for given timeframe string"""
    try:
        return db.execute(
            text("SELECT timeframe_id FROM timeframe WHERE tf_name = :tf LIMIT 1"),
            {"tf": timeframe}
        ).scalar()
    except Exception as e:
        logger.error(
            "timeframe_id_error",
            timeframe=timeframe,
            error=str(e),
            exc_info=True
        )
        return None


def get_qualified_symbols(db: Session) -> Tuple[List[str], List[str]]:
    """Get symbols from database that meet market cap and volume criteria
    Filters by ingestion config values from ingestion_config table.
    Also reactivates any inactive symbols that now meet the criteria.
    
    Returns:
        Tuple of (qualified_symbols_list, reactivated_symbols_list)
    """
    try:
        # Get ingestion config thresholds
        min_volume = get_ingestion_config_value(db, "limit_volume_up", default_value=50000000.0)
        min_market_cap = get_ingestion_config_value(db, "limit_market_cap", default_value=50000000.0)
        
        min_volume = min_volume if min_volume is not None else 50000000.0
        min_market_cap = min_market_cap if min_market_cap is not None else 50000000.0
        
        # Reactivate inactive symbols that now meet criteria (bulk update - more efficient)
        reactivated_result = db.execute(
            text("""
                UPDATE symbols AS s
                SET is_active = TRUE,
                    removed_at = NULL,
                    updated_at = NOW()
                FROM (
                    SELECT DISTINCT ON (symbol_id)
                        symbol_id, market_cap, volume_24h
                    FROM market_data
                    WHERE market_cap IS NOT NULL
                      AND volume_24h IS NOT NULL
                    ORDER BY symbol_id, timestamp DESC
                ) md
                WHERE s.symbol_id = md.symbol_id
                  AND md.market_cap >= :min_market_cap
                  AND md.volume_24h >= :min_volume
                  AND s.is_active = FALSE
                RETURNING s.symbol_id, s.symbol_name
            """),
            {
                "min_market_cap": min_market_cap,
                "min_volume": min_volume
            }
        ).fetchall()
        
        reactivated_count = len(reactivated_result)
        reactivated_symbols = []
        if reactivated_count > 0:
            # Clean reactivated symbol names
            for row in reactivated_result:
                symbol_name = row[1]
                if symbol_name:
                    cleaned = symbol_name.lstrip("@").upper()
                    reactivated_symbols.append(cleaned)
        
        # Now get all qualified symbols (including newly reactivated ones)
        result = db.execute(
            text("""
                SELECT s.symbol_name
                FROM symbols s
                INNER JOIN (
                    SELECT DISTINCT ON (symbol_id)
                        symbol_id, market_cap, volume_24h
                    FROM market_data
                    WHERE market_cap IS NOT NULL
                    AND volume_24h IS NOT NULL
                    ORDER BY symbol_id, timestamp DESC
                ) md ON s.symbol_id = md.symbol_id
                WHERE s.is_active = TRUE
                AND s.removed_at IS NULL
                AND md.market_cap >= :min_market_cap
                AND md.volume_24h >= :min_volume
                ORDER BY md.market_cap DESC, s.symbol_name;
            """),
            {
                "min_market_cap": min_market_cap,
                "min_volume": min_volume
            }
        ).fetchall()
        
        # Clean symbols: remove @ prefix if present and ensure uppercase
        symbols = []
        for row in result:
            symbol = row[0]
            if symbol:
                cleaned = symbol.lstrip("@").upper()
                if cleaned != symbol:
                    logger.warning(
                        "symbol_cleaned_from_db",
                        original=symbol,
                        cleaned=cleaned
                    )
                symbols.append(cleaned)
        
        # Commit only after both operations succeed
        if reactivated_count > 0:
            db.commit()
            logger.info(
                "symbols_reactivated",
                count=reactivated_count,
                symbols=reactivated_symbols[:10] if len(reactivated_symbols) > 10 else reactivated_symbols,
                message=f"Reactivated {reactivated_count} previously inactive symbols that now meet criteria"
            )
        
        logger.info(
            "qualified_symbols_found",
            count=len(symbols),
            reactivated_count=reactivated_count,
            min_market_cap=min_market_cap,
            min_volume=min_volume
        )
        return symbols, reactivated_symbols
    except Exception as e:
        logger.error("qualified_symbols_error", error=str(e), exc_info=True)
        db.rollback()
        return DEFAULT_SYMBOLS, []


def get_ingestion_timeframes(db: Session) -> List[str]:
    """Get ingestion timeframes from timeframe table, fallback to DEFAULT_TIMEFRAME list"""
    try:
        results = db.execute(
            text("SELECT tf_name FROM timeframe ORDER BY seconds ASC")
        ).fetchall()
        timeframes = [row[0] for row in results]
        if timeframes:
            logger.info("ingestion_timeframes_loaded", timeframes=timeframes, count=len(timeframes))
            return timeframes
    except Exception as e:
        logger.error("ingestion_timeframes_error", error=str(e), exc_info=True)
    
    logger.warning("timeframe_fallback", default_timeframe=DEFAULT_TIMEFRAME)
    return [DEFAULT_TIMEFRAME]


def get_strategy_config_value(db: Session, config_key: str, default_value: Optional[float] = None) -> Optional[float]:
    """Get strategy config value from database, returning as float for numeric types
    
    Args:
        db: Database session
        config_key: Configuration key to look up
        default_value: Default value to return if not found or error occurs
    
    Returns:
        Config value as float, or default_value if not found/error
    """
    try:
        result = db.execute(
            text("""
                SELECT config_value, config_type
                FROM strategy_config
                WHERE config_key = :config_key
            """),
            {"config_key": config_key}
        ).fetchone()
        
        if result:
            config_value, config_type = result
            if config_type == 'number':
                try:
                    return float(config_value)
                except (ValueError, TypeError):
                    logger.warning(
                        "config_value_parse_error",
                        config_key=config_key,
                        config_value=config_value,
                        config_type=config_type
                    )
                    return default_value
            else:
                logger.warning(
                    "config_type_mismatch",
                    config_key=config_key,
                    expected_type="number",
                    actual_type=config_type
                )
                return default_value
        
        logger.debug(f"Config key '{config_key}' not found in database, using default: {default_value}")
        return default_value
    except Exception as e:
        logger.error(
            "strategy_config_error",
            config_key=config_key,
            error=str(e),
            exc_info=True
        )
        return default_value


def get_ingestion_config_value(db: Session, config_key: str, default_value: Optional[float] = None) -> Optional[float]:
    """Get ingestion config value from database, returning as float for numeric types
    
    Args:
        db: Database session
        config_key: Configuration key to look up (e.g., 'limit_volume_up', 'limit_market_cap', 'coingecko_limit')
        default_value: Default value to return if not found or error occurs
    
    Returns:
        Config value as float, or default_value if not found/error
    """
    try:
        result = db.execute(
            text("""
                SELECT config_value, config_type
                FROM ingestion_config
                WHERE config_key = :config_key
            """),
            {"config_key": config_key}
        ).fetchone()
        
        if result:
            config_value, config_type = result
            if config_type == 'number':
                try:
                    return float(config_value)
                except (ValueError, TypeError):
                    logger.warning(
                        "ingestion_config_value_parse_error",
                        config_key=config_key,
                        config_value=config_value,
                        config_type=config_type
                    )
                    return default_value
            else:
                logger.warning(
                    "ingestion_config_type_mismatch",
                    config_key=config_key,
                    expected_type="number",
                    actual_type=config_type
                )
                return default_value
        
        logger.debug(f"Ingestion config key '{config_key}' not found in database, using default: {default_value}")
        return default_value
    except Exception as e:
        logger.error(
            "ingestion_config_error",
            config_key=config_key,
            error=str(e),
            exc_info=True
        )
        return default_value


def set_ingestion_config_value(
    db: Session, 
    config_key: str, 
    config_value: float, 
    updated_by: Optional[str] = None
) -> bool:
    """Set ingestion config value in database
    
    Args:
        db: Database session
        config_key: Configuration key to set (e.g., 'limit_volume_up', 'limit_market_cap', 'coingecko_limit')
        config_value: Configuration value to set (will be converted to string)
        updated_by: Optional identifier of who/what updated the value
    
    Returns:
        True if successful, False otherwise
    """
    try:
        db.execute(
            text("""
                INSERT INTO ingestion_config (config_key, config_value, config_type, updated_at, updated_by)
                VALUES (:config_key, :config_value, 'number', NOW(), :updated_by)
                ON CONFLICT (config_key) DO UPDATE SET
                    config_value = EXCLUDED.config_value,
                    updated_at = NOW(),
                    updated_by = EXCLUDED.updated_by
            """),
            {
                "config_key": config_key,
                "config_value": str(config_value),
                "updated_by": updated_by or "ingestion-service"
            }
        )
        db.commit()
        logger.info(
            "ingestion_config_updated",
            config_key=config_key,
            config_value=config_value
        )
        return True
    except Exception as e:
        logger.error(
            "ingestion_config_update_error",
            config_key=config_key,
            config_value=config_value,
            error=str(e),
            exc_info=True
        )
        db.rollback()
        return False

