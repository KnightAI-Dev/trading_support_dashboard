"""
Confluence Analysis Module

This module handles confirmation of Fibonacci levels against support/resistance
and calculates confluence scores.
"""
from typing import List, Dict, Tuple, Optional
from core.models import FibResult, ConfirmedFibResult
from config.settings import StrategyConfig


class ConfluenceAnalyzer:
    """Analyzes confluence between Fibonacci levels and support/resistance."""
    
    def __init__(self, config: StrategyConfig):
        """
        Initialize the confluence analyzer.
        
        Args:
            config: StrategyConfig instance
        """
        self.config = config
    
    def confirm_fib_levels(
        self,
        fib_levels: List[FibResult],
        support_resistance_dict: Dict[str, Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]],
        timeframe: str
    ) -> List[ConfirmedFibResult]:
        """
        Confirm Fibonacci levels by checking if they align with support/resistance levels
        from multiple timeframes.
        
        Args:
            fib_levels: List of FibResult objects to confirm
            support_resistance_dict: Dictionary with timeframe names as keys and tuples (support, resistance) as values.
                                   Each support/resistance list contains tuples of (unix_timestamp, price).
                                   Example: {"4h": (support_list, resistance_list), "1h": (support_list, resistance_list)}
            timeframe: Timeframe string for the swing highs/lows (e.g., "4h", "1h")
            
        Returns:
            List of confirmed Fibonacci levels with matching flags
        """
        confirmed_levels: List[ConfirmedFibResult] = []
        
        # Input validation
        if support_resistance_dict is None or not isinstance(support_resistance_dict, dict):
            return confirmed_levels
        
        if timeframe is None:
            timeframe = ""
        
        # Normalize timeframe names in the dictionary keys
        timeframe_keys = {}
        for key in support_resistance_dict.keys():
            # Normalize key (e.g., "4H" -> "4h", "1H" -> "1h")
            normalized_key = str(key).lower().replace("hour", "h").replace("hours", "h")
            timeframe_keys[normalized_key] = key
        
        for fib_level in fib_levels:
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
                        if abs(fib_bear_level - sup_res_price) / max(abs(fib_bear_level), abs(sup_res_price), 1e-10) <= self.config.swing_sup_res_tolerance_pct:
                            is_matched = True
                            break
                
                # Check bullish Fibonacci lower level
                if not is_matched and fib_bull_lower_level is not None:
                    for sup_res_price in sup_res_prices_sorted:
                        if abs(fib_bull_lower_level - sup_res_price) / max(abs(fib_bull_lower_level), abs(sup_res_price), 1e-10) <= self.config.swing_sup_res_tolerance_pct:
                            is_matched = True
                            break
                
                # Check bullish Fibonacci higher level
                if not is_matched and fib_bull_higher_level is not None:
                    for sup_res_price in sup_res_prices_sorted:
                        if abs(fib_bull_higher_level - sup_res_price) / max(abs(fib_bull_higher_level), abs(sup_res_price), 1e-10) <= self.config.swing_sup_res_tolerance_pct:
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
                
                confirmed_levels.append(confirmed_level)

        return confirmed_levels
    
    def add_confluence_marks(self, confirmed_levels: List[ConfirmedFibResult]) -> List[ConfirmedFibResult]:
        """
        Add confluence scoring marks to confirmed levels based on match flags.
        
        Confluence scoring rules:
        - If fib level matches HTF support/resistance → mark = "high"
        - If fib level matches LTF support/resistance → mark = "good"
        - If additional confluences appear → increase the mark severity
        
        Args:
            confirmed_levels: List of confirmed Fibonacci levels
            
        Returns:
            List of confirmed levels with confluence marks added
        """
        marked_levels: List[ConfirmedFibResult] = []
        
        for level in confirmed_levels:
            mark: Optional[str] = None
            confluence_count = 0
            
            # Use the match flags from confirm_fib_levels
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

