"""
Cloud Admin Routes - Firestore Database Initialization & Data Seeding
====================================================================
Protected endpoints for database management (call once per environment).

Feature flags used:
  FEATURE_SEED_ADMIN — gates /admin/seed/* endpoints (default: false in cloud)
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException

from firestore_db import (
    get_firestore_db,
    batch_write_teams,
    batch_write_players,
    batch_write_collection
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
async def admin_status():
    """
    Quick admin status check - works without Firestore.
    Now surfaces feature flag states for observability.
    """
    try:
        from vanguard.core.feature_flags import flag_defaults
        flags = flag_defaults()
    except ImportError:
        flags = {}
    return {
        "status": "admin_routes_active",
        "timestamp": datetime.utcnow().isoformat(),
        "feature_flags": flags,
        "endpoints_available": [
            "/admin/status",
            "/admin/init-collections",
            "/admin/collections/status",
            "/admin/seed/sample-data (requires FEATURE_SEED_ADMIN=true)",
            "/admin/seed/all-teams"
        ]
    }


@router.post("/init-collections")
async def initialize_collections():
    """
    Initialize Firestore collections (idempotent operation)
    """
    try:
        db = get_firestore_db()
        
        # Check if collections exist
        collections = ['teams', 'players', 'player_stats', 'game_logs', 'team_stats']
        existing = []
        
        for coll_name in collections:
            coll_ref = db.collection(coll_name)
            docs = list(coll_ref.limit(1).stream())
            if docs:
                existing.append(coll_name)
        
        return {
            "message": "Firestore collections initialized",
            "collections": collections,
            "already_exists": existing,
            "note": "Collections are created automatically when documents are added"
        }
        
    except Exception as e:
        logger.error(f"Error initializing collections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collections/status")
async def get_collections_status():
    """Get status of all Firestore collections"""
    try:
        db = get_firestore_db()
        
        collections = {
            'teams': 0,
            'players': 0,
            'player_stats': 0,
            'game_logs': 0,
            'team_stats': 0
        }
        
        for coll_name in collections.keys():
            coll_ref = db.collection(coll_name)
            # Get count (expensive operation, but okay for admin endpoint)
            docs = list(coll_ref.stream())
            collections[coll_name] = len(docs)
        
        return {
            "status": "success",
            "collections": collections,
            "total_documents": sum(collections.values())
        }
        
    except Exception as e:
        logger.error(f"Error checking collections status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed/sample-data")
async def seed_sample_data(
    _confirmed: bool = False  # kept for backward compat; flag is the real guard
):
    """
    Seed Firestore with sample data (for testing).

    Requires FEATURE_SEED_ADMIN=true. Returns 403 in cloud unless explicitly enabled.
    """
    from vanguard.core.feature_flags import flag, forbidden_response
    if not flag("FEATURE_SEED_ADMIN"):
        raise HTTPException(
            status_code=403,
            detail=forbidden_response(
                "Seed endpoint is disabled in this environment. Set FEATURE_SEED_ADMIN=true to enable.",
                "FEATURE_SEED_ADMIN"
            )
        )
    try:
        sample_team = {
            "abbreviation": "LAL",
            "full_name": "Los Angeles Lakers",
            "city": "Los Angeles",
            "state": "California",
            "year_founded": 1946,
            "championship_titles": 17,
            "last_updated": datetime.utcnow()
        }
        
        sample_player = {
            "player_id": "2544",
            "player_name": "LeBron James",
            "team_abbreviation": "LAL",
            "team_name": "Los Angeles Lakers",
            "position": "F",
            "jersey_number": "23",
            "height": "6-9",
            "weight": "250",
            "is_active": True,
            "season": "2024-25",
            "last_updated": datetime.utcnow()
        }
        
        batch_write_teams([sample_team])
        batch_write_players([sample_player])
        
        return {
            "status": "success",
            "message": "Sample data seeded",
            "teams": 1,
            "players": 1
        }
        
    except Exception as e:
        logger.error(f"Error seeding sample data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/collections/{collection_name}/clear")
async def clear_collection(collection_name: str):
    """
    Clear all documents from a collection
    ⚠️ DANGEROUS - Use with caution
    """
    try:
        db = get_firestore_db()
        coll_ref = db.collection(collection_name)
        
        # Delete in batches
        batch_size = 500
        docs = coll_ref.limit(batch_size).stream()
        deleted = 0
        
        while True:
            batch = db.batch()
            docs_list = list(docs)
            
            if not docs_list:
                break
            
            for doc in docs_list:
                batch.delete(doc.reference)
                deleted += 1
            
            batch.commit()
            
            # Get next batch
            docs = coll_ref.limit(batch_size).stream()
        
        return {
            "status": "success",
            "collection": collection_name,
            "deleted": deleted
        }
        
    except Exception as e:
        logger.error(f"Error clearing collection {collection_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
