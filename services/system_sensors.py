"""
SystemSensorGenerator - Real-time health monitoring for QuantSight platform.

Replaces hardcoded mocks with actual system checks and latency measurements.
"""

import time
import sqlite3
import requests
import logging
from typing import Dict, Optional
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SensorData(BaseModel):
    """Health sensor data model."""
    database_status: str  # "healthy" | "warning" | "critical"
    api_status: str
    gemini_status: str
    database_latency_ms: Optional[float] = None
    api_latency_ms: Optional[float] = None
    timestamp: str
    supervisor_status: str = "unknown"


class SystemSensorGenerator:
    """
    Real-time system health monitoring.
    
    Status Logic:
    - healthy: All checks pass, latency < 500ms
    - warning: Checks pass but latency 500-1000ms
    - critical: Any check fails or latency > 1000ms
    """
    
    def __init__(self, db_path: str):
        """
        Initialize sensor generator.
        
        Args:
            db_path: Path to SQLite database for health checks
        """
        self.db_path = db_path
        self.nba_api_url = "https://stats.nba.com"
    
    def check_database(self) -> Dict[str, any]:
        """
        Check SQLite database health.
        
        Returns:
            Dict with status and latency_ms
        """
        start = time.time()
        try:
            if not Path(self.db_path).exists():
                logger.warning(f"[SENSOR] Database file not found: {self.db_path}")
                return {"status": "critical", "latency_ms": 0}
            
            # Simple query to verify connectivity
            conn = sqlite3.connect(self.db_path, timeout=2.0)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM players LIMIT 1")
            cursor.fetchone()
            conn.close()
            
            latency_ms = (time.time() - start) * 1000
            
            if latency_ms < 500:
                status = "healthy"
            elif latency_ms < 1000:
                status = "warning"
            else:
                status = "critical"
            
            logger.info(f"[SENSOR] Database check: {status} ({latency_ms:.0f}ms)")
            return {"status": status, "latency_ms": round(latency_ms, 2)}
            
        except sqlite3.Error as e:
            logger.error(f"[SENSOR] Database error: {e}")
            return {"status": "critical", "latency_ms": 0}
        except Exception as e:
            logger.error(f"[SENSOR] Unexpected database error: {e}")
            return {"status": "critical", "latency_ms": 0}
    
    def check_nba_api(self) -> Dict[str, any]:
        """
        Check NBA API connectivity with HEAD request.
        
        Returns:
            Dict with status and latency_ms
        """
        start = time.time()
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.nba.com/'
            }
            
            response = requests.head(
                self.nba_api_url,
                headers=headers,
                timeout=3.0,
                allow_redirects=True
            )
            
            latency_ms = (time.time() - start) * 1000
            
            if response.status_code < 400:
                if latency_ms < 500:
                    status = "healthy"
                elif latency_ms < 1000:
                    status = "warning"
                else:
                    status = "critical"
            else:
                status = "warning"  # API reachable but returned error
            
            logger.info(f"[SENSOR] NBA API check: {status} ({latency_ms:.0f}ms)")
            return {"status": status, "latency_ms": round(latency_ms, 2)}
            
        except requests.ConnectionError:
            logger.error("[SENSOR] NBA API connection failed")
            return {"status": "critical", "latency_ms": 0}
        except requests.Timeout:
            logger.error("[SENSOR] NBA API timeout")
            return {"status": "critical", "latency_ms": 3000}
        except Exception as e:
            logger.error(f"[SENSOR] Unexpected API error: {e}")
            return {"status": "critical", "latency_ms": 0}
    
    def check_gemini(self) -> Dict[str, any]:
        """
        Check Gemini API health with a simple token count or small generation.
        
        Returns:
            Dict with status and latency_ms
        """
        start = time.time()
        try:
            from google import genai
            import os
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                return {"status": "critical", "latency_ms": 0}
            
            client = genai.Client(api_key=api_key)
            # Use a tiny generation to verify connectivity
            client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents='health_check'
            )
            
            latency_ms = (time.time() - start) * 1000
            status = "healthy" if latency_ms < 1000 else "warning"
            
            return {"status": status, "latency_ms": round(latency_ms, 2)}
        except Exception as e:
            logger.error(f"[SENSOR] Gemini health check failed: {e}")
            return {"status": "critical", "latency_ms": 0}

    def check_all(self) -> SensorData:
        """
        Execute all health checks and return consolidated sensor data.
        
        Returns:
            SensorData with all system health metrics
        """
        db_result = self.check_database()
        api_result = self.check_nba_api()
        gemini_result = self.check_gemini()
        
        return SensorData(
            database_status=db_result["status"],
            api_status=api_result["status"],
            gemini_status=gemini_result["status"],
            database_latency_ms=db_result["latency_ms"],
            api_latency_ms=api_result["latency_ms"],
            timestamp=datetime.now().isoformat(),
            supervisor_status="running"
        )
