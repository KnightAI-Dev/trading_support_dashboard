-- Migration: Create binance_coingecko_matching table
-- Created: 2025-01-XX
-- Description: Stores matching data between Binance symbols and CoinGecko coins

-- ============================================================================
-- BINANCE COINGECKO MATCHING TABLE
-- ============================================================================

-- Binance CoinGecko matching table
CREATE TABLE IF NOT EXISTS binance_coingecko_matching (
    id SERIAL PRIMARY KEY,
    binance_symbol VARCHAR(20) UNIQUE NOT NULL,
    coingecko_id VARCHAR(100) NOT NULL,
    base_asset VARCHAR(20) NOT NULL,
    normalized_base VARCHAR(20) NOT NULL,
    coingecko_symbol VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_binance_coingecko_symbol ON binance_coingecko_matching(binance_symbol);
CREATE INDEX IF NOT EXISTS idx_binance_coingecko_coingecko_id ON binance_coingecko_matching(coingecko_id);
CREATE INDEX IF NOT EXISTS idx_binance_coingecko_base_asset ON binance_coingecko_matching(base_asset);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON binance_coingecko_matching TO trading_user;
GRANT USAGE, SELECT ON SEQUENCE binance_coingecko_matching_id_seq TO trading_user;

-- Add comments for documentation
COMMENT ON TABLE binance_coingecko_matching IS 'Matching table between Binance perpetual symbols and CoinGecko coins';
COMMENT ON COLUMN binance_coingecko_matching.binance_symbol IS 'Binance symbol (e.g., BTCUSDT)';
COMMENT ON COLUMN binance_coingecko_matching.coingecko_id IS 'CoinGecko coin ID (e.g., bitcoin)';
COMMENT ON COLUMN binance_coingecko_matching.base_asset IS 'Base asset extracted from Binance symbol';
COMMENT ON COLUMN binance_coingecko_matching.normalized_base IS 'Normalized base asset (handles multiplier prefixes)';
COMMENT ON COLUMN binance_coingecko_matching.coingecko_symbol IS 'CoinGecko symbol (e.g., BTC)';

