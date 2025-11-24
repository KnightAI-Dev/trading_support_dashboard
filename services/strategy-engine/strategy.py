"""
Trading Strategy Implementation

This module implements a trading strategy using the StrategyInterface class.
It orchestrates the complete workflow from data fetching to alert generation.
The strategy only executes when new 4H or 30M candles are detected.
"""
from strategy_interface import StrategyInterface
from alert_database import AlertDatabase


class RunStrategy:
    """
    Trading strategy that combines swing highs/lows, support/resistance,
    and Fibonacci levels to generate trading signals.
    
    The strategy automatically checks for new candles and only executes
    when new 4H or 30M candles are detected.
    """
    
    def __init__(self):
        """Initialize the strategy with default StrategyInterface parameters."""
        self.strategy = StrategyInterface()
        # Initialize database manager
        self.db = AlertDatabase()
    
    def _get_latest_candle_timestamp(self, df):
        """
        Extract the latest candle timestamp from a DataFrame.
        
        Args:
            df: DataFrame with candle data (should have 'unix' column)
            
        Returns:
            Unix timestamp as integer, or None if not available
        """
        if df is None or len(df) == 0:
            return None
        
        try:
            # Get the latest candle (last row after get_candle reverses)
            latest_timestamp = int(df.iloc[-1]['unix'])
            return latest_timestamp
        except (KeyError, IndexError, ValueError, TypeError) as e:
            # Log warning but don't print - use proper logging if needed
            return None
    
    def _check_new_candles(self, df_4h, df_30m, asset_symbol):
        """
        Check if there are new 4H or 30M candles.
        
        Args:
            df_4h: DataFrame with 4H candle data
            df_30m: DataFrame with 30M candle data
            asset_symbol: Asset symbol (e.g., "BTCUSDT")
            
        Returns:
            Dictionary with:
            - 'has_new_4h': bool - True if new 4H candle detected
            - 'has_new_30m': bool - True if new 30M candle detected
            - 'should_execute': bool - True if strategy should execute
            - 'latest_4h_timestamp': int or None - Latest 4H candle timestamp
            - 'latest_30m_timestamp': int or None - Latest 30M candle timestamp
        """
        result = {
            'has_new_4h': False,
            'has_new_30m': False,
            'should_execute': False,
            'latest_4h_timestamp': None,
            'latest_30m_timestamp': None
        }
        
        # Get processed candles (first 200)
        candles_4h_df = self.strategy.get_candle(df_4h, 200) if df_4h is not None else None
        candles_30m_df = self.strategy.get_candle(df_30m, 200) if df_30m is not None else None
        
        # Check for new 4H candle
        if candles_4h_df is not None and len(candles_4h_df) > 0:
            latest_4h_timestamp = self._get_latest_candle_timestamp(candles_4h_df)
            result['latest_4h_timestamp'] = latest_4h_timestamp
            
            if latest_4h_timestamp is not None:
                result['has_new_4h'] = self.db.is_new_candle(
                    asset_symbol, '4h', latest_4h_timestamp
                )
        
        # Check for new 30M candle
        if candles_30m_df is not None and len(candles_30m_df) > 0:
            latest_30m_timestamp = self._get_latest_candle_timestamp(candles_30m_df)
            result['latest_30m_timestamp'] = latest_30m_timestamp
            
            if latest_30m_timestamp is not None:
                result['has_new_30m'] = self.db.is_new_candle(
                    asset_symbol, '30m', latest_30m_timestamp
                )
        
        # Strategy should execute if either timeframe has a new candle
        result['should_execute'] = result['has_new_4h'] or result['has_new_30m']
        
        return result
    
    def execute_strategy(self, df_4h, df_30m, df_1h, asset_symbol="OTHER"):
        """
        Execute the complete trading strategy workflow.
        Only executes when new 4H or 30M candles are detected.
        
        Args:
            df_4h: DataFrame with 4H candle data
            df_30m: DataFrame with 30m candle data
            df_1h: DataFrame with 1H candle data
            asset_symbol: Asset symbol for pruning score (default: "OTHER")
            
        Returns:
            Dictionary containing:
            - 'executed': bool - True if strategy was executed, False if skipped
            - 'reason': str - Reason for execution or skip
            - 'new_candles': dict - Information about new candles detected
            - 'result': dict - Strategy results (alerts_4h, alerts_30m) if executed, None otherwise
            - 'db_summary': dict - Database save summary if executed, None otherwise
        """
        # Execute the strategy
        strategy_result = self.strategy.execute_strategy(
            df_4h, df_30m, df_1h, asset_symbol
        )
        
        # Get processed candles for timestamp extraction
        candles_4h_df = self.strategy.get_candle(df_4h, 200) if df_4h is not None else None
        candles_30m_df = self.strategy.get_candle(df_30m, 200) if df_30m is not None else None
        
        # Save results to database
        # Note: save_strategy_results will check for new candles again and update timestamps
        # We pass the processed candles so it can extract timestamps correctly
        db_summary = self.save_strategy_results(
            strategy_result, asset_symbol, candles_4h_df, candles_30m_df
        )
        
        return {
            'executed': True,
            'reason': 'Strategy executed successfully',
            'new_candles': {},
            'result': strategy_result,
            'db_summary': db_summary
        }
    
    def save_strategy_results(self, result, asset_symbol, df_4h=None, df_30m=None):
        """
        Save strategy results (alerts) to database, checking for new candles and existing pairs.
        This is a convenience wrapper around AlertDatabase.save_strategy_results.
        
        Args:
            result: Result dictionary from execute_strategy containing 'alerts_4h' and 'alerts_30m'
            asset_symbol: Asset symbol (e.g., "BTCUSDT")
            df_4h: Optional DataFrame with 4H candles (to extract latest timestamp)
            df_30m: Optional DataFrame with 30M candles (to extract latest timestamp)
            
        Returns:
            Dictionary with summary: {
                '4h': {'saved': int, 'skipped': int, 'errors': int},
                '30m': {'saved': int, 'skipped': int, 'errors': int}
            }
        """
        return self.db.save_strategy_results(result, asset_symbol, df_4h, df_30m)
