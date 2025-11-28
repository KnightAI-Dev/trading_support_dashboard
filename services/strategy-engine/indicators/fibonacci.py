"""
Fibonacci Level Calculation

This module provides functions to calculate Fibonacci retracement and extension levels
from swing highs and lows. Uses Decimal for exact price calculations to avoid
floating-point precision issues with very small price values.
"""
from typing import List, Tuple, Optional
from decimal import Decimal
from core.models import FibResult
from config.settings import StrategyConfig
from utils.decimal_utils import to_decimal, to_decimal_safe


def calculate_fibonacci_levels(
    swing_highs: List[Tuple[int, float]], 
    swing_lows: List[Tuple[int, float]], 
    timeframe: str,
    config: StrategyConfig
) -> List[FibResult]:
    """
    Calculate Fibonacci levels from swing highs and lows.
    
    Args:
        swing_highs: List of (datetime, price) tuples for swing highs
        swing_lows: List of (datetime, price) tuples for swing lows
        timeframe: Timeframe string (e.g., "4h", "30m")
        config: StrategyConfig instance with Fibonacci level parameters
        
    Returns:
        List of FibResult objects with calculated Fibonacci levels
    """
    output: List[FibResult] = []
    
    # Input validation
    if not isinstance(swing_lows, (list, tuple)) or not swing_lows:
        return output
    
    if not isinstance(swing_highs, (list, tuple)):
        swing_highs = []
    
    if not isinstance(timeframe, str):
        timeframe = ""
    
    # Pre-validate and filter swing highs for efficiency
    # Use Decimal for price validation to handle very small values
    valid_highs = []
    for swing_high in swing_highs:
        if not isinstance(swing_high, (list, tuple)) or len(swing_high) < 2:
            continue
        try:
            h_dt, h_price = swing_high[0], swing_high[1]
            # Validate datetime and price
            if not isinstance(h_dt, (int, float)):
                continue
            
            # Convert price to Decimal for exact validation
            h_price_decimal = to_decimal(h_price)
            if h_price_decimal is None or h_price_decimal <= 0:
                continue
            
            valid_highs.append((int(h_dt), float(h_price)))
        except (IndexError, TypeError, ValueError):
            continue
    
    # Sort valid highs by datetime for efficient searching
    valid_highs.sort(key=lambda x: x[0])
    
    # Process each swing low
    for swing_low in swing_lows:
        # Validate swing_low structure
        if not isinstance(swing_low, (list, tuple)) or len(swing_low) < 2:
            continue
        
        try:
            low_dt, low_price = swing_low[0], swing_low[1]
        except (IndexError, TypeError):
            continue
        
        # Validate datetime
        if not isinstance(low_dt, (int, float)):
            continue
        
        low_dt = int(low_dt)
        
        # Convert price to Decimal for exact validation
        low_price_decimal = to_decimal(low_price)
        if low_price_decimal is None or low_price_decimal <= 0:
            continue
        
        low_price = float(low_price)
        
        # Find RIGHT HIGH (later in time - after this low)
        # This is the first swing high that occurs after this low
        right_high = None
        for h_dt, h_price in valid_highs:
            if h_dt > low_dt:  # Compare datetime, not index
                right_high = (h_dt, h_price)
                # Found the first high after the low, can break
                break
        
        # Find LEFT HIGH (earlier in time - before this low)
        # This is the last swing high that occurs before this low (nearest to the low)
        left_high = None
        for h_dt, h_price in valid_highs:
            if h_dt < low_dt:  # Compare datetime, not index
                left_high = (h_dt, h_price)
                # Keep updating until we find one >= low_dt (since list is sorted ascending)
            else:
                # Since valid_highs is sorted, we can break once we pass the low datetime
                break
        
        # Calculate Bullish Fibonacci levels (extension from low to right high)
        if right_high is not None:
            rh_dt, rh_price = right_high
            
            # Convert prices to Decimal for exact comparison and calculation
            rh_price_decimal = to_decimal(rh_price)
            low_price_decimal = to_decimal(low_price)
            
            # Validate price relationship using Decimal (high should be above low)
            if rh_price_decimal is not None and low_price_decimal is not None and rh_price_decimal > low_price_decimal:
                try:
                    # Use Decimal for exact arithmetic
                    price_diff = rh_price_decimal - low_price_decimal
                    
                    # Convert config value to Decimal
                    bull_lower_factor = to_decimal_safe(config.bullish_fib_level_lower)
                    
                    # Calculate bullish extension level using Decimal
                    fib_bull_lower_decimal = rh_price_decimal - price_diff * bull_lower_factor
                    
                    # Ensure fib level is above the low (safety check using Decimal)
                    fib_bull_lower_decimal = max(low_price_decimal, fib_bull_lower_decimal)
                    
                    # Convert back to float for return value
                    fib_bull_lower_level = float(fib_bull_lower_decimal)
                    
                    # Create FibResult for bull
                    output.append(
                        FibResult(
                            timeframe=timeframe,
                            swing_low=(low_dt, low_price),
                            swing_high=(rh_dt, rh_price),
                            fib_level=fib_bull_lower_level,
                            fib_type="bull"
                        )
                    )
                except (TypeError, ValueError, OverflowError):
                    # Skip if calculation fails
                    pass
        
        # Calculate Bearish Fibonacci level (retracement from left high to low)
        if left_high is not None:
            lh_dt, lh_price = left_high
            
            # Convert prices to Decimal for exact comparison and calculation
            lh_price_decimal = to_decimal(lh_price)
            low_price_decimal = to_decimal(low_price)
            
            # Validate price relationship using Decimal (high should be above low)
            if lh_price_decimal is not None and low_price_decimal is not None and lh_price_decimal > low_price_decimal:
                try:
                    # Use Decimal for exact arithmetic
                    price_diff = lh_price_decimal - low_price_decimal
                    
                    # Convert config value to Decimal
                    bear_factor = to_decimal_safe(config.bearish_fib_level)
                    
                    # Calculate bearish retracement level using Decimal
                    fib_bear_decimal = low_price_decimal + price_diff * bear_factor
                    
                    # Ensure the fib level is between low and high (safety check using Decimal)
                    fib_bear_decimal = max(low_price_decimal, min(lh_price_decimal, fib_bear_decimal))
                    
                    # Convert back to float for return value
                    fib_bear_level = float(fib_bear_decimal)
                    
                    # Create separate FibResult for bear
                    output.append(
                        FibResult(
                            timeframe=timeframe,
                            swing_low=(low_dt, low_price),
                            swing_high=(lh_dt, lh_price),
                            fib_level=fib_bear_level,
                            fib_type="bear"
                        )
                    )
                except (TypeError, ValueError, OverflowError):
                    # Skip if calculation fails
                    pass
    
    return output

