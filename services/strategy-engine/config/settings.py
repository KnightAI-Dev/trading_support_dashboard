"""
Configuration management for strategy engine.

Loads configuration from database with fallback to defaults.
"""
import json
import sys
import os

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../../'))

from shared.config import STRATEGY_CANDLE_COUNT
from shared.storage import StorageService


class StrategyConfig:
    """Manages strategy configuration with database-backed values."""
    
    def __init__(self):
        """Initialize configuration with values from database or defaults."""
        self._load_config()
    
    def _load_config(self):
        """Load configuration values from database, with fallback to defaults."""
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
            self._set_defaults()
        else:
            # Set defaults for values not in database
            self.bearish_alert_level = 0.5
            self.bullish_alert_level = 0.618
            self.swing_sup_res_tolerance_pct = 0.01
            self.approaching_tolerance_pct = 0.01
    
    def _set_defaults(self):
        """Set all configuration to default values."""
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
        self.candle_counts_for_support_resistance = STRATEGY_CANDLE_COUNT
        self.bearish_alert_level = 0.5
        self.bullish_alert_level = 0.618
        self.swing_sup_res_tolerance_pct = 0.01
        self.approaching_tolerance_pct = 0.01
    
    def reload(self):
        """Reload configuration from database (useful for hot-reloading)."""
        self._load_config()
    
    def get_pruning_score(self, asset_symbol: str) -> float:
        """Get pruning score for a given asset symbol."""
        return self.swing_high_low_pruning_score.get(
            asset_symbol,
            self.swing_high_low_pruning_score.get('OTHER', 0.03)
        )

