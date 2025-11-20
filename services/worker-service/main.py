"""
Worker Service - Celery task queue for processing trading signals
"""
import sys
import os
from celery import Celery
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.database import SessionLocal, init_db
from shared.models import OHLCVCandle
from shared.logger import setup_logger
from shared.config import REDIS_URL, DEFAULT_TIMEFRAME
from shared.redis_client import get_redis

# Import engines
sys.path.append(os.path.join(os.path.dirname(__file__), '../swing-engine'))
from main import process_swing_detection

sys.path.append(os.path.join(os.path.dirname(__file__), '../sr-engine'))
from main import process_sr_detection

sys.path.append(os.path.join(os.path.dirname(__file__), '../fib-entry-engine'))
from main import process_fibonacci

sys.path.append(os.path.join(os.path.dirname(__file__), '../confluence-engine'))
from main import calculate_confluence

sys.path.append(os.path.join(os.path.dirname(__file__), '../risk-engine'))
from main import calculate_risk_reward, RiskEngine

from shared.storage import save_signal, StorageService

logger = setup_logger(__name__)

# Initialize Celery
celery_app = Celery(
    "trading_worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task(name="process_swing_detection_task")
def process_swing_detection_task(symbol: str, timeframe: str = DEFAULT_TIMEFRAME):
    """Task to process swing detection"""
    try:
        logger.info(f"Processing swing detection for {symbol}")
        process_swing_detection(symbol, timeframe)
        return {"status": "success", "symbol": symbol}
    except Exception as e:
        logger.error(f"Error in swing detection task: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="process_sr_detection_task")
def process_sr_detection_task(symbol: str, timeframe: str = DEFAULT_TIMEFRAME):
    """Task to process S/R detection"""
    try:
        logger.info(f"Processing S/R detection for {symbol}")
        process_sr_detection(symbol, timeframe)
        return {"status": "success", "symbol": symbol}
    except Exception as e:
        logger.error(f"Error in S/R detection task: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="process_fibonacci_task")
def process_fibonacci_task(symbol: str, timeframe: str, current_price: float):
    """Task to process Fibonacci calculations"""
    try:
        logger.info(f"Processing Fibonacci for {symbol}")
        result = process_fibonacci(symbol, timeframe, Decimal(str(current_price)))
        return {"status": "success", "symbol": symbol, "result": result}
    except Exception as e:
        logger.error(f"Error in Fibonacci task: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="process_full_analysis_task")
def process_full_analysis_task(symbol: str, timeframe: str = DEFAULT_TIMEFRAME):
    """Task to process full analysis pipeline"""
    try:
        logger.info(f"Processing full analysis for {symbol}")
        
        db = SessionLocal()
        try:
            # Get latest candle
            from sqlalchemy import desc, and_
            latest_candle = db.query(OHLCVCandle).filter(
                and_(
                    OHLCVCandle.symbol == symbol,
                    OHLCVCandle.timeframe == timeframe
                )
            ).order_by(desc(OHLCVCandle.timestamp)).first()
            
            if not latest_candle:
                return {"status": "error", "error": "No candles found"}
            
            current_price = Decimal(str(latest_candle.close))
            
            # Get recent candles
            candles = db.query(OHLCVCandle).filter(
                and_(
                    OHLCVCandle.symbol == symbol,
                    OHLCVCandle.timeframe == timeframe
                )
            ).order_by(desc(OHLCVCandle.timestamp)).limit(200).all()
            candles.reverse()
            
            # 1. Swing detection
            process_swing_detection(symbol, timeframe)
            
            # 2. S/R detection
            process_sr_detection(symbol, timeframe)
            
            # 3. Fibonacci calculation
            fib_result = process_fibonacci(symbol, timeframe, current_price)
            if not fib_result:
                return {"status": "error", "error": "Fibonacci calculation failed"}
            
            direction = fib_result["direction"]
            entry1 = fib_result["entry_levels"]["entry1"]
            sl = fib_result["entry_levels"]["sl"]
            tp1 = fib_result["tp_levels"]["tp1"]
            tp2 = fib_result["tp_levels"]["tp2"]
            tp3 = fib_result["tp_levels"]["tp3"]
            
            # 4. Confluence calculation
            confluence_result = calculate_confluence(
                symbol, timeframe, current_price, direction, candles
            )
            
            # 5. Risk-reward calculation
            rr_result = calculate_risk_reward(entry1, sl, tp1, tp2, tp3)
            
            # 6. Calculate confidence score
            risk_engine = RiskEngine()
            confidence_score = risk_engine.calculate_confidence_score(
                confluence_result["percentage_score"],
                rr_result["rr_tp1"],
                len(confluence_result["factors"])
            )
            
            # 7. Get swing points and S/R levels
            with StorageService() as storage:
                swings = storage.get_latest_swings(symbol, timeframe)
                sr_levels = storage.get_active_sr_levels(symbol, timeframe)
            
            # 8. Build and save signal
            signal_data = {
                "symbol": symbol,
                "timestamp": latest_candle.timestamp,
                "market_score": confluence_result["percentage_score"],
                "direction": direction,
                "price": float(current_price),
                "entry1": float(entry1),
                "entry2": float(fib_result["entry_levels"]["entry2"]),
                "sl": float(sl),
                "tp1": float(tp1),
                "tp2": float(tp2),
                "tp3": float(tp3),
                "swing_high": swings.get("swing_high"),
                "swing_low": swings.get("swing_low"),
                "support_level": sr_levels["support"][0] if sr_levels["support"] else None,
                "resistance_level": sr_levels["resistance"][0] if sr_levels["resistance"] else None,
                "confluence": ",".join(confluence_result["factors"]),
                "risk_reward_ratio": float(rr_result["rr_tp1"]),
                "pullback_detected": fib_result["pullback_detected"],
                "pullback_start_level": float(fib_result["pullback_level"]) if fib_result["pullback_level"] else None,
                "approaching_fib_level": float(fib_result["entry_levels"]["approaching"]),
                "confidence_score": float(confidence_score)
            }
            
            save_signal(signal_data)
            
            logger.info(f"Full analysis completed for {symbol}")
            return {"status": "success", "symbol": symbol, "signal": signal_data}
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error in full analysis task: {e}")
        return {"status": "error", "error": str(e)}


if __name__ == "__main__":
    if not init_db():
        logger.error("Database initialization failed")
    else:
        celery_app.start()

