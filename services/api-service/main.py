"""
API Service - FastAPI REST API for Trading Support Architecture
"""
import sys
import os
import asyncio
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.database import get_db, init_db, DatabaseManager
from shared.models import OHLCVCandle
from shared.logger import setup_logger
from shared.storage import StorageService
from shared.redis_client import get_redis
from sqlalchemy import text

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
class StrategyAlertResponse(BaseModel):
    id: int
    symbol: str
    timeframe: str
    timestamp: datetime
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: Optional[float]
    take_profit_3: Optional[float]
    risk_score: Optional[str]
    swing_low_price: float
    swing_low_timestamp: datetime
    swing_high_price: float
    swing_high_timestamp: datetime
    direction: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class AlertSummary(BaseModel):
    symbol: str
    timeframe: str
    direction: Optional[str]
    entry_price: float
    stop_loss: float
    take_profit_1: float
    risk_score: Optional[str]


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
        # Create a copy of keys to avoid "dictionary keys changed during iteration" error
        # if connections are removed during iteration
        clients_notified = 0
        for ws_id in list(self.active_connections.keys()):
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
        # Create a copy of keys to avoid "dictionary keys changed during iteration" error
        for ws_id in list(self.active_connections.keys()):
            await self.send_personal_message(ws_id, {
                "type": "marketcap_update",
                "data": marketcap_data
            })
            clients_notified += 1
        
        logger.debug(f"Broadcasted market cap update for {symbol} to {clients_notified} clients")
    
    async def broadcast_strategy_alert(self, alert_data: dict):
        """Broadcast strategy alert to all connected clients as TradingSignal"""
        symbol = alert_data.get("symbol")
        timeframe = alert_data.get("timeframe", "")
        
        if not symbol:
            logger.warning(f"Strategy alert missing symbol: {alert_data}")
            return
        
        # Ensure timestamp is a string (ISO format)
        timestamp = alert_data.get("timestamp")
        if timestamp and not isinstance(timestamp, str):
            # Convert datetime to ISO string if needed
            if hasattr(timestamp, 'isoformat'):
                timestamp = timestamp.isoformat()
            else:
                timestamp = str(timestamp)
        
        # Extract swing timestamps and ensure they're in ISO format
        swing_low_timestamp = alert_data.get("swing_low_timestamp")
        if swing_low_timestamp and not isinstance(swing_low_timestamp, str):
            if hasattr(swing_low_timestamp, 'isoformat'):
                swing_low_timestamp = swing_low_timestamp.isoformat()
            else:
                swing_low_timestamp = str(swing_low_timestamp)
        
        swing_high_timestamp = alert_data.get("swing_high_timestamp")
        if swing_high_timestamp and not isinstance(swing_high_timestamp, str):
            if hasattr(swing_high_timestamp, 'isoformat'):
                swing_high_timestamp = swing_high_timestamp.isoformat()
            else:
                swing_high_timestamp = str(swing_high_timestamp)
        
        # Map strategy_alert to TradingSignal format expected by frontend
        signal_data = {
            "id": alert_data.get("id"),
            "symbol": symbol,
            "timeframe": timeframe,  # Include timeframe
            "timestamp": timestamp or datetime.now().isoformat(),
            "market_score": 0,  # Not available in strategy_alerts, default to 0
            "direction": alert_data.get("direction", "long"),
            "price": alert_data.get("entry_price", 0),
            "entry1": alert_data.get("entry_price"),
            "entry2": None,  # Not available in strategy_alerts
            "sl": alert_data.get("stop_loss"),
            "tp1": alert_data.get("take_profit_1"),
            "tp2": alert_data.get("take_profit_2"),
            "tp3": alert_data.get("take_profit_3"),
            "swing_high": alert_data.get("swing_high_price"),
            "swing_high_timestamp": swing_high_timestamp,  # Add swing high timestamp
            "swing_low": alert_data.get("swing_low_price"),
            "swing_low_timestamp": swing_low_timestamp,  # Add swing low timestamp
            "support_level": None,  # Not available in strategy_alerts
            "resistance_level": None,  # Not available in strategy_alerts
            "confluence": alert_data.get("risk_score"),  # Use risk_score as confluence
            "risk_reward_ratio": None,  # Can be calculated if needed
            "pullback_detected": False,  # Not available in strategy_alerts
            "confidence_score": None  # Not available in strategy_alerts
        }
        
        clients_notified = 0
        # Broadcast to all connected clients (signals are important, everyone should see them)
        # Create a copy of keys to avoid "dictionary keys changed during iteration" error
        for ws_id in list(self.active_connections.keys()):
            try:
                await self.send_personal_message(ws_id, {
                    "type": "signal",
                    "data": signal_data
                })
                clients_notified += 1
            except Exception as e:
                logger.error(f"Error sending signal to client {ws_id}: {e}")
        
        logger.info(
            f"Broadcasted strategy alert for {symbol} {timeframe} to {clients_notified} clients",
            extra={
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": signal_data.get("direction"),
                "clients_notified": clients_notified
            }
        )
    
    async def start_redis_listener(self):
        """Start listening to Redis pub/sub for candle updates"""
        redis_client = get_redis()
        if not redis_client:
            logger.warning("Redis not available, WebSocket candle updates disabled")
            return
        
        async def listen():
            """Listen for Redis pub/sub messages"""
            pubsub = redis_client.pubsub()
            pubsub.subscribe("candle_update", "symbol_update", "marketcap_update", "strategy_alert")
            
            logger.info("Redis listener started for candle, symbol, marketcap, and strategy alert updates")
            
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
                            elif channel == "strategy_alert":
                                logger.info(
                                    f"Received strategy_alert event: {data.get('symbol')} {data.get('timeframe')}",
                                    extra={"alert_id": data.get("id"), "symbol": data.get("symbol")}
                                )
                                await self.broadcast_strategy_alert(data)
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


@app.get("/alerts", response_model=List[StrategyAlertResponse])
async def get_alerts(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    timeframe: Optional[str] = Query(None, description="Filter by timeframe"),
    direction: Optional[str] = Query(None, description="Filter by direction (long/short)"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    db: Session = Depends(get_db)
):
    """Get strategy alerts"""
    try:
        with StorageService() as storage:
            alerts = storage.get_strategy_alerts(symbol=symbol, timeframe=timeframe, direction=direction, limit=limit)
            return alerts
    except Exception as e:
        logger.error(f"Error getting alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/{symbol}/latest", response_model=StrategyAlertResponse)
async def get_latest_alert(
    symbol: str,
    timeframe: Optional[str] = Query(None, description="Filter by timeframe"),
    db: Session = Depends(get_db)
):
    """Get latest alert for a symbol"""
    try:
        with StorageService() as storage:
            alert = storage.get_latest_strategy_alert(symbol, timeframe=timeframe)
            if not alert:
                raise HTTPException(status_code=404, detail=f"No alert found for {symbol}")
            return alert
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/{symbol}/swings", response_model=List[StrategyAlertResponse])
async def get_alerts_for_swings(
    symbol: str,
    timeframe: str = Query(..., description="Timeframe (required)"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    db: Session = Depends(get_db)
):
    """Get strategy alerts for a specific symbol and timeframe to extract swing points from database"""
    try:
        with StorageService() as storage:
            alerts = storage.get_strategy_alerts(symbol=symbol, timeframe=timeframe, limit=limit)
            return alerts
    except Exception as e:
        logger.error(f"Error getting alerts for swings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/summary", response_model=List[AlertSummary])
async def get_alerts_summary(
    db: Session = Depends(get_db)
):
    """Get summary of latest alerts for all symbols"""
    try:
        with StorageService() as storage:
            # Get latest alert for each symbol/timeframe combination
            alerts = storage.get_strategy_alerts(limit=1000)
            
            # Group by symbol and get latest
            symbol_map = {}
            for alert in alerts:
                key = f"{alert['symbol']}_{alert.get('timeframe', '')}"
                if key not in symbol_map:
                    symbol_map[key] = alert
                elif alert['timestamp'] > symbol_map[key]['timestamp']:
                    symbol_map[key] = alert
            
            return [
                AlertSummary(
                    symbol=a['symbol'],
                    timeframe=a.get('timeframe', ''),
                    direction=a.get('direction'),
                    entry_price=a['entry_price'],
                    stop_loss=a['stop_loss'],
                    take_profit_1=a['take_profit_1'],
                    risk_score=a.get('risk_score')
                )
                for a in symbol_map.values()
            ]
    except Exception as e:
        logger.error(f"Error getting alerts summary: {e}")
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


@app.get("/symbols/{symbol}/details")
async def get_symbol_details(symbol: str, db: Session = Depends(get_db)):
    """Get detailed symbol information including market data"""
    try:
        with StorageService() as storage:
            details = storage.get_symbol_details(symbol)
            if not details:
                raise HTTPException(status_code=404, detail=f"Symbol {symbol} not found")
            return details
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting symbol details for {symbol}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Strategy Configuration endpoints
class StrategyConfigResponse(BaseModel):
    config_key: str
    config_value: str
    config_type: str
    description: Optional[str]
    updated_at: Optional[datetime]
    updated_by: Optional[str]
    
    class Config:
        from_attributes = True


class StrategyConfigUpdate(BaseModel):
    config_value: str


class StrategyConfigBulkUpdate(BaseModel):
    configs: Dict[str, str]


@app.get("/strategy-config", response_model=Dict[str, Any])
async def get_strategy_config(
    config_key: Optional[str] = Query(None, description="Get specific config key"),
    db: Session = Depends(get_db)
):
    """Get strategy configuration values"""
    try:
        with StorageService() as storage:
            configs = storage.get_strategy_config(config_key)
            return configs
    except Exception as e:
        logger.error(f"Error getting strategy config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/strategy-config/{config_key}")
async def update_strategy_config(
    config_key: str,
    config_update: StrategyConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update a strategy configuration value"""
    try:
        with StorageService() as storage:
            success = storage.update_strategy_config(
                config_key=config_key,
                config_value=config_update.config_value,
                updated_by="api-service"  # Could be enhanced to track user
            )
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update config")
            return {"success": True, "config_key": config_key, "config_value": config_update.config_value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/strategy-config")
async def update_strategy_configs(
    bulk_update: StrategyConfigBulkUpdate,
    db: Session = Depends(get_db)
):
    """Update multiple strategy configuration values at once"""
    try:
        with StorageService() as storage:
            success = storage.update_strategy_configs(
                configs=bulk_update.configs,
                updated_by="api-service"  # Could be enhanced to track user
            )
            if not success:
                raise HTTPException(status_code=500, detail="Failed to update configs")
            return {"success": True, "updated_count": len(bulk_update.configs)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating strategy configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Ingestion Configuration endpoints
class IngestionConfigResponse(BaseModel):
    config_key: str
    config_value: str
    config_type: str
    description: Optional[str]
    updated_at: Optional[datetime]
    updated_by: Optional[str]
    
    class Config:
        from_attributes = True


class IngestionConfigUpdate(BaseModel):
    config_value: str


class IngestionConfigBulkUpdate(BaseModel):
    configs: Dict[str, str]


@app.get("/ingestion-config", response_model=Dict[str, Any])
async def get_ingestion_config(
    config_key: Optional[str] = Query(None, description="Get specific config key"),
    db: Session = Depends(get_db)
):
    """Get ingestion configuration values"""
    try:
        with StorageService() as storage:
            configs = storage.get_ingestion_config(config_key)
            return configs
    except Exception as e:
        logger.error(f"Error getting ingestion config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/ingestion-config/{config_key}")
async def update_ingestion_config(
    config_key: str,
    config_update: IngestionConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update an ingestion configuration value"""
    try:
        storage = StorageService()
        storage.db = db  # Use the provided session from FastAPI dependency
        success = storage.update_ingestion_config(
            config_key=config_key,
            config_value=config_update.config_value,
            updated_by="api-service"  # Could be enhanced to track user
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update config")
        # StorageService.update_ingestion_config already commits the transaction
        return {"success": True, "config_key": config_key, "config_value": config_update.config_value}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ingestion config: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/ingestion-config")
async def update_ingestion_configs(
    bulk_update: IngestionConfigBulkUpdate,
    db: Session = Depends(get_db)
):
    """Update multiple ingestion configuration values at once"""
    try:
        storage = StorageService()
        storage.db = db  # Use the provided session from FastAPI dependency
        success = storage.update_ingestion_configs(
            configs=bulk_update.configs,
            updated_by="api-service"  # Could be enhanced to track user
        )
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update configs")
        # StorageService.update_ingestion_configs already commits the transaction
        return {"success": True, "updated_count": len(bulk_update.configs)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating ingestion configs: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingestion-config/reload")
async def reload_ingestion_config(db: Session = Depends(get_db)):
    """Trigger ingestion service to reload symbols based on updated config"""
    try:
        # Publish event via Redis to notify ingestion service
        from shared.redis_client import publish_event
        publish_event("ingestion_config_changed", {
            "timestamp": datetime.now().isoformat(),
            "message": "Ingestion config updated, symbols need to be re-evaluated"
        })
        logger.info("Ingestion config reload triggered via API")
        return {"success": True, "message": "Ingestion service will reload symbols"}
    except Exception as e:
        logger.error(f"Error triggering ingestion reload: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SYMBOL FILTER ENDPOINTS (Whitelist/Blacklist)
# ============================================================================

class SymbolFilterAdd(BaseModel):
    symbol: str
    filter_type: str  # 'whitelist' or 'blacklist'


class SymbolFilterResponse(BaseModel):
    symbol: str
    filter_type: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True


@app.get("/symbol-filters", response_model=List[SymbolFilterResponse])
async def get_symbol_filters(
    filter_type: Optional[str] = Query(None, description="Filter by type: 'whitelist' or 'blacklist'"),
    db: Session = Depends(get_db)
):
    """Get all symbol filters, optionally filtered by type"""
    try:
        with DatabaseManager() as db_session:
            if filter_type:
                if filter_type not in ('whitelist', 'blacklist'):
                    raise HTTPException(status_code=400, detail="filter_type must be 'whitelist' or 'blacklist'")
                
                result = db_session.execute(
                    text("""
                        SELECT symbol, filter_type, created_at, updated_at
                        FROM symbol_filters
                        WHERE filter_type = :filter_type
                        ORDER BY symbol
                    """),
                    {"filter_type": filter_type}
                ).fetchall()
            else:
                result = db_session.execute(
                    text("""
                        SELECT symbol, filter_type, created_at, updated_at
                        FROM symbol_filters
                        ORDER BY filter_type, symbol
                    """)
                ).fetchall()
            
            return [
                SymbolFilterResponse(
                    symbol=row[0],
                    filter_type=row[1],
                    created_at=row[2],
                    updated_at=row[3]
                )
                for row in result
            ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting symbol filters: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/symbol-filters", response_model=SymbolFilterResponse)
async def add_symbol_filter(
    filter_data: SymbolFilterAdd,
    db: Session = Depends(get_db)
):
    """Add a symbol to whitelist or blacklist"""
    try:
        if filter_data.filter_type not in ('whitelist', 'blacklist'):
            raise HTTPException(status_code=400, detail="filter_type must be 'whitelist' or 'blacklist'")
        
        # Normalize symbol
        symbol_normalized = filter_data.symbol.lstrip("@").upper().strip()
        
        if not symbol_normalized:
            raise HTTPException(status_code=400, detail="Invalid symbol")
        
        with DatabaseManager() as db_session:
            # Remove from opposite filter type if exists
            db_session.execute(
                text("""
                    DELETE FROM symbol_filters
                    WHERE symbol = :symbol AND filter_type != :filter_type
                """),
                {
                    "symbol": symbol_normalized,
                    "filter_type": filter_data.filter_type
                }
            )
            
            # Insert or update
            result = db_session.execute(
                text("""
                    INSERT INTO symbol_filters (symbol, filter_type, updated_at)
                    VALUES (:symbol, :filter_type, NOW())
                    ON CONFLICT (symbol, filter_type) 
                    DO UPDATE SET updated_at = NOW()
                    RETURNING symbol, filter_type, created_at, updated_at
                """),
                {
                    "symbol": symbol_normalized,
                    "filter_type": filter_data.filter_type
                }
            ).fetchone()
            
            db_session.commit()
            
            # Trigger ingestion reload
            try:
                from shared.redis_client import publish_event
                publish_event("ingestion_config_changed", {
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Symbol filter updated: {symbol_normalized} added to {filter_data.filter_type}"
                })
            except Exception as e:
                logger.warning(f"Failed to publish filter update event: {e}")
            
            return SymbolFilterResponse(
                symbol=result[0],
                filter_type=result[1],
                created_at=result[2],
                updated_at=result[3]
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding symbol filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/symbol-filters/{symbol}")
async def remove_symbol_filter(
    symbol: str,
    db: Session = Depends(get_db)
):
    """Remove a symbol from both whitelist and blacklist"""
    try:
        # Normalize symbol
        symbol_normalized = symbol.lstrip("@").upper().strip()
        
        with DatabaseManager() as db_session:
            result = db_session.execute(
                text("""
                    DELETE FROM symbol_filters
                    WHERE symbol = :symbol
                """),
                {"symbol": symbol_normalized}
            )
            
            db_session.commit()
            deleted_count = result.rowcount
            
            if deleted_count == 0:
                raise HTTPException(status_code=404, detail=f"Symbol {symbol_normalized} not found in filters")
            
            # Trigger ingestion reload
            try:
                from shared.redis_client import publish_event
                publish_event("ingestion_config_changed", {
                    "timestamp": datetime.now().isoformat(),
                    "message": f"Symbol filter removed: {symbol_normalized}"
                })
            except Exception as e:
                logger.warning(f"Failed to publish filter update event: {e}")
            
            return {"success": True, "message": f"Removed {symbol_normalized} from filters"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing symbol filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/symbol-filters/{symbol}/check")
async def check_symbol_filter(
    symbol: str,
    db: Session = Depends(get_db)
):
    """Check if a symbol is whitelisted or blacklisted"""
    try:
        # Normalize symbol
        symbol_normalized = symbol.lstrip("@").upper().strip()
        
        with DatabaseManager() as db_session:
            result = db_session.execute(
                text("""
                    SELECT filter_type
                    FROM symbol_filters
                    WHERE symbol = :symbol
                """),
                {"symbol": symbol_normalized}
            ).fetchone()
            
            if result:
                return {
                    "symbol": symbol_normalized,
                    "is_whitelisted": result[0] == "whitelist",
                    "is_blacklisted": result[0] == "blacklist",
                    "filter_type": result[0]
                }
            else:
                return {
                    "symbol": symbol_normalized,
                    "is_whitelisted": False,
                    "is_blacklisted": False,
                    "filter_type": None
                }
    except Exception as e:
        logger.error(f"Error checking symbol filter: {e}")
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

