"""
H2H Data Generation - Complete (All Active Players)
===================================================
Simplified version that uses the cloud API for player data and Firestore for H2H storage.
Fetches head-to-head matchup data for ALL active players.
"""
import requests
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

#Cloud API base URL
CLOUD_API = "https://quantsight-cloud-458498663186.us-central1.run.app"

# Import services after path setup
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.h2h_fetcher import get_h2h_fetcher

def get_active_players():
    """Fetch active players from cloud API"""
    try:
        url = f"{CLOUD_API}/players?is_active=true"
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            players = response.json()
            logger.info(f"✅ Fetched {len(players)} active players from API")
            return players
        else:
            logger.error(f"❌ API returned {response.status_code}")
            return []
    except Exception as e:
        logger.error(f"❌ Failed to fetch players: {e}")
        return []

def main():
    """Generate H2H data for all active players"""
    print("="*80)
    print("🚀 H2H DATA GENERATION - ALL ACTIVE PLAYERS")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Initialize H2H fetcher
    fetcher = get_h2h_fetcher()
    logger.info("✅ H2H Fetcher initialized\n")
    
    # Get all active players
    all_players = get_active_players()
    if not all_players:
        logger.error("No players found. Exiting.")
        return
    
    # Get unique teams
    all_teams = sorted(list(set(
        p.get('team_abbreviation') or p.get('team_id', '') 
        for p in all_players 
        if p.get('team_abbreviation') or p.get('team_id')
   )))
    logger.info(f"🏀 Found {len(all_teams)} NBA teams\n")
    
    # Track stats
    total_combinations = len(all_players) * (len(all_teams) - 1)  # Excluding own team
    fetched = 0
    skipped = 0
    errors = 0
    start_time = time.time()
    
    print(f"📊 Processing {len(all_players)} players vs {len(all_teams)} teams")
    print(f"   Total combinations: ~{total_combinations}\n")
    
    for i, player in enumerate(all_players, 1):
        player_id = str(player.get('player_id') or player.get('id'))
        player_name = player.get('name', 'Unknown')
        player_team = (player.get('team_abbreviation') or player.get('team_id', '')).upper()
        
        logger.info(f"\n[{i}/{len(all_players)}] {player_name} ({player_team})")
        
        player_fetched = 0
        player_errors = 0
        
        for opponent in all_teams:
            if opponent.upper() == player_team:
                continue  # Skip own team
            
            try:
                result = fetcher.fetch_h2h(player_id, opponent)
                if result.get('success'):
                    games = result.get('games_found', 0)
                    if games > 0:
                        fetched += 1
                        player_fetched += 1
                        logger.info(f"  ✅ vs {opponent}: {games} games")
                    else:
                        skipped += 1
                else:
                    errors += 1
                    player_errors += 1
                    logger.warning(f"  ❌ vs {opponent}: {result.get('error', 'Unknown')}")
            except Exception as e:
                errors += 1
                player_errors += 1
                logger.error(f"  ❌ vs {opponent}: {e}")
            
            # Rate limiting
            time.sleep(0.6)
        
        # Progress summary
        elapsed = time.time() - start_time
        rate = i / elapsed if elapsed > 0 else 0
        remaining = (len(all_players) - i) / rate if rate > 0 else 0
        
        print(f"\n📈 Player Summary: {player_fetched} fetched | {player_errors} errors")
        print(f"🕐 Overall Progress: {i}/{len(all_players)} players")
        print(f"   Total H2H Records: {fetched} | Skipped: {skipped} | Errors: {errors}")
        print(f"   Rate: {rate*60:.1f} players/min | ETA: {remaining/60:.1f} min\n")
    
    # Final summary
    total_time = time.time() - start_time
    print("\n" + "="*80)
    print("🎉 H2H DATA GENERATION COMPLETE")
    print("="*80)
    print(f"Total runtime: {total_time/60:.1f} minutes ({total_time/3600:.2f} hours)")
    print(f"Players processed: {len(all_players)}")
    print(f"H2H records fetched: {fetched}")
    print(f"H2H records skipped (no games): {skipped}")
    print(f"Errors: {errors}")
    print(f"Success rate: {(fetched/(fetched+errors)*100):.1f}%" if (fetched+errors) > 0 else "N/A")
    print("="*80)
    print("\n✅ Check Firestore 'player_h2h' collection for results!")

if __name__ == "__main__":
    main()
