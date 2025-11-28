-- Migration: Remove Order Block fields from strategy_alerts table
-- Date: 2024
-- Description: Removes order block columns that were added but are no longer needed

-- Drop indexes first
DROP INDEX IF EXISTS idx_strategy_alerts_ob_type;
DROP INDEX IF EXISTS idx_strategy_alerts_ob_timestamp;

-- Remove order block columns from strategy_alerts table
ALTER TABLE strategy_alerts
    DROP COLUMN IF EXISTS ob_top,
    DROP COLUMN IF EXISTS ob_bottom,
    DROP COLUMN IF EXISTS ob_type,
    DROP COLUMN IF EXISTS ob_timestamp,
    DROP COLUMN IF EXISTS order_blocks;

-- Restore the latest_strategy_alerts view to original format (without order block fields)
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

