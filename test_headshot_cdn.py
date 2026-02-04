"""
Headshot CDN Test Script
Tests NBA.com CDN URLs for player headshots using real player data from the database.
"""

import sqlite3
import requests
from pathlib import Path

def get_nba_db():
    """Get connection to the NBA database"""
    db_path = Path(__file__).parent / 'data' / 'nba_data.db'
    return sqlite3.connect(str(db_path))

def test_headshot_urls():
    """Test various NBA CDN URL patterns with real player IDs"""
    
    print("=" * 80)
    print("NBA HEADSHOT CDN TEST")
    print("=" * 80)
    
    # Get some real players from database
    conn = get_nba_db()
    cursor = conn.cursor()
    
    # Get a sample of players (any players from database)
    cursor.execute("""
        SELECT player_id, name, team_id, position
        FROM players
        LIMIT 10
    """)

    
    players = cursor.fetchall()
    conn.close()
    
    if not players:
        print("X No players found in database!")
        print("\nMake sure the database is populated with player data.")
        return
    
    print(f"\n[TEST] Testing with {len(players)} sample players:\n")
    
    # Different CDN URL patterns to test
    cdn_patterns = [
        ("260x190", "https://cdn.nba.com/headshots/nba/latest/260x190/{player_id}.png"),
        ("1040x760", "https://cdn.nba.com/headshots/nba/latest/1040x760/{player_id}.png"),
        ("CDN Legacy", "https://ak-static.cms.nba.com/wp-content/uploads/headshots/nba/latest/260x190/{player_id}.png"),
    ]
    
    results = {pattern[0]: {"success": 0, "failed": 0, "examples": []} for pattern in cdn_patterns}
    
    for player_id, name, team_id, position in players:
        print(f"\n[PLAYER] {name} (ID: {player_id}, Team: {team_id}, Pos: {position})")
        print("-" * 80)
        
        for pattern_name, url_template in cdn_patterns:
            url = url_template.format(player_id=player_id)
            
            try:
                response = requests.head(url, timeout=5, allow_redirects=True)
                
                if response.status_code == 200:
                    print(f"  [OK]   {pattern_name:15} - SUCCESS: {url}")
                    results[pattern_name]["success"] += 1
                    if len(results[pattern_name]["examples"]) < 3:
                        results[pattern_name]["examples"].append({
                            "name": name,
                            "id": player_id,
                            "url": url
                        })
                else:
                    print(f"  [FAIL] {pattern_name:15} - FAILED ({response.status_code}): {url}")
                    results[pattern_name]["failed"] += 1
            except Exception as e:
                print(f"  [ERR]  {pattern_name:15} - ERROR: {str(e)[:50]}")
                results[pattern_name]["failed"] += 1
    
    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    
    for pattern_name, data in results.items():
        total = data["success"] + data["failed"]
        success_rate = (data["success"] / total * 100) if total > 0 else 0
        print(f"\n[PATTERN] {pattern_name}")
        print(f"   Success: {data['success']}/{total} ({success_rate:.1f}%)")
        
        if data["examples"]:
            print(f"   Working examples:")
            for ex in data["examples"]:
                print(f"     * {ex['name']}: {ex['url']}")
    
    # Recommendations
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    best_pattern = max(results.items(), key=lambda x: x[1]["success"])
    if best_pattern[1]["success"] > 0:
        print(f"\n[BEST] Best CDN pattern: {best_pattern[0]}")
        print(f"  Success rate: {best_pattern[1]['success']}/{len(players)}")
        
        # Find the URL template for this pattern
        for name, template in cdn_patterns:
            if name == best_pattern[0]:
                print(f"\n  Recommended URL template:")
                print(f"  {template}")
    else:
        print("\n[WARN] No CDN patterns were successful!")
        print("   Possible issues:")
        print("   1. Player IDs in database might not match NBA.com format")
        print("   2. Network connectivity issues")
        print("   3. CDN URL patterns may have changed")
    
    print("\n" + "=" * 80)
    print("NEXT STEPS")
    print("=" * 80)
    print("""
1. If CDN URLs work: Update backend avatar logic to use the best pattern
2. If CDN URLs fail: Check player ID format in database
3. Always implement fallback to generic avatars (ui-avatars.com)
4. Consider caching successful headshot URLs to reduce CDN requests
    """)

if __name__ == "__main__":
    test_headshot_urls()
