"""
Support and Resistance Level Detection

This module provides functions to detect support and resistance levels in price data.
Support levels are price points where the price tends to bounce upward.
Resistance levels are price points where the price tends to bounce downward.
"""


def support(
    df, 
    candle_index: int, 
    before_candle_count: int, 
    after_candle_count: int, 
    high_timeframe_flag: bool
) -> bool | None:
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
    df, 
    candle_index: int, 
    before_candle_count: int, 
    after_candle_count: int, 
    high_timeframe_flag: bool
) -> bool | None:
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
