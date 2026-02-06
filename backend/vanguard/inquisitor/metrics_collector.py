"""
Metrics Collection
==================
Background task to collect system metrics (CPU, memory, DB pool, event loop).
"""

import asyncio
import psutil
import time
from typing import Dict, Any
from datetime import datetime

from ..bootstrap.redis_client import get_redis
from ..utils.logger import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """
    Collects system metrics every 10 seconds and stores in Redis.
    Time-series data with 60-second retention.
    """
    
    def __init__(self):
        self.running = False
        self.task: asyncio.Task | None = None
        self.process = psutil.Process()
    
    async def start(self) -> None:
        """Start the background metrics collection task."""
        if self.running:
            logger.warning("metrics_collector_already_running")
            return
        
        self.running = True
        self.task = asyncio.create_task(self._collect_loop())
        logger.info("metrics_collector_started")
    
    async def stop(self) -> None:
        """Stop the metrics collection task."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("metrics_collector_stopped")
    
    async def _collect_loop(self) -> None:
        """Main collection loop (runs every 10s)."""
        while self.running:
            try:
                await self._collect_metrics()
                await asyncio.sleep(10)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("metrics_collection_error", error=str(e))
                await asyncio.sleep(10)
    
    async def _collect_metrics(self) -> None:
        """Collect current metrics and store in Redis."""
        try:
            # Collect metrics
            metrics = {
                "timestamp": datetime.utcnow().isoformat(),
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "memory_mb": self.process.memory_info().rss / 1024 / 1024,
                "event_loop_latency_ms": await self._measure_event_loop_latency(),
                # TODO: Add DB connection pool metrics when available
            }
            
            # Store in Redis (with 60s TTL)
            redis_client = await get_redis()
            key = f"vanguard:metrics:{int(time.time())}"
            await redis_client.setex(key, 60, str(metrics))
            
            logger.debug("metrics_collected", **metrics)
        
        except Exception as e:
            logger.error("metrics_storage_error", error=str(e))
    
    async def _measure_event_loop_latency(self) -> float:
        """
        Measure event loop latency by timing a sleep(0).
        
        Returns:
            Latency in milliseconds
        """
        start = time.perf_counter()
        await asyncio.sleep(0)  # Yield to event loop
        end = time.perf_counter()
        latency_ms = (end - start) * 1000
        return latency_ms
    
    async def get_recent_metrics(self, seconds: int = 60) -> list[Dict[str, Any]]:
        """
        Retrieve metrics from Redis for the last N seconds.
        
        Args:
            seconds: Lookback window (default 60s)
        
        Returns:
            List of metric dictionaries
        """
        try:
            redis_client = await get_redis()
            current_time = int(time.time())
            
            metrics = []
            for i in range(seconds):
                key = f"vanguard:metrics:{current_time - i}"
                data = await redis_client.get(key)
                if data:
                    # Parse stored metrics (simple eval for now, TODO: use json)
                    metrics.append(eval(data))
            
            return metrics
        
        except Exception as e:
            logger.error("metrics_retrieval_error", error=str(e))
            return []


# Global collector instance
_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get or create the global metrics collector."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector()
    return _collector
