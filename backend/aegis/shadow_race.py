"""
Shadow-Race Pattern - Non-blocking live data retrieval

The "Patient" Data Pattern:
1. Launch simulation/analysis request
2. If no response in patience_threshold_ms, return cached data immediately
3. Live request continues in background
4. On late arrival, push update via SSE or store for next request

Result: User never waits excessively, live data is never wasted.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Any, Optional, TypeVar, Generic, Dict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')


class DataSource(Enum):
    """Source of returned data."""
    LIVE = "live"           # Fresh from API/computation
    CACHE = "cache"         # From cache due to timeout
    FALLBACK = "fallback"   # From fallback after failure
    STALE = "stale"         # Old cached data (may be outdated)


@dataclass
class ShadowRaceResult(Generic[T]):
    """Result from Shadow-Race execution."""
    data: Optional[T]
    source: DataSource
    late_arrival_pending: bool = False
    execution_time_ms: float = 0
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    
    @property
    def success(self) -> bool:
        """Check if operation succeeded."""
        return self.data is not None and self.error is None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dict."""
        return {
            "data": self.data,
            "source": self.source.value,
            "late_arrival_pending": self.late_arrival_pending,
            "execution_time_ms": self.execution_time_ms,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class LateArrival:
    """Represents data that arrived after patience threshold."""
    request_id: str
    endpoint: str
    data: Any
    original_request_time: datetime
    arrival_time: datetime = field(default_factory=datetime.now)
    
    @property
    def delay_ms(self) -> float:
        """How late the data arrived."""
        delta = self.arrival_time - self.original_request_time
        return delta.total_seconds() * 1000


class SSEBroadcaster:
    """
    Server-Sent Events broadcaster for late arrivals.
    
    Allows frontend to receive updates when live data
    finally arrives after cache was displayed.
    """
    
    def __init__(self):
        self.listeners: Dict[str, asyncio.Queue] = {}
        self.late_arrivals: Dict[str, LateArrival] = {}
    
    async def push(self, event_type: str, data: Any) -> None:
        """Push event to all listeners."""
        for listener_id, queue in self.listeners.items():
            try:
                await queue.put({
                    "type": event_type,
                    "data": data,
                    "timestamp": datetime.now().isoformat()
                })
            except Exception as e:
                logger.warning(f"[SHADOW-RACE] Failed to push to {listener_id}: {e}")
    
    def register_listener(self, listener_id: str) -> asyncio.Queue:
        """Register a new SSE listener."""
        queue = asyncio.Queue()
        self.listeners[listener_id] = queue
        return queue
    
    def unregister_listener(self, listener_id: str) -> None:
        """Unregister an SSE listener."""
        if listener_id in self.listeners:
            del self.listeners[listener_id]
    
    def store_late_arrival(self, request_id: str, arrival: LateArrival) -> None:
        """Store late arrival for polling retrieval."""
        self.late_arrivals[request_id] = arrival
        # Auto-expire after 5 minutes
        asyncio.get_event_loop().call_later(
            300, 
            lambda: self.late_arrivals.pop(request_id, None)
        )
    
    def get_late_arrival(self, request_id: str) -> Optional[LateArrival]:
        """Retrieve and consume a late arrival."""
        return self.late_arrivals.pop(request_id, None)


class ShadowRace:
    """
    The "Patient" Data Pattern implementation.
    
    Flow:
    1. Launch simulation request
    2. If no response in patience_threshold_ms, return cached data immediately
    3. Live request continues in background
    4. On late arrival, push update via SSE to OrbitalContext
    
    Result: User never waits, live data never wasted.
    
    Example usage:
        shadow_race = ShadowRace()
        result = await shadow_race.execute(
            live_task=lambda: fetch_simulation(player_id),
            cache_fallback=lambda: get_cached_simulation(player_id),
            patience_ms=800
        )
    """
    
    DEFAULT_PATIENCE_MS = 800
    
    def __init__(self, sse_broadcaster: SSEBroadcaster = None):
        """
        Initialize ShadowRace.
        
        Args:
            sse_broadcaster: Optional broadcaster for late arrivals
        """
        self.sse_broadcaster = sse_broadcaster or SSEBroadcaster()
        self._pending_requests: Dict[str, asyncio.Task] = {}
        self._stats = {
            "total_requests": 0,
            "cache_served": 0,
            "live_served": 0,
            "late_arrivals": 0,
            "failures": 0
        }
    
    async def execute(
        self,
        live_task: Callable[[], Any],
        cache_fallback: Callable[[], Any],
        patience_ms: int = None,
        request_id: str = None,
        endpoint: str = None
    ) -> ShadowRaceResult:
        """
        Execute Shadow-Race pattern.
        
        Args:
            live_task: Async callable that fetches live data
            cache_fallback: Async callable that returns cached data
            patience_ms: How long to wait before serving cache
            request_id: Unique ID for tracking late arrivals
            endpoint: Endpoint path for logging/tracking
            
        Returns:
            ShadowRaceResult with data and source information
        """
        if patience_ms is None:
            patience_ms = self.DEFAULT_PATIENCE_MS
        
        if request_id is None:
            request_id = f"{endpoint}_{datetime.now().timestamp()}"
        
        start_time = datetime.now()
        self._stats["total_requests"] += 1
        
        try:
            # Start live request
            if asyncio.iscoroutinefunction(live_task):
                live_future = asyncio.create_task(live_task())
            else:
                # Wrap sync function
                live_future = asyncio.create_task(
                    asyncio.get_event_loop().run_in_executor(None, live_task)
                )
            
            try:
                # Wait for patience threshold
                result = await asyncio.wait_for(
                    live_future, 
                    timeout=patience_ms / 1000
                )
                
                # Live returned in time!
                execution_time = (datetime.now() - start_time).total_seconds() * 1000
                self._stats["live_served"] += 1
                
                logger.info(f"[SHADOW-RACE] Live returned in {execution_time:.0f}ms for {endpoint}")
                
                return ShadowRaceResult(
                    data=result,
                    source=DataSource.LIVE,
                    late_arrival_pending=False,
                    execution_time_ms=execution_time
                )
                
            except asyncio.TimeoutError:
                # Patience threshold exceeded - serve cache immediately
                logger.info(f"[SHADOW-RACE] Patience exceeded ({patience_ms}ms) for {endpoint}, serving cache")
                
                try:
                    # Get cached data
                    if asyncio.iscoroutinefunction(cache_fallback):
                        cached_data = await cache_fallback()
                    else:
                        cached_data = cache_fallback()
                    
                    execution_time = (datetime.now() - start_time).total_seconds() * 1000
                    self._stats["cache_served"] += 1
                    
                    # But DON'T cancel the live request! Let it finish in background
                    self._pending_requests[request_id] = live_future
                    asyncio.create_task(
                        self._handle_late_arrival(
                            live_future, 
                            request_id, 
                            endpoint or "unknown",
                            start_time
                        )
                    )
                    
                    return ShadowRaceResult(
                        data=cached_data,
                        source=DataSource.CACHE,
                        late_arrival_pending=True,
                        execution_time_ms=execution_time
                    )
                    
                except Exception as cache_error:
                    logger.error(f"[SHADOW-RACE] Cache fallback failed: {cache_error}")
                    
                    # Try to wait for live a bit longer as last resort
                    try:
                        result = await asyncio.wait_for(live_future, timeout=2.0)
                        return ShadowRaceResult(
                            data=result,
                            source=DataSource.LIVE,
                            late_arrival_pending=False,
                            execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                        )
                    except:
                        self._stats["failures"] += 1
                        return ShadowRaceResult(
                            data=None,
                            source=DataSource.FALLBACK,
                            error=f"Both live and cache failed: {cache_error}",
                            execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
                        )
                        
        except Exception as e:
            self._stats["failures"] += 1
            logger.error(f"[SHADOW-RACE] Execution failed for {endpoint}: {e}")
            return ShadowRaceResult(
                data=None,
                source=DataSource.FALLBACK,
                error=str(e),
                execution_time_ms=(datetime.now() - start_time).total_seconds() * 1000
            )
    
    async def _handle_late_arrival(
        self,
        live_future: asyncio.Task,
        request_id: str,
        endpoint: str,
        original_request_time: datetime
    ) -> None:
        """Handle the live result when it finally arrives."""
        try:
            result = await live_future
            arrival = LateArrival(
                request_id=request_id,
                endpoint=endpoint,
                data=result,
                original_request_time=original_request_time
            )
            
            self._stats["late_arrivals"] += 1
            logger.info(f"[SHADOW-RACE] Late arrival for {endpoint} after {arrival.delay_ms:.0f}ms")
            
            # Push update via SSE
            await self.sse_broadcaster.push("simulation_update", {
                "request_id": request_id,
                "endpoint": endpoint,
                "data": result,
                "delay_ms": arrival.delay_ms
            })
            
            # Also store for polling retrieval
            self.sse_broadcaster.store_late_arrival(request_id, arrival)
            
        except asyncio.CancelledError:
            logger.info(f"[SHADOW-RACE] Live request cancelled for {endpoint}")
        except Exception as e:
            logger.warning(f"[SHADOW-RACE] Live request failed for {endpoint}: {e}")
        finally:
            # Clean up pending request
            self._pending_requests.pop(request_id, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get Shadow-Race statistics."""
        total = self._stats["total_requests"]
        return {
            **self._stats,
            "cache_hit_rate": (
                self._stats["cache_served"] / total * 100 if total > 0 else 0
            ),
            "live_hit_rate": (
                self._stats["live_served"] / total * 100 if total > 0 else 0
            ),
            "failure_rate": (
                self._stats["failures"] / total * 100 if total > 0 else 0
            ),
            "pending_requests": len(self._pending_requests)
        }
    
    def cancel_pending(self, request_id: str) -> bool:
        """Cancel a pending live request."""
        if request_id in self._pending_requests:
            self._pending_requests[request_id].cancel()
            del self._pending_requests[request_id]
            return True
        return False
    
    def cancel_all_pending(self) -> int:
        """Cancel all pending requests."""
        count = len(self._pending_requests)
        for task in self._pending_requests.values():
            task.cancel()
        self._pending_requests.clear()
        return count


# Convenience function for simple usage
async def shadow_race(
    live_task: Callable,
    cache_fallback: Callable,
    patience_ms: int = 800
) -> ShadowRaceResult:
    """
    Simple interface for Shadow-Race pattern.
    
    Example:
        result = await shadow_race(
            live_task=lambda: fetch_from_api(player_id),
            cache_fallback=lambda: get_from_cache(player_id),
            patience_ms=600
        )
        if result.source == DataSource.CACHE:
            print("Served from cache, live data pending...")
    """
    racer = ShadowRace()
    return await racer.execute(live_task, cache_fallback, patience_ms)
