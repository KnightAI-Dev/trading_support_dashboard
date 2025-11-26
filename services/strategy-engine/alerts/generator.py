"""
Alert Generator

This module generates trading alerts from confirmed Fibonacci levels.
Uses Decimal for exact price comparisons and calculations to avoid
floating-point precision issues with very small price values.
"""
from typing import List, Dict, Optional
from decimal import Decimal
import pandas as pd
from core.models import ConfirmedFibResult
from config.settings import StrategyConfig
from utils.decimal_utils import to_decimal, to_decimal_safe, decimal_compare


class AlertGenerator:
    """Generates trading alerts from confirmed Fibonacci levels."""
    
    def __init__(self, config: StrategyConfig):
        """
        Initialize the alert generator.
        
        Args:
            config: StrategyConfig instance with alert parameters
        """
        self.config = config
    
    def generate_alerts(
        self, 
        asset_symbol: str, 
        confirmed_levels: List[ConfirmedFibResult], 
        df: Optional[pd.DataFrame] = None
    ) -> List[Dict]:
        """
        Generate alerts based on key Fibonacci levels.
        
        The alert uses the highest confluence mark from the confirmed level.
        Filters out alerts where the rate between swing high and swing low is less than
        the predefined swing_pruning_rate.
        
        Args:
            asset_symbol: Asset symbol (e.g., "BTCUSDT")
            confirmed_levels: List of confirmed Fibonacci levels with confluence marks
            df: Optional DataFrame with candle data (not currently used, kept for compatibility)
            
        Returns:
            List of alert dictionaries with highest mark, including swing timestamps
        """
        alerts = []
        
        # Get the swing pruning rate for this asset symbol and convert to Decimal
        swing_pruning_rate = self.config.get_pruning_score(asset_symbol)
        swing_pruning_rate_decimal = to_decimal_safe(swing_pruning_rate)
        
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
                low_dt = low_center[0] if isinstance(low_center, (tuple, list)) and len(low_center) >= 2 else None
                low_price = low_center[1] if isinstance(low_center, (tuple, list)) and len(low_center) >= 2 else None
                right_high_dt = right_high[0] if right_high and isinstance(right_high, (tuple, list)) and len(right_high) >= 2 else None
                right_high_price = right_high[1] if right_high and isinstance(right_high, (tuple, list)) and len(right_high) >= 2 else None
                left_high_dt = left_high[0] if left_high and isinstance(left_high, (tuple, list)) and len(left_high) >= 2 else None
                left_high_price = left_high[1] if left_high and isinstance(left_high, (tuple, list)) and len(left_high) >= 2 else None
                
                # Convert prices to Decimal for exact validation and comparison
                low_price_decimal = to_decimal(low_price)
                if low_price_decimal is None or low_price_decimal <= 0:
                    continue
                
                # Validate price relationships using Decimal
                if right_high_price is not None:
                    right_high_decimal = to_decimal(right_high_price)
                    if right_high_decimal is None or decimal_compare(right_high_decimal, low_price_decimal) <= 0:
                        continue
                
                if left_high_price is not None:
                    left_high_decimal = to_decimal(left_high_price)
                    if left_high_decimal is None or decimal_compare(left_high_decimal, low_price_decimal) <= 0:
                        continue
                    
            except (IndexError, TypeError, ValueError) as e:
                # Skip this level if we can't extract prices
                continue
            
            # Extract swing timestamps from tuples
            swing_low_timestamp = low_dt if low_dt is not None and low_dt > 0 else None
            
            # Get the confluence score (cap at 3 for very_high)
            confluence_score = min(level.confluence_count or 0, 3)
            
            # Get the fib level prices
            entry_level_07 = level.fib_bull_lower or 0.0
            entry_level_618 = level.fib_bear_level or 0.0
            
            # Calculate the sl, tp1, tp2, tp3 for bearish (only if we have left_high)
            # Use Decimal for exact calculations
            bearish_sl = None
            bearish_tp1 = None
            bearish_tp2 = None
            bearish_tp3 = None
            
            if left_high_price is not None:
                left_high_decimal = to_decimal(left_high_price)
                if left_high_decimal is not None:
                    price_diff = left_high_decimal - low_price_decimal
                    bearish_sl = float(low_price_decimal + price_diff * to_decimal_safe(self.config.bearish_sl_fib_level))
                    bearish_tp1 = float(low_price_decimal + price_diff * to_decimal_safe(self.config.tp1_fib_level))
                    bearish_tp2 = float(low_price_decimal + price_diff * to_decimal_safe(self.config.tp2_fib_level))
                    bearish_tp3 = float(low_price_decimal + price_diff * to_decimal_safe(self.config.tp3_fib_level))

            # Calculate the sl, tp1, tp2, tp3 for bullish (only if we have right_high)
            # Use Decimal for exact calculations
            bullish_sl = None
            bullish_tp1 = None
            bullish_tp2 = None
            bullish_tp3 = None
            
            if right_high_price is not None:
                right_high_decimal = to_decimal(right_high_price)
                if right_high_decimal is not None:
                    price_diff = right_high_decimal - low_price_decimal
                    bullish_sl = float(right_high_decimal - price_diff * to_decimal_safe(self.config.bullish_sl_fib_level))
                    bullish_tp1 = float(right_high_decimal - price_diff * to_decimal_safe(self.config.tp1_fib_level))
                    bullish_tp2 = float(right_high_decimal - price_diff * to_decimal_safe(self.config.tp2_fib_level))
                    bullish_tp3 = float(right_high_decimal - price_diff * to_decimal_safe(self.config.tp3_fib_level))
            
            # Extract swing high timestamp for bullish alert (right_high)
            bullish_swing_high_timestamp = right_high_dt if right_high_dt is not None and right_high_dt > 0 else None
            
            # Calculate rate for bullish alert (swing high to swing low) using Decimal
            bullish_rate_decimal = None
            if right_high_price is not None:
                right_high_decimal = to_decimal(right_high_price)
                if right_high_decimal is not None and low_price_decimal is not None and low_price_decimal > 0:
                    try:
                        bullish_rate_decimal = (right_high_decimal - low_price_decimal) / low_price_decimal
                    except (ZeroDivisionError, TypeError, ValueError):
                        bullish_rate_decimal = None
            
            # Generate bullish alert only if rate meets the pruning threshold (using Decimal comparison)
            if bullish_rate_decimal is not None and bullish_rate_decimal >= swing_pruning_rate_decimal:
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
                    "risk_score": confluence_score,
                })
            
            # Extract swing high timestamp for bearish alert (left_high)
            bearish_swing_high_timestamp = left_high_dt if left_high_dt is not None and left_high_dt > 0 else None
            
            # Calculate rate for bearish alert (swing high to swing low) using Decimal
            bearish_rate_decimal = None
            if left_high_price is not None:
                left_high_decimal = to_decimal(left_high_price)
                if left_high_decimal is not None and low_price_decimal is not None and low_price_decimal > 0:
                    try:
                        bearish_rate_decimal = (left_high_decimal - low_price_decimal) / low_price_decimal
                    except (ZeroDivisionError, TypeError, ValueError):
                        bearish_rate_decimal = None
            
            # Generate bearish alert only if rate meets the pruning threshold (using Decimal comparison)
            if bearish_rate_decimal is not None and bearish_rate_decimal >= swing_pruning_rate_decimal:
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
                    "risk_score": confluence_score,
                })
        return alerts

