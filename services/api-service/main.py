"""
API Service - FastAPI REST API for Trading Support Architecture
"""
import sys
import os
import asyncio
import json
from typing import List, Optional, Dict
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.database import get_db, init_db
from shared.models import TradingSignal, OHLCVCandle
from shared.logger import setup_logger
from shared.storage import StorageService
from shared.redis_client import get_redis

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


# WebSocket Connection Manager
class ConnectionManager:
    """Manages WebSocket connections and subscriptions"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Dict[str, set]] = {}  # ws_id -> {symbol -> {timeframe}}
        self.redis_listener_task: Optional[asyncio.Task] = None
    
    async def connect(self, websocket: WebSocket):
        """Accept a new WebSocket connection"""
        await websocket.accept()
        ws_id = str(id(websocket))
        self.active_connections[ws_id] = websocket
        self.subscriptions[ws_id] = {}
        logger.info(f"WebSocket client connected: {ws_id}")
        return ws_id
    
    def disconnect(self, ws_id: str):
        """Remove a WebSocket connection"""
        if ws_id in self.active_connections:
            del self.active_connections[ws_id]
        if ws_id in self.subscriptions:
            del self.subscriptions[ws_id]
        logger.info(f"WebSocket client disconnected: {ws_id}")
    
    def subscribe(self, ws_id: str, symbol: str, timeframe: str):
        """Subscribe a client to symbol/timeframe updates"""
        if ws_id not in self.subscriptions:
            self.subscriptions[ws_id] = {}
        if symbol not in self.subscriptions[ws_id]:
            self.subscriptions[ws_id][symbol] = set()
        self.subscriptions[ws_id][symbol].add(timeframe)
        logger.debug(f"Client {ws_id} subscribed to {symbol} {timeframe}")
    
    async def send_personal_message(self, ws_id: str, message: dict):
        """Send a message to a specific client"""
        if ws_id in self.active_connections:
            try:
                await self.active_connections[ws_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to client {ws_id}: {e}")
                self.disconnect(ws_id)
    
    async def broadcast_candle_update(self, candle_data: dict):
        """Broadcast candle update to all subscribed clients"""
        symbol = candle_data.get("symbol")
        timeframe = candle_data.get("timeframe")
        
        if not symbol or not timeframe:
            logger.warning(f"Candle update missing symbol or timeframe: {candle_data}")
            return
        
        clients_notified = 0
        for ws_id, subscriptions in self.subscriptions.items():
            if symbol in subscriptions and timeframe in subscriptions[symbol]:
                await self.send_personal_message(ws_id, {
                    "type": "candle",
                    "data": candle_data
                })
                clients_notified += 1
        
        logger.debug(f"Broadcasted candle update for {symbol} {timeframe} to {clients_notified} clients")
    
    async def broadcast_symbol_update(self, symbol_data: dict):
        """Broadcast symbol update to all connected clients - sends ticker data directly without DB query"""
        symbol = symbol_data.get("symbol")
        
        if not symbol:
            logger.warning(f"Symbol update missing symbol: {symbol_data}")
            return
        
        # Parse base/quote from symbol name if not present (e.g., "BTCUSDT" -> base: "BTC", quote: "USDT")
        if "base" not in symbol_data or "quote" not in symbol_data:
            symbol_str = symbol.upper()
            # Common quote assets to check
            quote_assets = ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB", "USD", "EUR", "GBP", "TRY"]
            for quote in quote_assets:
                if symbol_str.endswith(quote):
                    symbol_data["base"] = symbol_str[:-len(quote)]
                    symbol_data["quote"] = quote
                    break
            else:
                # Fallback: use entire symbol as base, default to USDT
                symbol_data["base"] = symbol_str
                symbol_data["quote"] = "USDT"
        
        # Broadcast directly - ticker event already contains: symbol, price, volume_24h, change24h
        # No need to query database which would be slow and potentially return stale data
        clients_notified = 0
        for ws_id in self.active_connections.keys():
            await self.send_personal_message(ws_id, {
                "type": "symbol_update",
                "data": symbol_data
            })
            clients_notified += 1
        
        logger.debug(f"Broadcasted symbol update for {symbol} to {clients_notified} clients")
    
    async def broadcast_marketcap_update(self, marketcap_data: dict):
        """Broadcast market cap update to all connected clients"""
        symbol = marketcap_data.get("symbol")
        
        if not symbol:
            logger.warning(f"Market cap update missing symbol: {marketcap_data}")
            return
        
        clients_notified = 0
        # Broadcast to all connected clients
        for ws_id in self.active_connections.keys():
            await self.send_personal_message(ws_id, {
                "type": "marketcap_update",
                "data": marketcap_data
            })
            clients_notified += 1
        
        logger.debug(f"Broadcasted market cap update for {symbol} to {clients_notified} clients")
    
    async def start_redis_listener(self):
        """Start listening to Redis pub/sub for candle updates"""
        redis_client = get_redis()
        if not redis_client:
            logger.warning("Redis not available, WebSocket candle updates disabled")
            return
        
        async def listen():
            """Listen for Redis pub/sub messages"""
            pubsub = redis_client.pubsub()
            pubsub.subscribe("candle_update", "symbol_update", "marketcap_update")
            
            logger.info("Redis listener started for candle, symbol, and marketcap updates")
            
            while True:
                try:
                    # Use asyncio.to_thread for blocking Redis call
                    message = await asyncio.to_thread(
                        pubsub.get_message,
                        ignore_subscribe_messages=True,
                        timeout=1.0
                    )
                    
                    if message and message.get("type") == "message":
                        try:
                            # Get channel name - handle both bytes and string
                            channel_raw = message.get("channel")
                            if isinstance(channel_raw, bytes):
                                channel = channel_raw.decode("utf-8")
                            else:
                                channel = str(channel_raw) if channel_raw else ""
                            
                            data = json.loads(message["data"])
                            
                            if channel == "candle_update":
                                logger.debug(f"Received candle_update event: {data.get('symbol')} {data.get('timeframe')}")
                                
                                # If full candle data is already in the message, use it
                                if all(key in data for key in ["symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume"]):
                                    logger.debug(f"Broadcasting full candle data for {data.get('symbol')} {data.get('timeframe')}")
                                    await self.broadcast_candle_update(data)
                                else:
                                    # Otherwise, fetch from database
                                    symbol = data.get("symbol")
                                    timeframe = data.get("timeframe")
                                    if symbol and timeframe:
                                        logger.debug(f"Fetching candle from DB for {symbol} {timeframe}")
                                        with StorageService() as storage:
                                            candles = storage.get_latest_candles(
                                                symbol,
                                                timeframe,
                                                limit=1
                                            )
                                            if candles:
                                                await self.broadcast_candle_update(candles[0])
                            
                            elif channel == "symbol_update":
                                await self.broadcast_symbol_update(data)
                            elif channel == "marketcap_update":
                                await self.broadcast_marketcap_update(data)
                            else:
                                logger.debug(f"Received message on unknown channel: {channel}")
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"Error parsing Redis message: {e}")
                        except Exception as e:
                            logger.error(f"Error processing update: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error in Redis listener: {e}")
                    await asyncio.sleep(1)
        
        self.redis_listener_task = asyncio.create_task(listen())
        logger.info("WebSocket Redis listener task started")

# Global connection manager instance
manager = ConnectionManager()


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    if not init_db():
        logger.error("Database initialization failed")
    else:
        logger.info("API service started")
    
    # Start Redis listener for WebSocket updates
    await manager.start_redis_listener()


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
    before: Optional[str] = Query(None, description="Fetch candles before this timestamp (ISO format)"),
    db: Session = Depends(get_db)
):
    """Get OHLCV candles for a symbol, optionally before a timestamp"""
    try:
        with StorageService() as storage:
            candles = storage.get_latest_candles(symbol, timeframe, limit, before)
            # Storage service already returns properly formatted dictionaries
            return candles
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


@app.get("/symbols")
async def get_symbols(db: Session = Depends(get_db)):
    """Get all symbols with latest prices and 24h change"""
    try:
        with StorageService() as storage:
            symbols = storage.get_symbols_with_prices()
            return symbols
    except Exception as e:
        logger.error(f"Error getting symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    ws_id = await manager.connect(websocket)
    
    # Send connection confirmation
    await websocket.send_json({
        "type": "connected",
        "message": "WebSocket connected successfully"
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "subscribe":
                symbol = data.get("symbol")
                timeframe = data.get("timeframe")
                if symbol and timeframe:
                    manager.subscribe(ws_id, symbol, timeframe)
                    logger.info(f"Client {ws_id} subscribed to {symbol} {timeframe}")
                    # Send subscription confirmation
                    await websocket.send_json({
                        "type": "subscribed",
                        "symbol": symbol,
                        "timeframe": timeframe,
                        "message": f"Subscribed to {symbol} {timeframe}"
                    })
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Missing symbol or timeframe in subscribe message"
                    })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {data.get('type')}"
                })
    except WebSocketDisconnect:
        manager.disconnect(ws_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        manager.disconnect(ws_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

