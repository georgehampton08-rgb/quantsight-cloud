"""
Vanguard Telemetry Middleware
==============================
Captures request/response metrics and integrates with adaptive sampling.
"""

import time
import traceback
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..core.types import Trace, Incident
from ..core.context import get_request_id
from ..utils.logger import get_logger
from .sampler import get_sampler
from .fingerprint import generate_error_fingerprint

# Defensive import — storage may fail to initialize
_STORAGE_AVAILABLE = False
_get_incident_storage = None
try:
    from ..archivist.storage import get_incident_storage as _get_incident_storage
    _STORAGE_AVAILABLE = True
except Exception as _import_err:
    import logging
    logging.warning(f"Incident storage import failed: {_import_err}")

logger = get_logger(__name__)


def _safe_get_storage():
    """Safely get incident storage, returning None if unavailable."""
    if not _STORAGE_AVAILABLE or _get_incident_storage is None:
        return None
    try:
        return _get_incident_storage()
    except Exception:
        return None


class VanguardTelemetryMiddleware(BaseHTTPMiddleware):
    """
    Telemetry middleware for request/response capture.
    Works in conjunction with RequestIDMiddleware.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Get request ID from context (set by RequestIDMiddleware)
        request_id = get_request_id()
        
        # ✅ PHASE 4: Check quarantine and rate limits BEFORE processing request
        endpoint = request.url.path
        
        # Check if endpoint is quarantined
        storage = _safe_get_storage()
        if storage is not None:
            try:
                quarantine_doc = await storage.get_document(
                    collection="vanguard_quarantine",
                    document_id=endpoint.replace("/", "_")
                )
                
                if quarantine_doc and quarantine_doc.get("active"):
                    from fastapi.responses import JSONResponse
                    logger.warning("quarantine_block", endpoint=endpoint)
                    return JSONResponse(
                        status_code=503,
                        content={
                            "error": "Service temporarily unavailable",
                            "reason": "Endpoint quarantined by Vanguard Surgeon",
                            "contact": "Check Vanguard Control Room for details"
                        }
                    )
            except Exception as quarantine_error:
                logger.error("quarantine_check_failed", error=str(quarantine_error))
        
            # Check rate limits
            try:
                import random
                rate_limit_doc = await storage.get_document(
                    collection="vanguard_rate_limits",
                    document_id=endpoint.replace("/", "_")
                )
                
                if rate_limit_doc and rate_limit_doc.get("active"):
                    limit_pct = rate_limit_doc.get("limit_pct", 100)
                    # Drop requests above limit percentage
                    if random.randint(1, 100) > limit_pct:
                        from fastapi.responses import JSONResponse
                        logger.info("rate_limit_drop", endpoint=endpoint, limit=limit_pct)
                        return JSONResponse(
                            status_code=429,
                            content={"error": "Too many requests", "retry_after": 60}
                        )
            except Exception as rate_limit_error:
                logger.error("rate_limit_check_failed", error=str(rate_limit_error))

        
        # Check if we should fully trace this request
        sampler = get_sampler()
        should_sample = sampler.should_sample(request.url.path)
        
        # Record start time
        start_time = time.perf_counter()
        
        # Track request
        error_occurred = None
        
        try:
            # Process request
            response = await call_next(request)
            
        except Exception as e:
            # Capture error
            error_occurred = e
            error_type = type(e).__name__
            error_message = str(e)
            tb_lines = traceback.format_exc().split("\n")
            
            # Generate error fingerprint
            fingerprint = generate_error_fingerprint(
                exception_type=error_type,
                traceback_lines=tb_lines,
                endpoint=request.url.path
            )
            
            # Log error with fingerprint
            logger.error(
                "request_error",
                request_id=request_id,
                error_type=error_type,
                error_message=error_message,
                fingerprint=fingerprint,
                endpoint=request.url.path,
                method=request.method,
            )
            
            # Store incident to Archivist
            try:
                from datetime import datetime, timezone
                storage = _safe_get_storage()
                if storage is None:
                    raise RuntimeError("Storage unavailable")
                incident: Incident = {
                    "fingerprint": fingerprint,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "severity": "RED",  # Unhandled exceptions are critical
                    "status": "ACTIVE",
                    "error_type": error_type,
                    "error_message": error_message,
                    "endpoint": request.url.path,
                    "request_id": request_id or "unknown",
                    "traceback": "\\n".join(tb_lines[:10]),  # First 10 lines as string
                    "context_vector": {
                        "method": request.method,
                        "user_agent": request.headers.get("User-Agent", "unknown"),
                        "ip": request.client.host if request.client else "unknown"
                    },
                    "remediation_log": [],
                    "resolved_at": None
                }
                await storage.store(incident)
                logger.debug("incident_stored", fingerprint=fingerprint)
                
                # ✅ PHASE 3: Trigger AI Analyzer + Surgeon for RED severity incidents
                if incident["severity"] == "RED":
                    try:
                        from ..ai.ai_analyzer import get_ai_analyzer
                        from ..surgeon.remediation import get_surgeon
                        from ..core.config import get_vanguard_config
                        
                        # Get smart analysis with GitHub context
                        ai_analyzer = get_ai_analyzer()
                        analysis = await ai_analyzer.analyze_incident(
                            incident=incident,
                            storage=storage,
                            force_regenerate=False  # Use cache if available
                        )
                        
                        # Surgeon makes decision based on AI analysis
                        surgeon = get_surgeon()
                        config = get_vanguard_config()
                        
                        decision = await surgeon.decide_remediation(
                            incident=incident,
                            analysis=analysis.dict() if hasattr(analysis, 'dict') else analysis,
                            mode=config.mode
                        )
                        
                        # ✅ PHASE 4: Execute remediation
                        result = await surgeon.execute_remediation(decision, storage)
                        
                        # Update incident with AI analysis and surgeon decision
                        incident["ai_analysis"] = analysis.dict() if hasattr(analysis, 'dict') else analysis
                        incident["surgeon_decision"] = decision
                        incident["surgeon_result"] = result
                        await storage.store(incident)  # Re-save with full data
                        
                        logger.info(
                            "surgeon_remediation_complete",
                            fingerprint=fingerprint,
                            confidence=analysis.get("confidence") if isinstance(analysis, dict) else getattr(analysis, 'confidence', 0),
                            action=decision.get("action"),
                            executed=result.get("executed")
                        )
                    except Exception as surgeon_error:
                        logger.error("surgeon_remediation_failed", error=str(surgeon_error), traceback=traceback.format_exc())
                        
            except Exception as store_error:
                logger.error("incident_storage_failed", error=str(store_error))
            
            # Force full sampling for this endpoint (incident detected)
            sampler.force_sampling(request.url.path, rate=1.0, duration_sec=300)
            
            # Re-raise error
            raise
        
        finally:
            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Check if response is an HTTP error (404, 422, 500, etc.)
            if not error_occurred and hasattr(response, 'status_code') and response.status_code >= 400:
                # Treat HTTP errors as incidents
                try:
                    from datetime import datetime, timezone
                    from ..archivist.storage import get_incident_storage
                    
                    # Generate fingerprint for HTTP error
                    fingerprint = generate_error_fingerprint(
                        exception_type=f"HTTPError{response.status_code}",
                        traceback_lines=[f"{response.status_code} {request.method} {request.url.path}"],
                        endpoint=request.url.path
                    )
                    
                    # Create incident
                    storage = _safe_get_storage()
                    if storage is None:
                        raise RuntimeError("Storage unavailable")
                    incident: Incident = {
                        "fingerprint": fingerprint,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "severity": "YELLOW" if response.status_code < 500 else "RED",
                        "status": "ACTIVE",
                        "error_type": f"HTTPError{response.status_code}",
                        "error_message": f"{response.status_code} {request.method} {request.url.path}",
                        "endpoint": request.url.path,
                        "request_id": request_id or "unknown",
                        "traceback": None,
                        "context_vector": {
                            "method": request.method,
                            "status_code": response.status_code,
                            "user_agent": request.headers.get("User-Agent", "unknown"),
                            "ip": request.client.host if request.client else "unknown"
                        },
                        "remediation_log": [],
                        "resolved_at": None
                    }
                    await storage.store(incident)
                    logger.info("http_error_captured", status=response.status_code, fingerprint=fingerprint)
                    
                    # ✅ PHASE 3: Trigger AI Analyzer + Surgeon for 500 errors
                    if response.status_code >= 500:
                        try:
                            from ..ai.ai_analyzer import get_ai_analyzer
                            from ..surgeon.remediation import get_surgeon
                            from ..core.config import get_vanguard_config
                            
                            ai_analyzer = get_ai_analyzer()
                            analysis = await ai_analyzer.analyze_incident(
                                incident=incident,
                                storage=storage,
                                force_regenerate=False
                            )
                            
                            surgeon = get_surgeon()
                            config = get_vanguard_config()
                            decision = await surgeon.decide_remediation(
                                incident=incident,
                                analysis=analysis.dict() if hasattr(analysis, 'dict') else analysis,
                                mode=config.mode
                            )
                            
                            result = await surgeon.execute_remediation(decision, storage)
                            
                            incident["ai_analysis"] = analysis.dict() if hasattr(analysis, 'dict') else analysis
                            incident["surgeon_decision"] = decision
                            incident["surgeon_result"] = result
                            await storage.store(incident)
                        except Exception as surgeon_error:
                            logger.error("surgeon_remediation_failed", error=str(surgeon_error))
                            
                except Exception as http_error_capture:
                    logger.error("http_error_capture_failed", error=str(http_error_capture))
            
            # Log trace
            if should_sample or error_occurred:
                trace: Trace = {
                    "request_id": request_id or "unknown",
                    "timestamp": time.time(),
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code if not error_occurred else 500,
                    "duration_ms": duration_ms,
                    "error": str(error_occurred) if error_occurred else None,
                    "sampled": True
                }
                
                logger.info("request_traced", **trace)
            else:
                # Metadata only
                logger.debug(
                    "request_metadata",
                    request_id=request_id,
                    path=request.url.path,
                    duration_ms=duration_ms,
                    sampled=False
                )
        
        return response
