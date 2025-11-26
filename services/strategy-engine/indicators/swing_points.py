"""
Swing High/Low Detection Module

This module provides functions to detect swing highs and lows in price data,
which are used to identify key price levels for trading strategies.

A swing high is a local maximum where the price is higher than surrounding bars.
A swing low is a local minimum where the price is lower than surrounding bars.

Uses Decimal for exact price comparisons to avoid floating-point precision issues.
"""
from typing import List, Tuple, Optional
from decimal import Decimal
import pandas as pd
import numpy as np
from utils.decimal_utils import to_decimal, to_decimal_safe


def calculate_swing_points(
    df: pd.DataFrame, 
    window: int = 2
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Calculate swing highs and swing lows in a DataFrame using a rolling window approach.

    A swing high is a high that is higher than 'window' bars before and after it.
    A swing low is a low that is lower than 'window' bars before and after it.

    Args:
        df: DataFrame with 'high' and 'low' columns (case-sensitive lowercase).
            Must contain numeric data. Should also have 'unix' column for datetime.
        window: Number of bars to look back and forward for comparison.
                A window of 2 means 2 bars before and 2 bars after (total 5 bars).
                Must be >= 1.

    Returns:
        Tuple of (swing_high_list, swing_low_list) where each list contains
        tuples of (datetime, price). datetime is Unix timestamp from the 'unix' column.

    Raises:
        ValueError: If window is invalid or DataFrame structure is invalid.
    """
    # Input validation
    if df is None:
        return [], []
    
    if not isinstance(df, pd.DataFrame):
        return [], []
    
    if len(df) == 0:
        return [], []
    
    # Validate window parameter
    if not isinstance(window, int) or window < 1:
        return [], []
    
    # Validate required columns exist
    required_columns = ['high', 'low']
    if not all(col in df.columns for col in required_columns):
        return [], []
    
    # Check for minimum data requirement
    min_required = 2 * window + 1
    if len(df) < min_required:
        return [], []
    
    try:
        # Create a copy to avoid modifying the original DataFrame
        df_work = df.copy()
        
        # Validate that high and low columns contain numeric data (including Decimal)
        # Decimal values from PostgreSQL are stored as object dtype, so we check the actual values
        def is_numeric_column(series):
            """Check if a series contains numeric values (int, float, or Decimal)"""
            if pd.api.types.is_numeric_dtype(series):
                return True
            # Check if it's object dtype with numeric values (e.g., Decimal)
            if series.dtype == 'object':
                # Sample a few non-null values to check if they're numeric
                non_null_values = series.dropna()
                if len(non_null_values) > 0:
                    sample_values = non_null_values.head(10)
                    return all(
                        isinstance(val, (int, float, Decimal, np.number))
                        for val in sample_values
                    )
            return False
        
        if not is_numeric_column(df_work['high']) or not is_numeric_column(df_work['low']):
            return [], []
        
        # Check for NaN values in critical columns
        if df_work['high'].isna().all() or df_work['low'].isna().all():
            return [], []
        
        # Calculate rolling window size (center=True means window extends both ways)
        rolling_window = 2 * window + 1
        
        # Use shared Decimal utility for consistency
        
        # Identify Swing Highs
        # A swing high must be the maximum in its rolling window AND have valid neighbors
        high_rolling_max = df_work['high'].rolling(
            window=rolling_window, 
            center=True, 
            min_periods=rolling_window
        ).max()
        
        # Use Decimal for exact comparison to avoid floating point precision issues
        # This is critical for very small price values like SHIB (0.008-0.009 range)
        def decimal_equals(series1, series2):
            """Compare two series using Decimal for exact equality"""
            result = pd.Series(False, index=series1.index)
            for idx in series1.index:
                val1 = series1.loc[idx]
                val2 = series2.loc[idx]
                if pd.notna(val1) and pd.notna(val2):
                    # Convert to Decimal via string to preserve exact precision
                    dec1 = to_decimal(val1)
                    dec2 = to_decimal(val2)
                    result.loc[idx] = (dec1 is not None and dec2 is not None and dec1 == dec2)
            return result
        
        # Check that the high equals the rolling max (it's a local maximum)
        # Use Decimal comparison for exact precision with small price values
        # AND has valid data on both sides
        is_swing_high = (
            decimal_equals(df_work['high'], high_rolling_max) &
            (df_work['high'].shift(window).notna()) &
            (df_work['high'].shift(-window).notna()) &
            (df_work['high'].notna())
        )
        
        # Identify Swing Lows
        # A swing low must be the minimum in its rolling window AND have valid neighbors
        low_rolling_min = df_work['low'].rolling(
            window=rolling_window, 
            center=True, 
            min_periods=rolling_window
        ).min()
        
        # Check that the low equals the rolling min (it's a local minimum)
        # Use Decimal comparison for exact precision with small price values
        # AND has valid data on both sides
        is_swing_low = (
            decimal_equals(df_work['low'], low_rolling_min) &
            (df_work['low'].shift(window).notna()) &
            (df_work['low'].shift(-window).notna()) &
            (df_work['low'].notna())
        )
        
        # Extract swing points as (datetime, price) tuples using vectorized operations
        # float() handles both Decimal and numeric types automatically
        # Get datetime from 'unix' column if available, otherwise use 0
        has_unix = 'unix' in df_work.columns
        
        swing_high_list = [
            (int(df_work['unix'].iloc[idx]) if has_unix and pd.notna(df_work['unix'].iloc[idx]) else 0, float(df_work['high'].iloc[idx]))
            for idx in df_work.index[is_swing_high]
            if pd.notna(df_work['high'].iloc[idx])
        ]
        
        swing_low_list = [
            (int(df_work['unix'].iloc[idx]) if has_unix and pd.notna(df_work['unix'].iloc[idx]) else 0, float(df_work['low'].iloc[idx]))
            for idx in df_work.index[is_swing_low]
            if pd.notna(df_work['low'].iloc[idx])
        ]
        
        return swing_high_list, swing_low_list
        
    except (ValueError, TypeError, KeyError, IndexError) as e:
        # Return empty lists on any error
        return [], []
    except Exception:
        # Catch any other unexpected errors
        return [], []


def filter_between(
    points_main: List[Tuple[int, float]], 
    points_other: List[Tuple[int, float]], 
    keep: str = "min"
) -> List[Tuple[int, float]]:
    """
    Filter points that fall between boundary points.
    
    This function filters points from points_other that fall between consecutive
    points in points_main, keeping either the minimum or maximum value in each interval.
    
    Args:
        points_main: List of (datetime, price) tuples representing boundary points (highs or lows).
                    Must be sorted by datetime.
        points_other: List of (datetime, price) tuples representing points to filter 
                     (opposite of main). Must be sorted by datetime.
        keep: "min" to keep lowest point in each interval, "max" to keep highest.
              Default is "min".
        
    Returns:
        Filtered list of (datetime, price) tuples, sorted by datetime.
        
    Example:
        points_main = [(1000, 100), (2000, 110), (3000, 105)]
        points_other = [(1200, 95), (1500, 98), (2200, 97), (2500, 99)]
        keep = "min"
        Returns points between each pair of main points, keeping the minimum in each interval.
    """
    # Input validation
    if not points_main or not points_other:
        return []
    
    if not isinstance(points_main, list) or not isinstance(points_other, list):
        return []
    
    # Validate keep parameter
    if keep not in ("min", "max"):
        keep = "min"  # Default to min
    
    # If we don't have enough boundary points, return all other points
    if len(points_main) < 2:
        return sorted(points_other.copy(), key=lambda x: x[0]) if points_other else []
    
    # Ensure points are sorted by datetime
    points_main = sorted(points_main, key=lambda x: x[0])
    points_other = sorted(points_other, key=lambda x: x[0])
    
    filtered = []
    
    # Process each interval between consecutive main points
    for i in range(len(points_main) - 1):
        start_dt = points_main[i][0]  # datetime of start point
        end_dt = points_main[i + 1][0]  # datetime of end point
        
        # Skip if datetimes are invalid
        if start_dt >= end_dt:
            continue
        
        # Collect opposite points inside (start, end) - exclusive boundaries
        # Compare based on datetime (position 0)
        inside = [
            p for p in points_other 
            if start_dt < p[0] < end_dt
        ]
        
        if not inside:
            continue
        
        # Select the extreme point based on keep parameter
        # p[1] is the price value
        if keep == "min":
            selected = min(inside, key=lambda x: x[1])
        else:  # keep == "max"
            selected = max(inside, key=lambda x: x[1])
        
        filtered.append(selected)
    
    # Ensure outermost points are preserved if they exist
    # if points_other:
    #     first_point = points_other[0]
    #     last_point = points_other[-1]
        
    #     # Add left-most point if not already included
    #     if first_point not in filtered:
    #         filtered.insert(0, first_point)
        
    #     # Add right-most point if not already included
    #     if last_point not in filtered:
    #         filtered.append(last_point)
    
    # Return sorted by datetime to ensure consistent ordering
    return sorted(filtered, key=lambda x: x[0])


def enforce_strict_alternation(
    highs: List[Tuple[int, float]], 
    lows: List[Tuple[int, float]]
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Enforce strict alternation between swing highs and lows.
    
    If two highs or two lows appear consecutively, keep only the more extreme one.
    This ensures that swing points alternate: high, low, high, low, etc.
    
    Uses Decimal for exact price comparisons to handle very small price values.
    
    Args:
        highs: List of (datetime, price) tuples for swing highs.
        lows: List of (datetime, price) tuples for swing lows.
        
    Returns:
        Tuple of (filtered_highs, filtered_lows) with strict alternation enforced.
        Both lists are sorted by datetime.
    """
    # Input validation
    if not highs and not lows:
        return [], []
    
    if not isinstance(highs, list) or not isinstance(lows, list):
        return [], []
    
    # Helper function to convert price to Decimal for exact comparison
    def price_to_decimal(price):
        """Convert price to Decimal for exact comparison"""
        if isinstance(price, Decimal):
            return price
        return Decimal(str(price))
    
    # Sort by datetime to ensure chronological order
    highs = sorted(highs, key=lambda x: x[0])
    lows = sorted(lows, key=lambda x: x[0])
    
    # Merge lists with type markers for easier processing
    # highs and lows are (datetime, price) tuples
    merged = [(dt, val, 'H') for dt, val in highs] + \
             [(dt, val, 'L') for dt, val in lows]
    merged.sort(key=lambda x: x[0])
    
    if not merged:
        return [], []
    
    final_highs = []
    final_lows = []
    last_type = None
    
    for dt, val, point_type in merged:
        # Validate tuple structure
        if not isinstance(dt, (int, np.integer)) or not isinstance(val, (int, float, np.floating, Decimal)):
            continue
        
        # Convert price to Decimal for exact comparison
        val_decimal = to_decimal(val)
        if val_decimal is None:
            continue
        
        # If two of the same type appear consecutively, keep only the more extreme one
        if point_type == last_type:
            if point_type == 'H':
                # For highs, keep the higher one using Decimal comparison
                if final_highs:
                    last_price_decimal = to_decimal(final_highs[-1][1])
                    if last_price_decimal is not None and val_decimal > last_price_decimal:
                        final_highs[-1] = (dt, val)
            else:  # point_type == 'L'
                # For lows, keep the lower one using Decimal comparison
                if final_lows:
                    last_price_decimal = to_decimal(final_lows[-1][1])
                    if last_price_decimal is not None and val_decimal < last_price_decimal:
                        final_lows[-1] = (dt, val)
        else:
            # Different type - add to appropriate list
            if point_type == 'H':
                final_highs.append((dt, val))
            else:  # point_type == 'L'
                final_lows.append((dt, val))
        
        last_type = point_type
    
    return final_highs, final_lows


def filter_rate(
    highs: List[Tuple[int, float]], 
    lows: List[Tuple[int, float]], 
    rate: float = 0.03
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Filter swing points based on minimum price movement rate (percentage).
    
    This function removes swing points that don't meet the minimum price movement
    requirement, helping to filter out noise and keep only significant swings.
    
    Rules:
    1. For each swing high, compare with nearest left and right swing lows based on datetime
    2. Calculate percentage move from each low to the high
    3. If both moves are < rate: remove the high, keep the lower of the two lows
    4. If only left move < rate: remove the high and the left low
    5. If only right move < rate: remove the high and the right low
    6. If both moves >= rate: keep the high
    7. Finally, enforce strict alternation
    
    Args:
        highs: List of (datetime, price) tuples for swing highs. Should be sorted by datetime.
        lows: List of (datetime, price) tuples for swing lows. Should be sorted by datetime.
        rate: Minimum percentage move required (e.g., 0.03 = 3%). Must be > 0.
        
    Returns:
        Tuple of (filtered_highs, filtered_lows) with points that meet the rate requirement.
        Both lists are sorted by datetime.
    """
    # Input validation
    if not highs and not lows:
        return [], []
    
    if not isinstance(highs, list) or not isinstance(lows, list):
        return [], []
    
    # Validate rate
    if not isinstance(rate, (int, float)) or rate <= 0:
        # If rate is invalid, return copies of original lists
        return highs.copy() if highs else [], lows.copy() if lows else []
    
    # Create copies to avoid modifying original lists
    # Sort by datetime (position 0)
    highs = sorted(highs, key=lambda x: x[0])
    lows = sorted(lows, key=lambda x: x[0])
    
    # Build new clean lists
    clean_highs = []
    clean_lows = lows.copy()  # Start with all lows, remove as needed
    
    # Convert rate to Decimal for exact comparison
    rate_decimal = to_decimal_safe(rate)
    
    # Process each swing high
    for h_dt, h_val in highs:
        # Validate high tuple
        if not isinstance(h_dt, (int, np.integer)) or not isinstance(h_val, (int, float, np.floating, Decimal)):
            continue
        
        # Convert high value to Decimal
        h_val_decimal = to_decimal(h_val)
        if h_val_decimal is None or h_val_decimal <= 0:
            continue  # Invalid price
        
        # Find nearest left low (after this high - later in time)
        # clean_lows is sorted by datetime ascending, so lows after h_dt are also sorted ascending
        # The first one (index 0) is the nearest one after the high
        left_candidates = [l for l in clean_lows if l[0] > h_dt]
        left_low = left_candidates[0] if left_candidates else None
        
        # Find nearest right low (before this high - earlier in time)
        # clean_lows is sorted by datetime ascending, so lows before h_dt are also sorted ascending
        # The last one (index -1) is the nearest one before the high
        right_candidates = [l for l in clean_lows if l[0] < h_dt]
        right_low = right_candidates[-1] if right_candidates else None
        
        # Edge case: keep high if no left OR right low exists
        if left_low is None or right_low is None:
            clean_highs.append((h_dt, h_val))
            continue
        
        # Convert low prices to Decimal
        left_low_decimal = to_decimal(left_low[1])
        right_low_decimal = to_decimal(right_low[1])
        
        if left_low_decimal is None or right_low_decimal is None:
            continue
        
        # Validate low prices
        if left_low_decimal <= 0 or right_low_decimal <= 0:
            continue  # Invalid prices
        
        # Compute percentage move (price increase from low to high) using Decimal
        try:
            left_rate = (h_val_decimal - left_low_decimal) / left_low_decimal
            right_rate = (h_val_decimal - right_low_decimal) / right_low_decimal
        except (ZeroDivisionError, TypeError, ValueError):
            # Skip if we can't calculate rates
            continue
        
        # CASE 1: Both sides fail the rate requirement
        if left_rate < rate_decimal and right_rate < rate_decimal:
            # Remove the HIGH completely
            # Keep the lower of the two lows (more significant) using Decimal comparison
            lower_low = left_low if left_low_decimal < right_low_decimal else right_low
            
            # Remove both lows from clean_lows, then add back the lower one
            clean_lows = [
                l for l in clean_lows 
                if l not in (left_low, right_low)
            ]
            if lower_low not in clean_lows:
                clean_lows.append(lower_low)
                clean_lows.sort(key=lambda x: x[0])  # Maintain sorted order by datetime
            continue
        
        # CASE 2: Only left side fails the rate requirement
        if left_rate < rate_decimal:
            # Remove the left low and the high
            if left_low in clean_lows:
                clean_lows.remove(left_low)
            continue  # Don't add high to clean_highs
        
        # CASE 3: Only right side fails the rate requirement
        if right_rate < rate_decimal:
            # Remove the right low and the high
            if right_low in clean_lows:
                clean_lows.remove(right_low)
            continue  # Don't add high to clean_highs
        
        # CASE 4: Both rates meet the requirement → keep the high
        clean_highs.append((h_dt, h_val))
    
    # Final step: enforce strict alternation to ensure proper high-low-high-low pattern
    clean_highs, clean_lows = enforce_strict_alternation(clean_highs, clean_lows)
    
    return clean_highs, clean_lows

