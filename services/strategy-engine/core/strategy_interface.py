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

from config.settings import StrategyConfig
from indicators.swing_points import calculate_swing_points, filter_between, filter_rate
from indicators.support_resistance import get_support_resistance_levels
from indicators.fibonacci import calculate_fibonacci_levels
from core.confluence import ConfluenceAnalyzer
from alerts.generator import AlertGenerator
from shared.config import STRATEGY_CANDLE_COUNT


class StrategyInterface:
    """Core trading strategy interface."""
    
    def __init__(self, config: Optional[StrategyConfig] = None):
        """
        Initialize the strategy interface.
        
        Args:
            config: Optional StrategyConfig instance. If None, creates a new one.
        """
        self.config = config or StrategyConfig()
        self.confluence_analyzer = ConfluenceAnalyzer(self.config)
        self.alert_generator = AlertGenerator(self.config)
    
    def reload_config(self):
        """Reload configuration from database (useful for hot-reloading)."""
        self.config.reload()
    
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
        
        df = timeframe_ticker_df.copy()
        df = pd.concat([df, df.tail(1)], axis=0, ignore_index=True)
        df.dropna(inplace=True)
        df = df.iloc[:candle_counts+1]
        return df
    
    def get_swingHL(
        self, 
        timeframe_ticker_df: pd.DataFrame, 
        swing_high_low_candle_counts: int, 
        swing_pruning_rate: float
    ) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """
        Calculate and filter swing highs and lows from candle data.
        
        Args:
            timeframe_ticker_df: DataFrame with OHLC data (should have 'unix' column for datetime)
            swing_high_low_candle_counts: Minimum number of candles required
            swing_pruning_rate: Rate threshold for filtering swing points
            
        Returns:
            Tuple of (swing_highs_list, swing_lows_list) where each list contains (datetime, price) tuples
        """
        if timeframe_ticker_df is None or len(timeframe_ticker_df) < swing_high_low_candle_counts:
            return [], []
        
        try:
            swing_high_list, swing_low_list = calculate_swing_points(
                timeframe_ticker_df, 
                window=self.config.swing_window
            )

            filtered_swing_lows = filter_between(swing_high_list, swing_low_list, keep="min")
            filtered_swing_highs = filter_between(swing_low_list, swing_high_list, keep="max")

            filtered_swing_high_list, filtered_swing_low_list = \
                filter_rate(filtered_swing_highs, filtered_swing_lows, swing_pruning_rate)
            
            return filtered_swing_high_list, filtered_swing_low_list
        except Exception as e:
            # Return empty lists on any error
            return [], []
    
    def get_support_resistance(
        self, 
        timeframe_ticker_df: pd.DataFrame, 
        high_timeframe_flag: bool
    ) -> Tuple[List[Tuple[int, float]], List[Tuple[int, float]]]:
        """
        Calculate support and resistance levels from the DataFrame.
        
        Args:
            timeframe_ticker_df: pandas DataFrame with OHLC data (should have 'unix' column for timestamps)
            high_timeframe_flag: If True, uses open/close for HTF analysis. If False, uses low/high for LTF analysis.
            
        Returns:
            Tuple of (support_level_list, resistance_level_list) where each list contains
            tuples of (unix_timestamp, price)
        """
        return get_support_resistance_levels(
            timeframe_ticker_df,
            high_timeframe_flag,
            self.config.sensible_window
        )
    
    def execute_strategy(
        self, 
        df_4h: Optional[pd.DataFrame], 
        df_30m: Optional[pd.DataFrame], 
        df_1h: Optional[pd.DataFrame], 
        asset_symbol: str = "OTHER"
    ) -> Dict:
        """
        Execute the complete trading strategy workflow.
        
        Args:
            df_4h: DataFrame with 4H candle data
            df_30m: DataFrame with 30m candle data
            df_1h: DataFrame with 1H candle data
            asset_symbol: Asset symbol for pruning score (default: "OTHER")
            
        Returns:
            Dictionary containing:
            - alerts_4h: List of alerts for 4H timeframe
            - alerts_30m: List of alerts for 30M timeframe
        """
        # Step 1: Get candles (configurable count from environment variable)
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
        
        # Step 2: Get swing highs and lows
        swing_pruning_rate = self.config.get_pruning_score(asset_symbol)
        
        # Get swing highs and lows for available timeframes
        swing_highs_4h, swing_lows_4h = [], []
        if has_4h:
            swing_highs_4h, swing_lows_4h = self.get_swingHL(
                candles_4h_df, 
                self.config.candle_counts_for_swing_high_low,
                swing_pruning_rate
            )
            if swing_highs_4h is None:
                swing_highs_4h = []
            if swing_lows_4h is None:
                swing_lows_4h = []
        
        swing_highs_30m, swing_lows_30m = [], []
        if has_30m:
            swing_highs_30m, swing_lows_30m = self.get_swingHL(
                candles_30m_df,
                self.config.candle_counts_for_swing_high_low,
                swing_pruning_rate
            )
            if swing_highs_30m is None:
                swing_highs_30m = []
            if swing_lows_30m is None:
                swing_lows_30m = []
        
        # Step 3: Get support/resistance levels
        support_4h, resistance_4h = [], []
        if has_4h:
            support_4h, resistance_4h = self.get_support_resistance(
                candles_4h_df,
                high_timeframe_flag=True
            )
        
        support_1h, resistance_1h = self.get_support_resistance(
            candles_1h_df,
            high_timeframe_flag=False
        )
        
        # Step 4: Calculate Fibonacci levels
        fib_levels_4h = []
        if has_4h:
            fib_levels_4h = calculate_fibonacci_levels(
                swing_highs_4h,
                swing_lows_4h,
                timeframe="4h",
                config=self.config
            )
        
        fib_levels_30m = []
        if has_30m:
            fib_levels_30m = calculate_fibonacci_levels(
                swing_highs_30m,
                swing_lows_30m,
                timeframe="30m",
                config=self.config
            )
        
        # Step 5: Confirm swing high/low zones
        confirmed_4h = []
        if has_4h:
            support_resistance_dict_4h = {
                "4h": (support_4h, resistance_4h),
                "1h": (support_1h, resistance_1h)
            }
            
            confirmed_4h = self.confluence_analyzer.confirm_fib_levels(
                fib_levels_4h,
                support_resistance_dict_4h,
                timeframe="4h"
            )
        
        confirmed_30m = []
        if has_30m:
            support_resistance_dict_30m = {
                "1h": (support_1h, resistance_1h),
                "4h": (support_4h, resistance_4h)
            }
            
            confirmed_30m = self.confluence_analyzer.confirm_fib_levels(
                fib_levels_30m,
                support_resistance_dict_30m,
                timeframe="30m"
            )
        
        # Step 6: Confluence scoring
        confirmed_4h_with_marks = self.confluence_analyzer.add_confluence_marks(confirmed_4h) if has_4h else []
        confirmed_30m_with_marks = self.confluence_analyzer.add_confluence_marks(confirmed_30m) if has_30m else []
        
        # Step 7: Alert generation
        alerts_4h = []
        if has_4h:
            alerts_4h = self.alert_generator.generate_alerts(
                asset_symbol,
                confirmed_4h_with_marks,
                df=candles_4h_df
            )
        
        alerts_30m = []
        if has_30m:
            alerts_30m = self.alert_generator.generate_alerts(
                asset_symbol,
                confirmed_30m_with_marks,
                df=candles_30m_df
            )
        
        # Compile final result
        result = {
            "alerts_4h": alerts_4h,
            "alerts_30m": alerts_30m
        }
        
        return result

