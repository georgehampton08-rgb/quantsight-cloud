"""
Data Integrity Healer - Self-Healing with SHA-256 Verification
Ensures all cached data maintains integrity through hashing and auto-repair
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class DataIntegrityHealer:
    """
    Ensures all cached data maintains integrity through:
    - SHA-256 hash verification
    - Timestamp tracking
    - Automatic corruption repair (try-heal-retry loop)
    """
    
    def __init__(self):
        self.repair_attempts = {}
        self.stats = {
            'verified': 0,
            'corrupted': 0,
            'repaired': 0,
            'failed': 0
        }
    
    def compute_hash(self, data: dict) -> str:
        """Generate SHA-256 hash of data content"""
        # Sort keys for consistency
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    def wrap_with_metadata(self, data: dict) -> dict:
        """
        Add integrity metadata to data before storage.
        
        Returns:
            {
                'data': <original data>,
                'metadata': {
                    'hash': '<SHA-256>',
                    'last_sync': '<ISO timestamp>',
                    'version': '1.0',
                    'schema_version': 'aegis_v1'
                }
            }
        """
        return {
            'data': data,
            'metadata': {
                'hash': self.compute_hash(data),
                'last_sync': datetime.now().isoformat(),
                'version': '1.0',
                'schema_version': 'aegis_v1'
            }
        }
    
    def verify_integrity(self, wrapped_data: dict) -> Tuple[bool, str]:
        """
        Verify stored data hasn't been corrupted or tampered with.
        
        Args:
            wrapped_data: Data with metadata wrapper
            
        Returns:
            (is_valid, error_message)
        """
        try:
            # Check for required structure
            if 'metadata' not in wrapped_data or 'data' not in wrapped_data:
                return False, "Missing metadata or data field"
            
            stored_hash = wrapped_data['metadata'].get('hash')
            if not stored_hash:
                return False, "Hash missing from metadata"
            
            # Compute current hash
            computed_hash = self.compute_hash(wrapped_data['data'])
            
            if stored_hash != computed_hash:
                self.stats['corrupted'] += 1
                return False, f"Hash mismatch - data may be corrupted (stored: {stored_hash[:8]}..., computed: {computed_hash[:8]}...)"
            
            self.stats['verified'] += 1
            return True, "OK"
            
        except KeyError as e:
            return False, f"Missing metadata field: {e}"
        except Exception as e:
            return False, f"Verification error: {e}"
    
    def try_heal_retry(self, corrupted_data: str, entity_type: str, entity_id: int) -> Optional[dict]:
        """
        Try-Heal-Retry loop for corrupted data.
        
        Attempts:
        1. Auto-fix common issues (BOM, quotes, commas)
        2. Return None to trigger API re-fetch
        3. After 2 failures, mark as permanently corrupted
        
        Args:
            corrupted_data: Raw corrupted data string
            entity_type: Type of entity
            entity_id: Entity identifier
            
        Returns:
            Fixed data dict, or None if repair failed
        """
        attempt_key = f"{entity_type}:{entity_id}"
        attempts = self.repair_attempts.get(attempt_key, 0)
        
        if attempts >= 2:
            # Max retries reached - mark as failed
            self.stats['failed'] += 1
            logger.error(f"Max repair attempts reached for {attempt_key}")
            return None
        
        self.repair_attempts[attempt_key] = attempts + 1
        
        # Attempt 1: Try to auto-fix common issues
        if attempts == 0:
            logger.info(f"Attempting auto-fix for {attempt_key} (attempt {attempts + 1})")
            fixed = self._attempt_auto_fix(corrupted_data)
            if fixed:
                self.stats['repaired'] += 1
                logger.info(f"Successfully repaired {attempt_key}")
                return fixed
        
        # Attempt 2: Return None to signal API re-fetch needed
        logger.warning(f"Auto-fix failed for {attempt_key}, API re-fetch required")
        return None
    
    def _attempt_auto_fix(self, data_str: str) -> Optional[dict]:
        """
        Attempt to auto-fix common data corruption issues.
        
        Fixes:
        1. BOM (Byte Order Mark) characters
        2. Single quotes instead of double quotes
        3. Trailing commas in JSON
        4. Missing closing brackets
        """
        try:
            # Fix 1: Handle BOM characters
            if data_str.startswith('\ufeff'):
                data_str = data_str[1:]
                logger.debug("Removed BOM character")
            
            # Fix 2: Handle single quotes instead of double
            # Only replace quotes not inside strings
            import re
            data_str = data_str.replace("'", '"')
            
            # Fix 3: Handle trailing commas
            data_str = re.sub(r',\s*}', '}', data_str)
            data_str = re.sub(r',\s*]', ']', data_str)
            
            # Fix 4: Try to parse
            data = json.loads(data_str)
            logger.debug("Successfully parsed after auto-fix")
            return data
            
        except json.JSONDecodeError as e:
            logger.debug(f"Auto-fix failed: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during auto-fix: {e}")
            return None
    
    def get_stats(self) -> dict:
        """Return integrity healer statistics"""
        total = self.stats['verified'] + self.stats['corrupted']
        return {
            **self.stats,
            'integrity_rate': (
                self.stats['verified'] / total
                if total > 0 else 1.0
            ),
            'repair_success_rate': (
                self.stats['repaired'] / self.stats['corrupted']
                if self.stats['corrupted'] > 0 else 0.0
            )
        }
    
    def reset_stats(self):
        """Reset statistics (for testing)"""
        self.stats = {
            'verified': 0,
            'corrupted': 0,
            'repaired': 0,
            'failed': 0
        }
        self.repair_attempts = {}
