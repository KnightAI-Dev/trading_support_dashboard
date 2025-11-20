"""
API Service - FastAPI REST API for Trading Support Architecture
"""
import sys
import os
from typing import List, Optional, Dict
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.database import get_db, init_db
from shared.models import TradingSignal, OHLCVCandle
from shared.logger import setup_logger
from shared.storage import StorageService

logger = setup_logger(__name__)

DEFAULT_SYMBOLS = [
    symbol.strip()
    for symbol in os.getenv("DEFAULT_SYMBOLS", "BTCUSDT,ETHUSDT,SOLUSDT").split(",")
    if symbol.strip()
]

DEFAULT_TIMEFRAMES = [
    tf.strip()
    for tf in os.getenv("DEFAULT_TIMEFRAMES", "1m,5m,15m,1h,4h").split(",")
    if tf.strip()
]

app = FastAPI(
    title="Trading Support API",
    description="REST API for Trading Support Architecture",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class TradingSignalResponse(BaseModel):
    id: int
    symbol: str
    timestamp: datetime
    market_score: int
    direction: str
    price: float
    entry1: Optional[float]
    entry2: Optional[float]
    sl: Optional[float]
    tp1: Optional[float]
    tp2: Optional[float]
    tp3: Optional[float]
    swing_high: Optional[float]
    swing_low: Optional[float]
    support_level: Optional[float]
    resistance_level: Optional[float]
    confluence: Optional[str]
    risk_reward_ratio: Optional[float]
    pullback_detected: bool
    confidence_score: Optional[float]
    
    class Config:
        from_attributes = True


class SignalSummary(BaseModel):
    symbol: str
    market_score: int
    direction: str
    price: float
    entry1: Optional[float]
    sl: Optional[float]
    tp1: Optional[float]
    tp2: Optional[float]
    tp3: Optional[float]
    swing_high: Optional[float]
    swing_low: Optional[float]
    support_level: Optional[float]
    resistance_level: Optional[float]
    confluence: Optional[str]


class MarketMetadataResponse(BaseModel):
    symbols: List[str]
    timeframes: List[str]
    symbol_timeframes: Dict[str, List[str]]


def _default_market_metadata() -> Dict[str, List[str]]:
    return {
        "symbols": DEFAULT_SYMBOLS,
        "timeframes": DEFAULT_TIMEFRAMES,
        "symbol_timeframes": {symbol: DEFAULT_TIMEFRAMES for symbol in DEFAULT_SYMBOLS},
    }


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    if not init_db():
        logger.error("Database initialization failed")
    else:
        logger.info("API service started")


@app.get("/")
async def root():
    """Root endpoint"""
    return {"message": "Trading Support API", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/metadata/market", response_model=MarketMetadataResponse)
async def get_market_metadata(db: Session = Depends(get_db)):
    """Get available symbols and timeframes from database"""
    try:
        with StorageService() as storage:
            # This queries the database directly from ohlcv_candles table
            metadata = storage.get_market_metadata()
            # StorageService already handles empty database case with defaults
            # but we ensure we always return valid data
            if not metadata or not metadata.get("symbols"):
                logger.warning("No symbols found in database, using defaults")
                metadata = _default_market_metadata()
            return metadata
    except Exception as e:
        logger.error(f"Error getting market metadata from database: {e}")
        # Only fallback to defaults on actual database errors
        return _default_market_metadata()


@app.get("/signals", response_model=List[TradingSignalResponse])
async def get_signals(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    direction: Optional[str] = Query(None, description="Filter by direction (long/short)"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    db: Session = Depends(get_db)
):
    """Get trading signals"""
    try:
        with StorageService() as storage:
            signals = storage.get_signals(symbol=symbol, direction=direction, limit=limit)
            return signals
    except Exception as e:
        logger.error(f"Error getting signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/{symbol}/latest", response_model=TradingSignalResponse)
async def get_latest_signal(
    symbol: str,
    db: Session = Depends(get_db)
):
    """Get latest signal for a symbol"""
    try:
        with StorageService() as storage:
            signal = storage.get_latest_signal(symbol)
            if not signal:
                raise HTTPException(status_code=404, detail=f"No signal found for {symbol}")
            return signal
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/signals/summary", response_model=List[SignalSummary])
async def get_signals_summary(
    db: Session = Depends(get_db)
):
    """Get summary of latest signals for all symbols"""
    try:
        with StorageService() as storage:
            # Get latest signal for each symbol
            signals = storage.get_signals(limit=1000)
            
            # Group by symbol and get latest
            symbol_map = {}
            for signal in signals:
                if signal.symbol not in symbol_map:
                    symbol_map[signal.symbol] = signal
                elif signal.timestamp > symbol_map[signal.symbol].timestamp:
                    symbol_map[signal.symbol] = signal
            
            return list(symbol_map.values())
    except Exception as e:
        logger.error(f"Error getting signals summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    timeframe: str = Query("1h", description="Timeframe"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    db: Session = Depends(get_db)
):
    """Get OHLCV candles for a symbol"""
    try:
        with StorageService() as storage:
            candles = storage.get_latest_candles(symbol, timeframe, limit)
            return [
                {
                    "symbol": c.symbol,
                    "timeframe": c.timeframe,
                    "timestamp": c.timestamp,
                    "open": float(c.open),
                    "high": float(c.high),
                    "low": float(c.low),
                    "close": float(c.close),
                    "volume": float(c.volume)
                }
                for c in candles
            ]
    except Exception as e:
        logger.error(f"Error getting candles: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/sr-levels/{symbol}")
async def get_sr_levels(
    symbol: str,
    timeframe: str = Query("1h", description="Timeframe"),
    db: Session = Depends(get_db)
):
    """Get support and resistance levels for a symbol"""
    try:
        with StorageService() as storage:
            levels = storage.get_active_sr_levels(symbol, timeframe)
            return levels
    except Exception as e:
        logger.error(f"Error getting S/R levels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/swings/{symbol}")
async def get_swings(
    symbol: str,
    timeframe: str = Query("1h", description="Timeframe"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    db: Session = Depends(get_db)
):
    """Get latest swing points for a symbol"""
    try:
        with StorageService() as storage:
            swings = storage.get_latest_swings(symbol, timeframe, limit)
            return swings
    except Exception as e:
        logger.error(f"Error getting swings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

