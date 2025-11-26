# Decimal Data Type Migration

## Overview

The strategy engine has been updated to use `Decimal` data type for all price comparisons and calculations to avoid floating-point precision issues. This is critical for very small price values like SHIB (0.008-0.009 range) where floating-point errors can cause incorrect swing point detection and price comparisons.

## Architecture

### Shared Utilities (`utils/decimal_utils.py`)

A centralized utility module provides reusable functions for Decimal operations:

- **`to_decimal(value)`**: Converts any value to Decimal, preserving exact precision via string conversion
- **`to_decimal_safe(value)`**: Always returns a Decimal (returns Decimal('0') for invalid values)
- **`decimal_equals(value1, value2)`**: Exact equality comparison using Decimal
- **`decimal_compare(value1, value2)`**: Returns -1, 0, or 1 for comparison
- **`decimal_abs_diff(value1, value2)`**: Calculates absolute difference using Decimal
- **`decimal_relative_diff(value1, value2)`**: Calculates relative difference (percentage) using Decimal

### Benefits

1. **Scalable**: Centralized utilities make it easy to extend Decimal usage to new modules
2. **Efficient**: Minimal overhead - only converts to Decimal when needed for comparisons
3. **Reusable**: All modules use the same utility functions for consistency
4. **Easy to Understand**: Clear function names and comprehensive documentation

## Updated Modules

### 1. `indicators/swing_points.py`

**Changes:**
- Uses `to_decimal()` and `to_decimal_safe()` from shared utilities
- All price comparisons in `calculate_swing_points()` use Decimal
- `enforce_strict_alternation()` uses Decimal for price comparisons
- `filter_rate()` uses Decimal for all rate calculations and comparisons

**Key Updates:**
- Line 107-125: `decimal_equals()` function uses Decimal for swing high/low detection
- Line 333-342: Price comparisons in `enforce_strict_alternation()` use Decimal
- Line 419-470: All rate calculations and comparisons in `filter_rate()` use Decimal

### 2. `indicators/fibonacci.py`

**Changes:**
- Price validation uses Decimal
- All Fibonacci calculations use Decimal arithmetic
- Config values converted to Decimal before calculations

**Key Updates:**
- Line 48-52: Price validation uses `to_decimal()`
- Line 106-124: Bullish Fibonacci calculations use Decimal
- Line 127-143: Bearish Fibonacci calculations use Decimal

### 3. `indicators/support_resistance.py`

**Changes:**
- Price comparisons in `support()` and `resistance()` functions use Decimal
- Uses `decimal_compare()` for exact price comparisons

**Key Updates:**
- Line 52-68: Support level detection uses Decimal comparison
- Line 118-134: Resistance level detection uses Decimal comparison

### 4. `core/confluence.py`

**Changes:**
- Tolerance-based comparisons use `decimal_relative_diff()` for exact percentage calculations
- All Fibonacci level matching uses Decimal

**Key Updates:**
- Line 92-113: All Fibonacci level matching uses Decimal relative difference calculations

### 5. `alerts/generator.py`

**Changes:**
- Price validations use Decimal
- Rate calculations use Decimal
- All price comparisons use Decimal
- SL/TP calculations use Decimal arithmetic

**Key Updates:**
- Line 72-79: Price relationship validation uses Decimal
- Line 101-117: SL/TP calculations use Decimal
- Line 122-131: Rate calculations use Decimal
- Line 151-160: Bearish rate calculations use Decimal

## Usage Examples

### Converting a Price to Decimal

```python
from utils.decimal_utils import to_decimal

price = 0.009222
price_decimal = to_decimal(price)  # Decimal('0.009222')
```

### Exact Price Comparison

```python
from utils.decimal_utils import decimal_equals

# Avoids floating-point errors
if decimal_equals(price1, price2):
    # Prices are exactly equal
    pass
```

### Relative Difference (Tolerance-Based Comparison)

```python
from utils.decimal_utils import decimal_relative_diff, to_decimal_safe

tolerance = to_decimal_safe(0.01)  # 1% tolerance
rel_diff = decimal_relative_diff(fib_level, support_level)

if rel_diff is not None and rel_diff <= tolerance:
    # Prices are within tolerance
    pass
```

## Performance Considerations

- **Minimal Overhead**: Decimal conversion only happens when needed for comparisons
- **String Conversion**: Using `Decimal(str(value))` preserves exact precision
- **Efficient**: Shared utilities avoid code duplication
- **Scalable**: Easy to add new Decimal operations as needed

## Testing Recommendations

1. Test with very small price values (e.g., SHIB: 0.008-0.009)
2. Test with large price values (e.g., BTC: 50000+)
3. Test edge cases: zero prices, negative prices, NaN values
4. Verify that all price comparisons are exact (no floating-point errors)

## Migration Notes

- All functions still return float values in their public APIs (for compatibility)
- Internal calculations use Decimal for exact precision
- No breaking changes to function signatures
- All modules consistently use the shared utility functions

## Future Enhancements

Potential improvements:
1. Add Decimal-based price validation utilities
2. Create Decimal-based statistical functions (mean, std dev, etc.)
3. Add Decimal-based rounding utilities for price formatting
4. Consider using Decimal throughout the data pipeline (not just comparisons)

