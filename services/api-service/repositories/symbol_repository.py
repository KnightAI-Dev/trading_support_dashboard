"""
Repository for symbol data
"""
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from .base_repository import BaseRepository


class SymbolRepository(BaseRepository):
    """Repository for symbol data access"""
    
    def find_all_with_prices(self) -> List[Dict]:
        """Find all symbols with latest prices and 24h change"""
        query = text("""
            WITH latest_prices AS (
                SELECT DISTINCT ON (s.symbol_name)
                    s.symbol_name as symbol,
                    oc.close as current_price,
                    oc.timestamp as current_timestamp
                FROM ohlcv_candles oc
                INNER JOIN symbols s ON oc.symbol_id = s.symbol_id
                INNER JOIN timeframe t ON oc.timeframe_id = t.timeframe_id
                WHERE t.tf_name = '1h'
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
        
        return symbols
    
    def find_by_symbol(self, symbol: str) -> Optional[Dict]:
        """Find symbol details by symbol name"""
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

