"""
Alert Generator

This module generates trading alerts from confirmed Fibonacci levels.
"""
from typing import List, Dict, Optional
import pandas as pd
from core.models import ConfirmedFibResult
from config.settings import StrategyConfig


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
            
            # Extract swing timestamps from tuples
            swing_low_timestamp = low_dt if low_dt is not None and low_dt > 0 else None
            
            # Get the confluence score (cap at 3 for very_high)
            confluence_score = min(level.confluence_count or 0, 3)
            
            # Get the fib level prices
            entry_level_07 = level.fib_bull_lower or 0.0
            entry_level_618 = level.fib_bear_level or 0.0
            
            # Calculate the sl, tp1, tp2, tp3 for bearish (only if we have left_high)
            bearish_sl = None
            bearish_tp1 = None
            bearish_tp2 = None
            bearish_tp3 = None
            
            if left_high_price is not None:
                bearish_sl = low_price + (left_high_price - low_price) * self.config.bearish_sl_fib_level
                bearish_tp1 = low_price + (left_high_price - low_price) * self.config.tp1_fib_level
                bearish_tp2 = low_price + (left_high_price - low_price) * self.config.tp2_fib_level
                bearish_tp3 = low_price + (left_high_price - low_price) * self.config.tp3_fib_level

            # Calculate the sl, tp1, tp2, tp3 for bullish (only if we have right_high)
            bullish_sl = None
            bullish_tp1 = None
            bullish_tp2 = None
            bullish_tp3 = None
            
            if right_high_price is not None:
                bullish_sl = right_high_price - (right_high_price - low_price) * self.config.bullish_sl_fib_level
                bullish_tp1 = right_high_price - (right_high_price - low_price) * self.config.tp1_fib_level
                bullish_tp2 = right_high_price - (right_high_price - low_price) * self.config.tp2_fib_level
                bullish_tp3 = right_high_price - (right_high_price - low_price) * self.config.tp3_fib_level
            
            # Extract swing high timestamp for bullish alert (right_high)
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
                "risk_score": confluence_score,
            })
            
            # Extract swing high timestamp for bearish alert (left_high)
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
                "risk_score": confluence_score,
            })
        return alerts

