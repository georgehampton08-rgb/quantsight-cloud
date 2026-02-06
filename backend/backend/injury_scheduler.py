"""
Injury Report Scheduler
=======================
Runs 3x daily:
- 8:00 AM: Morning sync
- 5:00 PM: Pre-game sync (2hrs before typical 7PM games)
- 11:00 PM: Night sync

Usage with Task Scheduler (Windows):
  schtasks /create /tn "NBA Injury Morning" /tr "python injury_scheduler.py morning" /sc daily /st 08:00
  schtasks /create /tn "NBA Injury PreGame" /tr "python injury_scheduler.py pregame" /sc daily /st 17:00
  schtasks /create /tn "NBA Injury Night" /tr "python injury_scheduler.py night" /sc daily /st 23:00

Usage with cron (Linux):
  0 8 * * * cd /path/to/backend && python injury_scheduler.py morning
  0 17 * * * cd /path/to/backend && python injury_scheduler.py pregame
  0 23 * * * cd /path/to/backend && python injury_scheduler.py night
"""
import sys
from pathlib import Path
import logging
from datetime import datetime

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from services.injury_manager import get_injury_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/injury_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def run_sync(sync_type: str):
    """
    Run injury report sync.
    
    Since we're using manual tracking, this mainly:
    1. Logs the sync event
    2. Cleans up old injury records
    3. Provides hook for future API integration
    """
    logger.info(f"=" * 60)
    logger.info(f"INJURY SYNC: {sync_type.upper()}")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"=" * 60)
    
    mgr = get_injury_manager()
    
    # Get current injuries
    injuries = mgr.get_all_injuries()
    logger.info(f"📋 Current injuries: {len(injuries)}")
    
    for inj in injuries:
        logger.info(f"   [{inj['team_abbr']}] {inj['player_name']}: {inj['status']} - {inj['injury_desc']}")
    
    # Cleanup old records (>30 days)
    if sync_type == 'night':
        deleted = mgr.cleanup_old_injuries(days=30)
        if deleted > 0:
            logger.info(f"🧹 Cleaned {deleted} stale injury records")
    
    # Log sync
    mgr.log_sync(
        sync_type=sync_type,
        players_checked=0,  # Manual tracking - no API check
        injuries_found=len(injuries)
    )
    
    logger.info(f"✅ {sync_type.capitalize()} sync complete")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python injury_scheduler.py <morning|pregame|night>")
        sys.exit(1)
    
    sync_type = sys.argv[1].lower()
    
    if sync_type not in ['morning', 'pregame', 'night']:
        print(f"Invalid sync type: {sync_type}")
        print("Must be one of: morning, pregame, night")
        sys.exit(1)
    
    run_sync(sync_type)
