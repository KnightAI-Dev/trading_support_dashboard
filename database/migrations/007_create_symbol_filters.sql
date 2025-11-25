-- Migration: Create symbol_filters table
-- Created: 2025-01-XX
-- Description: Adds symbol_filters table for whitelist/blacklist functionality

-- ============================================================================
-- SYMBOL FILTERS TABLE
-- ============================================================================

CREATE TABLE IF NOT EXISTS symbol_filters (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE NOT NULL,
    filter_type VARCHAR(10) NOT NULL CHECK (filter_type IN ('whitelist', 'blacklist')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol, filter_type)
);

CREATE INDEX idx_symbol_filters_symbol ON symbol_filters(symbol);
CREATE INDEX idx_symbol_filters_type ON symbol_filters(filter_type);

-- Add comment for documentation
COMMENT ON TABLE symbol_filters IS 'Symbol whitelist/blacklist filters. Blacklist overrides whitelist. Symbols are normalized to uppercase.';
COMMENT ON COLUMN symbol_filters.symbol IS 'Trading symbol (e.g., BTCUSDT), normalized to uppercase';
COMMENT ON COLUMN symbol_filters.filter_type IS 'Type of filter: whitelist or blacklist';

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON symbol_filters TO trading_user;
GRANT USAGE, SELECT ON SEQUENCE symbol_filters_id_seq TO trading_user;

