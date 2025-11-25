"""Database repository functions for ingestion service"""
import sys
import os
from typing import List, Optional, Tuple, Dict
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
            text("SELECT symbol_id, is_active, image_path FROM symbols WHERE symbol_name = :symbol"),
            {"symbol": symbol}
        ).fetchone()
        
        if result:
            symbol_id, is_active, current_image_path = result
            # Reactivate if inactive, update image_path if provided and current is NULL
            needs_update = False
            update_fields = []
            update_params = {"symbol_id": symbol_id}
            
            if not is_active:
                needs_update = True
                update_fields.append("is_active = TRUE")
                update_fields.append("removed_at = NULL")
                logger.debug("symbol_reactivated_during_creation", symbol=symbol)
            
            # Update image_path if provided and current is NULL
            if image_path and current_image_path is None:
                needs_update = True
                update_fields.append("image_path = :image_path")
                update_params["image_path"] = image_path
            
            if needs_update:
                update_fields.append("updated_at = NOW()")
                db.execute(
                    text(f"""
                        UPDATE symbols
                        SET {', '.join(update_fields)}
                        WHERE symbol_id = :symbol_id
                    """),
                    update_params
                )
            
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


def get_qualified_symbols(db: Session) -> List[str]:
    """Get symbols from database that meet market cap and volume criteria (PURE QUERY - NO SIDE EFFECTS)
    
    Filters by ingestion config values from ingestion_config table.
    Also applies whitelist/blacklist filters before market cap/volume filters.
    
    Filtering rules:
    - If blacklisted → NEVER include
    - If whitelisted → ALWAYS include (skip market cap/volume checks)
    - If neither → apply market cap/volume filters
    
    Returns:
        List of qualified symbol names
    """
    try:
        # Get ingestion config thresholds
        min_volume = get_ingestion_config_value(db, "limit_volume_up", default_value=50000000.0)
        min_market_cap = get_ingestion_config_value(db, "limit_market_cap", default_value=50000000.0)
        
        min_volume = min_volume if min_volume is not None else 50000000.0
        min_market_cap = min_market_cap if min_market_cap is not None else 50000000.0
        
        # Get whitelisted and blacklisted symbols
        whitelisted_symbols = set()
        blacklisted_symbols = set()
        filter_results = get_symbol_filters(db)
        for filter_item in filter_results:
            symbol = filter_item["symbol"]
            filter_type = filter_item["filter_type"]
            if filter_type == "whitelist":
                whitelisted_symbols.add(symbol)
            elif filter_type == "blacklist":
                blacklisted_symbols.add(symbol)
        
        logger.info(
            "symbol_filters_loaded",
            whitelist_count=len(whitelisted_symbols),
            blacklist_count=len(blacklisted_symbols)
        )
        
        # Get all qualified symbols (PURE QUERY - NO UPDATES)
        result = db.execute(
            text("""
                SELECT s.symbol_name, md.market_cap, md.volume_24h
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
                AND (
                    -- Whitelisted symbols: always include (skip market cap/volume checks)
                    UPPER(TRIM(BOTH '@' FROM s.symbol_name)) = ANY(:whitelisted)
                    OR
                    -- Non-blacklisted symbols that meet market cap/volume criteria
                    (UPPER(TRIM(BOTH '@' FROM s.symbol_name)) != ALL(:blacklisted)
                     AND md.market_cap >= :min_market_cap
                     AND md.volume_24h >= :min_volume)
                )
                ORDER BY md.market_cap DESC, s.symbol_name;
            """),
            {
                "min_market_cap": min_market_cap,
                "min_volume": min_volume,
                "whitelisted": list(whitelisted_symbols) if whitelisted_symbols else [],
                "blacklisted": list(blacklisted_symbols) if blacklisted_symbols else []
            }
        ).fetchall()
        
        # Clean symbols: remove @ prefix if present and ensure uppercase
        symbols = []
        whitelisted_included = 0
        blacklisted_excluded = 0
        for row in result:
            symbol = row[0]
            if symbol:
                cleaned = normalize_symbol(symbol)
                
                # Double-check blacklist (shouldn't happen due to SQL, but safety check)
                if cleaned in blacklisted_symbols:
                    blacklisted_excluded += 1
                    continue
                
                symbols.append(cleaned)
                if cleaned in whitelisted_symbols:
                    whitelisted_included += 1
        
        logger.info(
            "qualified_symbols_found",
            count=len(symbols),
            whitelisted_included=whitelisted_included,
            blacklisted_excluded=blacklisted_excluded,
            min_market_cap=min_market_cap,
            min_volume=min_volume
        )
        return symbols
    except Exception as e:
        logger.error("qualified_symbols_error", error=str(e), exc_info=True)
        return DEFAULT_SYMBOLS


def find_symbols_to_reactivate(
    db: Session,
    min_market_cap: float,
    min_volume: float,
    whitelisted_symbols: set,
    blacklisted_symbols: set
) -> List[str]:
    """Find symbols that should be reactivated (PURE QUERY - NO SIDE EFFECTS)
    
    Args:
        db: Database session
        min_market_cap: Minimum market cap threshold
        min_volume: Minimum volume threshold
        whitelisted_symbols: Set of whitelisted symbols
        blacklisted_symbols: Set of blacklisted symbols
        
    Returns:
        List of symbol names that should be reactivated
    """
    try:
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
                WHERE s.is_active = FALSE
                AND (
                    -- Whitelisted symbols: always reactivate
                    UPPER(TRIM(BOTH '@' FROM s.symbol_name)) = ANY(:whitelisted)
                    OR
                    -- Non-blacklisted symbols that meet market cap/volume criteria
                    (UPPER(TRIM(BOTH '@' FROM s.symbol_name)) != ALL(:blacklisted)
                     AND md.market_cap >= :min_market_cap
                     AND md.volume_24h >= :min_volume)
                )
            """),
            {
                "min_market_cap": min_market_cap,
                "min_volume": min_volume,
                "whitelisted": list(whitelisted_symbols) if whitelisted_symbols else [],
                "blacklisted": list(blacklisted_symbols) if blacklisted_symbols else []
            }
        ).fetchall()
        
        reactivated = [normalize_symbol(row[0]) for row in result if row[0]]
        return reactivated
    except Exception as e:
        logger.error("find_symbols_to_reactivate_error", error=str(e), exc_info=True)
        return []


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


# ============================================================================
# SYMBOL FILTER FUNCTIONS (Whitelist/Blacklist)
# ============================================================================

def normalize_symbol(symbol: str) -> str:
    """Normalize symbol to uppercase for consistent storage and comparison"""
    return symbol.lstrip("@").upper().strip()


def is_whitelisted(db: Session, symbol: str) -> bool:
    """Check if a symbol is in the whitelist
    
    Args:
        db: Database session
        symbol: Trading symbol to check
        
    Returns:
        True if symbol is whitelisted, False otherwise
    """
    try:
        normalized = normalize_symbol(symbol)
        result = db.execute(
            text("""
                SELECT COUNT(*) FROM symbol_filters
                WHERE symbol = :symbol AND filter_type = 'whitelist'
            """),
            {"symbol": normalized}
        ).scalar()
        return result > 0
    except Exception as e:
        logger.error(
            "whitelist_check_error",
            symbol=symbol,
            error=str(e),
            exc_info=True
        )
        return False


def is_blacklisted(db: Session, symbol: str) -> bool:
    """Check if a symbol is in the blacklist
    
    Args:
        db: Database session
        symbol: Trading symbol to check
        
    Returns:
        True if symbol is blacklisted, False otherwise
    """
    try:
        normalized = normalize_symbol(symbol)
        result = db.execute(
            text("""
                SELECT COUNT(*) FROM symbol_filters
                WHERE symbol = :symbol AND filter_type = 'blacklist'
            """),
            {"symbol": normalized}
        ).scalar()
        return result > 0
    except Exception as e:
        logger.error(
            "blacklist_check_error",
            symbol=symbol,
            error=str(e),
            exc_info=True
        )
        return False


def should_ingest_symbol(db: Session, symbol: str) -> bool:
    """Determine if a symbol should be ingested based on whitelist/blacklist rules
    
    Rules:
    - If blacklisted → NEVER ingest (return False)
    - If whitelisted → ALWAYS ingest (return True)
    - If neither → return None (caller should apply other filters)
    
    Args:
        db: Database session
        symbol: Trading symbol to check
        
    Returns:
        True if should ingest, False if should not ingest, None if no filter applies
    """
    normalized = normalize_symbol(symbol)
    
    # Blacklist overrides everything
    if is_blacklisted(db, normalized):
        return False
    
    # Whitelist means always ingest
    if is_whitelisted(db, normalized):
        return True
    
    # Neither whitelist nor blacklist - return None to indicate no filter applies
    return None


def add_symbol_filter(db: Session, symbol: str, filter_type: str) -> bool:
    """Add a symbol to whitelist or blacklist
    
    Args:
        db: Database session
        symbol: Trading symbol to add
        filter_type: 'whitelist' or 'blacklist'
        
    Returns:
        True if successful, False otherwise
    """
    try:
        normalized = normalize_symbol(symbol)
        
        if filter_type not in ('whitelist', 'blacklist'):
            logger.error(
                "invalid_filter_type",
                filter_type=filter_type,
                symbol=symbol
            )
            return False
        
        # Remove from opposite filter type if exists (a symbol can only be in one list)
        db.execute(
            text("""
                DELETE FROM symbol_filters
                WHERE symbol = :symbol AND filter_type != :filter_type
            """),
            {
                "symbol": normalized,
                "filter_type": filter_type
            }
        )
        
        # Insert or update
        db.execute(
            text("""
                INSERT INTO symbol_filters (symbol, filter_type, updated_at)
                VALUES (:symbol, :filter_type, NOW())
                ON CONFLICT (symbol, filter_type) 
                DO UPDATE SET updated_at = NOW()
            """),
            {
                "symbol": normalized,
                "filter_type": filter_type
            }
        )
        
        db.commit()
        logger.info(
            "symbol_filter_added",
            symbol=normalized,
            filter_type=filter_type
        )
        return True
    except Exception as e:
        logger.error(
            "symbol_filter_add_error",
            symbol=symbol,
            filter_type=filter_type,
            error=str(e),
            exc_info=True
        )
        db.rollback()
        return False


def remove_symbol_filter(db: Session, symbol: str) -> bool:
    """Remove a symbol from both whitelist and blacklist
    
    Args:
        db: Database session
        symbol: Trading symbol to remove
        
    Returns:
        True if successful, False otherwise
    """
    try:
        normalized = normalize_symbol(symbol)
        
        result = db.execute(
            text("""
                DELETE FROM symbol_filters
                WHERE symbol = :symbol
            """),
            {"symbol": normalized}
        )
        
        db.commit()
        deleted_count = result.rowcount
        
        if deleted_count > 0:
            logger.info(
                "symbol_filter_removed",
                symbol=normalized,
                deleted_count=deleted_count
            )
        
        return deleted_count > 0
    except Exception as e:
        logger.error(
            "symbol_filter_remove_error",
            symbol=symbol,
            error=str(e),
            exc_info=True
        )
        db.rollback()
        return False


def get_symbol_filters(db: Session, filter_type: Optional[str] = None) -> List[Dict]:
    """Get all symbol filters, optionally filtered by type
    
    Args:
        db: Database session
        filter_type: Optional filter type ('whitelist' or 'blacklist')
        
    Returns:
        List of dicts with symbol and filter_type
    """
    try:
        if filter_type:
            if filter_type not in ('whitelist', 'blacklist'):
                logger.error("invalid_filter_type", filter_type=filter_type)
                return []
            
            result = db.execute(
                text("""
                    SELECT symbol, filter_type, created_at, updated_at
                    FROM symbol_filters
                    WHERE filter_type = :filter_type
                    ORDER BY symbol
                """),
                {"filter_type": filter_type}
            ).fetchall()
        else:
            result = db.execute(
                text("""
                    SELECT symbol, filter_type, created_at, updated_at
                    FROM symbol_filters
                    ORDER BY filter_type, symbol
                """)
            ).fetchall()
        
        return [
            {
                "symbol": row[0],
                "filter_type": row[1],
                "created_at": row[2].isoformat() if row[2] else None,
                "updated_at": row[3].isoformat() if row[3] else None
            }
            for row in result
        ]
    except Exception as e:
        logger.error(
            "symbol_filters_get_error",
            filter_type=filter_type,
            error=str(e),
            exc_info=True
        )
        return []

