"""
Vanguard Score-Based Health System
====================================
Comprehensive health monitoring with weighted scoring.

Health Score Calculation (0-100):
- System Components (60 points):
  - NBA API: 25 points (critical for data)
  - Gemini AI: 15 points (important for analysis)
  - Firestore: 20 points (critical for storage)

- Endpoint Health (40 points):
  - Critical endpoints: 3 points each
  - Standard endpoints: 1 point each
  
Score Ranges:
- 90-100: Healthy (green)
- 70-89: Warning (yellow)
- 0-69: Critical (red)
"""

from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import asyncio


@dataclass
class EndpointHealth:
    """Health status of a single endpoint."""
    endpoint: str
    status: str  # 'healthy', 'warning', 'critical', 'unknown'
    latency_ms: Optional[float] = None
    last_check: Optional[str] = None
    error: Optional[str] = None
    uptime_percent: float = 100.0  # Last 24h uptime
    criticality: str = "standard"  # 'critical', 'standard', 'optional'


@dataclass
class SystemHealthScore:
    """Overall system health with detailed breakdown."""
    overall_score: float  # 0-100
    status: str  # 'healthy', 'warning', 'critical'
    components: Dict[str, EndpointHealth]
    endpoints: List[EndpointHealth]
    timestamp: str
    details: Dict


class HealthScoreCalculator:
    """Calculates weighted health scores for the system."""
    
    # Component weights (must sum to 60)
    COMPONENT_WEIGHTS = {
        'nba_api': 25,      # Critical - primary data source
        'gemini_ai': 15,    # Important - AI features
        'firestore': 20     # Critical - data persistence
    }
    
    # Endpoint criticality weights
    ENDPOINT_WEIGHTS = {
        'critical': 3,   # Core functionality
        'standard': 1,   # Normal features
        'optional': 0.5  # Nice-to-have
    }
    
    # Critical endpoints (worth more points)
    CRITICAL_ENDPOINTS = {
        '/health', '/teams', '/roster/*', '/players/search',
        '/player/*', '/live/stream', '/matchup/analyze'
    }
    
    def __init__(self):
        self.endpoint_history: Dict[str, List[EndpointHealth]] = {}
    
    def calculate_component_score(self, components: Dict[str, Dict]) -> float:
        """
        Calculate score from system components (0-60 points).
        
        Args:
            components: Dict of component_name -> health_result
            
        Returns:
            Score from 0-60
        """
        score = 0.0
        
        for component, weight in self.COMPONENT_WEIGHTS.items():
            health = components.get(component, {})
            status = health.get('status', 'unknown')
            
            # Convert status to multiplier
            if status == 'healthy':
                multiplier = 1.0
            elif status == 'warning':
                multiplier = 0.5
            elif status == 'critical' or status == 'unknown':
                multiplier = 0.0
            else:
                multiplier = 0.0
            
            score += weight * multiplier
        
        return score
    
    def calculate_endpoint_score(self, endpoints: List[EndpointHealth], max_points: float = 40.0) -> float:
        """
        Calculate score from endpoint health (0-40 points).
        
        Endpoints are weighted by criticality and their status.
        """
        if not endpoints:
            return 0.0
        
        total_weight = 0.0
        earned_points = 0.0
        
        for ep in endpoints:
            # Get weight based on criticality
            weight = self.ENDPOINT_WEIGHTS.get(ep.criticality, 1.0)
            total_weight += weight
            
            # Calculate multiplier from status and uptime
            if ep.status == 'healthy':
                status_mult = 1.0
            elif ep.status == 'warning':
                status_mult = 0.6
            elif ep.status == 'critical':
                status_mult = 0.2
            else:  # unknown
                status_mult = 0.0
            
            # Factor in uptime
            uptime_mult = ep.uptime_percent / 100.0
            
            # Combined multiplier
            multiplier = status_mult * uptime_mult
            earned_points += weight * multiplier
        
        # Normalize to max_points
        if total_weight > 0:
            return (earned_points / total_weight) * max_points
        return 0.0
    
    def determine_status(self, score: float) -> str:
        """Convert numerical score to status."""
        if score >= 90:
            return 'healthy'
        elif score >= 70:
            return 'warning'
        else:
            return 'critical'
    
    def calculate_overall_score(
        self,
        components: Dict[str, Dict],
        endpoints: List[EndpointHealth]
    ) -> SystemHealthScore:
        """
        Calculate comprehensive health score.
        
        Returns:
            SystemHealthScore with overall score (0-100) and breakdown
        """
        # Component score (60 points max)
        component_score = self.calculate_component_score(components)
        
        # Endpoint score (40 points max)
        endpoint_score = self.calculate_endpoint_score(endpoints)
        
        # Overall score (0-100)
        overall_score = component_score + endpoint_score
        status = self.determine_status(overall_score)
        
        # Convert components dict to EndpointHealth objects
        component_health = {}
        for name, data in components.items():
            component_health[name] = EndpointHealth(
                endpoint=name,
                status=data.get('status', 'unknown'),
                latency_ms=data.get('latency_ms'),
                last_check=data.get('last_check'),
                error=data.get('error'),
                criticality='critical' if name in ['nba_api', 'firestore'] else 'standard'
            )
        
        return SystemHealthScore(
            overall_score=round(overall_score, 2),
            status=status,
            components=component_health,
            endpoints=endpoints,
            timestamp=datetime.utcnow().isoformat(),
            details={
                'component_score': round(component_score, 2),
                'endpoint_score': round(endpoint_score, 2),
                'component_count': len(components),
                'endpoint_count': len(endpoints),
                'critical_endpoints_down': sum(
                    1 for ep in endpoints 
                    if ep.criticality == 'critical' and ep.status == 'critical'
                )
            }
        )
    
    def track_endpoint_health(self, endpoint: EndpointHealth):
        """
        Track endpoint health over time for uptime calculation.
        
        Keeps last 24 hours of checks.
        """
        if endpoint.endpoint not in self.endpoint_history:
            self.endpoint_history[endpoint.endpoint] = []
        
        history = self.endpoint_history[endpoint.endpoint]
        history.append(endpoint)
        
        # Keep only last 24 hours
        cutoff = datetime.utcnow() - timedelta(hours=24)
        self.endpoint_history[endpoint.endpoint] = [
            ep for ep in history
            if ep.last_check and datetime.fromisoformat(ep.last_check) > cutoff
        ]
    
    def calculate_uptime(self, endpoint_name: str) -> float:
        """
        Calculate uptime percentage for the last 24 hours.
        
        Returns:
            Uptime percentage (0-100)
        """
        history = self.endpoint_history.get(endpoint_name, [])
        if not history:
            return 100.0  # Assume healthy if no history
        
        healthy_count = sum(
            1 for ep in history
            if ep.status in ['healthy', 'warning']
        )
        
        return (healthy_count / len(history)) * 100.0


# Global instance
_score_calculator = None

def get_score_calculator() -> HealthScoreCalculator:
    """Get or create the global score calculator instance."""
    global _score_calculator
    if _score_calculator is None:
        _score_calculator = HealthScoreCalculator()
    return _score_calculator
