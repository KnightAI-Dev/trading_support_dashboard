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
            # Extract swing low and swing high from new structure
            swing_low = level.swing_low
            swing_high = level.swing_high
            fib_level = level.fib_level
            fib_type = level.fib_type
            
            # Validate required data
            if swing_low is None or swing_high is None:
                continue
            
            try:
                # Extract prices and datetimes from tuples
                swing_low_dt = swing_low[0] if isinstance(swing_low, (tuple, list)) and len(swing_low) >= 2 else None
                swing_low_price = swing_low[1] if isinstance(swing_low, (tuple, list)) and len(swing_low) >= 2 else None
                swing_high_dt = swing_high[0] if isinstance(swing_high, (tuple, list)) and len(swing_high) >= 2 else None
                swing_high_price = swing_high[1] if isinstance(swing_high, (tuple, list)) and len(swing_high) >= 2 else None
                
                # Convert prices to Decimal for exact validation and comparison
                swing_low_decimal = to_decimal(swing_low_price)
                if swing_low_decimal is None or swing_low_decimal <= 0:
                    continue
                
                # Validate swing_high_price extraction and price relationships
                if swing_high_price is None:
                    continue
                
                swing_high_decimal = to_decimal(swing_high_price)
                if swing_high_decimal is None or decimal_compare(swing_high_decimal, swing_low_decimal) <= 0:
                    continue
                    
            except (IndexError, TypeError, ValueError) as e:
                # Skip this level if we can't extract prices
                continue
            
            # Extract swing timestamps from tuples
            swing_low_timestamp = swing_low_dt if swing_low_dt is not None and swing_low_dt > 0 else None
            swing_high_timestamp = swing_high_dt if swing_high_dt is not None and swing_high_dt > 0 else None
            
            # Get the confluence score (cap at 3 for very_high)
            confluence_score = min(level.confluence_count or 0, 3)
            
            # Get the fib level price as entry level
            entry_level = fib_level if fib_level is not None else 0.0
            
            
            # Process based on fib_type
            if fib_type == "bull":
                # Bullish alert: Calculate SL/TP from swing_high to swing_low
                swing_high_decimal = to_decimal(swing_high_price)
                if swing_high_decimal is not None:
                    price_diff = swing_high_decimal - swing_low_decimal
                    sl = float(swing_high_decimal - price_diff * to_decimal_safe(self.config.bullish_sl_fib_level))
                    tp1 = float(swing_high_decimal - price_diff * to_decimal_safe(self.config.tp1_fib_level))
                    tp2 = float(swing_high_decimal - price_diff * to_decimal_safe(self.config.tp2_fib_level))
                    tp3 = float(swing_high_decimal - price_diff * to_decimal_safe(self.config.tp3_fib_level))
                    
                    alerts.append({
                        "timeframe": level.timeframe or "unknown",
                        "trend_type": "long",
                        "asset": asset_symbol,
                        "entry_level": entry_level,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "tp3": tp3,
                        "swing_low_price": swing_low_price,
                        "swing_high_price": swing_high_price,
                        "swing_low_timestamp": swing_low_timestamp,
                        "swing_high_timestamp": swing_high_timestamp,
                        "risk_score": confluence_score,
                    })
            
            elif fib_type == "bear":
                # Bearish alert: Calculate SL/TP from swing_low to swing_high
                swing_high_decimal = to_decimal(swing_high_price)
                if swing_high_decimal is not None:
                    price_diff = swing_high_decimal - swing_low_decimal
                    sl = float(swing_low_decimal + price_diff * to_decimal_safe(self.config.bearish_sl_fib_level))
                    tp1 = float(swing_low_decimal + price_diff * to_decimal_safe(self.config.tp1_fib_level))
                    tp2 = float(swing_low_decimal + price_diff * to_decimal_safe(self.config.tp2_fib_level))
                    tp3 = float(swing_low_decimal + price_diff * to_decimal_safe(self.config.tp3_fib_level))
                    
                    alerts.append({
                        "timeframe": level.timeframe or "unknown",
                        "trend_type": "short",
                        "asset": asset_symbol,
                        "entry_level": entry_level,
                        "sl": sl,
                        "tp1": tp1,
                        "tp2": tp2,
                        "tp3": tp3,
                        "swing_low_price": swing_low_price,
                        "swing_high_price": swing_high_price,
                        "swing_low_timestamp": swing_low_timestamp,
                        "swing_high_timestamp": swing_high_timestamp,
                        "risk_score": confluence_score,
                    })
        return alerts

