"""
Atomic Transactional Writer
Ensures zero data loss with temp → verify → move strategy
"""

import json
import shutil
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict
import logging
import hashlib
from core.config import CURRENT_SEASON

logger = logging.getLogger(__name__)


class AtomicWriter:
    """
    Atomic file writing with quality control.
    
    Strategy:
    1. Write to temp file (.tmp)
    2. Verify integrity (hash, schema, size)
    3. Atomically move to final location
    4. Confirm 100% write success
    
    Hierarchical Structure:
    data/
      └── Team_ID/
          └── Player_ID/
              ├── {CURRENT_SEASON}.json
              ├── career.json
    """
    
    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.stats = {
            'writes_attempted': 0,
            'writes_succeeded': 0,
            'writes_failed': 0,
            'bytes_written': 0
        }
    
    def get_path(self, team_id: str, player_id: str, filename: str) -> Path:
        """
        Get hierarchical file path.
        
        Args:
            team_id: NBA team ID
            player_id: NBA player ID  
            filename: File name (e.g., '2023-24.json', 'career.json')
            
        Returns:
            Path to file
        """
        return self.base_dir / team_id / player_id / filename
    
    async def write_atomic(self, team_id: str, player_id: str, filename: str, 
                           data: dict, verify_hash: Optional[str] = None) -> bool:
        """
        Atomically write data to hierarchical storage.
        
        Args:
            team_id: Team identifier
            player_id: Player identifier
            filename: Target filename
            data: Data dictionary to write
            verify_hash: Optional hash to verify against
            
        Returns:
            True if write succeeded, False otherwise
        """
        self.stats['writes_attempted'] += 1
        
        # 1. Prepare paths
        final_path = self.get_path(team_id, player_id, filename)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = final_path.with_suffix(final_path.suffix + '.tmp')
        
        try:
            # 2. Write to temp file
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            # 3. Verify temp file
            is_valid = self._verify_file(temp_path, data, verify_hash)
            if not is_valid:
                logger.error(f"Verification failed for {temp_path}")
                temp_path.unlink()  # Delete bad temp file
                self.stats['writes_failed'] += 1
                return False
            
            # 4. Atomic move
            shutil.move(str(temp_path), str(final_path))
            
            # 5. Confirm final file exists
            if not final_path.exists():
                raise FileNotFoundError(f"Atomic move failed: {final_path} not found")
            
            # 6. Update stats
            file_size = final_path.stat().st_size
            self.stats['bytes_written'] += file_size
            self.stats['writes_succeeded'] += 1
            
            logger.info(f"✓ Atomic write successful: {final_path} ({file_size} bytes)")
            return True
            
        except Exception as e:
            logger.error(f"Atomic write failed for {final_path}: {e}")
            # Cleanup temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            self.stats['writes_failed'] += 1
            return False
    
    def _verify_file(self, file_path: Path, original_data: dict, 
                     expected_hash: Optional[str] = None) -> bool:
        """
        Verify written file integrity.
        
        Checks:
        1. File exists and is readable
        2. JSON is valid
        3. Size is reasonable
        4. Hash matches (if provided)
        """
        try:
            # Check 1: Exists and readable
            if not file_path.exists():
                logger.error(f"File does not exist: {file_path}")
                return False
            
            # Check 2: Valid JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                loaded_data = json.load(f)
            
            # Check 3: Size check (not empty, not absurdly large)
            file_size = file_path.stat().st_size
            if file_size == 0:
                logger.error("File is empty")
                return False
            if file_size > 10 * 1024 * 1024:  # 10MB max
                logger.warning(f"File unusually large: {file_size} bytes")
            
            # Check 4: Hash verification (if provided)
            if expected_hash:
                computed_hash = self._compute_hash(loaded_data)
                if computed_hash != expected_hash:
                    logger.error(f"Hash mismatch: expected {expected_hash[:8]}..., got {computed_hash[:8]}...")
                    return False
            
            # Check 5: Data consistency
            if loaded_data != original_data:
                logger.error("Loaded data differs from original")
                return False
            
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return False
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return False
    
    def _compute_hash(self, data: dict) -> str:
        """Compute SHA-256 hash of data"""
        serialized = json.dumps(data, sort_keys=True)
        return hashlib.sha256(serialized.encode()).hexdigest()
    
    async def read_atomic(self, team_id: str, player_id: str, filename: str) -> Optional[dict]:
        """
        Read data from hierarchical storage.
        
        Args:
            team_id: Team identifier
            player_id: Player identifier
            filename: File to read
            
        Returns:
            Data dict or None if file doesn't exist
        """
        path = self.get_path(team_id, player_id, filename)
        
        if not path.exists():
            return None
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Read error for {path}: {e}")
            return None
    
    def list_player_files(self, team_id: str, player_id: str) -> list[str]:
        """
        List all data files for a player.
        
        Returns:
            List of filenames
        """
        player_dir = self.base_dir / team_id / player_id
        
        if not player_dir.exists():
            return []
        
        return [f.name for f in player_dir.iterdir() if f.is_file() and f.suffix == '.json']
    
    def get_stats(self) -> dict:
        """Return writer statistics"""
        return {
            **self.stats,
            'success_rate': (
                self.stats['writes_succeeded'] / self.stats['writes_attempted']
                if self.stats['writes_attempted'] > 0 else 1.0
            ),
            'total_mb_written': round(self.stats['bytes_written'] / 1024 / 1024, 2)
        }
    
    def run_quality_audit(self) -> dict:
        """
        Run quality control audit on all written files.
        
        Returns:
            Audit results with pass/fail counts
        """
        results = {
            'total_files': 0,
            'valid_files': 0,
            'invalid_files': 0,
            'errors': []
        }
        
        # Scan all files in hierarchical structure
        for team_dir in self.base_dir.iterdir():
            if not team_dir.is_dir():
                continue
                
            for player_dir in team_dir.iterdir():
                if not player_dir.is_dir():
                    continue
                
                for file_path in player_dir.iterdir():
                    if file_path.suffix != '.json':
                        continue
                    
                    results['total_files'] += 1
                    
                    try:
                        with open(file_path, 'r') as f:
                            data = json.load(f)
                        
                        # Basic validation
                        if data and isinstance(data, dict):
                            results['valid_files'] += 1
                        else:
                            results['invalid_files'] += 1
                            results['errors'].append(f"{file_path}: Invalid data structure")
                    except Exception as e:
                        results['invalid_files'] += 1
                        results['errors'].append(f"{file_path}: {str(e)}")
        
        results['pass_rate'] = (
            results['valid_files'] / results['total_files']
            if results['total_files'] > 0 else 1.0
        )
        
        return results
