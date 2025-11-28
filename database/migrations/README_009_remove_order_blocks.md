# Migration 009: Remove Order Blocks from Strategy Alerts

## Overview
This migration removes the order block fields from the `strategy_alerts` table that were previously added.

## Changes

### Database Schema
- Removes `ob_top` column
- Removes `ob_bottom` column
- Removes `ob_type` column
- Removes `ob_timestamp` column
- Removes `order_blocks` JSONB column

### Indexes
- Drops `idx_strategy_alerts_ob_type` index
- Drops `idx_strategy_alerts_ob_timestamp` index

### View Updates
- Restores `latest_strategy_alerts` view to original format (without order block fields)

## Migration Instructions

1. **Run the migration:**
   ```bash
   psql -U trading_user -d trading_db -f database/migrations/009_remove_order_blocks_from_strategy_alerts.sql
   ```

2. **Verify the migration:**
   ```sql
   -- Check that columns were removed
   SELECT column_name 
   FROM information_schema.columns 
   WHERE table_name = 'strategy_alerts' 
   AND (column_name LIKE 'ob_%' OR column_name = 'order_blocks');
   -- Should return no rows
   
   -- Check indexes were removed
   SELECT indexname FROM pg_indexes 
   WHERE tablename = 'strategy_alerts' 
   AND indexname LIKE '%ob_%';
   -- Should return no rows
   ```

## Notes

- This migration is safe to run even if the columns don't exist (uses IF EXISTS)
- All data in order block columns will be permanently deleted
- The view is restored to its original format
- This migration is idempotent - safe to run multiple times

