"""
ZigZag++ Indicator

This module implements a ZigZag++ indicator that identifies significant price swings
by filtering out minor price movements based on depth, deviation, and backstep parameters.

Based on PineScript ZigZag++ by Dev Lucem (ZigLib implementation).
"""
from typing import List, Tuple, Optional, Dict
from decimal import Decimal
import pandas as pd
import numpy as np
from utils.decimal_utils import to_decimal, to_decimal_safe


def calculate_zigzag(
    df: pd.DataFrame,
    depth: int = 12,
    deviation: int = 5,
    backstep: int = 2,
    mintick: Optional[float] = None
) -> Dict:
    """
    Calculate ZigZag++ indicator values.
    
    The ZigZag++ indicator filters out minor price movements and identifies
    significant swing points based on depth, deviation, and backstep parameters.
    This implementation matches the PineScript ZigZag++ (ZigLib) logic exactly.
    
    Args:
        df: DataFrame with 'high' and 'low' columns (case-sensitive lowercase).
            Should also have 'unix' column for datetime.
        depth: Number of bars to look back for highest/lowest points (default: 12)
        deviation: Minimum deviation in ticks required for a swing (default: 5)
        backstep: Number of bars required before direction change (default: 2)
        mintick: Minimum price tick size. If None, will be estimated from price data.
                 Default: None (auto-calculated)
    
    Returns:
        Dictionary containing:
        - 'direction': List of direction values (1 for up, -1 for down)
        - 'zigzag_points': List of (datetime, price) tuples representing current zigzag point (z)
        - 'z1': List of (datetime, price) tuples for previous zigzag point
        - 'z2': List of (datetime, price) tuples for current swing point
        - 'point_types': List of point type strings ('HH', 'LH', 'HL', 'LL') for each bar
    """
    # Input validation
    if df is None or len(df) == 0:
        return {
            'direction': [],
            'zigzag_points': [],
            'z1': [],
            'z2': [],
            'point_types': []
        }
    
    if not isinstance(df, pd.DataFrame):
        return {
            'direction': [],
            'zigzag_points': [],
            'z1': [],
            'z2': [],
            'point_types': []
        }
    
    # Validate required columns
    required_columns = ['high', 'low']
    if not all(col in df.columns for col in required_columns):
        return {
            'direction': [],
            'zigzag_points': [],
            'z1': [],
            'z2': [],
            'point_types': []
        }
    
    # Validate parameters
    if depth < 1 or deviation < 1 or backstep < 2:
        return {
            'direction': [],
            'zigzag_points': [],
            'z1': [],
            'z2': [],
            'point_types': []
        }
    
    # Check minimum data requirement
    if len(df) < depth + backstep + 1:
        return {
            'direction': [],
            'zigzag_points': [],
            'z1': [],
            'z2': [],
            'point_types': []
        }
    
    try:
        # Create a copy to avoid modifying the original DataFrame
        df_work = df.copy()
        
        # Auto-calculate mintick if not provided
        if mintick is None:
            # Estimate mintick from price data (use 0.01% of average price as approximation)
            avg_price = (df_work['high'].mean() + df_work['low'].mean()) / 2
            mintick = float(avg_price * 0.0001)  # 0.01% of average price
            if mintick <= 0:
                mintick = 0.01  # Fallback to 0.01
        
        # Convert to numpy arrays for faster computation
        high_values = df_work['high'].values.astype(float)
        low_values = df_work['low'].values.astype(float)
        has_unix = 'unix' in df_work.columns
        
        n = len(df_work)
        
        # Initialize arrays
        hr = np.zeros(n, dtype=int)  # bars since high condition was false
        lr = np.zeros(n, dtype=int)  # bars since low condition was false
        direction = np.ones(n, dtype=int)  # Default to 1 (upward)
        
        # Calculate hr and lr for each bar
        # PineScript: hr = ta.barssince(not (_high[-ta.highestbars(depth)] - _high > deviation*syminfo.mintick)[1])
        # PineScript: lr = ta.barssince(not (_low - _low[-ta.lowestbars(depth)] > deviation*syminfo.mintick)[1])
        # The [1] means we evaluate the condition on the previous bar
        for i in range(depth + 1, n):
            # Calculate on previous bar (i-1)
            prev_idx = i - 1
            
            # Find highest bar in depth period ending at prev_idx
            high_window_start = max(0, prev_idx - depth + 1)
            high_window = high_values[high_window_start:prev_idx + 1]
            if len(high_window) > 0:
                highest_idx_in_window = np.argmax(high_window)
                highest_idx_absolute = high_window_start + highest_idx_in_window
                highestbars = highest_idx_absolute - prev_idx  # Negative bars back
                
                # Calculate hr: bars since condition was false
                # Condition: (_high[-highestbars] - _high) > deviation*mintick
                hr_value = 0
                for j in range(prev_idx, max(-1, prev_idx - depth - 1), -1):
                    if j < 0:
                        break
                    high_at_highestbars_idx = j + highestbars
                    if high_at_highestbars_idx < 0 or high_at_highestbars_idx >= n:
                        continue
                    high_at_highestbars = high_values[high_at_highestbars_idx]
                    high_at_j = high_values[j]
                    condition = (high_at_highestbars - high_at_j) > (deviation * mintick)
                    if not condition:  # Condition is false
                        hr_value = prev_idx - j
                        break
                hr[i] = hr_value
            
            # Find lowest bar in depth period ending at prev_idx
            low_window_start = max(0, prev_idx - depth + 1)
            low_window = low_values[low_window_start:prev_idx + 1]
            if len(low_window) > 0:
                lowest_idx_in_window = np.argmin(low_window)
                lowest_idx_absolute = low_window_start + lowest_idx_in_window
                lowestbars = lowest_idx_absolute - prev_idx  # Negative bars back
                
                # Calculate lr: bars since condition was false
                # Condition: (_low - _low[-lowestbars]) > deviation*mintick
                lr_value = 0
                for j in range(prev_idx, max(-1, prev_idx - depth - 1), -1):
                    if j < 0:
                        break
                    low_at_j = low_values[j]
                    low_at_lowestbars_idx = j + lowestbars
                    if low_at_lowestbars_idx < 0 or low_at_lowestbars_idx >= n:
                        continue
                    low_at_lowestbars = low_values[low_at_lowestbars_idx]
                    condition = (low_at_j - low_at_lowestbars) > (deviation * mintick)
                    if not condition:  # Condition is false
                        lr_value = prev_idx - j
                        break
                lr[i] = lr_value
        
        # Calculate direction
        # PineScript: direction = ta.barssince(not (hr > lr)) >= backstep? -1: 1
        # This means: if bars since (hr <= lr) >= backstep, then direction = -1, else 1
        for i in range(depth + 1, n):
            # Count bars since hr <= lr (i.e., not (hr > lr))
            bars_since_hr_not_greater = 0
            for j in range(i, max(-1, i - depth - backstep - 1), -1):
                if j < 0:
                    break
                if hr[j] <= lr[j]:  # Condition: not (hr > lr) is true
                    bars_since_hr_not_greater = i - j
                    break
            
            if bars_since_hr_not_greater >= backstep:
                direction[i] = -1
            else:
                direction[i] = 1
        
        # Initialize zigzag tracking variables (matching PineScript chart.point structure)
        # z is current point, z1 is previous point, z2 is the swing point
        z_dt = int(df_work['unix'].iloc[0]) if has_unix else 0
        z_price = float(low_values[0])
        z1_dt = z_dt
        z1_price = z_price
        z2_dt = z_dt
        z2_price = float(high_values[0])
        
        # Track lastPoint for HH/LH/HL/LL identification
        # PineScript: var float lastPoint = z1.price[1]
        # Initialize with previous bar's z1 price (which is the initial z1_price at this point)
        last_point = z1_price
        
        # Initialize result lists
        direction_list = []
        z1_points = []
        z2_points = []
        zigzag_points = []
        point_types = []
        
        # Initialize with default values for first depth+1 bars
        for i in range(depth + 1):
            direction_list.append(1)  # Default to upward
            z1_points.append((z1_dt, z1_price))
            z2_points.append((z2_dt, z2_price))
            zigzag_points.append((z_dt, z_price))
            point_types.append("")  # No point type for initial bars
        
        # Process remaining bars
        for i in range(depth + 1, n):
            current_direction = direction[i]
            current_high = high_values[i]
            current_low = low_values[i]
            current_dt = int(df_work['unix'].iloc[i]) if has_unix else i
            prev_direction = direction[i - 1] if i > 0 else 1
            
            # Store previous z1_price before any updates (for lastPoint calculation)
            prev_z1_price = z1_price
            
            # Check for direction change
            direction_changed = (current_direction != prev_direction)
            
            if direction_changed:
                # Update z1 and z2 when direction changes (matching PineScript logic)
                # PineScript: z1 := z2.copy(), z2 := z.copy()
                z1_dt = z2_dt
                z1_price = z2_price
                z2_dt = z_dt
                z2_price = z_price
                # Update lastPoint when direction changes
                # PineScript: lastPoint := z1.price[1] (previous bar's z1 price)
                last_point = prev_z1_price
            
            # Update z, z1, z2 based on direction (matching PineScript ZigLib logic)
            if current_direction > 0:  # Upward trend
                if current_high > z2_price:
                    z2_dt = current_dt
                    z2_price = float(current_high)
                    z_dt = current_dt
                    z_price = float(current_low)
                if current_low < z_price:
                    z_dt = current_dt
                    z_price = float(current_low)
            else:  # current_direction < 0, downward trend
                if current_low < z2_price:
                    z2_dt = current_dt
                    z2_price = float(current_low)
                    z_dt = current_dt
                    z_price = float(current_high)
                if current_high > z_price:
                    z_dt = current_dt
                    z_price = float(current_high)
            
            # Determine point type (HH, LH, HL, LL)
            # PineScript: nowPoint := direction<0? (z2.price<lastPoint? "LL": "HL"): (z2.price>lastPoint? "HH": "LH")
            if current_direction < 0:
                if z2_price < last_point:
                    point_type = "LL"
                else:
                    point_type = "HL"
            else:  # direction > 0
                if z2_price > last_point:
                    point_type = "HH"
                else:
                    point_type = "LH"
            
            # Store values for this bar
            direction_list.append(current_direction)
            z1_points.append((z1_dt, z1_price))
            z2_points.append((z2_dt, z2_price))
            zigzag_points.append((z_dt, z_price))
            point_types.append(point_type)
        
        return {
            'direction': direction_list,
            'zigzag_points': zigzag_points,
            'z1': z1_points,
            'z2': z2_points,
            'point_types': point_types
        }
    
    except Exception as e:
        # Return empty results on any error
        print(f"Error in calculate_zigzag: {e}")
        import traceback
        traceback.print_exc()
        return {
            'direction': [],
            'zigzag_points': [],
            'z1': [],
            'z2': [],
            'point_types': []
        }


def get_zigzag_points(
    df: pd.DataFrame,
    depth: int = 12,
    deviation: int = 5,
    backstep: int = 2,
    mintick: Optional[float] = None,
    swing_pruning_rate: float = 0.03
) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
    """
    Get ZigZag++ swing points as highs and lows.
    
    This function extracts meaningful swing highs and lows from the ZigZag++ indicator,
    filtering out intermediate points to keep only significant swings suitable for technical analysis.
    Similar to TradingView's ZigZag++ behavior, it removes intermediate swings between
    more significant price movements.
    
    Args:
        df: DataFrame with 'high' and 'low' columns. Should have 'unix' column for datetime.
        depth: Number of bars to look back for highest/lowest points (default: 12)
        deviation: Minimum deviation in ticks required for a swing (default: 5)
        backstep: Number of bars required before direction change (default: 2)
        mintick: Minimum price tick size. If None, will be estimated. Default: None
        swing_pruning_rate: Minimum price rate change (as decimal, e.g., 0.03 = 3%) required
                           between consecutive swings to keep them. Default: 0.03 (3%)
    
    Returns:
        Tuple of (swing_highs, swing_lows) where each list contains (datetime, price) tuples.
        Only includes meaningful swing points with significant price movements, filtering out
        intermediate swings.
    """
    result = calculate_zigzag(df, depth, deviation, backstep, mintick)
    
    if not result['zigzag_points'] or not result['direction'] or not result['z2']:
        return [], []
    
    # Extract direction and z2 points
    direction = result['direction']
    z2_points = result['z2']
    
    # Step 1: Collect all swing points on direction changes
    all_swings = []  # List of (type, datetime, price) tuples
    prev_direction = None
    
    for i in range(len(z2_points)):
        if i >= len(direction):
            break
        
        current_direction = direction[i]
        
        # Check for direction change
        if prev_direction is not None and prev_direction != current_direction:
            # Direction changed - capture the previous z2 point as a confirmed swing
            if i > 0:
                prev_dt, prev_price = z2_points[i - 1]
                
                if prev_direction > 0:  # Was going up, now going down -> previous was a swing high
                    all_swings.append(('high', prev_dt, prev_price))
                else:  # Was going down, now going up -> previous was a swing low
                    all_swings.append(('low', prev_dt, prev_price))
        
        prev_direction = current_direction
    
    # Include the last point if meaningful
    if len(z2_points) > 0 and len(direction) > 0:
        last_idx = len(z2_points) - 1
        last_direction = direction[last_idx] if last_idx < len(direction) else None
        last_dt, last_price = z2_points[last_idx]
        
        if last_direction is not None:
            # Check if last point should be included
            if last_direction > 0:  # Currently going up -> last point is a high
                if not all_swings or all_swings[-1][0] != 'high':
                    all_swings.append(('high', last_dt, last_price))
            else:  # Currently going down -> last point is a low
                if not all_swings or all_swings[-1][0] != 'low':
                    all_swings.append(('low', last_dt, last_price))
    
    if len(all_swings) == 0:
        return [], []
    
    # Step 2: Filter by price movement rate (remove swings with small movements)
    filtered_swings = [all_swings[0]]  # Always keep the first point
    
    for i in range(1, len(all_swings)):
        prev_type, prev_dt, prev_price = all_swings[i - 1]
        curr_type, curr_dt, curr_price = all_swings[i]
        
        # Calculate price rate change
        if prev_price > 0:
            price_rate = abs(curr_price - prev_price) / prev_price
        else:
            price_rate = 0.0
        
        # Keep the point if price rate change is greater than swing_pruning_rate
        if price_rate > swing_pruning_rate:
            filtered_swings.append(all_swings[i])
    
    # Step 3: Remove intermediate swings (keep only most significant swings)
    # Between two opposite swings, keep only the most extreme one of each type
    final_swings = []
    
    if len(filtered_swings) == 0:
        return [], []
    
    # Always keep the first swing
    final_swings.append(filtered_swings[0])
    
    i = 1
    while i < len(filtered_swings):
        current_type, current_dt, current_price = filtered_swings[i]
        
        # Find the next swing of opposite type
        next_opposite_idx = None
        for j in range(i + 1, len(filtered_swings)):
            if filtered_swings[j][0] != current_type:
                next_opposite_idx = j
                break
        
        if next_opposite_idx is None:
            # No more opposite swings, keep the most extreme of remaining same-type swings
            if current_type == 'high':
                max_high = current_price
                max_high_swing = filtered_swings[i]
                for j in range(i, len(filtered_swings)):
                    if filtered_swings[j][0] == 'high' and filtered_swings[j][2] > max_high:
                        max_high = filtered_swings[j][2]
                        max_high_swing = filtered_swings[j]
                final_swings.append(max_high_swing)
            else:  # current_type == 'low'
                min_low = current_price
                min_low_swing = filtered_swings[i]
                for j in range(i, len(filtered_swings)):
                    if filtered_swings[j][0] == 'low' and filtered_swings[j][2] < min_low:
                        min_low = filtered_swings[j][2]
                        min_low_swing = filtered_swings[j]
                final_swings.append(min_low_swing)
            break
        
        # Find the most extreme swing of current type between i and next_opposite_idx
        if current_type == 'high':
            # Find the highest high in this range
            max_high = current_price
            max_high_idx = i
            for j in range(i, next_opposite_idx):
                if filtered_swings[j][0] == 'high' and filtered_swings[j][2] > max_high:
                    max_high = filtered_swings[j][2]
                    max_high_idx = j
            final_swings.append(filtered_swings[max_high_idx])
        else:  # current_type == 'low'
            # Find the lowest low in this range
            min_low = current_price
            min_low_idx = i
            for j in range(i, next_opposite_idx):
                if filtered_swings[j][0] == 'low' and filtered_swings[j][2] < min_low:
                    min_low = filtered_swings[j][2]
                    min_low_idx = j
            final_swings.append(filtered_swings[min_low_idx])
        
        i = next_opposite_idx
    
    # Step 4: Ensure strict alternation (remove consecutive same-type swings)
    strict_swings = [final_swings[0]]
    for i in range(1, len(final_swings)):
        if final_swings[i][0] != strict_swings[-1][0]:
            strict_swings.append(final_swings[i])
        else:
            # Consecutive same type - keep the more extreme one
            prev_type, prev_dt, prev_price = strict_swings[-1]
            curr_type, curr_dt, curr_price = final_swings[i]
            
            if curr_type == 'high':
                if curr_price > prev_price:
                    strict_swings[-1] = final_swings[i]
            else:  # curr_type == 'low'
                if curr_price < prev_price:
                    strict_swings[-1] = final_swings[i]
    
    # Step 5: Split into swing_highs and swing_lows
    swing_highs = []
    swing_lows = []
    
    for swing_type, dt, price in strict_swings:
        if swing_type == 'high':
            swing_highs.append((dt, price))
        else:
            swing_lows.append((dt, price))
    
    return swing_highs, swing_lows


# def get_zigzag_points(
#     df: pd.DataFrame,
#     depth: int = 12,
#     deviation: int = 5,
#     backstep: int = 2,
#     mintick: Optional[float] = None
# ) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
#     """
#     Get ZigZag++ swing points as highs and lows.
    
#     This is a convenience function that extracts swing highs and lows from
#     the ZigZag++ indicator results. It identifies swing points when direction changes.
    
#     Args:
#         df: DataFrame with 'high' and 'low' columns. Should have 'unix' column for datetime.
#         depth: Number of bars to look back for highest/lowest points (default: 12)
#         deviation: Minimum deviation in ticks required for a swing (default: 5)
#         backstep: Number of bars required before direction change (default: 2)
#         mintick: Minimum price tick size. If None, will be estimated. Default: None
    
#     Returns:
#         Tuple of (swing_highs, swing_lows) where each list contains (datetime, price) tuples.
#     """
#     result = calculate_zigzag(df, depth, deviation, backstep, mintick)
    
#     if not result['zigzag_points'] or not result['direction']:
#         return [], []
    
#     # Extract swing points from z2 (which represents the significant swing points)
#     z2_points = result['z2']
#     direction = result['direction']
    
#     swing_highs = []
#     swing_lows = []
    
#     # Identify swing highs and lows based on direction changes
#     # When direction changes, the previous z2 point is a confirmed swing point
#     prev_direction = None
#     for i in range(len(z2_points)):
#         if i == 0:
#             prev_direction = direction[i] if i < len(direction) else 1
#             continue
        
#         current_direction = direction[i] if i < len(direction) else prev_direction
        
#         # When direction changes, the previous z2 was a confirmed swing point
#         if prev_direction != current_direction:
#             prev_dt, prev_price = z2_points[i - 1]
            
#             if prev_direction < 0:  # Was going down, now going up -> previous was a swing low
#                 swing_lows.append((prev_dt, prev_price))
#             else:  # Was going up, now going down -> previous was a swing high
#                 swing_highs.append((prev_dt, prev_price))
        
#         prev_direction = current_direction
    
#     # Also include the last point if it's a valid swing
#     if len(z2_points) > 0 and len(direction) > 0:
#         last_idx = len(z2_points) - 1
#         last_direction = direction[last_idx] if last_idx < len(direction) else 1
#         last_dt, last_price = z2_points[last_idx]
        
#         # Add the last point based on current direction
#         if last_direction < 0:  # Currently going down -> last point is a low
#             # Only add if not already added
#             if not swing_lows or swing_lows[-1] != (last_dt, last_price):
#                 swing_lows.append((last_dt, last_price))
#         else:  # Currently going up -> last point is a high
#             # Only add if not already added
#             if not swing_highs or swing_highs[-1] != (last_dt, last_price):
#                 swing_highs.append((last_dt, last_price))
    
#     return swing_highs, swing_lows

