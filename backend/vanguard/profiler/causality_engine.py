"""
Causality Engine
================
T+0 analysis to identify Patient Zero in cascading failures.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from ..utils.logger import get_logger

logger = get_logger(__name__)


class CausalityEngine:
    """
    Analyzes temporal sequence of symptoms to identify root cause.
    Implements the First-Mover Rule from the manifest.
    """
    
    def analyze_t0(
        self,
        error_timestamp: datetime,
        historical_metrics: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Analyze the 5 seconds BEFORE an error to identify root cause.
        
        Args:
            error_timestamp: When the error occurred
            historical_metrics: Metrics from 5s before error
        
        Returns:
            {
                "patient_zero": str,  # First metric to spike
                "cascade": List[str],  # Secondary symptoms
                "evidence": str
            }
        """
        if not historical_metrics:
            return {
                "patient_zero": "UNKNOWN",
                "cascade": [],
                "evidence": "No historical metrics available"
            }
        
        # Sort metrics by timestamp
        sorted_metrics = sorted(historical_metrics, key=lambda m: m.get("timestamp", ""))
        
        # Detect first anomaly
        patient_zero = None
        cascade = []
        
        for metric_data in sorted_metrics:
            # Check for anomalies in each metric type
            if metric_data.get("cpu_percent", 0) > 80 and not patient_zero:
                patient_zero = "EVENT_LOOP_SATURATION"
                cascade.append(f"CPU spiked to {metric_data['cpu_percent']}% at {metric_data.get('timestamp')}")
            
            elif metric_data.get("memory_mb", 0) > 1000 and not patient_zero:
                patient_zero = "MEMORY_LEAK"
                cascade.append(f"Memory grew to {metric_data['memory_mb']}MB at {metric_data.get('timestamp')}")
            
            # TODO: Add more detection logic for DB latency, etc.
        
        if not patient_zero:
            patient_zero = "UNKNOWN_PATTERN"
            evidence = "No clear temporal correlation detected"
        else:
            evidence = f"First spike: {patient_zero}"
        
        logger.info("t0_analysis_complete", patient_zero=patient_zero, cascade_length=len(cascade))
        
        return {
            "patient_zero": patient_zero,
            "cascade": cascade,
            "evidence": evidence
        }


def identify_patient_zero(symptoms: List[str], temporal_data: List[Dict[str, Any]]) -> str:
    """
    Identify Patient Zero from multiple symptoms.
    
    Args:
        symptoms: List of observed symptoms
        temporal_data: Time-series metrics
    
    Returns:
        Name of Patient Zero metric
    """
    engine = CausalityEngine()
    
    # Use current time as reference (simplified)
    result = engine.analyze_t0(
        error_timestamp=datetime.utcnow(),
        historical_metrics=temporal_data
    )
    
    return result["patient_zero"]
