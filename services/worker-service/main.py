"""
Worker Service - Celery task queue for processing trading signals
"""
import sys
import os
from celery import Celery
from datetime import datetime

# Add shared to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))

from shared.database import SessionLocal, init_db
from shared.logger import setup_logger
from shared.config import REDIS_URL

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


@celery_app.task(name="health_check_task")
def health_check_task():
    """Health check task"""
    return {"status": "healthy", "service": "worker-service"}


if __name__ == "__main__":
    if not init_db():
        logger.error("Database initialization failed")
    else:
        logger.info("Worker service started")
        celery_app.start()
