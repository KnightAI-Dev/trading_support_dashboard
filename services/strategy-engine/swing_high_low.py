"""
Swing High/Low Detection Module

This module provides functions to detect swing highs and lows in price data,
which are used to identify key price levels for trading strategies.
"""
from typing import List, Tuple
import pandas as pd
import numpy as np


def calculate_swing_points(df: pd.DataFrame, window: int = 2) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Calculates swing highs and swing lows in a DataFrame.

    A swing high is a high that is higher than 'window' bars before and after it.
    A swing low is a low that is lower than 'window' bars before and after it.

    Args:
        df: DataFrame with 'high' and 'low' columns (case-sensitive lowercase)
        window: Number of bars to look back and forward for comparison.
                A window of 2 means 2 bars before and 2 bars after.

    Returns:
        Tuple of (swing_high_list, swing_low_list) where each list contains
        tuples of (index, price)
    """
    if df is None or len(df) == 0:
        return [], []
    
    # Validate required columns
    if 'high' not in df.columns or 'low' not in df.columns:
        return [], []
    
    # Need at least 2*window+1 candles to detect swing points
    if len(df) < 2 * window + 1:
        return [], []
    
    try:
        # Create copies to avoid modifying original DataFrame
        df = df.copy()
        
        # Initialize swing point columns
        df['SwingHigh'] = False
        df['SwingLow'] = False

        # Identify Swing Highs
        # A swing high is a high that is higher than 'window' bars before and after it.
        rolling_window = 2 * window + 1
        df['SwingHigh'] = np.where(
            (df['high'] == df['high'].rolling(window=rolling_window, center=True).max()) &
            (df['high'].shift(window).notna()) &
            (df['high'].shift(-window).notna()),
            df['high'],
            False
        )

        # Identify Swing Lows
        # A swing low is a low that is lower than 'window' bars before and after it.
        df['SwingLow'] = np.where(
            (df['low'] == df['low'].rolling(window=rolling_window, center=True).min()) &
            (df['low'].shift(window).notna()) &
            (df['low'].shift(-window).notna()),
            df['low'],
            False
        )
        
        # Extract swing points as (index, price) tuples
        swing_high_list = []
        swing_low_list = []
        
        for idx in range(len(df)):
            swing_high_value = df["SwingHigh"].iloc[idx]
            swing_low_value = df["SwingLow"].iloc[idx]
            
            # Check if value is truthy and not False (numpy/pandas can return 0.0 which is falsy)
            if swing_high_value and swing_high_value != False:
                swing_high_list.append((idx, float(swing_high_value)))
            if swing_low_value and swing_low_value != False:
                swing_low_list.append((idx, float(swing_low_value)))
        
        return swing_high_list, swing_low_list
        
    except Exception as e:
        # Return empty lists on any error
        return [], []

def filter_between(points_main: List[Tuple[int, float]], points_other: List[Tuple[int, float]], keep: str = "min") -> List[Tuple[int, float]]:
    """
    Filter points that fall between boundary points.
    
    This function filters points from points_other that fall between consecutive
    points in points_main, keeping either the minimum or maximum value in each interval.
    
    Args:
        points_main: List of (index, value) tuples representing boundary points (highs or lows)
        points_other: List of (index, value) tuples representing points to filter (opposite of main)
        keep: "min" to keep lowest point in each interval, "max" to keep highest
        
    Returns:
        Filtered list of (index, value) tuples
    """
    if not points_main or not points_other:
        return []
    
    if len(points_main) < 2:
        return points_other.copy() if points_other else []

    filtered = []

    for i in range(len(points_main) - 1):
        start_idx = points_main[i][0]
        end_idx = points_main[i + 1][0]

        # Collect opposite points inside (start, end)
        inside = [
            p for p in points_other 
            if start_idx < p[0] < end_idx
        ]

        if len(inside) == 0:
            continue

        if keep == "min":
            selected = min(inside, key=lambda x: x[1])
        else:
            selected = max(inside, key=lambda x: x[1])

        filtered.append(selected)

    # Ensure outermost points are preserved
    if points_other:
        # Add left-most point if not included
        if points_other[0] not in filtered:
            filtered.insert(0, points_other[0])

        # Add right-most point if not included
        if points_other[-1] not in filtered:
            filtered.append(points_other[-1])

    return filtered

def enforce_strict_alternation(highs: List[Tuple[int, float]], lows: List[Tuple[int, float]]) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Enforce strict alternation between swing highs and lows.
    
    If two highs or two lows appear consecutively, keep only the more extreme one.
    
    Args:
        highs: List of (index, price) tuples for swing highs
        lows: List of (index, price) tuples for swing lows
        
    Returns:
        Tuple of (filtered_highs, filtered_lows) with strict alternation enforced
    """
    if not highs and not lows:
        return [], []
    
    highs = sorted(highs, key=lambda x: x[0])
    lows = sorted(lows, key=lambda x: x[0])

    # Merge lists with type markers
    merged = [(i, v, 'H') for i, v in highs] + \
             [(i, v, 'L') for i, v in lows]
    merged.sort(key=lambda x: x[0])

    final_highs = []
    final_lows = []

    last_type = None

    for idx, val, t in merged:
        # If two of the same type in a row, keep only the more extreme one
        if t == last_type:
            if t == 'H':
                if val > final_highs[-1][1]:
                    final_highs[-1] = (idx, val)
            else:  # 'L'
                if val < final_lows[-1][1]:
                    final_lows[-1] = (idx, val)
        else:
            if t == 'H':
                final_highs.append((idx, val))
            else:  # 'L'
                final_lows.append((idx, val))

        last_type = t

    return final_highs, final_lows


def filter_rate(highs: List[Tuple[int, float]], lows: List[Tuple[int, float]], rate: float = 0.03) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Filter swing points based on minimum price movement rate.
    
    Rules:
    - Always keep the first and last swing points
    - For each swing high, compare with nearest left/right lows
    - Remove swing high when low-to-high move is < rate
    - Remove only the low that fails the rule
    - If both lows fail, remove high and keep the LOWER of the two lows
    
    Args:
        highs: List of (index, price) tuples for swing highs
        lows: List of (index, price) tuples for swing lows
        rate: Minimum percentage move required (e.g., 0.03 = 3%)
        
    Returns:
        Tuple of (filtered_highs, filtered_lows)
    """
    if not highs and not lows:
        return [], []
    
    if rate <= 0:
        return highs.copy(), lows.copy()

    highs = highs.copy()
    lows = lows.copy()

    # Build new clean lists
    clean_highs = []
    clean_lows = lows.copy()

    for h_idx, h_val in highs:
        # Find nearest left low
        left_candidates = [l for l in clean_lows if l[0] < h_idx]
        left_low = left_candidates[-1] if left_candidates else None

        # Find nearest right low
        right_candidates = [l for l in clean_lows if l[0] > h_idx]
        right_low = right_candidates[0] if right_candidates else None

        # Edge case: keep if no left OR right low
        if left_low is None or right_low is None:
            clean_highs.append((h_idx, h_val))
            continue

        # Compute % move (price increase from low to high)
        try:
            left_rate = (h_val - left_low[1]) / left_low[1] if left_low[1] > 0 else 0
            right_rate = (h_val - right_low[1]) / right_low[1] if right_low[1] > 0 else 0
        except (ZeroDivisionError, TypeError):
            # Skip if we can't calculate rates
            continue

        # CASE 1: both sides < rate
        if left_rate < rate and right_rate < rate:
            # Remove the HIGH completely
            # Keep the lower of the two lows
            lower_low = left_low if left_low[1] < right_low[1] else right_low
            clean_lows = [l for l in clean_lows if l == lower_low or l not in (left_low, right_low)]
            continue

        # CASE 2: left < rate only
        if left_rate < rate:
            if left_low in clean_lows:
                clean_lows.remove(left_low)
            continue  # Remove high too

        # CASE 3: right < rate only
        if right_rate < rate:
            if right_low in clean_lows:
                clean_lows.remove(right_low)
            continue  # Remove high too

        # CASE 4: both rates OK → keep high
        clean_highs.append((h_idx, h_val))

    # Final step: enforce alternation (recommended)
    clean_highs, clean_lows = enforce_strict_alternation(clean_highs, clean_lows)

    return clean_highs, clean_lows
