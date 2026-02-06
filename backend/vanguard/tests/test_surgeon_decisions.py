"""
Vanguard Surgeon Decision Logic Tests
======================================
Tests for the decide_remediation method with various confidence scenarios.
"""

import pytest
from vanguard.surgeon.remediation import VanguardSurgeon

@pytest.mark.asyncio
async def test_high_confidence_ready_to_resolve():
    """Test that high confidence + ready = MONITOR"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {
        "confidence": 90,
        "ready_to_resolve": True,
        "root_cause": "Fixed in commit abc123"
    }
    
    decision = await surgeon.decide_remediation(incident, analysis, "CIRCUIT_BREAKER")
    
    assert decision["action"] == "MONITOR"
    assert decision["confidence"] == 90
    assert "fixed" in decision["reason"].lower()
    assert decision["endpoint"] == "/test"
    assert decision["mode"] == "CIRCUIT_BREAKER"


@pytest.mark.asyncio
async def test_high_confidence_not_ready():
    """Test that high confidence but NOT ready = RATE_LIMIT"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {
        "confidence": 90,
        "ready_to_resolve": False,  # NOT ready
        "root_cause": "Still investigating"
    }
    
    decision = await surgeon.decide_remediation(incident, analysis, "CIRCUIT_BREAKER")
    
    # High confidence but not ready should still be cautious
    assert decision["action"] in ["RATE_LIMIT", "MONITOR"]
    assert decision["confidence"] == 90


@pytest.mark.asyncio
async def test_low_confidence_quarantine():
    """Test that low confidence = QUARANTINE"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {
        "confidence": 45,
        "ready_to_resolve": False,
        "root_cause": "Unknown error"
    }
    
    decision = await surgeon.decide_remediation(incident, analysis, "CIRCUIT_BREAKER")
    
    assert decision["action"] == "QUARANTINE"
    assert decision["confidence"] == 45
    assert "quarantine" in decision["reason"].lower()


@pytest.mark.asyncio
async def test_medium_confidence_rate_limit():
    """Test that medium confidence = RATE_LIMIT"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {
        "confidence": 75,
        "ready_to_resolve": False,
        "root_cause": "Possible database timeout"
    }
    
    decision = await surgeon.decide_remediation(incident, analysis, "CIRCUIT_BREAKER")
    
    assert decision["action"] == "RATE_LIMIT"
    assert decision["confidence"] == 75
    assert "50%" in decision["reason"]  # Should mention 50% traffic reduction


@pytest.mark.asyncio
async def test_silent_observer_mode():
    """Test that SILENT_OBSERVER mode = LOG_ONLY"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {
        "confidence": 45,  # Even low confidence
        "ready_to_resolve": False,
        "root_cause": "Critical error"
    }
    
    decision = await surgeon.decide_remediation(incident, analysis, "SILENT_OBSERVER")
    
    assert decision["action"] == "LOG_ONLY"
    assert decision["mode"] == "SILENT_OBSERVER"
    assert "silent" in decision["reason"].lower()


@pytest.mark.asyncio
async def test_boundary_confidence_85():
    """Test boundary: exactly 85% confidence + ready"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {
        "confidence": 85,  # Exactly at boundary
        "ready_to_resolve": True,
        "root_cause": "Fixed"
    }
    
    decision = await surgeon.decide_remediation(incident, analysis, "CIRCUIT_BREAKER")
    
    assert decision["action"] == "MONITOR"
    assert decision["confidence"] == 85


@pytest.mark.asyncio
async def test_boundary_confidence_70():
    """Test boundary: exactly 70% confidence"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {
        "confidence": 70,  # Exactly at boundary
        "ready_to_resolve": False,
        "root_cause": "Investigating"
    }
    
    decision = await surgeon.decide_remediation(incident, analysis, "CIRCUIT_BREAKER")
    
    assert decision["action"] == "RATE_LIMIT"
    assert decision["confidence"] == 70


@pytest.mark.asyncio
async def test_missing_confidence():
    """Test handling of missing confidence field"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {
        # No confidence field
        "ready_to_resolve": False,
        "root_cause": "Unknown"
    }
    
    decision = await surgeon.decide_remediation(incident, analysis, "CIRCUIT_BREAKER")
    
    # Should default to 0 confidence = QUARANTINE
    assert decision["action"] == "QUARANTINE"
    assert decision["confidence"] == 0


@pytest.mark.asyncio
async def test_decision_has_timestamp():
    """Test that decision includes timestamp"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {
        "confidence": 80,
        "ready_to_resolve": False,
        "root_cause": "Test"
    }
    
    decision = await surgeon.decide_remediation(incident, analysis, "CIRCUIT_BREAKER")
    
    assert "timestamp" in decision
    assert decision["timestamp"]  # Not empty
    assert "T" in decision["timestamp"]  # ISO format


@pytest.mark.asyncio
async def test_unknown_mode_logs_only():
    """Test that unknown mode defaults to LOG_ONLY"""
    surgeon = VanguardSurgeon()
    
    incident = {"endpoint": "/test", "error_type": "HTTPError500"}
    analysis = {"confidence": 90, "ready_to_resolve": True}
    
    decision = await surgeon.decide_remediation(incident, analysis, "UNKNOWN_MODE")
    
    assert decision["action"] == "LOG_ONLY"
    assert "unknown" in decision["reason"].lower()
