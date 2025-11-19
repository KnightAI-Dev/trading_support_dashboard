-- Trading Support Architecture Database Schema
-- PostgreSQL with TimescaleDB extension

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- METADATA TABLES
-- ============================================================================

-- Timeframes metadata
CREATE TABLE timeframe (
    timeframe_id SERIAL PRIMARY KEY,
    tf_name VARCHAR(10) UNIQUE NOT NULL,
    seconds INTEGER NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_timeframe_name ON timeframe(tf_name);

-- Insert standard timeframes
INSERT INTO timeframe (tf_name, seconds) VALUES 
    ('5m', 300),
    ('30m', 1800),
    ('1h', 3600),
    ('2h', 7200),
    ('4h', 14400),
    ('6h', 21600),
    ('8h', 28800),
    ('12h', 43200),
    ('1d', 86400)
ON CONFLICT (tf_name) DO NOTHING;

-- Symbols metadata
CREATE TABLE symbols (
    symbol_id SERIAL PRIMARY KEY,
    symbol_name VARCHAR(20) UNIQUE NOT NULL,
    base_asset VARCHAR(20) NOT NULL,
    quote_asset VARCHAR(20) NOT NULL,
    image_path VARCHAR(500),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_symbols_name ON symbols(symbol_name);

-- ============================================================================
-- MARKET DATA TABLES
-- ============================================================================

-- OHLCV Candles (time-series) - refactored with FKs
CREATE TABLE ohlcv_candles (
    id BIGSERIAL,
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    timeframe_id INTEGER NOT NULL REFERENCES timeframe(timeframe_id),
    timestamp TIMESTAMPTZ NOT NULL,
    open DECIMAL(20, 8) NOT NULL,
    high DECIMAL(20, 8) NOT NULL,
    low DECIMAL(20, 8) NOT NULL,
    close DECIMAL(20, 8) NOT NULL,
    volume DECIMAL(30, 8) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol_id, timeframe_id, timestamp)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('ohlcv_candles', 'timestamp', 
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Create indexes
CREATE INDEX idx_ohlcv_symbol_timeframe ON ohlcv_candles(symbol_id, timeframe_id, timestamp DESC);
CREATE INDEX idx_ohlcv_symbol_timestamp ON ohlcv_candles(symbol_id, timestamp DESC);

-- Market Data (Open Interest, CVD, etc.)
CREATE TABLE market_data (
    id BIGSERIAL,  -- Keep it, but NOT as primary key
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    timestamp TIMESTAMPTZ NOT NULL,
    market_cap DECIMAL(30, 2),
    price DECIMAL(20, 8),
    circulating_supply DECIMAL(30, 2),
    volume_24h DECIMAL(30, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol_id, timestamp)
);

SELECT create_hypertable('market_data', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX idx_market_data_symbol_timestamp ON market_data(symbol_id, timestamp DESC);

-- Asset Information (keeping for backward compatibility, can be deprecated later)
CREATE TABLE asset_info (
    id SERIAL PRIMARY KEY,
    symbol_id INTEGER UNIQUE NOT NULL REFERENCES symbols(symbol_id),
    symbol VARCHAR(20) UNIQUE NOT NULL,
    base_asset VARCHAR(20) NOT NULL,
    quote_asset VARCHAR(20) NOT NULL,
    tick_size DECIMAL(20, 8),
    lot_size DECIMAL(20, 8),
    min_qty DECIMAL(20, 8),
    max_qty DECIMAL(20, 8),
    step_size DECIMAL(20, 8),
    status VARCHAR(20) DEFAULT 'TRADING',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_asset_info_symbol ON asset_info(symbol);

-- ============================================================================
-- ANALYSIS TABLES
-- ============================================================================

-- Swing Highs and Lows
CREATE TABLE swing_points (
    id BIGSERIAL,  -- keep but not PK
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    timeframe_id INTEGER NOT NULL REFERENCES timeframe(timeframe_id),
    timestamp TIMESTAMPTZ NOT NULL,
    price DECIMAL(20, 8) NOT NULL,
    type VARCHAR(10) NOT NULL CHECK (type IN ('swing_high', 'swing_low')),
    strength INTEGER DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol_id, timeframe_id, timestamp, type)
);

SELECT create_hypertable('swing_points', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX idx_swing_symbol_timeframe ON swing_points(symbol_id, timeframe_id, timestamp DESC);
CREATE INDEX idx_swing_type ON swing_points(type);

-- Support and Resistance Levels
CREATE TABLE support_resistance (
    id BIGSERIAL PRIMARY KEY,
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    timeframe_id INTEGER NOT NULL REFERENCES timeframe(timeframe_id),
    level DECIMAL(20, 8) NOT NULL,
    type VARCHAR(10) NOT NULL CHECK (type IN ('support', 'resistance')),
    strength INTEGER DEFAULT 1, -- Number of touches
    first_touch TIMESTAMPTZ NOT NULL,
    last_touch TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_sr_symbol_timeframe ON support_resistance(symbol_id, timeframe_id, level);
CREATE INDEX idx_sr_active ON support_resistance(is_active, symbol_id, timeframe_id);

-- Fibonacci Levels
CREATE TABLE fibonacci_levels (
    id BIGSERIAL,
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    timeframe_id INTEGER NOT NULL REFERENCES timeframe(timeframe_id),
    timestamp TIMESTAMPTZ NOT NULL,
    swing_high DECIMAL(20, 8) NOT NULL,
    swing_low DECIMAL(20, 8) NOT NULL,
    fib_0 DECIMAL(20, 8) NOT NULL,
    fib_0_236 DECIMAL(20, 8),
    fib_0_382 DECIMAL(20, 8),
    fib_0_5 DECIMAL(20, 8),
    fib_0_618 DECIMAL(20, 8),
    fib_0_70 DECIMAL(20, 8),
    fib_0_72 DECIMAL(20, 8),
    fib_0_789 DECIMAL(20, 8),
    fib_0_90 DECIMAL(20, 8),
    fib_1 DECIMAL(20, 8) NOT NULL,
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('long', 'short')),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol_id, timeframe_id, timestamp)
);

SELECT create_hypertable('fibonacci_levels', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX idx_fib_symbol_timeframe ON fibonacci_levels(symbol_id, timeframe_id, timestamp DESC);

-- ============================================================================
-- TRADING SIGNALS & OUTPUTS
-- ============================================================================

-- Trading Signals (main output table)
CREATE TABLE trading_signals (
    id BIGSERIAL,
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    timestamp TIMESTAMPTZ NOT NULL,
    market_score INTEGER NOT NULL CHECK (market_score BETWEEN 0 AND 100),
    direction VARCHAR(10) NOT NULL CHECK (direction IN ('long', 'short')),
    price DECIMAL(20, 8) NOT NULL,
    entry1 DECIMAL(20, 8),
    entry2 DECIMAL(20, 8),
    sl DECIMAL(20, 8),
    tp1 DECIMAL(20, 8),
    tp2 DECIMAL(20, 8),
    tp3 DECIMAL(20, 8),
    swing_high DECIMAL(20, 8),
    swing_low DECIMAL(20, 8),
    support_level DECIMAL(20, 8),
    resistance_level DECIMAL(20, 8),
    confluence TEXT,
    risk_reward_ratio DECIMAL(10, 4),
    pullback_detected BOOLEAN DEFAULT FALSE,
    pullback_start_level DECIMAL(20, 8),
    approaching_fib_level DECIMAL(20, 8),
    confidence_score DECIMAL(5, 2),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol_id, timestamp)
);

SELECT create_hypertable('trading_signals', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX idx_signals_symbol_timestamp ON trading_signals(symbol_id, timestamp DESC);
CREATE INDEX idx_signals_direction ON trading_signals(direction);
CREATE INDEX idx_signals_score ON trading_signals(market_score DESC);

-- Confluence Factors
CREATE TABLE confluence_factors (
    id BIGSERIAL,
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    timestamp TIMESTAMPTZ NOT NULL,
    factor_type VARCHAR(20) NOT NULL,
    factor_value DECIMAL(20, 8),
    factor_score INTEGER DEFAULT 0 CHECK (factor_score BETWEEN 0 AND 100),
    metadata_json TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (symbol_id, timestamp, factor_type)
);

SELECT create_hypertable('confluence_factors', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

CREATE INDEX idx_confluence_symbol_timestamp ON confluence_factors(symbol_id, timestamp DESC);
CREATE INDEX idx_confluence_type ON confluence_factors(factor_type);

-- ============================================================================
-- CONFIGURATION TABLES
-- ============================================================================

-- Fibonacci Configuration
CREATE TABLE fib_config (
    id SERIAL PRIMARY KEY,
    setup_type VARCHAR(10) NOT NULL CHECK (setup_type IN ('long', 'short')),
    entry_level1 DECIMAL(5, 3) NOT NULL,
    entry_level2 DECIMAL(5, 3) NOT NULL,
    sl_level DECIMAL(5, 3) NOT NULL,
    approaching_level DECIMAL(5, 3) NOT NULL,
    pullback_start DECIMAL(5, 3) DEFAULT 0.382,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(setup_type)
);

-- Insert default Fibonacci configurations
INSERT INTO fib_config (setup_type, entry_level1, entry_level2, sl_level, approaching_level, pullback_start)
VALUES 
    ('long', 0.70, 0.72, 0.90, 0.618, 0.382),
    ('short', 0.618, 0.69, 0.789, 0.5, 0.382)
ON CONFLICT (setup_type) DO NOTHING;

-- ============================================================================
-- VIEWS FOR EASY QUERYING
-- ============================================================================

-- Latest trading signals view
CREATE OR REPLACE VIEW latest_signals AS
SELECT DISTINCT ON (symbol)
    symbol,
    timestamp,
    market_score,
    direction,
    price,
    entry1,
    entry2,
    sl,
    tp1,
    tp2,
    tp3,
    swing_high,
    swing_low,
    support_level,
    resistance_level,
    confluence,
    risk_reward_ratio,
    confidence_score,
    created_at
FROM trading_signals
ORDER BY symbol, timestamp DESC;

-- ============================================================================
-- FUNCTIONS
-- ============================================================================

-- Function to get latest signal for a symbol
CREATE OR REPLACE FUNCTION get_latest_signal(p_symbol VARCHAR(20))
RETURNS TABLE (
    symbol VARCHAR(20),
    signal_ts TIMESTAMPTZ,
    market_score INTEGER,
    direction VARCHAR(10),
    price DECIMAL(20, 8),
    entry1 DECIMAL(20, 8),
    sl DECIMAL(20, 8),
    tp1 DECIMAL(20, 8),
    tp2 DECIMAL(20, 8),
    tp3 DECIMAL(20, 8),
    confluence TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ts.symbol,
        ts."timestamp" AS signal_ts,
        ts.market_score,
        ts.direction,
        ts.price,
        ts.entry1,
        ts.sl,
        ts.tp1,
        ts.tp2,
        ts.tp3,
        ts.confluence
    FROM trading_signals ts
    WHERE ts.symbol = p_symbol
    ORDER BY ts."timestamp" DESC
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- GRANT PERMISSIONS
-- ============================================================================

-- Grant schema permissions
GRANT USAGE ON SCHEMA public TO trading_user;

-- Grant table permissions (all tables)
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO trading_user;

-- Grant sequence permissions (for auto-increment IDs)
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO trading_user;

-- Grant function permissions
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO trading_user;

-- Set default privileges for future tables/sequences/functions
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO trading_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO trading_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT EXECUTE ON FUNCTIONS TO trading_user;

