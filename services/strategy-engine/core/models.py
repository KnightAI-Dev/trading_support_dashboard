"""
Data models for strategy engine.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional


@dataclass
class FibResult:
    """Container for raw Fibonacci calculations derived from swing points."""
    timeframe: str
    swing_low: Tuple[int, float]  # (datetime, price)
    swing_high: Tuple[int, float]  # (datetime, price)
    fib_level: float  # Fibonacci level price
    fib_type: str  # Type of Fibonacci level: "bear", "bull"


@dataclass
class ConfirmedFibResult(FibResult):
    """Fibonacci result enriched with support/resistance matches and confluence metadata."""
    match_4h: bool = False
    match_1h: bool = False
    match_both: bool = False
    additional_matches: Dict[str, bool] = field(default_factory=dict)
    confluence_mark: str = "none"
    confluence_count: int = 0

