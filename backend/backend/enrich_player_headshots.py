"""
Headshot URL Enrichment Script
Updates player profiles with NBA CDN headshot URLs.
This only needs to run ONCE - URLs are cached in the database.
"""

import sqlite3
import requests
from pathlib import Path
from typing import Optional

def get_nba_db():
    """Get connection to the NBA database"""
    db_path = Path(__file__).parent / 'data' / 'nba_data.db'
    return sqlite3.connect(str(db_path))

def verify_headshot_url(player_id: str) -> Optional[str]:
    """
    Verify if NBA CDN has a headshot for this player.
    Returns the URL if available, None if not found.
    """
    url = f"https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"
    
    try:
        response = requests.head(url, timeout=3, allow_redirects=True)
        if response.status_code == 200:
            return url
    except:
        pass
    
    return None

def get_fallback_avatar(name: str) -> str:
    """Generate fallback UI avatar URL"""
    import urllib.parse
    safe_name = urllib.parse.quote(name)
    return f"https://ui-avatars.com/api/?name={safe_name}&background=1e293b&color=10b981&size=256&bold=true"

def enrich_player_headshots(batch_size: int = 100, max_players: Optional[int] = None):
    """
    Enrich player profiles with headshot URLs.
    This updates the database so future requests use cached URLs.
    
    Args:
        batch_size: How many players to process at once
        max_players: Limit total players (for testing)
    """
    conn = get_nba_db()
    cursor = conn.cursor()
    
    # Get players that need headshot URLs
    # We check if avatar is NULL or is a ui-avatars URL (generic)
    query = """
        SELECT player_id, name 
        FROM players 
        WHERE avatar IS NULL OR avatar LIKE '%ui-avatars.com%'
    """
    if max_players:
        query += f" LIMIT {max_players}"
    
    cursor.execute(query)
    players = cursor.fetchall()
    
    print(f"[ENRICHMENT] Found {len(players)} players to enrich")
    
    success_count = 0
    fallback_count = 0
    
    for i, (player_id, name) in enumerate(players):
        if i % 10 == 0:
            print(f"[PROGRESS] {i}/{len(players)} players processed...")
        
        # Try NBA CDN first
        headshot_url = verify_headshot_url(player_id)
        
        if headshot_url:
            avatar_url = headshot_url
            success_count += 1
        else:
            # Fallback to generic avatar
            avatar_url = get_fallback_avatar(name)
            fallback_count += 1
        
        # Update database with cached URL
        cursor.execute("""
            UPDATE players 
            SET avatar = ?, headshot_url = ?
            WHERE player_id = ?
        """, (avatar_url, headshot_url, player_id))
    
    # Commit all changes
    conn.commit()
    conn.close()
    
    print(f"\n[COMPLETE] Enrichment finished!")
    print(f"  NBA CDN headshots: {success_count}")
    print(f"  Fallback avatars: {fallback_count}")
    print(f"  Total updated: {len(players)}")
    print(f"\n[NOTE] These URLs are now cached in the database.")
    print(f"       No need to re-run this script unless adding new players.")

if __name__ == "__main__":
    # Enrich ALL active players
    print("Enriching all active players with NBA headshots...\n")
    enrich_player_headshots()  # No limit - process all players
