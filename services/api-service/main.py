"""
API Service - Refactored Architecture
Demonstrates improved structure with repository pattern, service layer, and proper error handling
"""
import sys
import os
import asyncio
import json
import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

# Add api-service directory to path for local imports
sys.path.insert(0, os.path.dirname(__file__))

from shared.database import get_db, init_db
from shared.logger import setup_logger
from shared.redis_client import get_redis, publish_event

# Import new architecture
from repositories import AlertRepository, CandleRepository, SymbolRepository, ConfigRepository, SymbolFilterRepository
from services import AlertService, CandleService, SymbolService, ConfigService, SymbolFilterService
from exceptions import NotFoundError, ValidationError, ConfigurationError
from dependencies import (
    get_alert_service_from_db,
    get_candle_service_from_db,
    get_symbol_service_from_db,
    get_config_service_from_db,
    get_symbol_filter_service_from_db
)

logger = setup_logger(__name__)

app = FastAPI(
    title="Trading Support API",
    description="REST API for Trading Support Architecture",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Pydantic Models
# ============================================================================

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


class StrategyConfigUpdate(BaseModel):
    config_value: str


class StrategyConfigBulkUpdate(BaseModel):
    configs: Dict[str, str]


class IngestionConfigUpdate(BaseModel):
    config_value: str


class IngestionConfigBulkUpdate(BaseModel):
    configs: Dict[str, str]


class SymbolFilterAdd(BaseModel):
    symbol: str
    filter_type: str  # 'whitelist' or 'blacklist'
    
    @field_validator('filter_type')
    @classmethod
    def validate_filter_type(cls, v):
        if v not in ('whitelist', 'blacklist'):
            raise ValueError("filter_type must be 'whitelist' or 'blacklist'")
        return v


class SymbolFilterResponse(BaseModel):
    symbol: str
    filter_type: str
    created_at: Optional[datetime]
    updated_at: Optional[datetime]


# ============================================================================
# WebSocket Connection Manager (Improved)
# ============================================================================

class ConnectionManager:
    """Manages WebSocket connections with proper lifecycle management"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.subscriptions: Dict[str, Dict[str, set]] = {}  # ws_id -> {symbol -> {timeframe}}
        self.redis_listener_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new WebSocket connection with stable ID"""
        await websocket.accept()
        ws_id = str(uuid.uuid4())  # Use UUID instead of id()
        async with self._lock:
            self.active_connections[ws_id] = websocket
            self.subscriptions[ws_id] = {}
        logger.info(f"WebSocket client connected: {ws_id}")
        return ws_id
    
    async def disconnect(self, ws_id: str):
        """Remove a WebSocket connection"""
        async with self._lock:
            if ws_id in self.active_connections:
                del self.active_connections[ws_id]
            if ws_id in self.subscriptions:
                del self.subscriptions[ws_id]
        logger.info(f"WebSocket client disconnected: {ws_id}")
    
    async def subscribe(self, ws_id: str, symbol: str, timeframe: str):
        """Subscribe a client to symbol/timeframe updates"""
        async with self._lock:
            if ws_id not in self.subscriptions:
                self.subscriptions[ws_id] = {}
            if symbol not in self.subscriptions[ws_id]:
                self.subscriptions[ws_id][symbol] = set()
            self.subscriptions[ws_id][symbol].add(timeframe)
        logger.debug(f"Client {ws_id} subscribed to {symbol} {timeframe}")
    
    async def send_personal_message(self, ws_id: str, message: dict):
        """Send a message to a specific client"""
        async with self._lock:
            websocket = self.active_connections.get(ws_id)
        
        if websocket:
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to client {ws_id}: {e}")
                await self.disconnect(ws_id)
    
    async def broadcast_candle_update(self, candle_data: dict):
        """Broadcast candle update to subscribed clients"""
        symbol = candle_data.get("symbol")
        timeframe = candle_data.get("timeframe")
        
        if not symbol or not timeframe:
            logger.warning(f"Candle update missing symbol or timeframe: {candle_data}")
            return
        
        async with self._lock:
            # Create copy to avoid iteration issues
            subscriptions = {k: v.copy() for k, v in self.subscriptions.items()}
        
        clients_notified = 0
        for ws_id, subs in subscriptions.items():
            if symbol in subs and timeframe in subs[symbol]:
                await self.send_personal_message(ws_id, {
                    "type": "candle",
                    "data": candle_data
                })
                clients_notified += 1
        
        logger.debug(f"Broadcasted candle update for {symbol} {timeframe} to {clients_notified} clients")
    
    async def broadcast_symbol_update(self, symbol_data: dict):
        """Broadcast symbol update to all connected clients"""
        symbol = symbol_data.get("symbol")
        if not symbol:
            logger.warning(f"Symbol update missing symbol: {symbol_data}")
            return
        
        # Parse base/quote if not present
        if "base" not in symbol_data or "quote" not in symbol_data:
            symbol_str = symbol.upper()
            quote_assets = ["USDT", "USDC", "BUSD", "BTC", "ETH", "BNB", "USD", "EUR", "GBP", "TRY"]
            for quote in quote_assets:
                if symbol_str.endswith(quote):
                    symbol_data["base"] = symbol_str[:-len(quote)]
                    symbol_data["quote"] = quote
                    break
            else:
                symbol_data["base"] = symbol_str
                symbol_data["quote"] = "USDT"
        
        async with self._lock:
            ws_ids = list(self.active_connections.keys())
        
        clients_notified = 0
        for ws_id in ws_ids:
            await self.send_personal_message(ws_id, {
                "type": "symbol_update",
                "data": symbol_data
            })
            clients_notified += 1
        
        logger.debug(f"Broadcasted symbol update for {symbol} to {clients_notified} clients")
    
    async def broadcast_strategy_alert(self, alert_data: dict):
        """Broadcast strategy alert to all connected clients"""
        symbol = alert_data.get("symbol")
        timeframe = alert_data.get("timeframe", "")
        
        if not symbol:
            logger.warning(f"Strategy alert missing symbol: {alert_data}")
            return
        
        # Ensure timestamps are strings
        timestamp = alert_data.get("timestamp")
        if timestamp and not isinstance(timestamp, str):
            timestamp = timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
        
        swing_low_timestamp = alert_data.get("swing_low_timestamp")
        if swing_low_timestamp and not isinstance(swing_low_timestamp, str):
            swing_low_timestamp = swing_low_timestamp.isoformat() if hasattr(swing_low_timestamp, 'isoformat') else str(swing_low_timestamp)
        
        swing_high_timestamp = alert_data.get("swing_high_timestamp")
        if swing_high_timestamp and not isinstance(swing_high_timestamp, str):
            swing_high_timestamp = swing_high_timestamp.isoformat() if hasattr(swing_high_timestamp, 'isoformat') else str(swing_high_timestamp)
        
        signal_data = {
            "id": alert_data.get("id"),
            "symbol": symbol,
            "timeframe": timeframe,
            "timestamp": timestamp or datetime.now().isoformat(),
            "market_score": 0,
            "direction": alert_data.get("direction", "long"),
            "price": alert_data.get("entry_price", 0),
            "entry1": alert_data.get("entry_price"),
            "entry2": None,
            "sl": alert_data.get("stop_loss"),
            "tp1": alert_data.get("take_profit_1"),
            "tp2": alert_data.get("take_profit_2"),
            "tp3": alert_data.get("take_profit_3"),
            "swing_high": alert_data.get("swing_high_price"),
            "swing_high_timestamp": swing_high_timestamp,
            "swing_low": alert_data.get("swing_low_price"),
            "swing_low_timestamp": swing_low_timestamp,
            "support_level": None,
            "resistance_level": None,
            "confluence": alert_data.get("risk_score"),
            "risk_reward_ratio": None,
            "pullback_detected": False,
            "confidence_score": None
        }
        
        async with self._lock:
            ws_ids = list(self.active_connections.keys())
        
        clients_notified = 0
        for ws_id in ws_ids:
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
        """Start listening to Redis pub/sub for updates"""
        redis_client = get_redis()
        if not redis_client:
            logger.warning("Redis not available, WebSocket updates disabled")
            return
        
        async def listen():
            pubsub = redis_client.pubsub()
            pubsub.subscribe("candle_update", "symbol_update", "marketcap_update", "strategy_alert")
            
            logger.info("Redis listener started for updates")
            
            while True:
                try:
                    message = await asyncio.to_thread(
                        pubsub.get_message,
                        ignore_subscribe_messages=True,
                        timeout=1.0
                    )
                    
                    if message and message.get("type") == "message":
                        try:
                            channel_raw = message.get("channel")
                            channel = channel_raw.decode("utf-8") if isinstance(channel_raw, bytes) else str(channel_raw)
                            data = json.loads(message["data"])
                            
                            if channel == "candle_update":
                                if all(key in data for key in ["symbol", "timeframe", "timestamp", "open", "high", "low", "close", "volume"]):
                                    await self.broadcast_candle_update(data)
                            elif channel == "symbol_update":
                                await self.broadcast_symbol_update(data)
                            elif channel == "strategy_alert":
                                await self.broadcast_strategy_alert(data)
                                
                        except json.JSONDecodeError as e:
                            logger.error(f"Error parsing Redis message: {e}")
                        except Exception as e:
                            logger.error(f"Error processing update: {e}", exc_info=True)
                except Exception as e:
                    logger.error(f"Error in Redis listener: {e}")
                    await asyncio.sleep(1)
        
        self.redis_listener_task = asyncio.create_task(listen())
        logger.info("WebSocket Redis listener task started")
    
    async def shutdown(self):
        """Cleanup on shutdown"""
        if self.redis_listener_task:
            self.redis_listener_task.cancel()
            try:
                await self.redis_listener_task
            except asyncio.CancelledError:
                pass
        logger.info("WebSocket manager shut down")


# Global connection manager
manager = ConnectionManager()


@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    if not init_db():
        logger.error("Database initialization failed")
    else:
        logger.info("API service started")
    
    await manager.start_redis_listener()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await manager.shutdown()


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(NotFoundError)
async def not_found_handler(request, exc: NotFoundError):
    raise HTTPException(status_code=404, detail=str(exc))


@app.exception_handler(ValidationError)
async def validation_handler(request, exc: ValidationError):
    raise HTTPException(status_code=400, detail=str(exc))


@app.exception_handler(ConfigurationError)
async def configuration_handler(request, exc: ConfigurationError):
    raise HTTPException(status_code=500, detail=str(exc))


# ============================================================================
# Health & Root Endpoints
# ============================================================================

@app.get("/")
async def root():
    return {"message": "Trading Support API", "version": "2.0.0"}


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


# ============================================================================
# Alert Endpoints (Refactored)
# ============================================================================

@app.get("/alerts", response_model=List[StrategyAlertResponse])
async def get_alerts(
    symbol: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    direction: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    alert_service: AlertService = Depends(get_alert_service_from_db)
):
    """Get strategy alerts"""
    alerts = alert_service.get_alerts(
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        limit=limit
    )
    return alerts


@app.get("/alerts/{symbol}/latest", response_model=StrategyAlertResponse)
async def get_latest_alert(
    symbol: str,
    timeframe: Optional[str] = Query(None),
    alert_service: AlertService = Depends(get_alert_service_from_db)
):
    """Get latest alert for a symbol"""
    try:
        alert = alert_service.get_latest_alert(symbol, timeframe)
        return alert
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@app.get("/alerts/{symbol}/swings", response_model=List[StrategyAlertResponse])
async def get_alerts_for_swings(
    symbol: str,
    timeframe: str = Query(..., description="Timeframe (required)"),
    limit: int = Query(100, ge=1, le=1000, description="Limit results"),
    alert_service: AlertService = Depends(get_alert_service_from_db)
):
    """Get strategy alerts for a specific symbol and timeframe to extract swing points from database"""
    try:
        alerts = alert_service.get_alerts(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit
        )
        return alerts
    except Exception as e:
        logger.error(f"Error getting alerts for swings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/alerts/summary", response_model=List[AlertSummary])
async def get_alerts_summary(
    alert_service: AlertService = Depends(get_alert_service_from_db)
):
    """Get summary of latest alerts"""
    alerts = alert_service.get_alerts_summary()
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
        for a in alerts
    ]


# ============================================================================
# Candle Endpoints (Refactored)
# ============================================================================

@app.get("/candles/{symbol}")
async def get_candles(
    symbol: str,
    timeframe: str = Query("1h"),
    limit: int = Query(100, ge=1, le=1000),
    before: Optional[str] = Query(None),
    candle_service: CandleService = Depends(get_candle_service_from_db)
):
    """Get OHLCV candles for a symbol"""
    candles = candle_service.get_candles(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
        before=before
    )
    return candles


@app.get("/metadata/market", response_model=MarketMetadataResponse)
async def get_market_metadata(
    candle_service: CandleService = Depends(get_candle_service_from_db)
):
    """Get available symbols and timeframes"""
    metadata = candle_service.get_market_metadata()
    return metadata


# ============================================================================
# Symbol Endpoints (Refactored)
# ============================================================================

@app.get("/symbols")
async def get_symbols(
    symbol_service: SymbolService = Depends(get_symbol_service_from_db)
):
    """Get all symbols with latest prices"""
    symbols = symbol_service.get_symbols_with_prices()
    return symbols


@app.get("/symbols/{symbol}/details")
async def get_symbol_details(
    symbol: str,
    symbol_service: SymbolService = Depends(get_symbol_service_from_db)
):
    """Get detailed symbol information"""
    try:
        details = symbol_service.get_symbol_details(symbol)
        return details
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ============================================================================
# Config Endpoints (Refactored)
# ============================================================================

@app.get("/strategy-config", response_model=Dict[str, Any])
async def get_strategy_config(
    config_key: Optional[str] = Query(None),
    config_service: ConfigService = Depends(get_config_service_from_db)
):
    """Get strategy configuration"""
    return config_service.get_strategy_config(config_key)


@app.put("/strategy-config/{config_key}")
async def update_strategy_config(
    config_key: str,
    config_update: StrategyConfigUpdate,
    config_service: ConfigService = Depends(get_config_service_from_db)
):
    """Update strategy configuration"""
    try:
        config_service.update_strategy_config(
            config_key=config_key,
            config_value=config_update.config_value,
            updated_by="api-service"
        )
        return {"success": True, "config_key": config_key, "config_value": config_update.config_value}
    except ConfigurationError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/strategy-config")
async def update_strategy_configs(
    bulk_update: StrategyConfigBulkUpdate,
    config_service: ConfigService = Depends(get_config_service_from_db)
):
    """Update multiple strategy configurations"""
    try:
        config_service.update_strategy_configs(
            configs=bulk_update.configs,
            updated_by="api-service"
        )
        return {"success": True, "updated_count": len(bulk_update.configs)}
    except ConfigurationError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/ingestion-config", response_model=Dict[str, Any])
async def get_ingestion_config(
    config_key: Optional[str] = Query(None),
    config_service: ConfigService = Depends(get_config_service_from_db)
):
    """Get ingestion configuration"""
    return config_service.get_ingestion_config(config_key)


@app.put("/ingestion-config/{config_key}")
async def update_ingestion_config(
    config_key: str,
    config_update: IngestionConfigUpdate,
    config_service: ConfigService = Depends(get_config_service_from_db)
):
    """Update ingestion configuration"""
    try:
        config_service.update_ingestion_config(
            config_key=config_key,
            config_value=config_update.config_value,
            updated_by="api-service"
        )
        return {"success": True, "config_key": config_key, "config_value": config_update.config_value}
    except ConfigurationError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/ingestion-config")
async def update_ingestion_configs(
    bulk_update: IngestionConfigBulkUpdate,
    config_service: ConfigService = Depends(get_config_service_from_db)
):
    """Update multiple ingestion configurations"""
    try:
        config_service.update_ingestion_configs(
            configs=bulk_update.configs,
            updated_by="api-service"
        )
        return {"success": True, "updated_count": len(bulk_update.configs)}
    except ConfigurationError as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ingestion-config/reload")
async def reload_ingestion_config():
    """Trigger ingestion service to reload symbols"""
    try:
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
# Symbol Filter Endpoints (Refactored)
# ============================================================================

@app.get("/symbol-filters", response_model=List[SymbolFilterResponse])
async def get_symbol_filters(
    filter_type: Optional[str] = Query(None),
    filter_service: SymbolFilterService = Depends(get_symbol_filter_service_from_db)
):
    """Get all symbol filters"""
    try:
        filters = filter_service.get_filters(filter_type)
        return [
            SymbolFilterResponse(
                symbol=f["symbol"],
                filter_type=f["filter_type"],
                created_at=f["created_at"],
                updated_at=f["updated_at"]
            )
            for f in filters
        ]
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/symbol-filters", response_model=SymbolFilterResponse)
async def add_symbol_filter(
    filter_data: SymbolFilterAdd,
    filter_service: SymbolFilterService = Depends(get_symbol_filter_service_from_db)
):
    """Add a symbol to whitelist or blacklist"""
    try:
        result = filter_service.add_filter(filter_data.symbol, filter_data.filter_type)
        
        # Trigger ingestion reload
        try:
            publish_event("ingestion_config_changed", {
                "timestamp": datetime.now().isoformat(),
                "message": f"Symbol filter updated: {result['symbol']} added to {result['filter_type']}"
            })
        except Exception as e:
            logger.warning(f"Failed to publish filter update event: {e}")
        
        return SymbolFilterResponse(
            symbol=result["symbol"],
            filter_type=result["filter_type"],
            created_at=result["created_at"],
            updated_at=result["updated_at"]
        )
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error adding symbol filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/symbol-filters/{symbol}")
async def remove_symbol_filter(
    symbol: str,
    filter_service: SymbolFilterService = Depends(get_symbol_filter_service_from_db)
):
    """Remove a symbol from both whitelist and blacklist"""
    try:
        filter_service.remove_filter(symbol)
        
        # Trigger ingestion reload
        try:
            publish_event("ingestion_config_changed", {
                "timestamp": datetime.now().isoformat(),
                "message": f"Symbol filter removed: {symbol}"
            })
        except Exception as e:
            logger.warning(f"Failed to publish filter update event: {e}")
        
        return {"success": True, "message": f"Removed {symbol} from filters"}
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error removing symbol filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/symbol-filters/{symbol}/check")
async def check_symbol_filter(
    symbol: str,
    filter_service: SymbolFilterService = Depends(get_symbol_filter_service_from_db)
):
    """Check if a symbol is whitelisted or blacklisted"""
    try:
        return filter_service.get_filter_by_symbol(symbol)
    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error checking symbol filter: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# WebSocket Endpoint (Improved)
# ============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    ws_id = await manager.connect(websocket)
    
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
                    await manager.subscribe(ws_id, symbol, timeframe)
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
        await manager.disconnect(ws_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await manager.disconnect(ws_id)


if __name__ == "__main__":
    import uvicorn
    import os
    # Allow running on different port for testing
    port = int(os.getenv("API_PORT", "8000"))
    print(f"Starting Refactored API Service on port {port}")
    print(f"Original API should be on port 8000 for comparison")
    uvicorn.run(app, host="0.0.0.0", port=port)

