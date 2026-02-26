"""
Phase 9 — Incident Model (Lazy-Loaded Inference Wrapper)
==========================================================
Provides a production-safe interface for ML incident classification.

Key patterns:
    - asyncio.to_thread() for non-blocking GCS downloads
    - Singleton with memory cache, /tmp disk cache, GCS origin
    - Fallback to None (caller must handle) if model unavailable
    - Feature extraction reuses ml.incident_classifier.features
    - Admin reload endpoint clears cache and re-downloads

Integration point:
    ai_analyzer.py → _create_fallback_analysis() → incident_model.classify()
"""

import asyncio
import os
import io
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

logger = logging.getLogger("vanguard.ml.incident_model")

# ─────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────
GCS_BUCKET = os.getenv("ML_ARTIFACTS_BUCKET", "quantsight-ml-artifacts")
GCS_MODEL_BLOB = "models/incident_classifier/latest.joblib"
GCS_ENCODER_BLOB = "models/incident_classifier/latest_encoder.joblib"
LOCAL_MODEL_PATH = "/tmp/ml_models/incident_classifier.joblib"
LOCAL_ENCODER_PATH = "/tmp/ml_models/label_encoder.joblib"
CONFIDENCE_THRESHOLD = 0.75  # Minimum confidence to use ML prediction


class IncidentModelWrapper:
    """Production wrapper for the incident classifier.
    
    Thread-safe, lazy-loaded, with graceful degradation.
    All GCS operations are offloaded to a thread pool to
    avoid blocking the async event loop.
    """
    
    def __init__(self):
        self._model = None
        self._encoder = None
        self._loaded = False
        self._load_error: Optional[str] = None
        self._model_version: Optional[str] = None
        self._load_timestamp: Optional[str] = None
    
    @property
    def is_loaded(self) -> bool:
        return self._loaded and self._model is not None
    
    @property
    def model_version(self) -> Optional[str]:
        return self._model_version
    
    @property
    def load_error(self) -> Optional[str]:
        return self._load_error
    
    def _try_load_from_local(self) -> bool:
        """Try loading model from local cache (/tmp)."""
        try:
            import joblib
            
            if os.path.exists(LOCAL_MODEL_PATH) and os.path.exists(LOCAL_ENCODER_PATH):
                self._model = joblib.load(LOCAL_MODEL_PATH)
                self._encoder = joblib.load(LOCAL_ENCODER_PATH)
                logger.info(f"ML model loaded from local cache: {LOCAL_MODEL_PATH}")
                return True
        except Exception as e:
            logger.debug(f"Local model load failed: {e}")
        return False
    
    def _try_load_from_gcs(self) -> bool:
        """Download model from GCS and cache locally.
        
        WARNING: This method performs synchronous I/O. In async contexts,
        always call via asyncio.to_thread() or use load_async().
        """
        try:
            from google.cloud import storage
            import joblib
            
            client = storage.Client()
            bucket = client.bucket(GCS_BUCKET)
            
            # Download model
            model_blob = bucket.blob(GCS_MODEL_BLOB)
            if not model_blob.exists():
                logger.warning(f"Model blob not found: gs://{GCS_BUCKET}/{GCS_MODEL_BLOB}")
                return False
            
            model_bytes = model_blob.download_as_bytes()
            self._model = joblib.load(io.BytesIO(model_bytes))
            
            # Download encoder
            encoder_blob = bucket.blob(GCS_ENCODER_BLOB)
            encoder_bytes = None
            if encoder_blob.exists():
                encoder_bytes = encoder_blob.download_as_bytes()
                self._encoder = joblib.load(io.BytesIO(encoder_bytes))
            
            # Cache locally for faster subsequent loads (cold start optimization)
            os.makedirs(os.path.dirname(LOCAL_MODEL_PATH), exist_ok=True)
            with open(LOCAL_MODEL_PATH, "wb") as f:
                f.write(model_bytes)
            if encoder_bytes:
                with open(LOCAL_ENCODER_PATH, "wb") as f:
                    f.write(encoder_bytes)
            
            logger.info(f"ML model loaded from GCS: gs://{GCS_BUCKET}/{GCS_MODEL_BLOB}")
            return True
            
        except Exception as e:
            logger.warning(f"GCS model load failed: {e}")
            return False
    
    def _try_load_from_artifacts_dir(self) -> bool:
        """Try loading from the local ml_artifacts build directory."""
        try:
            import joblib
            
            artifacts_dir = os.path.join(
                os.path.dirname(__file__), "..", "..", "ml_artifacts"
            )
            model_path = os.path.join(artifacts_dir, "incident_classifier.joblib")
            encoder_path = os.path.join(artifacts_dir, "label_encoder.joblib")
            
            if os.path.exists(model_path):
                self._model = joblib.load(model_path)
                if os.path.exists(encoder_path):
                    self._encoder = joblib.load(encoder_path)
                logger.info(f"ML model loaded from artifacts dir: {model_path}")
                return True
        except Exception as e:
            logger.debug(f"Artifacts dir load failed: {e}")
        return False
    
    def _load_sync(self) -> bool:
        """Synchronous load from any available source.
        
        Priority: local /tmp cache → GCS → artifacts dir
        """
        if self._loaded:
            return self._model is not None
        
        self._loaded = True  # Mark attempted (even if fails)
        
        for loader_name, loader in [
            ("local_cache", self._try_load_from_local),
            ("gcs", self._try_load_from_gcs),
            ("artifacts_dir", self._try_load_from_artifacts_dir),
        ]:
            if loader():
                self._load_error = None
                self._load_timestamp = datetime.now(timezone.utc).isoformat()
                self._model_version = f"loaded_from_{loader_name}"
                return True
        
        self._load_error = "Model not found in any source"
        logger.warning(f"ML incident classifier unavailable: {self._load_error}")
        return False
    
    async def load_async(self) -> bool:
        """Non-blocking model load. Offloads GCS I/O to thread pool.
        
        Use this from async contexts (FastAPI request handlers, middleware).
        """
        if self._loaded:
            return self._model is not None
        
        # Try local cache first (fast, no I/O worth offloading)
        if self._try_load_from_local():
            self._loaded = True
            self._load_error = None
            self._load_timestamp = datetime.now(timezone.utc).isoformat()
            self._model_version = "loaded_from_local_cache"
            return True
        
        # GCS download is the blocking operation — offload to thread pool
        result = await asyncio.to_thread(self._load_sync)
        return result
    
    def load(self) -> bool:
        """Synchronous load for non-async callers (e.g. CLI, tests).
        
        In async contexts, prefer load_async().
        """
        return self._load_sync()
    
    async def reload(self) -> bool:
        """Force reload model from origin (for admin endpoint).
        
        Clears all caches and re-downloads from GCS.
        """
        logger.info("ML model reload requested — clearing caches")
        
        # Clear memory state
        self._model = None
        self._encoder = None
        self._loaded = False
        self._load_error = None
        
        # Clear local disk cache
        for path in [LOCAL_MODEL_PATH, LOCAL_ENCODER_PATH]:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        
        # Reload from origin (non-blocking)
        return await self.load_async()
    
    def classify(
        self,
        incident: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Classify a single incident using the ML model.
        
        Args:
            incident: Raw incident dictionary
            
        Returns:
            Classification result dict or None if model unavailable/low confidence.
            Result includes:
                - label: str (predicted class)
                - confidence: float (0.0–1.0)
                - probabilities: dict (class → probability)
                - model_version: str
        """
        # Ensure model is loaded (sync — fast if cached in memory)
        if not self.load():
            return None
        
        try:
            from ml.incident_classifier.features import extract_features_single
            
            # Extract features
            features = extract_features_single(incident)
            feature_names = sorted(features.keys())
            X = [[features[name] for name in feature_names]]
            
            # Predict
            model = self._model
            
            # Handle imblearn Pipeline vs plain model
            if hasattr(model, "predict_proba"):
                probas = model.predict_proba(X)[0]
                predicted_idx = probas.argmax()
                confidence = float(probas[predicted_idx])
            elif hasattr(model, "named_steps") and hasattr(model.named_steps.get("clf", None), "predict_proba"):
                probas = model.named_steps["clf"].predict_proba(X)[0]
                predicted_idx = probas.argmax()
                confidence = float(probas[predicted_idx])
            else:
                # Fallback: predict without probabilities
                predicted_idx = model.predict(X)[0]
                confidence = 0.5
                probas = None
            
            # Decode label
            if self._encoder is not None:
                label = self._encoder.inverse_transform([predicted_idx])[0]
                if probas is not None:
                    prob_dict = {
                        self._encoder.inverse_transform([i])[0]: round(float(p), 4)
                        for i, p in enumerate(probas)
                        if i < len(self._encoder.classes_)
                    }
                else:
                    prob_dict = {}
            else:
                label = str(predicted_idx)
                prob_dict = {}
            
            # Apply confidence threshold
            if confidence < CONFIDENCE_THRESHOLD:
                logger.debug(
                    f"ML confidence {confidence:.3f} below threshold "
                    f"{CONFIDENCE_THRESHOLD} for {incident.get('fingerprint', '?')}"
                )
                return None
            
            return {
                "label": label,
                "confidence": round(confidence, 4),
                "probabilities": prob_dict,
                "model_version": self._model_version,
                "classified_at": datetime.now(timezone.utc).isoformat(),
            }
            
        except Exception as e:
            logger.error(f"ML classification failed: {e}", exc_info=True)
            return None
    
    def health_status(self) -> Dict[str, Any]:
        """Return health status for SYSTEM_SNAPSHOT integration."""
        return {
            "ml_classifier_ok": self.is_loaded,
            "ml_classifier_version": self._model_version,
            "ml_classifier_error": self._load_error,
            "ml_classifier_loaded_at": self._load_timestamp,
        }


# ─────────────────────────────────────────────
# Singleton accessor
# ─────────────────────────────────────────────
_instance: Optional[IncidentModelWrapper] = None


def get_incident_model() -> IncidentModelWrapper:
    """Get or create the global incident model wrapper.
    
    Thread-safe singleton pattern matching Vanguard conventions.
    """
    global _instance
    if _instance is None:
        _instance = IncidentModelWrapper()
    return _instance
