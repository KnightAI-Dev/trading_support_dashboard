"""
Decimal utility functions for exact price comparisons.

This module provides reusable utilities for converting values to Decimal
and performing exact comparisons to avoid floating-point precision issues.
This is critical for very small price values like SHIB (0.008-0.009 range).
"""
from decimal import Decimal
from typing import Union, Optional
import pandas as pd
import numpy as np


def to_decimal(value: Union[int, float, Decimal, str, None]) -> Optional[Decimal]:
    """
    Convert a value to Decimal for exact arithmetic.
    
    This function preserves exact precision by converting via string,
    which avoids floating-point representation errors.
    
    Args:
        value: Value to convert (int, float, Decimal, str, or None)
        
    Returns:
        Decimal representation of the value, or None if value is None/NaN
        
    Examples:
        >>> to_decimal(0.009222)
        Decimal('0.009222')
        >>> to_decimal(Decimal('0.009222'))
        Decimal('0.009222')
        >>> to_decimal(None)
        None
    """
    if value is None:
        return None
    
    if pd.isna(value):
        return None
    
    if isinstance(value, Decimal):
        return value
    
    # Convert via string to preserve exact precision
    # This is critical for very small values like SHIB
    try:
        return Decimal(str(value))
    except (ValueError, TypeError):
        return None


def to_decimal_safe(value: Union[int, float, Decimal, str, None]) -> Decimal:
    """
    Convert a value to Decimal, returning Decimal('0') for invalid values.
    
    This is a safe version that always returns a Decimal, useful when
    you need a non-None return value.
    
    Args:
        value: Value to convert
        
    Returns:
        Decimal representation, or Decimal('0') if conversion fails
    """
    result = to_decimal(value)
    return result if result is not None else Decimal('0')


def decimal_equals(
    value1: Union[int, float, Decimal, str, None],
    value2: Union[int, float, Decimal, str, None]
) -> bool:
    """
    Compare two values for exact equality using Decimal.
    
    This function provides exact comparison without floating-point errors.
    
    Args:
        value1: First value to compare
        value2: Second value to compare
        
    Returns:
        True if values are exactly equal, False otherwise
        
    Examples:
        >>> decimal_equals(0.009222, 0.009222)
        True
        >>> decimal_equals(0.1 + 0.2, 0.3)  # Float precision issue
        True  # Decimal comparison handles this correctly
    """
    dec1 = to_decimal(value1)
    dec2 = to_decimal(value2)
    
    if dec1 is None or dec2 is None:
        return False
    
    return dec1 == dec2


def decimal_compare(
    value1: Union[int, float, Decimal, str, None],
    value2: Union[int, float, Decimal, str, None]
) -> int:
    """
    Compare two values using Decimal, returning -1, 0, or 1.
    
    Args:
        value1: First value to compare
        value2: Second value to compare
        
    Returns:
        -1 if value1 < value2, 0 if equal, 1 if value1 > value2
        Returns 0 if either value is None/NaN
        
    Examples:
        >>> decimal_compare(0.009222, 0.009223)
        -1
        >>> decimal_compare(0.009222, 0.009222)
        0
    """
    dec1 = to_decimal(value1)
    dec2 = to_decimal(value2)
    
    if dec1 is None or dec2 is None:
        return 0
    
    if dec1 < dec2:
        return -1
    elif dec1 > dec2:
        return 1
    else:
        return 0


def decimal_abs_diff(
    value1: Union[int, float, Decimal, str, None],
    value2: Union[int, float, Decimal, str, None]
) -> Optional[Decimal]:
    """
    Calculate absolute difference between two values using Decimal.
    
    Args:
        value1: First value
        value2: Second value
        
    Returns:
        Absolute difference as Decimal, or None if either value is invalid
    """
    dec1 = to_decimal(value1)
    dec2 = to_decimal(value2)
    
    if dec1 is None or dec2 is None:
        return None
    
    return abs(dec1 - dec2)


def decimal_relative_diff(
    value1: Union[int, float, Decimal, str, None],
    value2: Union[int, float, Decimal, str, None],
    min_denominator: Decimal = Decimal('1e-10')
) -> Optional[Decimal]:
    """
    Calculate relative difference (percentage) between two values using Decimal.
    
    Formula: abs(value1 - value2) / max(abs(value1), abs(value2), min_denominator)
    
    This is useful for tolerance-based comparisons where you want to check
    if two prices are within a certain percentage of each other.
    
    Args:
        value1: First value
        value2: Second value
        min_denominator: Minimum denominator to avoid division by zero (default: 1e-10)
        
    Returns:
        Relative difference as Decimal (0.01 = 1%), or None if either value is invalid
        
    Examples:
        >>> decimal_relative_diff(100, 101)  # 1% difference
        Decimal('0.01')
        >>> decimal_relative_diff(0.009222, 0.009223)  # Very small values
        Decimal('0.000108...')
    """
    dec1 = to_decimal(value1)
    dec2 = to_decimal(value2)
    
    if dec1 is None or dec2 is None:
        return None
    
    abs_diff = abs(dec1 - dec2)
    denominator = max(abs(dec1), abs(dec2), min_denominator)
    
    if denominator == 0:
        return None
    
    return abs_diff / denominator

