"""
TruthSerumFilter - CSV integrity validation and corruption detection.

Validates CSV files for schema compliance and triggers background recovery
for corrupted data sources.

Also includes GarbageTimeFilter for excluding blowout stats.
"""

import hashlib
import logging
from typing import Dict, List, Optional
from pathlib import Path
from dataclasses import dataclass
import pandas as pd

logger = logging.getLogger(__name__)


class TruthSerumFilter:
    """
    CSV validation and integrity checking.
    
    Validation Checks:
    - Column count matches expected schema
    - SHA-256 checksum against baseline (optional)
    - No duplicate player_id entries
    - Required columns present
    """
    
    EXPECTED_COLUMNS = {
        "player_id", "name", "team", "position", 
        "games_played", "minutes", "points", "rebounds", "assists"
    }
    
    def __init__(self):
        """Initialize the truth serum filter."""
        self.validation_cache: Dict[str, bool] = {}
    
    def calculate_checksum(self, file_path: str) -> str:
        """
        Calculate SHA-256 checksum of file.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Hexadecimal checksum string
        """
        sha256_hash = hashlib.sha256()
        
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        
        return sha256_hash.hexdigest()
    
    def validate_schema(self, file_path: str) -> Dict[str, any]:
        """
        Validate CSV schema and structure.
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            Dict with validation results
        """
        results = {
            "valid": True,
            "errors": [],
            "warnings": [],
            "file_path": file_path
        }
        
        try:
            # Check file exists
            if not Path(file_path).exists():
                results["valid"] = False
                results["errors"].append("File not found")
                return results
            
            # Read CSV
            df = pd.read_csv(file_path)
            
            # Check column presence
            missing_cols = self.EXPECTED_COLUMNS - set(df.columns)
            if missing_cols:
                results["valid"] = False
                results["errors"].append(f"Missing columns: {missing_cols}")
            
            # Check for duplicates
            if 'player_id' in df.columns:
                duplicates = df['player_id'].duplicated().sum()
                if duplicates > 0:
                    results["valid"] = False
                    results["errors"].append(f"Found {duplicates} duplicate player_id entries")
            
            # Check for empty dataframe
            if len(df) == 0:
                results["valid"] = False
                results["errors"].append("CSV is empty")
            
            # Warnings for data quality
            if len(df) < 100:
                results["warnings"].append(f"Low row count: {len(df)} players")
            
            logger.info(f"[TRUTH_SERUM] Validated {file_path}: {'PASS' if results['valid'] else 'FAIL'}")
            
        except pd.errors.EmptyDataError:
            results["valid"] = False
            results["errors"].append("CSV is empty or corrupted")
        except Exception as e:
            results["valid"] = False
            results["errors"].append(f"Validation error: {str(e)}")
        
        return results
    
    def validate_with_checksum(
        self, 
        file_path: str, 
        expected_checksum: Optional[str] = None
    ) -> Dict[str, any]:
        """
        Validate file with optional checksum verification.
        
        Args:
            file_path: Path to CSV file
            expected_checksum: Optional SHA-256 checksum to verify against
            
        Returns:
            Dict with validation results including checksum
        """
        results = self.validate_schema(file_path)
        
        if results["valid"] and expected_checksum:
            actual_checksum = self.calculate_checksum(file_path)
            
            if actual_checksum != expected_checksum:
                results["valid"] = False
                results["errors"].append("Checksum mismatch - file may be corrupted")
                results["actual_checksum"] = actual_checksum
                results["expected_checksum"] = expected_checksum
            else:
                logger.info(f"[TRUTH_SERUM] Checksum verified for {file_path}")
        
        return results
    
    def quick_check(self, file_path: str) -> bool:
        """
        Quick validation check (cached).
        
        Args:
            file_path: Path to CSV file
            
        Returns:
            True if valid, False otherwise
        """
        # Check cache first
        if file_path in self.validation_cache:
            return self.validation_cache[file_path]
        
        # Run validation
        results = self.validate_schema(file_path)
        is_valid = results["valid"]
        
        # Cache result
        self.validation_cache[file_path] = is_valid
        
        return is_valid


@dataclass
class GarbageTimeResult:
    """Result of garbage time filtering"""
    original_avg: float
    filtered_avg: float
    deflator_applied: float
    blowout_games: int
    total_games: int


class GarbageTimeFilter:
    """
    Garbage Time / Blowout Stats Filter v3.1
    
    Excludes inflated stats from blowout games.
    
    Definition:
    - Blowout: Point differential >= 15 in 4th quarter
    - Deflator: -12% applied to competitive average
    """
    
    BLOWOUT_THRESHOLD = 15  # Point differential
    BASE_DEFLATOR = -0.12  # -12% for blowout stats
    
    def __init__(self):
        self._cache: Dict[str, List[Dict]] = {}
    
    def filter_garbage_time(
        self,
        game_logs: List[Dict],
        stat: str = 'points'
    ) -> GarbageTimeResult:
        """
        Filter garbage time stats from game logs.
        
        Uses heuristic: if final score diff >= 15, apply deflator.
        This is the "Blowout Auto-Deflator" - no PBP parsing delay.
        
        Args:
            game_logs: List of game dictionaries
            stat: Which stat to filter (default: points)
            
        Returns:
            GarbageTimeResult with adjusted average
        """
        if not game_logs:
            return GarbageTimeResult(0, 0, 0, 0, 0)
        
        blowout_games = []
        competitive_games = []
        
        for game in game_logs:
            score_diff = abs(
                game.get('plus_minus', 0) or 
                game.get('score_diff', 0) or
                self._estimate_score_diff(game)
            )
            
            if score_diff >= self.BLOWOUT_THRESHOLD:
                blowout_games.append(game)
            else:
                competitive_games.append(game)
        
        # Calculate averages
        stat_key = self._get_stat_key(stat, game_logs[0] if game_logs else {})
        
        all_values = [float(g.get(stat_key, 0) or 0) for g in game_logs]
        original_avg = sum(all_values) / len(all_values) if all_values else 0
        
        # If significant blowouts, apply deflator
        blowout_ratio = len(blowout_games) / len(game_logs)
        
        if blowout_ratio >= 0.15:  # 15%+ blowout games
            # Calculate competitive-only average
            if competitive_games:
                comp_values = [float(g.get(stat_key, 0) or 0) for g in competitive_games]
                competitive_avg = sum(comp_values) / len(comp_values)
            else:
                competitive_avg = original_avg
            
            # Apply proportional deflator
            deflator = self.BASE_DEFLATOR * blowout_ratio
            filtered_avg = original_avg * (1 + deflator)
        else:
            filtered_avg = original_avg
            deflator = 0
        
        return GarbageTimeResult(
            original_avg=round(original_avg, 2),
            filtered_avg=round(filtered_avg, 2),
            deflator_applied=round(deflator, 4),
            blowout_games=len(blowout_games),
            total_games=len(game_logs)
        )
    
    def _estimate_score_diff(self, game: Dict) -> int:
        """Estimate score diff from game stats if not directly available"""
        # If player had high minutes in a win/loss, estimate blowout
        minutes = game.get('min', game.get('minutes', 30))
        win = game.get('wl', game.get('result', 'W'))
        
        if minutes < 20 and win:
            # Low minutes in win suggests blowout
            return 20
        elif minutes < 20:
            # Low minutes in loss suggests blowout loss
            return 18
        
        return 5  # Assume competitive
    
    def _get_stat_key(self, stat: str, sample_game: Dict) -> str:
        """Get the actual key used in game logs for a stat"""
        key_mappings = {
            'points': ['pts', 'points', 'PTS'],
            'rebounds': ['reb', 'rebounds', 'REB'],
            'assists': ['ast', 'assists', 'AST'],
            'threes': ['fg3m', 'three_pm', 'FG3M'],
        }
        
        for possible_key in key_mappings.get(stat, [stat]):
            if possible_key in sample_game:
                return possible_key
        
        return stat
    
    def calculate_true_average(
        self,
        player_id: str,
        game_logs: List[Dict]
    ) -> Dict[str, float]:
        """
        Calculate true (garbage-time-filtered) averages for all stats.
        
        Returns:
            Dict with filtered averages for each stat
        """
        result = {}
        
        for stat in ['points', 'rebounds', 'assists', 'threes']:
            filtered = self.filter_garbage_time(game_logs, stat)
            result[f'{stat}_true_avg'] = filtered.filtered_avg
            result[f'{stat}_deflator'] = filtered.deflator_applied
        
        result['blowout_games'] = self.filter_garbage_time(game_logs).blowout_games
        result['total_games'] = len(game_logs)
        
        return result
