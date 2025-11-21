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
-- STRATEGY ALERTS TABLE
-- ============================================================================

-- Strategy Engine Alerts (main output table for strategy-engine)
CREATE TABLE strategy_alerts (
    id BIGSERIAL PRIMARY KEY,
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    timeframe_id INTEGER NOT NULL REFERENCES timeframe(timeframe_id),
    timestamp TIMESTAMPTZ NOT NULL,
    
    -- Entry and Risk Management
    entry_price DECIMAL(20, 8) NOT NULL,
    stop_loss DECIMAL(20, 8) NOT NULL,
    take_profit_1 DECIMAL(20, 8) NOT NULL,
    take_profit_2 DECIMAL(20, 8),
    take_profit_3 DECIMAL(20, 8),
    risk_score VARCHAR(20),  -- e.g., 'none', 'good', 'high', 'higher', 'very_high'
    
    -- Swing Pair Context (snapshot of the specific pair used for this alert)
    swing_low_price DECIMAL(20, 8) NOT NULL,
    swing_low_timestamp TIMESTAMPTZ NOT NULL,
    swing_high_price DECIMAL(20, 8) NOT NULL,
    swing_high_timestamp TIMESTAMPTZ NOT NULL,
    
    -- Additional context
    direction VARCHAR(10) CHECK (direction IN ('long', 'short')),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Prevent duplicate alerts for same swing pair at same timestamp
    UNIQUE(symbol_id, timeframe_id, swing_low_price, swing_high_price, timestamp)
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('strategy_alerts', 'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE);

-- Indexes for common queries
CREATE INDEX idx_strategy_alerts_symbol_timeframe ON strategy_alerts(symbol_id, timeframe_id, timestamp DESC);
CREATE INDEX idx_strategy_alerts_risk_score ON strategy_alerts(risk_score);
CREATE INDEX idx_strategy_alerts_direction ON strategy_alerts(direction);
CREATE INDEX idx_strategy_alerts_swing_prices ON strategy_alerts(swing_low_price, swing_high_price);

-- Candle Timestamps (for tracking last processed candles)
CREATE TABLE IF NOT EXISTS candle_timestamps (
    id SERIAL PRIMARY KEY,
    symbol_id INTEGER NOT NULL REFERENCES symbols(symbol_id),
    timeframe_id INTEGER NOT NULL REFERENCES timeframe(timeframe_id),
    last_candle_timestamp BIGINT NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(symbol_id, timeframe_id)
);

CREATE INDEX idx_candle_timestamps_symbol_timeframe ON candle_timestamps(symbol_id, timeframe_id);

-- ============================================================================
-- VIEWS FOR EASY QUERYING
-- ============================================================================

-- Latest strategy alerts view
CREATE OR REPLACE VIEW latest_strategy_alerts AS
SELECT DISTINCT ON (s.symbol_name)
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
ORDER BY s.symbol_name, sa.timestamp DESC;

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

