"""
Order Blocks Detection Module

This module provides functions to calculate order blocks from swing points
using the Smart Money Concepts (SMC) methodology.

Order blocks are price zones where institutional traders placed large orders,
identified by the last bullish/bearish candle before a swing point break.
"""
from typing import Optional, List, Tuple
import pandas as pd
from indicators.swing_points import swing_points_to_dataframe
from indicators.smc import smc


def get_order_blocks(
    ohlc_df: pd.DataFrame,
    swing_highs: List[Tuple[int, float]],
    swing_lows: List[Tuple[int, float]],
    close_mitigation: bool = False
) -> Optional[pd.DataFrame]:
    """
    Calculate order blocks from pre-calculated swing points.
    
    This function takes already-calculated and filtered swing points,
    converts them to DataFrame format, and calculates order blocks using
    the SMC methodology.
    
    Args:
        ohlc_df: DataFrame with OHLC data. Must have columns:
                 ['open', 'high', 'low', 'close', 'volume', 'unix']
        swing_highs: List of (unix_timestamp, price) tuples for swing highs.
                    Should already be filtered and cleaned.
        swing_lows: List of (unix_timestamp, price) tuples for swing lows.
                   Should already be filtered and cleaned.
        close_mitigation: If True, order block mitigation uses close price.
                         If False, uses high/low. Default: False
        
    Returns:
        DataFrame with order blocks containing columns:
        - OB: 1 (bullish), -1 (bearish), or NaN
        - Top: Top price of the order block
        - Bottom: Bottom price of the order block
        - OBVolume: Volume calculation (current + 2 previous volumes)
        - Percentage: Strength percentage of the order block
        - Timestamp: Unix timestamp of the order block candle
        - MitigatedIndex: Index where OB was mitigated (NaN if still active)
        - MitigatedTimestamp: Unix timestamp where OB was mitigated (None if still active)
        
        Returns None if:
        - Input DataFrame is None or empty
        - 'unix' column is missing
        - No swing points provided
        - Error occurs during calculation
        
    Example:
        # First, calculate and filter swing points separately
        from indicators.swing_points import (
            calculate_swing_points,
            enforce_strict_alternation,
            filter_between,
            filter_rate
        )
        
        # Calculate swing points
        swing_highs, swing_lows = calculate_swing_points(ohlc_df, window=2)
        
        # Filter and clean (apply your own parameters)
        swing_highs, swing_lows = enforce_strict_alternation(swing_highs, swing_lows)
        filtered_swing_lows = filter_between(swing_highs, swing_lows, keep="min")
        filtered_swing_highs = filter_between(swing_lows, swing_highs, keep="max")
        swing_highs, swing_lows = filter_rate(
            filtered_swing_highs,
            filtered_swing_lows,
            rate=0.03  # Your own rate
        )
        swing_highs, swing_lows = enforce_strict_alternation(swing_highs, swing_lows)
        
        # Then calculate order blocks
        order_blocks = get_order_blocks(
            ohlc_df=ohlc_df,
            swing_highs=swing_highs,
            swing_lows=swing_lows,
            close_mitigation=False
        )
        
        # Access results
        if order_blocks is not None:
            bullish_obs = order_blocks[order_blocks['OB'] == 1]
            bearish_obs = order_blocks[order_blocks['OB'] == -1]
            active_obs = order_blocks[order_blocks['MitigatedIndex'].isna()]
            
            # Access timestamps
            for idx, row in active_obs.iterrows():
                print(f"Order Block at timestamp: {row['Timestamp']}")
                print(f"Price range: {row['Bottom']} - {row['Top']}")
                if pd.notna(row['MitigatedTimestamp']):
                    print(f"Mitigated at: {row['MitigatedTimestamp']}")
    """
    # Input validation
    if ohlc_df is None or len(ohlc_df) == 0:
        return None
    
    # Check required columns
    required_columns = ['open', 'high', 'low', 'close', 'volume', 'unix']
    if not all(col in ohlc_df.columns for col in required_columns):
        missing = [col for col in required_columns if col not in ohlc_df.columns]
        print(f"Missing required columns: {missing}")
        return None
    
    # Check if swing points are provided
    if not swing_highs and not swing_lows:
        return None
    
    try:
        # Step 1: Convert swing points to DataFrame format required by smc.ob()
        swing_hl_df = swing_points_to_dataframe(
            ohlc_df,
            swing_highs,
            swing_lows
        )
        
        # Step 2: Calculate order blocks using SMC methodology
        order_blocks = smc.ob(
            ohlc_df,
            swing_hl_df,
            close_mitigation=close_mitigation
        )
        
        # Step 3: Add timestamps to order blocks
        # Map index to unix timestamp from ohlc_df
        def get_timestamp(idx):
            """Get timestamp for order block index"""
            if idx in ohlc_df.index:
                return ohlc_df.loc[idx, 'unix']
            return None
        
        order_blocks['Timestamp'] = order_blocks.index.map(get_timestamp)
        
        # Add mitigated timestamp (map MitigatedIndex to unix timestamp)
        def get_mitigated_timestamp(row):
            """Get timestamp for mitigated index if it exists"""
            if pd.notna(row['MitigatedIndex']):
                try:
                    mitigated_idx = int(row['MitigatedIndex'])
                    if mitigated_idx in ohlc_df.index:
                        return ohlc_df.loc[mitigated_idx, 'unix']
                except (ValueError, TypeError):
                    pass
            return None
        
        order_blocks['MitigatedTimestamp'] = order_blocks.apply(
            get_mitigated_timestamp, axis=1
        )
        
        # Reorder columns for better readability
        column_order = [
            'OB', 'Top', 'Bottom', 'OBVolume', 'Percentage',
            'Timestamp', 'MitigatedIndex', 'MitigatedTimestamp'
        ]
        order_blocks = order_blocks[column_order]
        
        return order_blocks
        
    except Exception as e:
        print(f"Error calculating order blocks: {e}")
        import traceback
        traceback.print_exc()
        return None

