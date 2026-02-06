"""Check and update database schema for headshot caching"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / 'data' / 'nba_data.db'
conn = sqlite3.connect(str(db_path))
c = conn.cursor()

# Check if headshot_url column exists
c.execute("PRAGMA table_info(players)")
columns = [col[1] for col in c.fetchall()]

print(f"Current columns in players table: {columns}\n")

if 'headshot_url' not in columns:
    print("Adding headshot_url column...")
    c.execute("ALTER TABLE players ADD COLUMN headshot_url TEXT")
    conn.commit()
    print("  [OK] Column added")
else:
    print("  [OK] headshot_url column already exists")

if 'avatar' not in columns:
    print("\nAdding avatar column...")
    c.execute("ALTER TABLE players ADD COLUMN avatar TEXT")
    conn.commit()
    print("  [OK] Column added")
else:
    print("  [OK] avatar column already exists")

conn.close()
print("\n[READY] Database schema ready for headshot caching")
