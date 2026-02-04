"""
NBA Injuries Package Fetcher
=============================
Option 2: FREE official NBA injury data using nbainjuries package.
"""
import sys
import logging
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))

logger = logging.getLogger(__name__)

try:
    from nbainjuries import get_injuries
    HAS_NBAINJURIES = True
except ImportError:
    HAS_NBAINJURIES = False
    logger.warning("nbainjuries not installed. Run: pip install nbainjuries")

from services.automated_injury_worker import get_injury_worker


class NBAInjuriesFetcher:
    """FREE fetcher using official NBA injury reports"""
    
    def __init__(self):
        if not HAS_NBAINJURIES:
            raise ImportError("nbainjuries package required")
        self.worker = get_injury_worker()
    
    def fetch_and_sync(self):
        """Fetch latest injuries from NBA and sync to database"""
        print("\n🔄 Fetching from NBA official injury reports...")
        
        try:
            # Get all current injuries
            injuries_df = get_injuries()
            
            print(f"✅ Retrieved {len(injuries_df)} injury reports")
            
            # Sync to database
            synced = 0
            for _, row in injuries_df.iterrows():
                try:
                    # Extract data
                    player_name = row.get('Player', '')
                    team = row.get('Team', '')
                    status = row.get('Status', 'QUESTIONABLE')
                    injury_desc = row.get('Injury', '')
                    
                    # Need player ID - skip if not in our database
                    # In production, you'd lookup player_id from player_name
                    player_id = row.get('player_id', '0')  # Placeholder
                    
                    if player_name and team:
                        self.worker.mark_injured(
                            player_id=player_id,
                            player_name=player_name,
                            team=team,
                            status=status.upper(),
                            injury_desc=injury_desc
                        )
                        synced += 1
                        
                except Exception as e:
                    logger.error(f"Failed to sync {row.get('Player', 'unknown')}: {e}")
            
            print(f"✅ Synced {synced} injuries to database")
            return synced
            
        except Exception as e:
            logger.error(f"Failed to fetch injuries: {e}")
            return 0
    
    def get_todays_injuries(self):
        """Get current injuries as list"""
        try:
            injuries_df = get_injuries()
            return injuries_df.to_dict('records')
        except Exception as e:
            logger.error(f"Failed to fetch: {e}")
            return []


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    print("="*70)
    print("NBA INJURIES PACKAGE FETCHER - FREE OFFICIAL DATA")
    print("="*70)
    
    if not HAS_NBAINJURIES:
        print("\n❌ nbainjuries package not installed!")
        print("   Run: pip install nbainjuries")
        exit(1)
    
    fetcher = NBAInjuriesFetcher()
    
    # Fetch current injuries
    print("\n📊 Current NBA Injuries:")
    injuries = fetcher.get_todays_injuries()
    
    if injuries:
        print(f"\nFound {len(injuries)} total injuries across NBA\n")
        
        # Show first 10
        for i, inj in enumerate(injuries[:10]):
            print(f"{i+1}. {inj.get('Player', 'Unknown')} ({inj.get('Team', 'N/A')})")
            print(f"   Status: {inj.get('Status', 'Unknown')}")
            print(f"   Injury: {inj.get('Injury', 'Not specified')}")
            print()
        
        if len(injuries) > 10:
            print(f"... and {len(injuries) - 10} more")
    else:
        print("\n⚠️  No injuries fetched (package may need update or NBA site changed)")
    
    print("\n" + "="*70)
    print("✅ TEST COMPLETE")
    print("="*70)
