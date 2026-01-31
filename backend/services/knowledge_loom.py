import csv
import json
import os
from datetime import datetime
from pathlib import Path

class KnowledgeLoom:
    """
    The Knowledge-Loom: Persistent storage for player game logs.
    Stores data in CSV format for Kaggle compatibility.
    """
    
    def __init__(self, data_dir="backend/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.game_logs_path = self.data_dir / "game_logs.csv"
        self.metadata_path = self.data_dir / "sync_metadata.json"
        
        # Initialize CSV if not exists
        if not self.game_logs_path.exists():
            self._initialize_csv()
    
    def _initialize_csv(self):
        """Create the CSV with headers."""
        headers = [
            "player_id", "player_name", "game_date", "opponent",
            "points", "rebounds", "assists", "minutes",
            "sync_timestamp", "source"
        ]
        with open(self.game_logs_path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
        print(f"[LOOM] Initialized game_logs.csv at {self.game_logs_path}")
    
    def append_game_log(self, player_id, player_name, game_data, source="API"):
        """
        Append a game log entry to the CSV.
        
        Args:
            player_id: Player identifier
            player_name: Player name
            game_data: Dict with keys: date, opponent, pts, reb, ast, min
            source: Data source (API, Cache, Kaggle)
        """
        sync_time = datetime.now().isoformat()
        
        row = [
            player_id,
            player_name,
            game_data.get('date', ''),
            game_data.get('opponent', ''),
            game_data.get('pts', 0),
            game_data.get('reb', 0),
            game_data.get('ast', 0),
            game_data.get('min', 0),
            sync_time,
            source
        ]
        
        with open(self.game_logs_path, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(row)
        
        print(f"[LOOM] Appended game log: {player_name} on {game_data.get('date')}")
        return True
    
    def get_player_last_game(self, player_id):
        """
        Get the most recent game date for a player from storage.
        Returns None if player not found.
        """
        if not self.game_logs_path.exists():
            return None
        
        last_game = None
        with open(self.game_logs_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['player_id'] == str(player_id):
                    if not last_game or row['game_date'] > last_game:
                        last_game = row['game_date']
        
        return last_game
    
    def update_sync_metadata(self, sync_type, result):
        """
        Update metadata file with sync results.
        Tracks when last sync occurred and results.
        """
        metadata = {}
        if self.metadata_path.exists():
            with open(self.metadata_path, 'r') as f:
                metadata = json.load(f)
        
        if 'sync_history' not in metadata:
            metadata['sync_history'] = []
        
        metadata['sync_history'].append({
            "timestamp": datetime.now().isoformat(),
            "type": sync_type,
            "result": result
        })
        
        # Keep only last 50 sync records
        metadata['sync_history'] = metadata['sync_history'][-50:]
        
        with open(self.metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"[LOOM] Updated sync metadata: {sync_type}")
    
    def export_for_kaggle(self, output_path=None):
        """
        Export current data in Kaggle-ready format.
        Returns path to exported file.
        """
        if output_path is None:
            output_path = self.data_dir / f"kaggle_export_{datetime.now().strftime('%Y%m%d')}.csv"
        
        # Copy current game_logs.csv to export location
        import shutil
        shutil.copy(self.game_logs_path, output_path)
        
        print(f"[LOOM] Exported Kaggle dataset to {output_path}")
        return str(output_path)
