"""
Configuration management for Trading Support Architecture
"""
import os
from typing import Optional
from decimal import Decimal

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://trading_user:trading_pass@localhost:5432/trading_db")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Binance API
BINANCE_API_URL = os.getenv("BINANCE_API_URL", "https://fapi.binance.com")
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")

# Limit for Number of market data to ingest
MARKET_DATA_LIMIT = int(os.getenv("MARKET_DATA_LIMIT", "200"))

# Limit for Number of symbols to ingest
SYMBOL_LIMIT = int(os.getenv("SYMBOL_LIMIT", "400"))

# CoinGecko API
COINGECKO_API_URL = os.getenv("COINGECKO_API_URL", "https://api.coingecko.com/api/v3")
COINGECKO_MIN_MARKET_CAP = float(os.getenv("COINGECKO_MIN_MARKET_CAP", "50000000"))  # 50M USD
COINGECKO_MIN_VOLUME_24H = float(os.getenv("COINGECKO_MIN_VOLUME_24H", "50000000"))  # 50M USD

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Fibonacci Configuration
FIB_LONG_ENTRY1 = Decimal("0.70")
FIB_LONG_ENTRY2 = Decimal("0.72")
FIB_LONG_SL = Decimal("0.90")
FIB_LONG_APPROACHING = Decimal("0.618")

FIB_SHORT_ENTRY1 = Decimal("0.618")
FIB_SHORT_ENTRY2 = Decimal("0.69")
FIB_SHORT_SL = Decimal("0.789")
FIB_SHORT_APPROACHING = Decimal("0.5")

FIB_PULLBACK_START = Decimal("0.382")

# Swing Detection
SWING_LOOKBACK_PERIODS = int(os.getenv("SWING_LOOKBACK_PERIODS", "5"))

# Support/Resistance
SR_TOUCH_THRESHOLD = int(os.getenv("SR_TOUCH_THRESHOLD", "2"))
SR_PRICE_TOLERANCE = Decimal(os.getenv("SR_PRICE_TOLERANCE", "0.001"))  # 0.1% tolerance

# Confluence Scoring
CONFLUENCE_WEIGHTS = {
    "OB": 20,  # Order Block
    "SR": 25,  # Support/Resistance
    "RSI": 15,  # RSI
    "FIB": 20,  # Fibonacci
    "SWING": 20  # Swing Points
}

# Risk Management
MIN_RISK_REWARD_RATIO = Decimal(os.getenv("MIN_RISK_REWARD_RATIO", "1.5"))
MAX_RISK_PERCENT = Decimal(os.getenv("MAX_RISK_PERCENT", "2.0"))

# Timeframes
DEFAULT_TIMEFRAME = os.getenv("DEFAULT_TIMEFRAME", "1h")
SUPPORTED_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d", "3d", "1w", "1M"]

# Symbols
DEFAULT_SYMBOLS = os.getenv("DEFAULT_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")

