"""
SQLAlchemy models for Trading Support Architecture
"""
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Text, CheckConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
import json

Base = declarative_base()


class OHLCVCandle(Base):
    __tablename__ = "ohlcv_candles"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(30, 8), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class MarketData(Base):
    __tablename__ = "market_data"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    market_cap = Column(Numeric(30, 2), nullable=True)
    price = Column(Numeric(20, 8), nullable=True)
    circulating_supply = Column(Numeric(30, 2), nullable=True)
    volume_24h = Column(Numeric(30, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AssetInfo(Base):
    __tablename__ = "asset_info"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), unique=True, nullable=False, index=True)
    base_asset = Column(String(20), nullable=False)
    quote_asset = Column(String(20), nullable=False)
    tick_size = Column(Numeric(20, 8), nullable=True)
    lot_size = Column(Numeric(20, 8), nullable=True)
    min_qty = Column(Numeric(20, 8), nullable=True)
    max_qty = Column(Numeric(20, 8), nullable=True)
    step_size = Column(Numeric(20, 8), nullable=True)
    status = Column(String(20), default="TRADING")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class SwingPoint(Base):
    __tablename__ = "swing_points"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    price = Column(Numeric(20, 8), nullable=False)
    type = Column(String(10), nullable=False)  # 'swing_high' or 'swing_low'
    strength = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        CheckConstraint("type IN ('swing_high', 'swing_low')", name="check_swing_type"),
    )


class SupportResistance(Base):
    __tablename__ = "support_resistance"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    level = Column(Numeric(20, 8), nullable=False, index=True)
    type = Column(String(10), nullable=False)  # 'support' or 'resistance'
    strength = Column(Integer, default=1)
    first_touch = Column(DateTime(timezone=True), nullable=False)
    last_touch = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint("type IN ('support', 'resistance')", name="check_sr_type"),
    )


class FibonacciLevel(Base):
    __tablename__ = "fibonacci_levels"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    swing_high = Column(Numeric(20, 8), nullable=False)
    swing_low = Column(Numeric(20, 8), nullable=False)
    fib_0 = Column(Numeric(20, 8), nullable=False)
    fib_0_236 = Column(Numeric(20, 8), nullable=True)
    fib_0_382 = Column(Numeric(20, 8), nullable=True)
    fib_0_5 = Column(Numeric(20, 8), nullable=True)
    fib_0_618 = Column(Numeric(20, 8), nullable=True)
    fib_0_70 = Column(Numeric(20, 8), nullable=True)
    fib_0_72 = Column(Numeric(20, 8), nullable=True)
    fib_0_789 = Column(Numeric(20, 8), nullable=True)
    fib_0_90 = Column(Numeric(20, 8), nullable=True)
    fib_1 = Column(Numeric(20, 8), nullable=False)
    direction = Column(String(10), nullable=False)  # 'long' or 'short'
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        CheckConstraint("direction IN ('long', 'short')", name="check_fib_direction"),
    )


class TradingSignal(Base):
    __tablename__ = "trading_signals"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    market_score = Column(Integer, nullable=False)  # 0-100
    direction = Column(String(10), nullable=False)  # 'long' or 'short'
    price = Column(Numeric(20, 8), nullable=False)
    entry1 = Column(Numeric(20, 8), nullable=True)
    entry2 = Column(Numeric(20, 8), nullable=True)
    sl = Column(Numeric(20, 8), nullable=True)
    tp1 = Column(Numeric(20, 8), nullable=True)
    tp2 = Column(Numeric(20, 8), nullable=True)
    tp3 = Column(Numeric(20, 8), nullable=True)
    swing_high = Column(Numeric(20, 8), nullable=True)
    swing_low = Column(Numeric(20, 8), nullable=True)
    support_level = Column(Numeric(20, 8), nullable=True)
    resistance_level = Column(Numeric(20, 8), nullable=True)
    confluence = Column(Text, nullable=True)  # JSON array string
    risk_reward_ratio = Column(Numeric(10, 4), nullable=True)
    pullback_detected = Column(Boolean, default=False)
    pullback_start_level = Column(Numeric(20, 8), nullable=True)
    approaching_fib_level = Column(Numeric(20, 8), nullable=True)
    confidence_score = Column(Numeric(5, 2), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        CheckConstraint("direction IN ('long', 'short')", name="check_signal_direction"),
        CheckConstraint("market_score >= 0 AND market_score <= 100", name="check_market_score"),
    )
    
    def get_confluence_list(self) -> List[str]:
        """Parse confluence JSON string to list"""
        if not self.confluence:
            return []
        try:
            return json.loads(self.confluence)
        except:
            return []
    
    def set_confluence_list(self, factors: List[str]):
        """Set confluence as JSON string"""
        self.confluence = json.dumps(factors) if factors else None


class ConfluenceFactor(Base):
    __tablename__ = "confluence_factors"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    factor_type = Column(String(20), nullable=False, index=True)
    factor_value = Column(Numeric(20, 8), nullable=True)
    factor_score = Column(Integer, default=0)  # 0-100
    metadata_json = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class FibConfig(Base):
    __tablename__ = "fib_config"
    
    id = Column(Integer, primary_key=True, index=True)
    setup_type = Column(String(10), unique=True, nullable=False)  # 'long' or 'short'
    entry_level1 = Column(Numeric(5, 3), nullable=False)
    entry_level2 = Column(Numeric(5, 3), nullable=False)
    sl_level = Column(Numeric(5, 3), nullable=False)
    approaching_level = Column(Numeric(5, 3), nullable=False)
    pullback_start = Column(Numeric(5, 3), default=0.382)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint("setup_type IN ('long', 'short')", name="check_setup_type"),
    )

