"""
Redis client for caching and pub/sub
"""
import os
import redis
from typing import Optional
import json
import logging

logger = logging.getLogger(__name__)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    # Test connection
    redis_client.ping()
    logger.info("Redis connection established")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    redis_client = None


def get_redis() -> Optional[redis.Redis]:
    """Get Redis client instance"""
    return redis_client


def publish_event(channel: str, data: dict):
    """Publish event to Redis channel"""
    if redis_client:
        try:
            redis_client.publish(channel, json.dumps(data))
        except Exception as e:
            logger.error(f"Failed to publish event: {e}")


def cache_set(key: str, value: any, ttl: int = 3600):
    """Set cache value with TTL"""
    if redis_client:
        try:
            if isinstance(value, (dict, list)):
                value = json.dumps(value)
            redis_client.setex(key, ttl, value)
        except Exception as e:
            logger.error(f"Failed to set cache: {e}")


def cache_get(key: str) -> Optional[str]:
    """Get cache value"""
    if redis_client:
        try:
            return redis_client.get(key)
        except Exception as e:
            logger.error(f"Failed to get cache: {e}")
    return None

