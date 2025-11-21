"""
Strategy Interface - Core trading strategy logic

This module implements the main trading strategy that combines:
- Swing high/low detection
- Support/resistance level identification
- Fibonacci level calculations
- Confluence scoring
- Alert generation
"""
from typing import List, Dict, Tuple, Optional
import pandas as pd
from swing_high_low import calculate_swing_points, filter_between, filter_rate
import support_resistance


class StrategyInterface:
    def __init__(self):
        
        self.candle_counts_for_support_resistance = 400

        self.bullish_fib_level_lower = 0.7 
        self.bullish_fib_level_higher = 0.72
        self.bullish_sl_fib_level = 0.9

        self.bearish_fib_level = 0.618
        self.bearish_sl_fib_level = 0.786

        self.tp1_fib_level = 0.5
        self.tp2_fib_level = 0.382
        self.tp3_fib_level = 0.236

        self.candle_counts_for_swing_high_low = 200
        self.sensible_window = 2
        self.swing_window = 7

        self.swing_high_low_pruning_score = {
            'BTCUSDT': 0.015,
            'ETHUSDT': 0.015,
            'SOLUSDT': 0.02,
            'OTHER': 0.03
        }

        self.bearish_alert_level = 0.5
        self.bullish_alert_level = 0.618

        self.swing_sup_res_tolerance_pct = 0.01
        self.approaching_tolerance_pct = 0.01

        
        
    def get_candle(self, timeframe_ticker_df: Optional[pd.DataFrame], candle_counts: int) -> Optional[pd.DataFrame]:
        """
        Extract and reverse the last N candles from a DataFrame.
        
        Args:
            timeframe_ticker_df: DataFrame with OHLC data (newest first), or None
            candle_counts: Number of candles to extract
            
        Returns:
            DataFrame with candles in chronological order (oldest first), or None if insufficient data
        """
        if timeframe_ticker_df is None or len(timeframe_ticker_df) == 0:
            return None
        
        df = timeframe_ticker_df.iloc[::-1].copy()  # Reverse to get chronological order
        if len(df) < candle_counts:
            return None
        df = df.iloc[:candle_counts].copy()
        return df
    
    
    def get_swingHL(self, timeframe_ticker_df: pd.DataFrame, swing_high_low_candle_counts: int, swing_pruning_rate: float) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """
        Calculate and filter swing highs and lows from candle data.
        
        Args:
            timeframe_ticker_df: DataFrame with OHLC data
            swing_high_low_candle_counts: Minimum number of candles required
            swing_pruning_rate: Rate threshold for filtering swing points
            
        Returns:
            Tuple of (swing_highs_list, swing_lows_list) where each list contains (index, price) tuples
        """
        if timeframe_ticker_df is None or len(timeframe_ticker_df) < swing_high_low_candle_counts:
            return [], []
        
        try:
            swing_high_list, swing_low_list = calculate_swing_points(timeframe_ticker_df, window=self.swing_window)

            filtered_swing_lows = filter_between(swing_high_list, swing_low_list, keep="min")
            filtered_swing_highs = filter_between(swing_low_list, swing_high_list, keep="max")

            filtered_swing_high_list, filtered_swing_low_list = \
                filter_rate(filtered_swing_highs, filtered_swing_lows, swing_pruning_rate)
            
            return filtered_swing_high_list, filtered_swing_low_list
        except Exception as e:
            # Return empty lists on any error
            return [], []


    
    def get_support_resistance(self, timeframe_ticker_df: pd.DataFrame, high_timeframe_flag: bool) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """
        Calculate support and resistance levels from the DataFrame.
        
        Args:
            timeframe_ticker_df: pandas DataFrame with OHLC data
            high_timeframe_flag: If True, uses open/close for HTF analysis. If False, uses low/high for LTF analysis.
            
        Returns:
            Tuple of (support_level_list, resistance_level_list) where each list contains
            tuples of (index, price)
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
                
        # backward 3, forward sensible_window
        for sens_row in range(3, len(timeframe_ticker_df) - 1):
            try:
                # Check for support level
                support_result = support_resistance.support(
                    timeframe_ticker_df, 
                    sens_row, 
                    3,  # before_candle_count
                    self.sensible_window,  # after_candle_count
                    high_timeframe_flag
                )
                if support_result is True:
                    support_level_list.append((sens_row, float(timeframe_ticker_df.low[sens_row])))
                
                # Check for resistance level
                resistance_result = support_resistance.resistance(
                    timeframe_ticker_df, 
                    sens_row, 
                    3,  # before_candle_count
                    self.sensible_window,  # after_candle_count
                    high_timeframe_flag
                )
                if resistance_result is True:
                    resistance_level_list.append((sens_row, float(timeframe_ticker_df.high[sens_row])))
                    
            except (KeyError, IndexError, TypeError) as e:
                # Skip this row if there's an error accessing the data
                continue
            
        return support_level_list, resistance_level_list
    
    def calc_fib_levels(self, swingHighs: List[Tuple[int, float]], swingLows: List[Tuple[int, float]], timeframe: str) -> List[Dict]:
        """
        Calculate Fibonacci levels based on swing highs and lows.
        
        Args:
            swingHighs: List of tuples (index, price) for swing highs
            swingLows: List of tuples (index, price) for swing lows
            timeframe: Timeframe string (e.g., "4h", "1h") to associate with the calculations
            
        Returns:
            List of dictionaries containing Fibonacci level calculations with the following keys:
            - timeframe: The provided timeframe string
            - low_center: Tuple (index, price) of the center low or None
            - left_high: Tuple (index, price) of the left high (nearest larger index) or None
            - right_high: Tuple (index, price) of the right high (nearest smaller index) or None
            - fib_bear_level: Bearish Fibonacci level calculated from left high, or None
            - fib_bull_lower: Lower bullish Fibonacci level calculated from right high, or None
            - fib_bull_higher: Higher bullish Fibonacci level calculated from right high, or None
        """
        output = []
        
        # Input validation
        if swingLows is None or not isinstance(swingLows, (list, tuple)):
            return output
        
        if swingHighs is None:
            swingHighs = []
        
        if timeframe is None:
            timeframe = ""

        for swing_low in swingLows:
            # Validate swing_low is a tuple/list with at least 2 elements
            if not isinstance(swing_low, (list, tuple)) or len(swing_low) < 2:
                continue
            
            try:
                low_idx, low_price = swing_low[0], swing_low[1]
            except (IndexError, TypeError):
                continue
            
            # Validate low_idx and low_price
            # if not isinstance(low_idx, (int, float)) or not isinstance(low_price, (int, float)):
            #     continue
            
            if low_price <= 0:
                continue

            # RIGHT HIGH = nearest smaller index (earlier in time)
            right_candidates = []
            for swing_high in swingHighs:
                if not isinstance(swing_high, (list, tuple)) or len(swing_high) < 2:
                    continue
                try:
                    h_idx, h_price = swing_high[0], swing_high[1]
                    if isinstance(h_idx, (int, float)) and isinstance(h_price, (int, float)) and h_price > 0:
                        if h_idx < low_idx:
                            right_candidates.append((h_idx, h_price))
                except (IndexError, TypeError):
                    continue
            
            right_high = max(right_candidates, key=lambda x: x[0]) if right_candidates else None

            # LEFT HIGH = nearest larger index (later in time)
            left_candidates = []
            for swing_high in swingHighs:
                if not isinstance(swing_high, (list, tuple)) or len(swing_high) < 2:
                    continue
                try:
                    h_idx, h_price = swing_high[0], swing_high[1]
                    if isinstance(h_idx, (int, float)) and isinstance(h_price, (int, float)) and h_price > 0:
                        if h_idx > low_idx:
                            left_candidates.append((h_idx, h_price))
                except (IndexError, TypeError):
                    continue
            
            left_high = min(left_candidates, key=lambda x: x[0]) if left_candidates else None

            fib_bear_level = None
            fib_bull_lower_level = None
            fib_bull_higher_level = None

            # Bullish Fibonacci (right high): extension from low to high
            if right_high is not None:
                rh_idx, rh_price = right_high
                if rh_price > low_price:
                    diff = rh_price - low_price
                    fib_bull_lower_level = low_price + diff * self.bullish_fib_level_lower
                    fib_bull_higher_level = low_price + diff * self.bullish_fib_level_higher
                    # Ensure fib levels are above the low
                    fib_bull_lower_level = max(low_price, fib_bull_lower_level)
                    fib_bull_higher_level = max(low_price, fib_bull_higher_level)
            
            # Bearish Fibonacci (left high): retracement from high to low
            if left_high is not None:
                lh_idx, lh_price = left_high
                if lh_price > low_price:
                    fib_bear_level = lh_price - (lh_price - low_price) * self.bearish_fib_level
                    # Ensure the fib level is between low and high
                    fib_bear_level = max(low_price, min(lh_price, fib_bear_level))

            output.append({
                "timeframe": str(timeframe),
                "low_center": swing_low,
                "left_high": left_high,
                "right_high": right_high,
                "fib_bear_level": float(fib_bear_level) if fib_bear_level is not None else None,
                "fib_bull_lower": float(fib_bull_lower_level) if fib_bull_lower_level is not None else None,
                "fib_bull_higher": float(fib_bull_higher_level) if fib_bull_higher_level is not None else None
            })

        return output


    def confirm_swingHL(self, swingHighs: List[Tuple[int, float]], swingLows: List[Tuple[int, float]], support_resistance_dict: Dict, timeframe: str) -> List[Dict]:
        """
        Confirm swing high/low Fibonacci levels by checking if they align with support/resistance levels
        from multiple timeframes.
        
        Args:
            swingHighs: List of tuples (index, price) for swing highs
            swingLows: List of tuples (index, price) for swing lows
            support_resistance_dict: Dictionary with timeframe names as keys and tuples (support, resistance) as values.
                                   Example: {"4h": (support_list, resistance_list), "1h": (support_list, resistance_list)}
            timeframe: Timeframe string for the swing highs/lows (e.g., "4h", "1h")
            tolerance: Relative tolerance for price comparison (default: 0.01 = 1%)
            
        Returns:
            List of confirmed Fibonacci level dictionaries with matching flags:
            - match_4h: True if matches 4h support/resistance
            - match_1h: True if matches 1h support/resistance
            - match_both: True if matches both timeframes
        """
        confirmed_swingHL = []
        
        # Input validation
        if support_resistance_dict is None or not isinstance(support_resistance_dict, dict):
            return confirmed_swingHL
        
        if timeframe is None:
            timeframe = ""
        
        # Normalize timeframe names in the dictionary keys
        timeframe_keys = {}
        for key in support_resistance_dict.keys():
            # Normalize key (e.g., "4H" -> "4h", "1H" -> "1h")
            normalized_key = str(key).lower().replace("hour", "h").replace("hours", "h")
            timeframe_keys[normalized_key] = key
        
        # Calculate Fibonacci levels
        swing_fib_levels = self.calc_fib_levels(swingHighs, swingLows, timeframe)

        for fib_level in swing_fib_levels:
            fib_bear_level = fib_level["fib_bear_level"]
            fib_bull_lower_level = fib_level["fib_bull_lower"]
            fib_bull_higher_level = fib_level["fib_bull_higher"]

            # Track matches for each timeframe
            timeframe_matches = {}
            
            # Check against each timeframe's support/resistance
            for tf_key, original_key in timeframe_keys.items():
                sup_res_pair = support_resistance_dict[original_key]
                
                # Handle both tuple and dict formats
                if isinstance(sup_res_pair, tuple) and len(sup_res_pair) == 2:
                    support, resistance = sup_res_pair
                elif isinstance(sup_res_pair, dict):
                    support = sup_res_pair.get("support", [])
                    resistance = sup_res_pair.get("resistance", [])
                else:
                    continue
                
                # Normalize to lists
                if support is None:
                    support = []
                if resistance is None:
                    resistance = []
                
                # Combine support and resistance prices
                sup_res_prices = [p for _, p in support] + [p for _, p in resistance]
                sup_res_prices_sorted = sorted(sup_res_prices)
                
                # Check if any Fibonacci level matches
                is_matched = False
                
                # Check bearish Fibonacci level
                if not is_matched and fib_bear_level is not None:
                    for sup_res_price in sup_res_prices_sorted:
                        if abs(fib_bear_level - sup_res_price) / max(abs(fib_bear_level), abs(sup_res_price), 1e-10) <= self.swing_sup_res_tolerance_pct:
                            is_matched = True
                            break
                
                # Check bullish Fibonacci lower level
                if not is_matched and fib_bull_lower_level is not None:
                    for sup_res_price in sup_res_prices_sorted:
                        if abs(fib_bull_lower_level - sup_res_price) / max(abs(fib_bull_lower_level), abs(sup_res_price), 1e-10) <= self.swing_sup_res_tolerance_pct:
                            is_matched = True
                            break
                
                # Check bullish Fibonacci higher level
                if not is_matched and fib_bull_higher_level is not None:
                    for sup_res_price in sup_res_prices_sorted:
                        if abs(fib_bull_higher_level - sup_res_price) / max(abs(fib_bull_higher_level), abs(sup_res_price), 1e-10) <= self.swing_sup_res_tolerance_pct:
                            is_matched = True
                            break
                
                timeframe_matches[tf_key] = is_matched
            
            # Only add if at least one timeframe matches
            if any(timeframe_matches.values()):
                # Create a copy of fib_level with matching flags
                confirmed_level = fib_level.copy()
                
                # Add matching flags for common timeframes
                confirmed_level["match_4h"] = timeframe_matches.get("4h", False)
                confirmed_level["match_1h"] = timeframe_matches.get("1h", False)
                
                # Check if both 4h and 1h match
                confirmed_level["match_both"] = (
                    confirmed_level["match_4h"] and confirmed_level["match_1h"]
                )
                
                # Add flags for any other timeframes found
                for tf_key, matched in timeframe_matches.items():
                    if tf_key not in ["4h", "1h"]:
                        confirmed_level[f"match_{tf_key}"] = matched
                
                confirmed_swingHL.append(confirmed_level)

        return confirmed_swingHL

    def add_confluence_marks(self, confirmed_levels: List[Dict]) -> List[Dict]:
        """
        Add confluence scoring marks to confirmed levels based on match flags.
        
        Confluence scoring rules:
        - If fib level matches HTF support/resistance → mark = "high"
        - If fib level matches LTF support/resistance → mark = "good"
        - If additional confluences appear → increase the mark severity
        
        Args:
            confirmed_levels: List of confirmed Fibonacci level dictionaries
                              (already contains match_4h and match_1h flags from confirm_swingHL)
            
        Returns:
            List of confirmed levels with confluence marks added
        """
        marked_levels = []
        
        for level in confirmed_levels:
            marked_level = level.copy()
            mark = None
            confluence_count = 0
            
            # Use the match flags from confirm_swingHL
            match_4h = level.get("match_4h", False)
            match_1h = level.get("match_1h", False)
            match_both = level.get("match_both", False)
            
            # Count confluences
            if match_4h:
                confluence_count += 2
                mark = "high"  # HTF match = "high"
            
            if match_1h:
                confluence_count += 1
                if mark is None:
                    mark = "good"  # LTF match = "good"
                elif mark == "good":
                    mark = "high"  # Both LTF and HTF = upgrade to "high"
            
            # If both timeframes match, increase severity
            if match_both:
                if mark == "high":
                    mark = "higher"
                confluence_count = max(confluence_count, 3)
            
            # Check for additional confluences from other timeframes
            for key in level.keys():
                if key.startswith("match_") and key not in ["match_4h", "match_1h", "match_both"]:
                    if level.get(key, False):
                        confluence_count += 1
                        # Increase severity with additional confluences
                        if mark == "good":
                            mark = "high"
                        elif mark == "high":
                            mark = "higher"
            
            # Set final mark
            if mark is None:
                mark = "none"
            elif confluence_count > 3 and mark == "higher":
                # Multiple additional confluences beyond both timeframes
                mark = "very_high"
            
            marked_level["confluence_mark"] = mark
            marked_level["confluence_count"] = confluence_count
            marked_levels.append(marked_level)
        
        return marked_levels
    
    def generate_alerts(self, asset_symbol: str, latest_close_price: float, confirmed_levels: List[Dict], bearish_alert_val: float = 0.5, bullish_alert_val: float = 0.618) -> List[Dict]:
        """
        Generate alerts based on price approach to key Fibonacci levels.
        
        Alert Rules:
        - If price approaches 0.618 level (bullish extension from low_center to right_high) → bullish alert
        - If price approaches 0.5 level (bearish retracement from right_high to low_center) → bearish alert
        
        The alert uses the highest confluence mark from the confirmed level.
        
        Args:
            latest_close_price: Current closing price
            confirmed_levels: List of confirmed Fibonacci levels with confluence marks
            
        Returns:
            List of alert dictionaries with highest mark
        """
        alerts = []
        
        for level in confirmed_levels:
            right_high = level.get("right_high")
            left_high = level.get("left_high")
            low_center = level.get("low_center")
            
            # Validate required data
            if low_center is None:
                continue
            
            # Need at least one high (right or left) to calculate levels
            if right_high is None and left_high is None:
                continue
            
            try:
                # Extract prices from tuples
                low_price = low_center[1] if isinstance(low_center, (tuple, list)) and len(low_center) >= 2 else None
                right_high_price = right_high[1] if right_high and isinstance(right_high, (tuple, list)) and len(right_high) >= 2 else None
                left_high_price = left_high[1] if left_high and isinstance(left_high, (tuple, list)) and len(left_high) >= 2 else None
                
                if low_price is None or low_price <= 0:
                    continue
                
                # Validate price relationships
                if right_high_price is not None and right_high_price <= low_price:
                    continue
                if left_high_price is not None and left_high_price <= low_price:
                    continue
                    
            except (IndexError, TypeError, ValueError) as e:
                # Skip this level if we can't extract prices
                continue
            
            # Get the confluence mark (highest available)
            confluence_mark = level.get("confluence_mark", "none")
            
            # Calculate fib_05_level: bearish retracement from right_high to low_center
            # Only calculate if we have right_high
            fib_05_level = None
            if right_high_price is not None:
                fib_05_level = right_high_price - (right_high_price - low_price) * self.bearish_alert_level
            
            # Calculate fib_level_618: bullish extension from low_center to left_high
            # Only calculate if we have left_high
            fib_level_618 = None
            if left_high_price is not None:
                fib_level_618 = low_price + (left_high_price - low_price) * self.bullish_alert_level
            
            # Get the fib level prices
            entry_level_07 = level.get("fib_bull_lower", 0.0)
            entry_level_618 = level.get("fib_bear_level", 0.0)
            
            # Calculate percentage differences for both levels (only if levels are valid)
            diff_pct_618 = float('inf')
            if fib_level_618 is not None and fib_level_618 > 0:
                diff_pct_618 = abs(latest_close_price - fib_level_618) / fib_level_618
            
            diff_pct_05 = float('inf')
            if fib_05_level is not None and fib_05_level > 0:
                diff_pct_05 = abs(latest_close_price - fib_05_level) / fib_05_level
            
            # Calculate the sl, tp1, tp2, tp3 for bearish (only if we have left_high)
            bearish_sl = None
            bearish_tp1 = None
            bearish_tp2 = None
            bearish_tp3 = None
            bearish_approaching = float('inf')
            
            if left_high_price is not None:
                bearish_sl = left_high_price - (left_high_price - low_price) * self.bearish_sl_fib_level
                bearish_tp1 = left_high_price - (left_high_price - low_price) * self.tp1_fib_level
                bearish_tp2 = left_high_price - (left_high_price - low_price) * self.tp2_fib_level
                bearish_tp3 = left_high_price - (left_high_price - low_price) * self.tp3_fib_level
                if entry_level_618 and entry_level_618 > 0:
                    bearish_approaching = abs(latest_close_price - entry_level_618) / entry_level_618

            # Calculate the sl, tp1, tp2, tp3 for bullish (only if we have right_high)
            bullish_sl = None
            bullish_tp1 = None
            bullish_tp2 = None
            bullish_tp3 = None
            bullish_approaching = float('inf')
            
            if right_high_price is not None:
                bullish_sl = low_price + (right_high_price - low_price) * self.bullish_sl_fib_level
                bullish_tp1 = low_price + (right_high_price - low_price) * self.tp1_fib_level
                bullish_tp2 = low_price + (right_high_price - low_price) * self.tp2_fib_level
                bullish_tp3 = low_price + (right_high_price - low_price) * self.tp3_fib_level
                if entry_level_07 and entry_level_07 > 0:
                    bullish_approaching = abs(latest_close_price - entry_level_07) / entry_level_07
            
            # Check if price is approaching 0.618 level (bullish alert)
            # if fib_level_618 is not None and diff_pct_618 <= self.approaching_tolerance_pct:
                # Only trigger if closer to 0.618 than to 0.5
            alerts.append({
                    "timeframe": level.get("timeframe", "unknown"),
                    "trend_type": "long",
                    "asset": asset_symbol,
                    "current_price": latest_close_price,
                    'approaching': bullish_approaching,
                    "entry_level": entry_level_07,
                    "sl": bullish_sl,
                    "tp1": bullish_tp1,
                    "tp2": bullish_tp2,
                    "tp3": bullish_tp3,
                    "swing_low": low_center,
                    "swing_high": right_high,
                    "risk_score": confluence_mark,
                })
            
            # Check if price is approaching 0.5 level (bearish alert)
            # if fib_05_level is not None and diff_pct_05 <= self.approaching_tolerance_pct:
                # Only trigger if closer to 0.5 than to 0.618
            alerts.append({
                    "timeframe": level.get("timeframe", "unknown"),
                    "trend_type": "short",
                    "asset": asset_symbol,
                    "current_price": latest_close_price,
                    'approaching': bearish_approaching,
                    "entry_level": entry_level_618,
                    "sl": bearish_sl,
                    "tp1": bearish_tp1,
                    "tp2": bearish_tp2,
                    "tp3": bearish_tp3,
                    "swing_low": low_center,
                    "swing_high": left_high,
                    "risk_score": confluence_mark,
                })
        return alerts

    def execute_strategy(self, df_4h: Optional[pd.DataFrame], df_30m: Optional[pd.DataFrame], df_1h: Optional[pd.DataFrame], latest_close_price: float, asset_symbol: str = "OTHER") -> Dict:
        """
        Execute the complete trading strategy workflow.
        
        Args:
            df_4h: DataFrame with 4H candle data
            df_30m: DataFrame with 30m candle data
            df_1h: DataFrame with 1H candle data
            latest_close_price: Current closing price for alert logic
            asset_symbol: Asset symbol for pruning score (default: "OTHER")
            
        Returns:
            Dictionary containing:
            - swing_highs_lows: Raw and confirmed swing highs/lows
            - support_resistance: HTF and LTF support/resistance levels
            - fib_levels: Calculated Fibonacci levels
            - confirmed_levels: Confirmed Fibonacci levels with confluence marks
            - alerts: Trading alerts based on price approach to key levels
        """
        # Step 1: Initialize StrategyInterface (already done in __init__)
        
        # Step 2: Get candles (200 candles for each timeframe)
        candles_4h_df = self.get_candle(df_4h, 400)
        candles_30m_df = self.get_candle(df_30m, 400)
        candles_1h_df = self.get_candle(df_1h, 400)
        
        # Validate candle data - need at least one of 4h or 30m, and 1h for support/resistance
        has_4h = candles_4h_df is not None and len(candles_4h_df) > 0
        has_30m = candles_30m_df is not None and len(candles_30m_df) > 0
        has_1h = candles_1h_df is not None and len(candles_1h_df) > 0
        
        if not (has_4h or has_30m):
            return {"alerts_4h": [], "alerts_30m": []}
        
        if not has_1h:
            return {"alerts_4h": [], "alerts_30m": []}
        
        # Step 3: Get swing highs and lows
        # Use 'OTHER' as fallback if symbol not in pruning score dictionary
        swing_pruning_rate = self.swing_high_low_pruning_score.get(
            asset_symbol, 
            self.swing_high_low_pruning_score.get('OTHER', 0.03)
        )
        
        # Get swing highs and lows for available timeframes
        swing_highs_4h, swing_lows_4h = [], []
        if has_4h:
            swing_highs_4h, swing_lows_4h = self.get_swingHL(
                candles_4h_df, 
                self.candle_counts_for_swing_high_low,
                swing_pruning_rate
            )
            # Handle None returns
            if swing_highs_4h is None:
                swing_highs_4h = []
            if swing_lows_4h is None:
                swing_lows_4h = []
        
        swing_highs_30m, swing_lows_30m = [], []
        if has_30m:
            swing_highs_30m, swing_lows_30m = self.get_swingHL(
                candles_30m_df,
                self.candle_counts_for_swing_high_low,
                swing_pruning_rate
            )
            # Handle None returns
            if swing_highs_30m is None:
                swing_highs_30m = []
            if swing_lows_30m is None:
                swing_lows_30m = []
        
        # Step 4: Get support/resistance levels
        # HTF (4H) with high_timeframe_flag=True (only if we have 4h data)
        support_4h, resistance_4h = [], []
        if has_4h:
            support_4h, resistance_4h = self.get_support_resistance(
                candles_4h_df,
                high_timeframe_flag=True
            )
        
        # LTF (1H) with high_timeframe_flag=False (always needed for confluence)
        support_1h, resistance_1h = self.get_support_resistance(
            candles_1h_df,
            high_timeframe_flag=False
        )
        
        # Step 5: Calculate Fibonacci levels
        fib_levels_4h = []
        if has_4h:
            fib_levels_4h = self.calc_fib_levels(
                swing_highs_4h,
                swing_lows_4h,
                timeframe="4h"
            )
        
        fib_levels_30m = []
        if has_30m:
            fib_levels_30m = self.calc_fib_levels(
                swing_highs_30m,
                swing_lows_30m,
                timeframe="30m"
            )
        
        # Step 6: Confirm swing high/low zones
        confirmed_4h = []
        if has_4h:
            # For 4H: use HTF support/resistance AND LTF support/resistance
            support_resistance_dict_4h = {
                "4h": (support_4h, resistance_4h),
                "1h": (support_1h, resistance_1h)
            }
            
            confirmed_4h = self.confirm_swingHL(
                swing_highs_4h,
                swing_lows_4h,
                support_resistance_dict_4h,
                timeframe="4h"
            )
        
        confirmed_30m = []
        if has_30m:
            # For 30m: use LTF support/resistance AND HTF support/resistance
            support_resistance_dict_30m = {
                "1h": (support_1h, resistance_1h),
                "4h": (support_4h, resistance_4h)
            }
            
            confirmed_30m = self.confirm_swingHL(
                swing_highs_30m,
                swing_lows_30m,
                support_resistance_dict_30m,
                timeframe="30m"
            )
        
        # Step 7: Confluence scoring
        # Add confluence marks to confirmed levels based on match flags
        confirmed_4h_with_marks = self.add_confluence_marks(confirmed_4h) if has_4h else []
        confirmed_30m_with_marks = self.add_confluence_marks(confirmed_30m) if has_30m else []
        
        # Step 8: Alert logic
        alerts_4h = []
        if has_4h:
            alerts_4h = self.generate_alerts(
                asset_symbol,
                latest_close_price,
                confirmed_4h_with_marks,
                self.bearish_alert_level,
                self.bullish_alert_level
            )
        
        alerts_30m = []
        if has_30m:
            alerts_30m = self.generate_alerts(
                asset_symbol,
                latest_close_price,
                confirmed_30m_with_marks,
                self.bearish_alert_level,
                self.bullish_alert_level
            )
        
        # Compile final result
        result = {
            "alerts_4h": alerts_4h,
            "alerts_30m": alerts_30m
        }
        
        return result