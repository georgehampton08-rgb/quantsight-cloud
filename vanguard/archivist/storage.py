"""
Incident Storage
================
Async JSON file I/O for incident persistence with Redis fallback.
"""

import json
import os
import re
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import aiofiles

from ..core.types import Incident
from ..core.config import get_vanguard_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class IncidentStorage:
    """Manages incident file storage with async I/O and Redis fallback."""
    
    def __init__(self):
        self.config = get_vanguard_config()
        self.storage_path = Path(self.config.storage_path) / "incidents"
        self.metadata_path = Path(self.config.storage_path) / "metadata.json"
        
        # Ensure directories exist
        try:
            self.storage_path.mkdir(parents=True, exist_ok=True)
            logger.info("storage_initialized", path=str(self.storage_path))
        except Exception as e:
            logger.error("storage_init_failed", error=str(e))
        
        # In-memory fallback cache
        self._memory_cache: Dict[str, Incident] = {}
    
    def _get_incident_path(self, fingerprint: str) -> Path:
        """Get file path for an incident."""
        return self.storage_path / f"{fingerprint}.json"
    
    def _auto_label_incident(self, incident: Incident) -> Dict[str, str]:
        """Auto-label incident by service, component, and error category."""
        labels = {}
        endpoint = incident.get("endpoint", "")
        error_type = incident.get("error_type", "")
        traceback_str = incident.get("traceback", "") or ""
        
        # Service from endpoint
        if "/player" in endpoint:
            labels["service"] = "player_api"
            labels["category"] = "player_data"
        elif "/team" in endpoint or "/roster" in endpoint:
            labels["service"] = "team_api"
            labels["category"] = "team_data"
        elif "/matchup" in endpoint or "/analyze" in endpoint:
            labels["service"] = "matchup_engine"
            labels["category"] = "analysis"
        elif "/vanguard" in endpoint:
            labels["service"] = "vanguard"
            labels["category"] = "system"
        elif "/admin" in endpoint:
            labels["service"] = "admin_api"
            labels["category"] = "admin"
        else:
            labels["service"] = "api"
            labels["category"] = "general"
        
        # Error category from type
        if "404" in error_type:
            labels["error_category"] = "not_found"
        elif "422" in error_type or "Validation" in error_type:
            labels["error_category"] = "validation"
        elif "500" in error_type or "Internal" in error_type:
            labels["error_category"] = "internal_error"
        elif "Timeout" in error_type or "Connection" in error_type:
            labels["error_category"] = "network"
        elif "Auth" in error_type or "Permission" in error_type:
            labels["error_category"] = "auth"
        else:
            labels["error_category"] = "logic"
        
        # Component from traceback
        if traceback_str:
            match = re.search(r'File ".*?([^/\\]+\.py)"', traceback_str)
            if match:
                labels["component"] = match.group(1).replace(".py", "")
        
        # Root cause system
        if "firestore" in traceback_str.lower():
            labels["root_cause"] = "firestore"
        elif "redis" in traceback_str.lower():
            labels["root_cause"] = "redis"
        elif "api" in traceback_str.lower():
            labels["root_cause"] = "api_layer"
        else:
            labels["root_cause"] = "application"
        
        return labels
    
    async def _update_metadata(self, is_new: bool = True, is_resolved: bool = False, is_purge: bool = False) -> None:
        """Update metadata with incident counts (FileSystem or Firestore)."""
        try:
            if self.config.storage_mode == "FIRESTORE":
                from ..core.config import get_vanguard_config
                # We can't easily import from ..firestore_db due to circular dependencies or path issues
                # so we'll try a local import
                try:
                    import firebase_admin
                    from firebase_admin import firestore
                    db = firestore.client()
                    meta_ref = db.collection('vanguard_metadata').document('global')
                    
                    # Use a transaction for atomic increments
                    @firestore.transactional
                    def update_in_transaction(transaction, ref):
                        snapshot = ref.get(transaction=transaction)
                        data = snapshot.to_dict() if snapshot.exists else {
                            "total_incidents": 0, "active_count": 0, "resolved_count": 0, "last_purge_timestamp": None
                        }
                        
                        if is_new:
                            data["total_incidents"] = data.get("total_incidents", 0) + 1
                            data["active_count"] = data.get("active_count", 0) + 1
                        elif is_resolved:
                            data["active_count"] = max(0, data.get("active_count", 0) - 1)
                            data["resolved_count"] = data.get("resolved_count", 0) + 1
                        elif is_purge:
                            data["last_purge_timestamp"] = datetime.now(timezone.utc).isoformat()
                            
                        transaction.set(ref, data)
                        return data

                    transaction = db.transaction()
                    update_in_transaction(transaction, meta_ref)
                    return
                except Exception as e:
                    logger.error("firestore_metadata_update_failed", error=str(e))
                    # Fallback to local file if Firestore fails

            # Load current metadata (File system)
            metadata = {"total_incidents": 0, "active_count": 0, "resolved_count": 0, "last_purge_timestamp": None}
            if self.metadata_path.exists():
                async with aiofiles.open(self.metadata_path, "r") as f:
                    metadata = json.loads(await f.read())
            
            # Update counts
            if is_new:
                metadata["total_incidents"] = metadata.get("total_incidents", 0) + 1
                metadata["active_count"] = metadata.get("active_count", 0) + 1
            elif is_resolved:
                metadata["active_count"] = max(0, metadata.get("active_count", 0) - 1)
                metadata["resolved_count"] = metadata.get("resolved_count", 0) + 1
            elif is_purge:
                metadata["last_purge_timestamp"] = datetime.now(timezone.utc).isoformat()
            
            # Save updated metadata
            async with aiofiles.open(self.metadata_path, "w") as f:
                await f.write(json.dumps(metadata, indent=2))
            
            logger.debug("metadata_updated", total=metadata["total_incidents"], active=metadata["active_count"])
        except Exception as e:
            logger.error("metadata_update_failed", error=str(e))
    
    async def store(self, incident: Incident) -> bool:
        """Store an incident with support for Firestore and state-based persistence."""
        fingerprint = incident["fingerprint"]
        
        # Auto-label the incident
        labels = self._auto_label_incident(incident)
        incident["labels"] = labels
        incident["status"] = incident.get("status", "active").lower()
        
        now = datetime.now(timezone.utc).isoformat()
        
        # FIRESTORE TIER (Preferred for Cloud)
        if self.config.storage_mode == "FIRESTORE":
            try:
                import firebase_admin
                from firebase_admin import firestore
                db = firestore.client()
                incident_ref = db.collection('vanguard_incidents').document(fingerprint)
                
                doc = incident_ref.get()
                is_new = not doc.exists
                
                if not is_new:
                    existing = doc.to_dict()
                    # Increment occurrence count
                    existing["occurrence_count"] = existing.get("occurrence_count", 1) + 1
                    existing["last_seen"] = now
                    
                    # Track occurrence history (last 10)
                    if "occurrences" not in existing:
                        existing["occurrences"] = []
                    existing["occurrences"].append({
                        "timestamp": now,
                        "request_id": incident.get("request_id"),
                        "context": incident.get("context_vector", {})
                    })
                    existing["occurrences"] = existing["occurrences"][-10:]
                    existing["labels"] = labels
                    # Stay 'active' even if it was resolved but reappeared
                    existing["status"] = "active"
                    
                    incident_ref.set(existing)
                    logger.info("incident_duplicate_detected_firestore", fingerprint=fingerprint)
                else:
                    # New incident
                    incident["stored_at"] = now
                    incident["first_seen"] = now
                    incident["last_seen"] = now
                    incident["occurrence_count"] = 1
                    incident["occurrences"] = [{
                        "timestamp": now,
                        "request_id": incident.get("request_id"),
                        "context": incident.get("context_vector", {})
                    }]
                    incident["storage_tier"] = "firestore"
                    incident_ref.set(incident)
                    await self._update_metadata(is_new=True)
                    logger.info("incident_stored_firestore", fingerprint=fingerprint)
                
                return True
            except Exception as e:
                logger.warning("firestore_storage_failed", error=str(e))

        # FILE SYSTEM TIER (Original)
        file_path = self._get_incident_path(fingerprint)
        is_new = not file_path.exists()
        
        if not is_new:
            try:
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    existing = json.loads(await f.read())
                
                existing["occurrence_count"] = existing.get("occurrence_count", 1) + 1
                existing["last_seen"] = now
                if "occurrences" not in existing: existing["occurrences"] = []
                existing["occurrences"].append({"timestamp": now, "request_id": incident.get("request_id")})
                existing["occurrences"] = existing["occurrences"][-10:]
                existing["labels"] = labels
                existing["status"] = "active"
                
                async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(existing, indent=2))
                return True
            except Exception as e:
                logger.warning("file_merge_failed", error=str(e))
        
        # New File Incident
        incident["stored_at"] = now
        incident["first_seen"] = now
        incident["last_seen"] = now
        incident["occurrence_count"] = 1
        incident["occurrences"] = [{"timestamp": now, "request_id": incident.get("request_id")}]
        incident["storage_tier"] = "file"
        
        try:
            async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(incident, indent=2))
            await self._update_metadata(is_new=True)
            return True
        except Exception as e:
            logger.warning("file_storage_failed", error=str(e))
        
        # Redis Fallback
        try:
            from ..bootstrap.redis_client import get_redis
            redis = await get_redis()
            if redis:
                incident["storage_tier"] = "redis"
                await redis.set(f"vanguard:incident:{fingerprint}", json.dumps(incident), ex=604800)
                if is_new:
                    await redis.incr("vanguard:incidents:total")
                    await redis.incr("vanguard:incidents:active")
                return True
        except Exception: pass
        
        return False
    
    async def load(self, fingerprint: str) -> Optional[Incident]:
        """Load an incident (Firestore with Tier fallback)."""
        # Firestore
        if self.config.storage_mode == "FIRESTORE":
            try:
                import firebase_admin
                from firebase_admin import firestore
                db = firestore.client()
                doc = db.collection('vanguard_incidents').document(fingerprint).get()
                if doc.exists:
                    return doc.to_dict()
            except Exception: pass

        # File
        try:
            file_path = self._get_incident_path(fingerprint)
            if file_path.exists():
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    return json.loads(await f.read())
        except Exception: pass
        return self._memory_cache.get(fingerprint)
    
    async def update_incident(self, fingerprint: str, update_data: Dict[str, Any]) -> bool:
        """Update specific fields in an incident (Firestore update or File rewrite)."""
        # Firestore
        if self.config.storage_mode == "FIRESTORE":
            try:
                import firebase_admin
                from firebase_admin import firestore
                db = firestore.client()
                ref = db.collection('vanguard_incidents').document(fingerprint)
                if ref.get().exists:
                    ref.update(update_data)
                    return True
            except Exception as e:
                logger.warning(f"firestore_update_failed: {e}")

        # File
        try:
            file_path = self._get_incident_path(fingerprint)
            if file_path.exists():
                async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                    incident = json.loads(await f.read())
                
                # Apply updates
                incident.update(update_data)
                
                async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(incident, indent=2))
                return True
        except Exception as e:
            logger.warning(f"file_update_failed: {e}")
            
        return False
    
    async def resolve(self, fingerprint: str) -> bool:
        """Mark an incident as resolved instead of deleting it (Learning mode)."""
        # Firestore
        if self.config.storage_mode == "FIRESTORE":
            try:
                import firebase_admin
                from firebase_admin import firestore
                db = firestore.client()
                ref = db.collection('vanguard_incidents').document(fingerprint)
                if ref.get().exists:
                    ref.update({"status": "resolved", "resolved_at": datetime.now(timezone.utc).isoformat()})
                    await self._update_metadata(is_new=False, is_resolved=True)
                    return True
            except Exception: pass

        # File
        file_path = self._get_incident_path(fingerprint)
        if file_path.exists():
            try:
                async with aiofiles.open(file_path, "r") as f:
                    incident = json.loads(await f.read())
                incident["status"] = "resolved"
                incident["resolved_at"] = datetime.now(timezone.utc).isoformat()
                async with aiofiles.open(file_path, "w") as f:
                    await f.write(json.dumps(incident, indent=2))
                await self._update_metadata(is_new=False, is_resolved=True)
                return True
            except Exception: pass
            
        return False

    async def delete(self, fingerprint: str) -> bool:
        """Legacy alias for resolve (to maintain compatibility)."""
        return await self.resolve(fingerprint)
    
    async def list_incidents(self, limit: int = 2000) -> List[str]:
        """List recent incident fingerprints (Firestore or FileSystem)."""
        incidents = []
        
        # Firestore
        if self.config.storage_mode == "FIRESTORE":
            try:
                import firebase_admin
                from firebase_admin import firestore
                db = firestore.client()
                # Order by last_seen if possible, but status=active first
                docs = db.collection('vanguard_incidents') \
                         .where(filter=firestore.FieldFilter('status', '==', 'active')) \
                         .limit(limit) \
                         .stream()
                incidents.extend([doc.id for doc in docs])
                
                # If we need more, get some resolved ones
                if len(incidents) < limit:
                    resolved = db.collection('vanguard_incidents') \
                                 .where(filter=firestore.FieldFilter('status', '==', 'resolved')) \
                                 .limit(limit - len(incidents)) \
                                 .stream()
                    incidents.extend([doc.id for doc in resolved])
            except Exception as e:
                logger.error("firestore_list_failed", error=str(e))

        # File system
        try:
            file_incidents = [f.stem for f in self.storage_path.glob("*.json")]
            incidents.extend(file_incidents)
        except Exception: pass
        
        return list(dict.fromkeys(incidents))[:limit]
    
    def get_storage_size_mb(self) -> float:
        """Estimate storage size."""
        try:
            total_bytes = sum(f.stat().st_size for f in self.storage_path.glob("*.json"))
            return total_bytes / 1024 / 1024
        except Exception: return 0.0
    
    def get_incidents_by_label(self, label_key: str) -> Dict[str, int]:
        """Get incident counts grouped by a label."""
        counts: Dict[str, int] = {}
        try:
            for fp in self.list_incidents():
                incident = self._memory_cache.get(fp)
                if incident:
                    labels = incident.get("labels", {})
                    value = labels.get(label_key, "unknown")
                    counts[value] = counts.get(value, 0) + 1
        except Exception as e:
            logger.error("label_count_error", error=str(e))
        return counts


# Global storage instance
_storage: IncidentStorage | None = None


def get_incident_storage() -> IncidentStorage:
    """Get or create the global incident storage."""
    global _storage
    if _storage is None:
        _storage = IncidentStorage()
    return _storage

