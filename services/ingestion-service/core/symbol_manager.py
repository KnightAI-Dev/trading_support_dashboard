"""
Symbol Manager - Manages symbol lifecycle and subscriptions
Removes global state anti-pattern
"""
import asyncio
from typing import List, Callable, Set
import structlog

logger = structlog.get_logger(__name__)


class SymbolManager:
    """Manages symbol lifecycle and subscriptions in a thread-safe manner"""
    
    def __init__(self):
        self._symbols: List[str] = []
        self._timeframes: List[str] = []
        self._lock = asyncio.Lock()
        self._subscribers: List[Callable] = []
    
    async def get_symbols(self) -> List[str]:
        """Get current symbol list (thread-safe)"""
        async with self._lock:
            return self._symbols.copy()
    
    async def get_timeframes(self) -> List[str]:
        """Get current timeframe list (thread-safe)"""
        async with self._lock:
            return self._timeframes.copy()
    
    async def update_symbols(self, symbols: List[str], timeframes: List[str]):
        """Update symbols and notify subscribers
        
        Args:
            symbols: New list of symbols
            timeframes: New list of timeframes
        """
        async with self._lock:
            old_symbols = set(self._symbols)
            new_symbols = set(symbols)
            
            self._symbols = symbols
            self._timeframes = timeframes
            
            added = new_symbols - old_symbols
            removed = old_symbols - new_symbols
        
        # Notify subscribers (non-blocking, outside lock)
        for subscriber in self._subscribers:
            try:
                await subscriber(symbols, timeframes, added, removed)
            except Exception as e:
                logger.error("symbol_subscriber_error", error=str(e), exc_info=True)
        
        if added or removed:
            logger.info(
                "symbols_updated",
                old_count=len(old_symbols),
                new_count=len(symbols),
                added_count=len(added),
                removed_count=len(removed),
                added_symbols=list(added)[:10] if len(added) <= 10 else list(added)[:10],
                removed_symbols=list(removed)[:10] if len(removed) <= 10 else list(removed)[:10]
            )
    
    def subscribe(self, callback: Callable):
        """Subscribe to symbol updates
        
        Args:
            callback: Async function(symbols, timeframes, added, removed)
        """
        if callback not in self._subscribers:
            self._subscribers.append(callback)
            logger.debug("symbol_subscriber_added", subscriber_count=len(self._subscribers))
    
    def unsubscribe(self, callback: Callable):
        """Unsubscribe from symbol updates"""
        if callback in self._subscribers:
            self._subscribers.remove(callback)
            logger.debug("symbol_subscriber_removed", subscriber_count=len(self._subscribers))


