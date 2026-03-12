import os
import sys
# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.data.repository import SQLiteRepository

def test_repo():
    db_path = "./data/mock_test_db.db"
    if not os.path.exists("./data"):
        os.makedirs("./data")
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS players (player_id TEXT PRIMARY KEY, name TEXT)")
    conn.execute("INSERT OR IGNORE INTO players (player_id, name) VALUES ('test_id', 'Test Player')")
    conn.commit()
    conn.close()

    repo = SQLiteRepository(db_path)
    player = repo.get_player_stats("test_id")
    assert player is not None, "Failed to retrieve player from repository"
    assert player["name"] == "Test Player", "Player content mismatch"
    print("Phase 3 Tests Passed.")

if __name__ == "__main__":
    test_repo()
