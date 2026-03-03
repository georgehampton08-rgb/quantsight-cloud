"""
Cloud Admin Routes - Firestore Database Initialization & Data Seeding
====================================================================
Protected endpoints for database management (call once per environment).
"""
import os
import logging
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, Request
from api.validators import safe_collection
from api.auth_middleware import require_admin_role

from firestore_db import (
    get_firestore_db,
    batch_write_teams,
    batch_write_players,
    batch_write_collection
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/status")
async def admin_status(admin: dict = Depends(require_admin_role)):
    """
    Quick admin status check - works without Firestore
    """
    return {
        "status": "admin_routes_active",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints_available": [
            "/admin/status",
            "/admin/cache/purge",
            "/admin/init-collections",
            "/admin/collections/status",
            "/admin/seed/sample-data",
            "/admin/baselines/populate",
            "/admin/baselines/status",
        ]
    }


@router.post("/cache/purge")
async def purge_cache(request: Request, admin: dict = Depends(require_admin_role)):
    """
    Purge server-side in-memory caches (rate limiter buckets, NBA API response cache).
    Does NOT touch Firestore data. Safe to re-run — idempotent.
    Auth guard (require_admin_role) added in Phase 3.
    """
    purged = []

    # Clear in-process rate limiter sliding window buckets
    try:
        from vanguard.middleware.rate_limiter import _MEMORY_BUCKETS
        count = len(_MEMORY_BUCKETS)
        _MEMORY_BUCKETS.clear()
        purged.append(f"rate_limiter_buckets: {count} IP buckets cleared")
    except Exception as e:
        purged.append(f"rate_limiter: skipped ({type(e).__name__}: {e})")

    # Clear pulse producer cache if available
    try:
        from services.live_pulse_service_cloud import get_pulse_cache
        cache = get_pulse_cache()
        if cache and hasattr(cache, '_game_data'):
            size = len(cache._game_data)
            cache._game_data.clear()
            purged.append(f"pulse_cache: {size} entries cleared")
    except Exception as e:
        purged.append(f"pulse_cache: skipped ({type(e).__name__})")

    logger.info(f"[ADMIN] Cache purge executed. Results: {purged}")
    return {
        "status": "ok",
        "message": f"Cache purged. {len(purged)} components processed.",
        "detail": purged,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.post("/baselines/populate")
async def populate_baselines(admin: dict = Depends(require_admin_role)):
    """
    Populate season baselines from NBA API → Firestore.
    Fetches player season averages + team defense/pace.
    Takes 15-30s due to NBA API rate limits.
    """
    try:
        from services.baseline_populator import populate_all_baselines
        result = await populate_all_baselines()
        return result
    except ImportError as e:
        raise HTTPException(status_code=500, detail=f"Populator not available: {e}")
    except Exception as e:
        logger.error(f"Baseline population failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/baselines/status")
async def baselines_status(admin: dict = Depends(require_admin_role)):
    """
    Get current season baseline cache status.
    """
    try:
        from services.season_baseline_service import get_baseline_status
        return get_baseline_status()
    except ImportError:
        return {"status": "service_not_available"}


@router.post("/init-collections")
async def initialize_collections(admin: dict = Depends(require_admin_role)):
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
async def seed_sample_data():
    """
    Seed Firestore with sample data (for testing)
    """
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
    # Validate: only allowlisted collections can be cleared
    safe_collection(collection_name)
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
