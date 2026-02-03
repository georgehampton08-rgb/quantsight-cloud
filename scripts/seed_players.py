"""
Seed Players Table with Active NBA Roster
Uses NBA API to fetch current rosters for all 30 teams
"""
import os
import logging
import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
DB_URL = os.getenv('DATABASE_URL', 'postgresql://quantsight:QuantSight2026!@/nba_data?host=/cloudsql/quantsight-prod:us-central1:quantsight-db')
if DB_URL.startswith('postgres://'):
    DB_URL = DB_URL.replace('postgres://', 'postgresql://', 1)

engine = create_engine(DB_URL, pool_pre_ping=True)
Session = sessionmaker(bind=engine)


def fetch_team_roster(team_id):
    """Fetch roster from NBA stats API"""
    url = f"https://stats.nba.com/stats/commonteamroster?Season=2024-25&TeamID={team_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://www.nba.com/',
        'Origin': 'https://www.nba.com'
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        
        # Parse response
        headers_list = data['resultSets'][0]['headers']
        rows = data['resultSets'][0]['rowSet']
        
        # Find column indices
        player_id_idx = headers_list.index('PLAYER_ID')
        name_idx = headers_list.index('PLAYER')
        position_idx = headers_list.index('POSITION')
        
        players = []
        for row in rows:
            players.append({
                'player_id': row[player_id_idx],
                'name': row[name_idx],
                'position': row[position_idx] or 'G'
            })
        
        return players
    except Exception as e:
        logger.error(f"Error fetching roster for team {team_id}: {e}")
        return []


def seed_players():
    """Seed all active NBA players from all 30 teams"""
    session = Session()
    
    try:
        # Get all team IDs
        result = session.execute(text("SELECT team_id, abbreviation, full_name FROM teams ORDER BY full_name"))
        teams = [(row[0], row[1], row[2]) for row in result]
        
        logger.info(f"Found {len(teams)} teams to process")
        
        total_players = 0
        
        for team_id, abbr, full_name in teams:
            logger.info(f"Fetching roster for {full_name} ({abbr})...")
            
            players = fetch_team_roster(team_id)
            
            if not players:
                logger.warning(f"  No players found for {abbr}")
                continue
            
            # Insert players
            for player in players:
                try:
                    session.execute(text("""
                        INSERT INTO players (player_id, name, position, team_abbreviation)
                        VALUES (:player_id, :name, :position, :team_abbr)
                        ON CONFLICT (player_id) DO UPDATE
                        SET name = EXCLUDED.name,
                            position = EXCLUDED.position,
                            team_abbreviation = EXCLUDED.team_abbreviation
                    """), {
                        'player_id': player['player_id'],
                        'name': player['name'],
                        'position': player['position'],
                        'team_abbr': abbr
                    })
                    total_players += 1
                except Exception as e:
                    logger.error(f"  Error inserting {player['name']}: {e}")
            
            session.commit()
            logger.info(f"  ✓ Added {len(players)} players from {abbr}")
        
        logger.info(f"\n✅ Seeding complete! Total players: {total_players}")
        
        # Verify count
        count_result = session.execute(text("SELECT COUNT(*) FROM players"))
        final_count = count_result.scalar()
        logger.info(f"Players in database: {final_count}")
        
    except Exception as e:
        logger.error(f"Error seeding players: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    logger.info("Starting player seeding...")
    seed_players()
