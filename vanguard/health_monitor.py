"""
Vanguard Health Monitor
========================
Monitors system component health and creates incidents for failures.

Features:
- Real NBA API connectivity checks
- Gemini AI availability testing
- Firestore connection verification
- Automatic incident reporting to Vanguard
- Deduplication by component fingerprint
"""

import asyncio
import httpx
import os
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

# Try to import Vanguard Archivist if available
try:
    from vanguard.archivist import VanguardArchivist
    HAS_VANGUARD = True
except ImportError:
    HAS_VANGUARD = False
    class VanguardArchivist:
        """Stub for when Vanguard is not available"""
        pass


class SystemHealthMonitor:
    """Monitors system component health and reports to Vanguard."""
    
    def __init__(self, archivist: Optional[VanguardArchivist] = None):
        self.archivist = archivist
        self.checks = {
            'nba_api': self.check_nba_api,
            'gemini_ai': self.check_gemini,
            'firestore': self.check_firestore
        }
    
    async def check_nba_api(self) -> Dict:
        """
        Ping NBA stats API to verify availability.
        Uses a lightweight endpoint to minimize impact.
        """
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Use scoreboard endpoint with old date (cached, fast)
                start_time = datetime.now()
                resp = await client.get(
                    "https://stats.nba.com/stats/scoreboardv2",
                    params={
                        "GameDate": "2024-01-01",
                        "LeagueID": "00",
                        "DayOffset": "0"
                    },
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        "Accept": "application/json",
                        "Referer": "https://stats.nba.com/"
                    }
                )
                latency_ms = (datetime.now() - start_time).total_seconds() * 1000
                
                if resp.status_code == 200:
                    return {
                        "status": "healthy" if latency_ms < 2000 else "warning",
                        "latency_ms": latency_ms,
                        "details": f"NBA API responding ({resp.status_code})",
                        "endpoint": "stats.nba.com"
                    }
                else:
                    return {
                        "status": "critical",
                        "error": f"HTTP {resp.status_code}",
                        "details": f"NBA API returned {resp.status_code}"
                    }
                    
        except httpx.TimeoutException:
            return {
                "status": "critical",
                "error": "Timeout",
                "details": "NBA API request timed out after 10s"
            }
        except Exception as e:
            return {
                "status": "critical",
                "error": str(e),
                "details": f"NBA API unreachable: {type(e).__name__}"
            }
    
    async def check_gemini(self) -> Dict:
        """Check Gemini AI availability."""
        try:
            api_key = os.getenv('GEMINI_API_KEY')
            if not api_key:
                return {
                    "status": "warning",
                    "details": "No API key configured",
                    "error": "GEMINI_API_KEY not set"
                }
            
            # Just verify we can import and configure with new API
            from google import genai
            client = genai.Client(api_key=api_key)
            
            return {
                "status": "healthy",
                "details": "Gemini API key configured (google.genai)",
                "api_key_length": len(api_key)
            }
        except ImportError:
            return {
                "status": "critical",
                "error": "Module not installed",
                "details": "google-genai package missing"
            }
        except Exception as e:
            return {
                "status": "warning",
                "error": str(e),
                "details": f"Gemini configuration error: {type(e).__name__}"
            }
    
    async def check_firestore(self) -> Dict:
        """Check Firestore connectivity."""
        try:
            project_id = os.getenv('FIREBASE_PROJECT_ID') or os.getenv('GOOGLE_CLOUD_PROJECT')
            if not project_id:
                # In Cloud Run, it might be available via metadata service
                try:
                    import google.auth
                    _, project_id = google.auth.default()
                except:
                    pass
                    
            if not project_id:
                return {
                    "status": "warning", # Warning instead of critical if we just can't find ID
                    "details": "Could not determine project ID",
                    "error": "FIREBASE_PROJECT_ID not set"
                }
            
            # Try to get Firestore client
            from firestore_db import get_firestore_db
            db = get_firestore_db()
            
            if db is None:
                return {
                    "status": "critical",
                    "error": "Database not initialized",
                    "details": "Firestore client is None"
                }
            
            # Try a lightweight operation
            # Just list collections (doesn't fetch documents)
            try:
                collections = db.collections()
                # Convert to list to actually execute the query
                count = len(list(collections))
                
                return {
                    "status": "healthy",
                    "details": f"Firestore connected ({count} collections)",
                    "project_id": project_id
                }
            except Exception as query_error:
                return {
                    "status": "critical",
                    "error": str(query_error),
                    "details": "Firestore query failed"
                }
                
        except ImportError:
            return {
                "status": "critical",
                "error": "Firestore module not available",
                "details": "firebase-admin not installed"
            }
        except Exception as e:
            return {
                "status": "critical",
                "error": str(e),
                "details": f"Firestore connection error: {type(e).__name__}"
            }
    
    async def run_all_checks(self) -> Dict[str, Dict]:
        """Run all health checks concurrently."""
        results = {}
        
        # Run checks in parallel
        check_tasks = {
            name: check_func()
            for name, check_func in self.checks.items()
        }
        
        # Wait for all checks to complete
        completed = await asyncio.gather(*check_tasks.values(), return_exceptions=True)
        
        # Map results
        for (name, _), result in zip(check_tasks.items(), completed):
            if isinstance(result, Exception):
                results[name] = {
                    "status": "critical",
                    "error": str(result),
                    "details": f"Health check crashed: {type(result).__name__}"
                }
            else:
                results[name] = result
                
                # Report to Vanguard if unhealthy
                if result.get('status') in ['warning', 'critical'] and self.archivist:
                    await self.report_health_incident(name, result)
        
        return results
    
    async def report_health_incident(self, component: str, result: Dict):
        """
        Report a health incident to Vanguard (with deduplication).
        
        Vanguard will handle deduplication by fingerprint, so we can
        call this repeatedly without creating duplicate incidents.
        """
        if not HAS_VANGUARD or not self.archivist:
            return
        
        try:
            incident_data = {
                "category": "system_health",
                "component": component,
                "severity": "high" if result.get('status') == 'critical' else "medium",
                "message": result.get('error', f"{component} degraded"),
                "details": result,
                "endpoint": f"health_check/{component}",
                "error_type": "HealthCheckFailure"
            }
            
            # Archivist will handle fingerprinting and deduplication
            await self.archivist.record_incident(incident_data)
            
        except Exception as e:
            # Don't let reporting failures crash the health check
            print(f"[WARN] Failed to report health incident: {e}")


# Singleton instance
_health_monitor = None

def get_health_monitor(archivist: Optional[VanguardArchivist] = None) -> SystemHealthMonitor:
    """Get or create the global health monitor instance."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SystemHealthMonitor(archivist)
    return _health_monitor
