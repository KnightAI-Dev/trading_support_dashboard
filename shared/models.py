"""
SQLAlchemy models for Trading Support Architecture
"""
from sqlalchemy import Column, Integer, String, Numeric, Boolean, DateTime, Text, CheckConstraint, Float, ForeignKey, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from datetime import datetime
from typing import Optional, List
import json

Base = declarative_base()


class Symbol(Base):
    """Symbol model with soft-delete support"""
    __tablename__ = "symbols"
    
    symbol_id = Column(Integer, primary_key=True, index=True)
    symbol_name = Column(String(20), unique=True, nullable=False, index=True)
    base_asset = Column(String(20), nullable=False)
    quote_asset = Column(String(20), nullable=False)
    image_path = Column(String(500), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, index=True)
    removed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Timeframe(Base):
    """Timeframe metadata model"""
    __tablename__ = "timeframe"
    
    timeframe_id = Column(Integer, primary_key=True, index=True)
    tf_name = Column(String(10), unique=True, nullable=False, index=True)
    seconds = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OHLCVCandle(Base):
    """OHLCV Candle model matching database schema with foreign keys"""
    __tablename__ = "ohlcv_candles"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, ForeignKey('symbols.symbol_id'), nullable=False, index=True)
    timeframe_id = Column(Integer, ForeignKey('timeframe.timeframe_id'), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    open = Column(Numeric(20, 8), nullable=False)
    high = Column(Numeric(20, 8), nullable=False)
    low = Column(Numeric(20, 8), nullable=False)
    close = Column(Numeric(20, 8), nullable=False)
    volume = Column(Numeric(30, 8), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships for easier access (optional, for ORM queries)
    symbol = relationship("Symbol", backref="candles")
    timeframe_rel = relationship("Timeframe", backref="candles")
    
    __table_args__ = (
        # Composite primary key matches database schema
        PrimaryKeyConstraint('symbol_id', 'timeframe_id', 'timestamp'),
    )


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


class StrategyAlert(Base):
    __tablename__ = "strategy_alerts"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol_id = Column(Integer, nullable=False, index=True)
    timeframe_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Entry and Risk Management
    entry_price = Column(Numeric(20, 8), nullable=False)
    stop_loss = Column(Numeric(20, 8), nullable=False)
    take_profit_1 = Column(Numeric(20, 8), nullable=False)
    take_profit_2 = Column(Numeric(20, 8), nullable=True)
    take_profit_3 = Column(Numeric(20, 8), nullable=True)
    risk_score = Column(String(20), nullable=True)  # e.g., 'none', 'good', 'high', 'higher', 'very_high'
    
    # Swing Pair Context
    swing_low_price = Column(Numeric(20, 8), nullable=False)
    swing_low_timestamp = Column(DateTime(timezone=True), nullable=False)
    swing_high_price = Column(Numeric(20, 8), nullable=False)
    swing_high_timestamp = Column(DateTime(timezone=True), nullable=False)
    
    # Additional context
    direction = Column(String(10), nullable=True)  # 'long' or 'short'
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    __table_args__ = (
        CheckConstraint("direction IN ('long', 'short')", name="check_strategy_alert_direction"),
    )


class StrategyConfig(Base):
    __tablename__ = "strategy_config"
    
    config_key = Column(String(100), primary_key=True, index=True)
    config_value = Column(Text, nullable=False)
    config_type = Column(String(20), nullable=False, default='string')
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    updated_by = Column(String(100), nullable=True)