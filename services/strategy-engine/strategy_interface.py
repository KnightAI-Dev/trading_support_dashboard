"""
Strategy Interface - Core trading strategy logic

This module implements the main trading strategy that combines:
- Swing high/low detection
- Support/resistance level identification
- Fibonacci level calculations
- Confluence scoring
- Alert generation
"""
from re import L
import sys
import os
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import pandas as pd

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.config import STRATEGY_CANDLE_COUNT
from shared.storage import StorageService
from swing_high_low import calculate_swing_points, filter_between, filter_rate
import support_resistance
import json


@dataclass
class FibResult:
    """Container for raw Fibonacci calculations derived from swing points."""
    timeframe: str
    low_center: Tuple[int, float]  # (datetime, price)
    left_high: Optional[Tuple[int, float]] = None  # (datetime, price) - earlier in time
    right_high: Optional[Tuple[int, float]] = None  # (datetime, price) - later in time
    fib_bear_level: Optional[float] = None
    fib_bull_lower: Optional[float] = None
    fib_bull_higher: Optional[float] = None


@dataclass
class ConfirmedFibResult(FibResult):
    """Fibonacci result enriched with support/resistance matches and confluence metadata."""
    match_4h: bool = False
    match_1h: bool = False
    match_both: bool = False
    additional_matches: Dict[str, bool] = field(default_factory=dict)
    confluence_mark: str = "none"
    confluence_count: int = 0


class StrategyInterface:
    def __init__(self):
        # Load configuration from database, with fallback to defaults
        self._load_config_from_db()
        
    def _load_config_from_db(self):
        """Load configuration values from database, with fallback to defaults"""
        try:
            with StorageService() as storage:
                configs = storage.get_strategy_config()
                
                # Load values from database, with defaults as fallback
                self.bullish_fib_level_lower = configs.get('bullish_fib_level_lower', 0.7)
                self.bullish_fib_level_higher = configs.get('bullish_fib_level_higher', 0.72)
                self.bullish_sl_fib_level = configs.get('bullish_sl_fib_level', 0.9)
                
                self.bearish_fib_level = configs.get('bearish_fib_level', 0.618)
                self.bearish_sl_fib_level = configs.get('bearish_sl_fib_level', 0.786)
                
                self.tp1_fib_level = configs.get('tp1_fib_level', 0.5)
                self.tp2_fib_level = configs.get('tp2_fib_level', 0.382)
                self.tp3_fib_level = configs.get('tp3_fib_level', 0.236)
                
                self.candle_counts_for_swing_high_low = configs.get('candle_counts_for_swing_high_low', 200)
                self.sensible_window = configs.get('sensible_window', 2)
                self.swing_window = configs.get('swing_window', 6)
                
                # Load pruning scores (JSON object)
                pruning_scores = configs.get('swing_high_low_pruning_score', {
                    'BTCUSDT': 0.015,
                    'ETHUSDT': 0.015,
                    'SOLUSDT': 0.02,
                    'OTHER': 0.03
                })
                if isinstance(pruning_scores, str):
                    pruning_scores = json.loads(pruning_scores)
                self.swing_high_low_pruning_score = pruning_scores
                
                # Use STRATEGY_CANDLE_COUNT for support/resistance
                self.candle_counts_for_support_resistance = STRATEGY_CANDLE_COUNT
                
        except Exception as e:
            # Fallback to defaults if database load fails
            print(f"Warning: Failed to load config from database: {e}. Using defaults.")
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
            self.swing_window = 6
            self.swing_high_low_pruning_score = {
                'BTCUSDT': 0.015,
                'ETHUSDT': 0.015,
                'SOLUSDT': 0.02,
                'OTHER': 0.03
            }
            self.candle_counts_for_support_resistance = STRATEGY_CANDLE_COUNT
        
        # These are not in the database yet, keep as defaults
        self.bearish_alert_level = 0.5
        self.bullish_alert_level = 0.618
        self.swing_sup_res_tolerance_pct = 0.01
        self.approaching_tolerance_pct = 0.01
    
    def reload_config(self):
        """Reload configuration from database (useful for hot-reloading)"""
        self._load_config_from_db()
        
        
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
        
        if len(timeframe_ticker_df) < candle_counts:
            return None
        df = timeframe_ticker_df.copy()  # Reverse to get chronological order
        df = pd.concat([df, df.tail(1)], axis=0, ignore_index=True)
        df.dropna(inplace=True)
        df = df.iloc[:candle_counts+1]
        return df
    
    
    def get_swingHL(self, timeframe_ticker_df: pd.DataFrame, swing_high_low_candle_counts: int, swing_pruning_rate: float) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """
        Calculate and filter swing highs and lows from candle data.
        
        Args:
            timeframe_ticker_df: DataFrame with OHLC data (should have 'unix' column for datetime)
            swing_high_low_candle_counts: Minimum number of candles required
            swing_pruning_rate: Rate threshold for filtering swing points
            
        Returns:
            Tuple of (swing_highs_list, swing_lows_list) where each list contains (datetime, price) tuples
            datetime is Unix timestamp from the 'unix' column
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
    
    def calc_fib_levels(
        self, 
        swingHighs: List[Tuple[int, float]], 
        swingLows: List[Tuple[int, float]], 
        timeframe: str
    ) -> List[FibResult]:
        output: List[FibResult] = []
        
        # Input validation
        if not isinstance(swingLows, (list, tuple)) or not swingLows:
            return output
        
        if not isinstance(swingHighs, (list, tuple)):
            swingHighs = []
        
        if not isinstance(timeframe, str):
            timeframe = ""
        
        # Pre-validate and filter swing highs for efficiency
        valid_highs = []
        for swing_high in swingHighs:
            if not isinstance(swing_high, (list, tuple)) or len(swing_high) < 2:
                continue
            try:
                h_dt, h_price = swing_high[0], swing_high[1]
                # Validate datetime and price are numeric and price is positive
                if isinstance(h_dt, (int, float)) and isinstance(h_price, (int, float)) and h_price > 0:
                    valid_highs.append((int(h_dt), float(h_price)))
            except (IndexError, TypeError, ValueError):
                continue
        
        # Sort valid highs by datetime for efficient searching
        valid_highs.sort(key=lambda x: x[0])
        
        # Process each swing low
        for swing_low in swingLows:
            # Validate swing_low structure
            if not isinstance(swing_low, (list, tuple)) or len(swing_low) < 2:
                continue
            
            try:
                low_dt, low_price = swing_low[0], swing_low[1]
            except (IndexError, TypeError):
                continue
            
            # Validate datetime and price
            if not isinstance(low_dt, (int, float)) or not isinstance(low_price, (int, float)):
                continue
            
            low_dt = int(low_dt)
            low_price = float(low_price)
            
            # Validate price is positive
            if low_price <= 0:
                continue
            
            # Find RIGHT HIGH (later in time - after this low)
            # This is the first swing high that occurs after this low
            right_high = None
            for h_dt, h_price in valid_highs:
                if h_dt > low_dt:  # Compare datetime, not index
                    right_high = (h_dt, h_price)
                    # Found the first high after the low, can break
                    break
                # Continue searching until we find one > low_dt
            
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
            
            # Initialize Fibonacci levels
            fib_bear_level = None
            fib_bull_lower_level = None
            fib_bull_higher_level = None
            
            # Calculate Bullish Fibonacci levels (extension from low to right high)
            if right_high is not None:
                rh_dt, rh_price = right_high
                
                # Validate price relationship (high should be above low)
                if rh_price > low_price:
                    try:
                        price_diff = rh_price - low_price
                        
                        # Calculate bullish extension levels
                        # These extend beyond the right high
                        fib_bull_lower_level = rh_price - price_diff * self.bullish_fib_level_lower
                        fib_bull_higher_level = rh_price - price_diff * self.bullish_fib_level_higher
                        
                        # Ensure fib levels are above the low (safety check)
                        fib_bull_lower_level = max(low_price, fib_bull_lower_level)
                        fib_bull_higher_level = max(low_price, fib_bull_higher_level)
                    except (TypeError, ValueError, OverflowError):
                        # Skip if calculation fails
                        pass
            
            # Calculate Bearish Fibonacci level (retracement from left high to low)
            if left_high is not None:
                lh_dt, lh_price = left_high
                
                # Validate price relationship (high should be above low)
                if lh_price > low_price:
                    try:
                        price_diff = lh_price - low_price
                        
                        # Calculate bearish retracement level (0.618)
                        # This is a retracement from the high back toward the low
                        fib_bear_level = low_price + price_diff * self.bearish_fib_level
                        
                        # Ensure the fib level is between low and high (safety check)
                        fib_bear_level = max(low_price, min(lh_price, fib_bear_level))
                    except (TypeError, ValueError, OverflowError):
                        # Skip if calculation fails
                        pass
            
            # Build dataclass result
            output.append(
                FibResult(
                    timeframe=timeframe,
                    low_center=(low_dt, low_price),  # (datetime, price)
                    left_high=left_high,  # (datetime, price) or None
                    right_high=right_high,  # (datetime, price) or None
                    fib_bear_level=float(fib_bear_level) if fib_bear_level is not None else None,
                    fib_bull_lower=float(fib_bull_lower_level) if fib_bull_lower_level is not None else None,
                    fib_bull_higher=float(fib_bull_higher_level) if fib_bull_higher_level is not None else None,
                )
            )
        
        return output


    def confirm_swingHL(self, swingHighs: List[Tuple[int, float]], swingLows: List[Tuple[int, float]], support_resistance_dict: Dict, timeframe: str) -> List[ConfirmedFibResult]:
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
        confirmed_swingHL: List[ConfirmedFibResult] = []
        
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
            fib_bear_level = fib_level.fib_bear_level
            fib_bull_lower_level = fib_level.fib_bull_lower
            fib_bull_higher_level = fib_level.fib_bull_higher

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
                additional = {
                    tf_key: matched
                    for tf_key, matched in timeframe_matches.items()
                    if tf_key not in ["4h", "1h"]
                }

                confirmed_level = ConfirmedFibResult(
                    timeframe=fib_level.timeframe,
                    low_center=fib_level.low_center,
                    left_high=fib_level.left_high,
                    right_high=fib_level.right_high,
                    fib_bear_level=fib_level.fib_bear_level,
                    fib_bull_lower=fib_level.fib_bull_lower,
                    fib_bull_higher=fib_level.fib_bull_higher,
                    match_4h=timeframe_matches.get("4h", False),
                    match_1h=timeframe_matches.get("1h", False),
                    match_both=(
                        timeframe_matches.get("4h", False)
                        and timeframe_matches.get("1h", False)
                    ),
                    additional_matches=additional,
                )
                
                confirmed_swingHL.append(confirmed_level)

        return confirmed_swingHL

    def add_confluence_marks(self, confirmed_levels: List[ConfirmedFibResult]) -> List[ConfirmedFibResult]:
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
        marked_levels: List[ConfirmedFibResult] = []
        
        for level in confirmed_levels:
            mark: Optional[str] = None
            confluence_count = 0
            
            # Use the match flags from confirm_swingHL
            match_4h = level.match_4h
            match_1h = level.match_1h
            match_both = level.match_both
            
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
            for matched in level.additional_matches.values():
                if matched:
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
            
            level.confluence_mark = mark
            level.confluence_count = confluence_count
            marked_levels.append(level)
        
        return marked_levels
    
    def generate_alerts(
        self, 
        asset_symbol: str, 
        confirmed_levels: List[ConfirmedFibResult], 
        df: Optional[pd.DataFrame] = None,
        bearish_alert_val: float = 0.5, 
        bullish_alert_val: float = 0.618
    ) -> List[Dict]:
        """
        Generate alerts based on key Fibonacci levels.
        
        The alert uses the highest confluence mark from the confirmed level.
        
        Args:
            asset_symbol: Asset symbol (e.g., "BTCUSDT")
            confirmed_levels: List of confirmed Fibonacci levels with confluence marks
            df: Optional DataFrame with candle data (not currently used, kept for compatibility)
            
        Returns:
            List of alert dictionaries with highest mark, including swing timestamps
        """
        alerts = []
        
        for level in confirmed_levels:
            right_high = level.right_high
            left_high = level.left_high
            low_center = level.low_center
            
            # Validate required data
            if low_center is None:
                continue
            
            # Need at least one high (right or left) to calculate levels
            if right_high is None and left_high is None:
                continue
            
            try:
                # Extract prices and datetimes from tuples
                # Tuples are now (datetime, price) instead of (index, price)
                low_dt = low_center[0] if isinstance(low_center, (tuple, list)) and len(low_center) >= 2 else None
                low_price = low_center[1] if isinstance(low_center, (tuple, list)) and len(low_center) >= 2 else None
                right_high_dt = right_high[0] if right_high and isinstance(right_high, (tuple, list)) and len(right_high) >= 2 else None
                right_high_price = right_high[1] if right_high and isinstance(right_high, (tuple, list)) and len(right_high) >= 2 else None
                left_high_dt = left_high[0] if left_high and isinstance(left_high, (tuple, list)) and len(left_high) >= 2 else None
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
            
            # Extract swing timestamps from tuples (datetime is now included in tuples)
            swing_low_timestamp = low_dt if low_dt is not None and low_dt > 0 else None
            
            # Get the confluence mark (highest available)
            confluence_mark = level.confluence_mark or "none"
            
            # Get the fib level prices
            entry_level_07 = level.fib_bull_lower or 0.0
            entry_level_618 = level.fib_bear_level or 0.0
            
            # Calculate the sl, tp1, tp2, tp3 for bearish (only if we have left_high)
            bearish_sl = None
            bearish_tp1 = None
            bearish_tp2 = None
            bearish_tp3 = None
            
            if left_high_price is not None:
                bearish_sl = low_price + (left_high_price - low_price) * self.bearish_sl_fib_level
                bearish_tp1 = low_price + (left_high_price - low_price) * self.tp1_fib_level
                bearish_tp2 = low_price + (left_high_price - low_price) * self.tp2_fib_level
                bearish_tp3 = low_price + (left_high_price - low_price) * self.tp3_fib_level

            # Calculate the sl, tp1, tp2, tp3 for bullish (only if we have right_high)
            bullish_sl = None
            bullish_tp1 = None
            bullish_tp2 = None
            bullish_tp3 = None
            
            if right_high_price is not None:
                bullish_sl = right_high_price - (right_high_price - low_price) * self.bullish_sl_fib_level
                bullish_tp1 = right_high_price - (right_high_price - low_price) * self.tp1_fib_level
                bullish_tp2 = right_high_price - (right_high_price - low_price) * self.tp2_fib_level
                bullish_tp3 = right_high_price - (right_high_price - low_price) * self.tp3_fib_level
            
            # Extract swing high timestamp for bullish alert (right_high)
            # datetime is now included in the tuple
            bullish_swing_high_timestamp = right_high_dt if right_high_dt is not None and right_high_dt > 0 else None
            
            # Generate bullish alert
            alerts.append({
                    "timeframe": level.timeframe or "unknown",
                    "trend_type": "long",
                    "asset": asset_symbol,
                    "entry_level": entry_level_07,
                    "sl": bullish_sl,
                    "tp1": bullish_tp1,
                    "tp2": bullish_tp2,
                    "tp3": bullish_tp3,
                    "swing_low_price": low_price,
                    "swing_high_price": right_high_price,
                    "swing_low_timestamp": swing_low_timestamp,
                    "swing_high_timestamp": bullish_swing_high_timestamp,
                    "risk_score": confluence_mark,
                })
            
            # Extract swing high timestamp for bearish alert (left_high)
            # datetime is now included in the tuple
            bearish_swing_high_timestamp = left_high_dt if left_high_dt is not None and left_high_dt > 0 else None
            
            # Generate bearish alert
            alerts.append({
                    "timeframe": level.timeframe or "unknown",
                    "trend_type": "short",
                    "asset": asset_symbol,
                    "entry_level": entry_level_618,
                    "sl": bearish_sl,
                    "tp1": bearish_tp1,
                    "tp2": bearish_tp2,
                    "tp3": bearish_tp3,
                    "swing_low_price": low_price,
                    "swing_high_price": left_high_price,
                    "swing_low_timestamp": swing_low_timestamp,
                    "swing_high_timestamp": bearish_swing_high_timestamp,
                    "risk_score": confluence_mark,
                })
        return alerts

    def execute_strategy(self, df_4h: Optional[pd.DataFrame], df_30m: Optional[pd.DataFrame], df_1h: Optional[pd.DataFrame], asset_symbol: str = "OTHER") -> Dict:
        """
        Execute the complete trading strategy workflow.
        
        Args:
            df_4h: DataFrame with 4H candle data
            df_30m: DataFrame with 30m candle data
            df_1h: DataFrame with 1H candle data
            asset_symbol: Asset symbol for pruning score (default: "OTHER")
            
        Returns:
            Dictionary containing:
            - swing_highs_lows: Raw and confirmed swing highs/lows
            - support_resistance: HTF and LTF support/resistance levels
            - fib_levels: Calculated Fibonacci levels
            - confirmed_levels: Confirmed Fibonacci levels with confluence marks
            - alerts: Trading alerts based on key Fibonacci levels
        """
        # Step 1: Initialize StrategyInterface (already done in __init__)
        
        # Step 2: Get candles (configurable count from environment variable)
        candles_4h_df = self.get_candle(df_4h, STRATEGY_CANDLE_COUNT)
        candles_30m_df = self.get_candle(df_30m, STRATEGY_CANDLE_COUNT)
        candles_1h_df = self.get_candle(df_1h, STRATEGY_CANDLE_COUNT)
        
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
                confirmed_4h_with_marks,
                df=candles_4h_df,
                bearish_alert_val=self.bearish_alert_level,
                bullish_alert_val=self.bullish_alert_level
            )
        
        alerts_30m = []
        if has_30m:
            alerts_30m = self.generate_alerts(
                asset_symbol,
                confirmed_30m_with_marks,
                df=candles_30m_df,
                bearish_alert_val=self.bearish_alert_level,
                bullish_alert_val=self.bullish_alert_level
            )
        
        # Compile final result
        result = {
            "alerts_4h": alerts_4h,
            "alerts_30m": alerts_30m
        }
        
        return result