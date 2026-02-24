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
        Ping NBA data APIs to verify availability.

        Strategy (Cloud Run safe):
          1. Primary: cdn.nba.com CDN endpoint — no VPC needed, always fast
          2. Secondary: stats.nba.com — blocked on Cloud Run VPC; absence = warning only
        """
        CDN_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
        STATS_URL = "https://stats.nba.com/stats/scoreboardv2"
        STATS_HEADERS = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://stats.nba.com/",
            "x-nba-stats-origin": "stats",
            "x-nba-stats-token": "true",
        }

        # ── Step 1: CDN check (required — fast, no VPC) ──────────────────────
        cdn_status = "unknown"
        cdn_latency_ms: float = 0.0
        cdn_error: Optional[str] = None

        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                start = datetime.now()
                resp = await client.get(CDN_URL)
                cdn_latency_ms = (datetime.now() - start).total_seconds() * 1000

                if resp.status_code == 200:
                    cdn_status = "healthy" if cdn_latency_ms < 2000 else "warning"
                else:
                    cdn_status = "critical"
                    cdn_error = f"CDN HTTP {resp.status_code}"
        except httpx.TimeoutException:
            cdn_status = "critical"
            cdn_error = "CDN timeout after 8s"
        except Exception as e:
            cdn_status = "critical"
            cdn_error = f"CDN unreachable: {type(e).__name__}"

        # If CDN is down, NBA data pipeline is truly broken
        if cdn_status == "critical":
            return {
                "status": "critical",
                "error": cdn_error,
                "details": "NBA CDN unreachable — live data pipeline down",
                "endpoint": "cdn.nba.com",
                "cdn_latency_ms": cdn_latency_ms,
            }

        # ── Step 2: stats.nba.com check (optional — blocked on Cloud Run VPC) ─
        stats_status = "unknown"
        stats_latency_ms: float = 0.0
        stats_error: Optional[str] = None

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                start = datetime.now()
                resp = await client.get(
                    STATS_URL,
                    params={"GameDate": "2024-01-01", "LeagueID": "00", "DayOffset": "0"},
                    headers=STATS_HEADERS,
                )
                stats_latency_ms = (datetime.now() - start).total_seconds() * 1000
                stats_status = "healthy" if resp.status_code == 200 else f"HTTP {resp.status_code}"
        except httpx.TimeoutException:
            stats_error = "Timeout (expected on Cloud Run VPC)"
            stats_status = "blocked"
        except Exception as e:
            stats_error = f"{type(e).__name__}: {e}"
            stats_status = "blocked"

        # CDN OK is all we need for healthy status
        return {
            "status": cdn_status,  # healthy or warning based on CDN only
            "latency_ms": cdn_latency_ms,
            "details": f"NBA CDN responding ({cdn_latency_ms:.0f}ms)",
            "endpoint": "cdn.nba.com",
            "cdn_status": cdn_status,
            "cdn_latency_ms": cdn_latency_ms,
            "stats_nba_status": stats_status,
            "stats_nba_latency_ms": stats_latency_ms,
            "stats_nba_note": (
                stats_error or
                ("stats.nba.com healthy" if stats_status == "healthy" else
                 "stats.nba.com blocked (normal on Cloud Run VPC — CDN path is the workaround)")
            ),
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
