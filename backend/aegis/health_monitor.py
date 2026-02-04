"""
Worker Health Monitor
Tracks system health, API status, and performance metrics
"""

import time
import psutil
from datetime import datetime
from typing import Dict, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    DOWN = "down"


class WorkerHealthMonitor:
    """
    Monitors system health and worker status.
    
    Tracks:
    - CPU and memory usage
    - API response times
    - Cache hit rates
    - Error rates
    - Worker availability
    """
    
    def __init__(self):
        self.start_time = time.time()
        self.health_checks = []
        self.error_count = 0
        self.total_requests = 0
        
        # Thresholds
        self.cpu_warning_threshold = 80  # %
        self.cpu_critical_threshold = 95  # %
        self.memory_warning_threshold = 80  # %
        self.memory_critical_threshold = 95  # %
        
        logger.info("WorkerHealthMonitor initialized")
    
    def check_system_health(self) -> dict:
        """
        Perform comprehensive system health check.
        
        Returns:
            Health status dict
        """
        # CPU usage
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        # Memory usage
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        
        # Determine overall status
        status = self._determine_status(cpu_percent, memory_percent)
        
        health = {
            'status': status.value,
            'timestamp': datetime.now().isoformat(),
            'uptime_seconds': int(time.time() - self.start_time),
            'system': {
                'cpu_percent': round(cpu_percent, 1),
                'memory_percent': round(memory_percent, 1),
                'memory_available_mb': round(memory.available / 1024 / 1024, 0)
            },
            'metrics': {
                'total_requests': self.total_requests,
                'error_count': self.error_count,
                'error_rate': self._get_error_rate()
            }
        }
        
        # Record health check
        self.health_checks.append({
            'timestamp': time.time(),
            'status': status.value,
            'cpu': cpu_percent,
            'memory': memory_percent
        })
        
        # Keep only last 100 checks
        if len(self.health_checks) > 100:
            self.health_checks = self.health_checks[-100:]
        
        return health
    
    def _determine_status(self, cpu_percent: float, memory_percent: float) -> HealthStatus:
        """
        Determine overall health status based on metrics.
        
        Args:
            cpu_percent: CPU usage percentage
            memory_percent: Memory usage percentage
            
        Returns:
            HealthStatus enum
        """
        # Critical if either CPU or memory is critical
        if cpu_percent >= self.cpu_critical_threshold or memory_percent >= self.memory_critical_threshold:
            return HealthStatus.CRITICAL
        
        # Degraded if either is at warning level
        if cpu_percent >= self.cpu_warning_threshold or memory_percent >= self.memory_warning_threshold:
            return HealthStatus.DEGRADED
        
        # Otherwise healthy
        return HealthStatus.HEALTHY
    
    def record_request(self, success: bool = True):
        """
        Record a request for metrics tracking.
        
        Args:
            success: Whether request succeeded
        """
        self.total_requests += 1
        if not success:
            self.error_count += 1
    
    def _get_error_rate(self) -> float:
        """Calculate error rate"""
        if self.total_requests == 0:
            return 0.0
        return round(self.error_count / self.total_requests, 4)
    
    def get_uptime_formatted(self) -> str:
        """Get formatted uptime string"""
        uptime_seconds = int(time.time() - self.start_time)
        hours = uptime_seconds // 3600
        minutes = (uptime_seconds % 3600) // 60
        seconds = uptime_seconds % 60
        return f"{hours}h {minutes}m {seconds}s"
    
    def get_health_history(self, limit: int = 20) -> list:
        """
        Get recent health check history.
        
        Args:
            limit: Number of recent checks to return
            
        Returns:
            List of health check results
        """
        return self.health_checks[-limit:]
    
    def check_worker_status(self, worker_name: str, last_heartbeat: Optional[float] = None) -> dict:
        """
        Check status of a specific worker.
        
        Args:
            worker_name: Name of worker
            last_heartbeat: Timestamp of last heartbeat
            
        Returns:
            Worker status
        """
        if last_heartbeat is None:
            return {
                'worker': worker_name,
                'status': HealthStatus.DOWN.value,
                'message': 'No heartbeat received'
            }
        
        # Check if heartbeat is recent (within 30 seconds)
        time_since_heartbeat = time.time() - last_heartbeat
        
        if time_since_heartbeat > 30:
            status = HealthStatus.DOWN
        elif time_since_heartbeat > 15:
            status = HealthStatus.DEGRADED
        else:
            status = HealthStatus.HEALTHY
        
        return {
            'worker': worker_name,
            'status': status.value,
            'last_heartbeat': datetime.fromtimestamp(last_heartbeat).isoformat(),
            'seconds_since_heartbeat': int(time_since_heartbeat)
        }
    
    def get_diagnostics(self) -> dict:
        """
        Get full diagnostic report for troubleshooting.
        
        Returns:
            Comprehensive diagnostics
        """
        health = self.check_system_health()
        
        return {
            **health,
            'diagnostics': {
                'uptime_formatted': self.get_uptime_formatted(),
                'health_checks_recorded': len(self.health_checks),
                'average_cpu_last_20': self._get_average_metric('cpu', 20),
                'average_memory_last_20': self._get_average_metric('memory', 20)
            }
        }
    
    def _get_average_metric(self, metric: str, count: int) -> float:
        """Calculate average of a metric over recent checks"""
        if not self.health_checks:
            return 0.0
        
        recent = self.health_checks[-count:]
        values = [check[metric] for check in recent]
        return round(sum(values) / len(values), 1) if values else 0.0
    
    def reset_stats(self):
        """Reset request and error statistics"""
        self.total_requests = 0
        self.error_count = 0
        logger.info("Health monitor stats reset")
