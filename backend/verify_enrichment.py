"""Verify headshot enrichment results"""
import sqlite3
from pathlib import Path

db_path = Path(__file__).parent / 'data' / 'nba_data.db'
conn = sqlite3.connect(str(db_path))
c = conn.cursor()

# Count players with NBA CDN headshots
c.execute("SELECT COUNT(*) FROM players WHERE headshot_url LIKE '%cdn.nba.com%'")
nba_headshots = c.fetchone()[0]

# Count players with fallback avatars
c.execute("SELECT COUNT(*) FROM players WHERE avatar LIKE '%ui-avatars.com%'")
fallback_avatars = c.fetchone()[0]

# Total players
c.execute("SELECT COUNT(*) FROM players")
total = c.fetchone()[0]

# Sample successful headshots
c.execute("""
    SELECT name, headshot_url 
    FROM players 
    WHERE headshot_url IS NOT NULL 
    LIMIT 10
""")
samples = c.fetchall()

conn.close()

print("=" * 80)
print("HEADSHOT ENRICHMENT VERIFICATION")
print("=" * 80)
print(f"\nTotal players in database: {total}")
print(f"NBA CDN headshots: {nba_headshots} ({nba_headshots/total*100:.1f}%)")
print(f"Fallback avatars: {fallback_avatars} ({fallback_avatars/total*100:.1f}%)")

print(f"\nSample successful headshots:")
for name, url in samples[:5]:
    print(f"  • {name}: {url}")

print(f"\n{'✓' if nba_headshots > 600 else '✗'} Success: {nba_headshots}/1339 players have NBA headshots")
