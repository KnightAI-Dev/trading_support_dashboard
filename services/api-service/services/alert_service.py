"""
Service for alert business logic
"""
from typing import List, Optional, Dict
from repositories.alert_repository import AlertRepository
from exceptions import NotFoundError
from shared.redis_client import cache_get, cache_set
import json


class AlertService:
    """Service for alert operations"""
    
    def __init__(self, alert_repo: AlertRepository):
        self.alert_repo = alert_repo
    
    def get_alerts(
        self,
        symbol: Optional[str] = None,
        timeframe: Optional[str] = None,
        direction: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get alerts with filters"""
        return self.alert_repo.find_all(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            limit=limit
        )
    
    def get_latest_alert(
        self,
        symbol: str,
        timeframe: Optional[str] = None
    ) -> Dict:
        """Get latest alert for symbol"""
        alert = self.alert_repo.find_latest(symbol, timeframe)
        if not alert:
            raise NotFoundError(f"No alert found for {symbol}")
        return alert
    
    def get_alerts_summary(self) -> List[Dict]:
        """Get summary of latest alerts"""
        # Cache this expensive operation
        cache_key = "alerts:summary"
        cached = cache_get(cache_key)
        if cached:
            return json.loads(cached)
        
        alerts = self.alert_repo.find_summary(limit=1000)
        
        # Cache for 60 seconds
        cache_set(cache_key, json.dumps(alerts), ttl=60)
        return alerts

