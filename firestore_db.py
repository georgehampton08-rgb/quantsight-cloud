"""
Firestore Database Helper
Provides connection and query functions for Firebase Firestore
"""
import os
import logging
from typing import List, Dict, Optional, Any
import firebase_admin
from firebase_admin import credentials, firestore
from google.cloud.firestore_v1.base_query import FieldFilter

logger = logging.getLogger(__name__)

# Initialize Firebase Admin SDK (singleton pattern)
_firestore_client = None

def get_firestore_db():
    """Get Firestore database client (singleton)"""
    global _firestore_client
    
    if _firestore_client is None:
        try:
            # Check if already initialized
            if not firebase_admin._apps:
                # Use Application Default Credentials in Cloud Run
                cred = credentials.ApplicationDefault()
                firebase_admin.initialize_app(cred)
            
            _firestore_client = firestore.client()
            logger.info("Firestore connection established")
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            raise
    
    return _firestore_client

# ================== TEAMS QUERIES ==================

def get_all_teams() -> List[Dict[str, Any]]:
    """Get all teams from Firestore"""
    db = get_firestore_db()
    teams_ref = db.collection('teams')
    docs = teams_ref.stream()
    
    teams = []
    for doc in docs:
        team_data = doc.to_dict()
        team_data['id'] = doc.id  # Add document ID
        teams.append(team_data)
    
    return teams

def get_team_by_tricode(tricode: str) -> Optional[Dict[str, Any]]:
    """Get single team by tricode (e.g., 'LAL')"""
    db = get_firestore_db()
    team_ref = db.collection('teams').document(tricode.upper())
    doc = team_ref.get()
    
    if doc.exists:
        team_data = doc.to_dict()
        team_data['id'] = doc.id
        return team_data
    return None

# ================== PLAYERS QUERIES ==================

def get_all_players(active_only: bool = False) -> List[Dict[str, Any]]:
    """
    Get all players from Firestore
    
    Args:
        active_only: If True, only return players with is_active=True
    """
    db = get_firestore_db()
    players_ref = db.collection('players')
    
    if active_only:
        # Filter for active players only
        query = players_ref.where(filter=FieldFilter('is_active', '==', True))
        docs = query.stream()
    else:
        docs = players_ref.stream()
    
    players = []
    for doc in docs:
        player_data = doc.to_dict()
        player_data['id'] = doc.id
        players.append(player_data)
    
    return players

def get_player_by_id(player_id: str) -> Optional[Dict[str, Any]]:
    """Get single player by ID"""
    db = get_firestore_db()
    player_ref = db.collection('players').document(str(player_id))
    doc = player_ref.get()
    
    if doc.exists:
        player_data = doc.to_dict()
        player_data['id'] = doc.id
        return player_data
    return None

def get_players_by_team(team_abbr: str, active_only: bool = True) -> List[Dict[str, Any]]:
    """Get all players for a specific team"""
    db = get_firestore_db()
    players_ref = db.collection('players')
    
    # Build query with filters
    query = players_ref.where(filter=FieldFilter('team_abbreviation', '==', team_abbr.upper()))
    
    if active_only:
        query = query.where(filter=FieldFilter('is_active', '==', True))
    
    docs = query.stream()
    
    players = []
    for doc in docs:
        player_data = doc.to_dict()
        player_data['id'] = doc.id
        players.append(player_data)
    
    return players

# ================== STATS QUERIES ==================

def get_player_stats(player_id: str) -> Optional[Dict[str, Any]]:
    """Get player stats"""
    db = get_firestore_db()
    stats_ref = db.collection('player_stats').document(str(player_id))
    doc = stats_ref.get()
    
    if doc.exists:
        return doc.to_dict()
    return None

def get_team_stats(team_id: str) -> Optional[Dict[str, Any]]:
    """Get team stats"""
    db = get_firestore_db()
    stats_ref = db.collection('team_stats').document(team_id.upper())
    doc = stats_ref.get()
    
    if doc.exists:
        return doc.to_dict()
    return None

# ================== GAME LOGS QUERIES ==================

def get_player_game_logs(player_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent game logs for a player"""
    db = get_firestore_db()
    logs_ref = db.collection('game_logs')
    
    # Query game logs for this player
    query = logs_ref.where(filter=FieldFilter('player_id', '==', str(player_id))).limit(limit)
    docs = query.stream()
    
    logs = []
    for doc in docs:
        log_data = doc.to_dict()
        log_data['id'] = doc.id
        logs.append(log_data)
    
    return logs

# ================== WRITE OPERATIONS (Admin only) ==================

def batch_write_teams(teams: List[Dict[str, Any]]):
    """Batch write teams to Firestore"""
    db = get_firestore_db()
    batch = db.batch()
    
    for team in teams:
        team_id = team.get('abbreviation', team.get('tricode', team.get('id')))
        team_ref = db.collection('teams').document(team_id.upper())
        batch.set(team_ref, team)
    
    batch.commit()
    logger.info(f"✅ Batch wrote {len(teams)} teams")

def batch_write_players(players: List[Dict[str, Any]]):
    """Batch write players to Firestore (max 500 at a time)"""
    db = get_firestore_db()
    
    # Firestore batch limit is 500 operations
    batch_size = 500
    for i in range(0, len(players), batch_size):
        batch = db.batch()
        batch_players = players[i:i + batch_size]
        
        for player in batch_players:
            player_id = str(player.get('player_id', player.get('id')))
            player_ref = db.collection('players').document(player_id)
            batch.set(player_ref, player)
        
        batch.commit()
        logger.info(f"✅ Batch wrote {len(batch_players)} players ({i+1}-{i+len(batch_players)})")

def batch_write_collection(collection_name: str, documents: List[Dict[str, Any]], id_field: str = 'id'):
    """Generic batch write for any collection"""
    db = get_firestore_db()
    
    batch_size = 500
    for i in range(0, len(documents), batch_size):
        batch = db.batch()
        batch_docs = documents[i:i + batch_size]
        
        for doc_data in batch_docs:
            doc_id = str(doc_data.get(id_field))
            doc_ref = db.collection(collection_name).document(doc_id)
            batch.set(doc_ref, doc_data)
        
        batch.commit()
        logger.info(f"✅ Batch wrote {len(batch_docs)} {collection_name} ({i+1}-{i+len(batch_docs)})")
