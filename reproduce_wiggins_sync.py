
import asyncio
import logging
import sys
from pathlib import Path

# Setup paths
current_dir = Path.cwd()
sys.path.append(str(current_dir))
sys.path.append(str(current_dir / "backend"))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_wiggins_sync():
    logger.info("--- Starting Wiggins Sync Test ---")
    
    player_id = "203952" # Andrew Wiggins
    
    # 1. Test NBA Connector directly
    from backend.services.nba_api_connector import NBAAPIConnector
    db_path = current_dir / "backend/data/nba_data.db"
    connector = NBAAPIConnector(str(db_path))
    
    logger.info(f"Testing direct fetch for {player_id}...")
    games = connector.get_player_game_logs(player_id)
    logger.info(f"Direct fetch result count: {len(games)}")
    if games:
        logger.info(f"Sample game: {games[0]}")
    else:
        logger.error("Direct fetch returned EMPTY list!")
        
    # 2. Test Delta Sync
    from backend.services.delta_sync import DeltaSyncManager
    data_dir = current_dir / "backend/data"
    sync_manager = DeltaSyncManager(data_dir=data_dir, nba_api=connector)
    
    logger.info(f"Testing DeltaSync for {player_id}...")
    # Clean up existing file to force fresh sync
    csv_path = data_dir / "players" / f"{player_id}_games.csv"
    if csv_path.exists():
        logger.info(f"Removing existing file: {csv_path}")
        csv_path.unlink()
        
    result = await sync_manager.sync_player(player_id)
    logger.info(f"DeltaSync result: {result}")
    
    # 3. Verify File
    if csv_path.exists():
        content = csv_path.read_text()
        lines = content.strip().split('\n')
        logger.info(f"File created. Line count: {len(lines)}")
        logger.info(f"Header: {lines[0]}")
        if len(lines) > 1:
            logger.info(f"First row: {lines[1]}")
    else:
        logger.error("File was NOT created!")

if __name__ == "__main__":
    asyncio.run(test_wiggins_sync())
