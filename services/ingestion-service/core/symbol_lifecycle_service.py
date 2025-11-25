"""
Symbol Lifecycle Service - Manages symbol activation/deactivation
Separates lifecycle management from business logic
"""
import sys
import os
from typing import List, Set
from sqlalchemy.orm import Session
from sqlalchemy import text
import structlog
from datetime import datetime, timezone

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

# Import from local modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from database.repository import normalize_symbol

logger = structlog.get_logger(__name__)


class SymbolLifecycleService:
    """Service for managing symbol activation and deactivation"""
    
    async def activate_symbols(self, db: Session, symbols: List[str]) -> int:
        """Activate symbols (set is_active=True, removed_at=NULL)
        
        Args:
            db: Database session
            symbols: List of symbol names to activate
            
        Returns:
            Number of symbols activated
        """
        if not symbols:
            return 0
        
        try:
            result = db.execute(
                text("""
                    UPDATE symbols
                    SET is_active = TRUE,
                        removed_at = NULL,
                        updated_at = NOW()
                    WHERE symbol_name = ANY(:symbols)
                    AND (is_active = FALSE OR removed_at IS NOT NULL)
                """),
                {"symbols": symbols}
            )
            count = result.rowcount
            if count > 0:
                logger.info(
                    "symbols_activated",
                    count=count,
                    symbols=symbols[:10] if len(symbols) > 10 else symbols
                )
            return count
        except Exception as e:
            logger.error(
                "symbol_activation_error",
                error=str(e),
                symbols=symbols[:10] if len(symbols) > 10 else symbols,
                exc_info=True
            )
            raise
    
    async def deactivate_symbols(self, db: Session, symbols: List[str]) -> int:
        """Deactivate symbols (set is_active=FALSE, removed_at=NOW())
        
        Args:
            db: Database session
            symbols: List of symbol names to deactivate
            
        Returns:
            Number of symbols deactivated
        """
        if not symbols:
            return 0
        
        try:
            current_time = datetime.now(timezone.utc)
            result = db.execute(
                text("""
                    UPDATE symbols
                    SET is_active = FALSE,
                        removed_at = :removed_at,
                        updated_at = :updated_at
                    WHERE symbol_name = ANY(:symbols)
                    AND is_active = TRUE
                """),
                {
                    "symbols": symbols,
                    "removed_at": current_time,
                    "updated_at": current_time
                }
            )
            count = result.rowcount
            if count > 0:
                logger.info(
                    "symbols_deactivated",
                    count=count,
                    symbols=symbols[:10] if len(symbols) > 10 else symbols
                )
            return count
        except Exception as e:
            logger.error(
                "symbol_deactivation_error",
                error=str(e),
                symbols=symbols[:10] if len(symbols) > 10 else symbols,
                exc_info=True
            )
            raise
    
    async def reactivate_symbols_meeting_criteria(
        self,
        db: Session,
        min_market_cap: float,
        min_volume: float,
        whitelisted_symbols: Set[str],
        blacklisted_symbols: Set[str]
    ) -> List[str]:
        """Find and reactivate symbols that meet criteria
        
        Args:
            db: Database session
            min_market_cap: Minimum market cap threshold
            min_volume: Minimum volume threshold
            whitelisted_symbols: Set of whitelisted symbols (always reactivate)
            blacklisted_symbols: Set of blacklisted symbols (never reactivate)
            
        Returns:
            List of reactivated symbol names
        """
        try:
            result = db.execute(
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
                      AND s.is_active = FALSE
                      AND (
                          -- Whitelisted symbols: always reactivate
                          UPPER(TRIM(BOTH '@' FROM s.symbol_name)) = ANY(:whitelisted)
                          OR
                          -- Non-blacklisted symbols that meet market cap/volume criteria
                          (UPPER(TRIM(BOTH '@' FROM s.symbol_name)) != ALL(:blacklisted)
                           AND md.market_cap >= :min_market_cap
                           AND md.volume_24h >= :min_volume)
                      )
                    RETURNING s.symbol_id, s.symbol_name
                """),
                {
                    "min_market_cap": min_market_cap,
                    "min_volume": min_volume,
                    "whitelisted": list(whitelisted_symbols) if whitelisted_symbols else [],
                    "blacklisted": list(blacklisted_symbols) if blacklisted_symbols else []
                }
            ).fetchall()
            
            reactivated = [normalize_symbol(row[1]) for row in result if row[1]]
            
            if reactivated:
                logger.info(
                    "symbols_reactivated",
                    count=len(reactivated),
                    symbols=reactivated[:10] if len(reactivated) > 10 else reactivated
                )
            
            return reactivated
        except Exception as e:
            logger.error(
                "symbol_reactivation_error",
                error=str(e),
                exc_info=True
            )
            return []


def normalize_symbol(symbol: str) -> str:
    """Normalize symbol to uppercase for consistent storage and comparison"""
    return symbol.lstrip("@").upper().strip()

