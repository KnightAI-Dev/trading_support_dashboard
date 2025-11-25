"""
Support and Resistance Level Detection

This module provides functions to detect support and resistance levels in price data.
Support levels are price points where the price tends to bounce upward.
Resistance levels are price points where the price tends to bounce downward.
"""
from typing import List, Tuple, Optional
import pandas as pd


def support(
    df: pd.DataFrame, 
    candle_index: int, 
    before_candle_count: int, 
    after_candle_count: int, 
    high_timeframe_flag: bool
) -> Optional[bool]:
    """
    Check if the candle at the given index forms a support level.
    
    A support level is identified when:
    - The price (low for LTF, open for HTF) at candle_index is the lowest point
    - In the window of before_candle_count candles before and after_candle_count candles after
    
    Args:
        df: pandas DataFrame with OHLC data (must have 'low', 'high', 'open', 'close' columns)
        candle_index: The index of the candle to check for support level
        before_candle_count: Number of candles to check before the candle_index
        after_candle_count: Number of candles to check after the candle_index
        high_timeframe_flag: If True, use 'open' price for HTF analysis. If False, use 'low' price for LTF analysis.
    
    Returns:
        True if the candle forms a support level, False otherwise.
        None if there are any errors (missing keys, index out of range, etc.)
    """
    try:
        # Validate inputs
        if df is None or len(df) == 0:
            return None
        
        if candle_index < before_candle_count or candle_index >= len(df) - after_candle_count:
            return None
        
        # Determine which price column to use
        if high_timeframe_flag:
            price_column = df['open']
        else:
            price_column = df['low']
        
        # Get the price at the candidate support level
        support_price = price_column.iloc[candle_index]
        
        # Check all candles in the before window
        before_start = candle_index - before_candle_count
        before_end = candle_index
        
        for i in range(before_start, before_end):
            if price_column.iloc[i] < support_price:
                return False  # Found a lower price before, not a support
        
        # Check all candles in the after window
        after_start = candle_index + 1
        after_end = candle_index + after_candle_count + 1
        
        for i in range(after_start, after_end):
            if price_column.iloc[i] < support_price:
                return False  # Found a lower price after, not a support
        
        # If we get here, this candle has the lowest price in the window
        return True
        
    except (KeyError, IndexError, AttributeError, TypeError) as e:
        # Return None on any error (missing columns, index out of range, etc.)
        return None


def resistance(
    df: pd.DataFrame, 
    candle_index: int, 
    before_candle_count: int, 
    after_candle_count: int, 
    high_timeframe_flag: bool
) -> Optional[bool]:
    """
    Check if the candle at the given index forms a resistance level.
    
    A resistance level is identified when:
    - The price (high for LTF, close for HTF) at candle_index is the highest point
    - In the window of before_candle_count candles before and after_candle_count candles after
    
    Args:
        df: pandas DataFrame with OHLC data (must have 'low', 'high', 'open', 'close' columns)
        candle_index: The index of the candle to check for resistance level
        before_candle_count: Number of candles to check before the candle_index
        after_candle_count: Number of candles to check after the candle_index
        high_timeframe_flag: If True, use 'close' price for HTF analysis. If False, use 'high' price for LTF analysis.
    
    Returns:
        True if the candle forms a resistance level, False otherwise.
        None if there are any errors (missing keys, index out of range, etc.)
    """
    try:
        # Validate inputs
        if df is None or len(df) == 0:
            return None
        
        if candle_index < before_candle_count or candle_index >= len(df) - after_candle_count:
            return None
        
        # Determine which price column to use
        if high_timeframe_flag:
            price_column = df['close']
        else:
            price_column = df['high']
        
        # Get the price at the candidate resistance level
        resistance_price = price_column.iloc[candle_index]
        
        # Check all candles in the before window
        before_start = candle_index - before_candle_count
        before_end = candle_index
        
        for i in range(before_start, before_end):
            if price_column.iloc[i] > resistance_price:
                return False  # Found a higher price before, not a resistance
        
        # Check all candles in the after window
        after_start = candle_index + 1
        after_end = candle_index + after_candle_count + 1
        
        for i in range(after_start, after_end):
            if price_column.iloc[i] > resistance_price:
                return False  # Found a higher price after, not a resistance
        
        # If we get here, this candle has the highest price in the window
        return True
        
    except (KeyError, IndexError, AttributeError, TypeError) as e:
        # Return None on any error (missing columns, index out of range, etc.)
        return None


def get_support_resistance_levels(
    timeframe_ticker_df: pd.DataFrame, 
    high_timeframe_flag: bool,
    sensible_window: int = 2
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Calculate support and resistance levels from the DataFrame.
    
    Args:
        timeframe_ticker_df: pandas DataFrame with OHLC data (should have 'unix' column for timestamps)
        high_timeframe_flag: If True, uses open/close for HTF analysis. If False, uses low/high for LTF analysis.
        sensible_window: Number of candles to check after the candidate level (default: 2)
            
    Returns:
        Tuple of (support_level_list, resistance_level_list) where each list contains
        tuples of (unix_timestamp, price)
    """
    support_level_list = []
    resistance_level_list = []
    
    # Input validation
    if timeframe_ticker_df is None or not hasattr(timeframe_ticker_df, '__len__'):
        return support_level_list, resistance_level_list
    
    if len(timeframe_ticker_df) < 4:  # Need at least 4 rows for range(3, len-1) to work
        return support_level_list, resistance_level_list
    
    # Check required columns exist
    required_columns = ['low', 'high']
    if not all(col in timeframe_ticker_df.columns for col in required_columns):
        return support_level_list, resistance_level_list
    
    # Check if 'unix' column exists for timestamps
    has_unix = 'unix' in timeframe_ticker_df.columns
            
    # backward 3, forward sensible_window
    for sens_row in range(3, len(timeframe_ticker_df) - 1):
        try:
            # Get unix timestamp if available, otherwise use index as fallback
            if has_unix and pd.notna(timeframe_ticker_df['unix'].iloc[sens_row]):
                unix_timestamp = int(timeframe_ticker_df['unix'].iloc[sens_row])
            else:
                # Fallback to index if unix column is not available
                unix_timestamp = sens_row
            
            # Check for support level
            support_result = support(
                timeframe_ticker_df, 
                sens_row, 
                3,  # before_candle_count
                sensible_window,  # after_candle_count
                high_timeframe_flag
            )
            if support_result is True:
                support_level_list.append((unix_timestamp, float(timeframe_ticker_df.low[sens_row])))
            
            # Check for resistance level
            resistance_result = resistance(
                timeframe_ticker_df, 
                sens_row, 
                3,  # before_candle_count
                sensible_window,  # after_candle_count
                high_timeframe_flag
            )
            if resistance_result is True:
                resistance_level_list.append((unix_timestamp, float(timeframe_ticker_df.high[sens_row])))
                
        except (KeyError, IndexError, TypeError) as e:
            # Skip this row if there's an error accessing the data
            continue
        
    return support_level_list, resistance_level_list
