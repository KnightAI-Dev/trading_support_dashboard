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
    """Ensure symbol exists in symbols table and return symbol_id"""
    try:
        result = db.execute(
            text("SELECT symbol_id FROM symbols WHERE symbol_name = :symbol"),
            {"symbol": symbol}
        ).scalar()
        if result:
            symbol_id = result
            if image_path:
                db.execute(
                    text("""
                        UPDATE symbols
                        SET image_path = :image_path, updated_at = NOW()
                        WHERE symbol_id = :symbol_id AND (image_path IS NULL OR image_path != :image_path)
                    """),
                    {"symbol_id": symbol_id, "image_path": image_path}
                )
            return symbol_id
        
        base_asset, quote_asset = split_symbol_components(symbol)
        result = db.execute(
            text("""
                INSERT INTO symbols (symbol_name, base_asset, quote_asset, image_path)
                VALUES (:symbol, :base_asset, :quote_asset, :image_path)
                ON CONFLICT (symbol_name) DO UPDATE SET
                    image_path = COALESCE(EXCLUDED.image_path, symbols.image_path),
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
    """Get symbols from database that meet market cap and volume criteria"""
    try:
        # Query symbols with latest market_data that meet criteria
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
                ORDER BY md.market_cap DESC, s.symbol_name;
            """)
        ).fetchall()
        
        # Clean symbols: remove @ prefix if present and ensure uppercase
        symbols = []
        for row in result:
            symbol = row[0]
            if symbol:
                # Remove @ prefix if present (from WebSocket stream names)
                cleaned = symbol.lstrip("@").upper()
                if cleaned != symbol:
                    logger.warning(
                        "symbol_cleaned_from_db",
                        original=symbol,
                        cleaned=cleaned
                    )
                symbols.append(cleaned)
        
        logger.info("qualified_symbols_found", count=len(symbols))
        return symbols
    except Exception as e:
        logger.error("qualified_symbols_error", error=str(e), exc_info=True)
        return DEFAULT_SYMBOLS


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

