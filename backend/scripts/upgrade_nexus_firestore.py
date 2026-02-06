"""
Upgrade Script: Convert Nexus to Firestore
Upgrades nexus/routes.py from in-memory storage to Firestore persistence
"""
from pathlib import Path

FIRESTORE_NEXUS_CODE = '''from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio
from firestore_db import get_firestore_db

router = APIRouter(prefix="/nexus", tags=["nexus"])

def get_cooldowns_collection():
    """Get Firestore cooldowns collection"""
    db = get_firestore_db()
    return db.collection('nexus_cooldowns')

@router.get("/health")
async def get_nexus_health():
    """Check Nexus service health status"""
    try:
        collection = get_cooldowns_collection()
        # Count active cooldowns
        now = datetime.utcnow()
        all_docs = collection.stream()
        
        active_count = 0
        total_count = 0
        
        for doc in all_docs:
            total_count += 1
            data = doc.to_dict()
            expires_at = data.get('expires_at')
            if expires_at and expires_at.timestamp() > now.timestamp():
                active_count += 1
        
        return {
            "status": "healthy",
            "service": "nexus",
            "version": "2.0.0",
            "timestamp": now.isoformat() + "Z",
            "active_cooldowns": active_count,
            "total_cooldowns": total_count,
            "storage": "firestore"
        }
    except Exception as e:
        return {
            "status": "degraded",
            "service": "nexus",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

@router.get("/cooldowns")
async def get_cooldowns(
    active_only: bool = Query(True, description="Return only active cooldowns")
):
    """Get all cooldowns with their expiration times"""
    collection = get_cooldowns_collection()
    now = datetime.utcnow()
    
    cooldowns = {}
    
    for doc in collection.stream():
        data = doc.to_dict()
        expires_at = data.get('expires_at')
        
        if not expires_at:
            continue
        
        seconds_remaining = max(0, int((expires_at.timestamp() - now.timestamp())))
        is_active = expires_at.timestamp() > now.timestamp()
        
        if active_only and not is_active:
            continue
        
        cooldowns[doc.id] = {
            "expires_at": expires_at.isoformat() + "Z",
            "seconds_remaining": seconds_remaining,
            "expired": not is_active
        }
    
    return {
        "cooldowns": cooldowns,
        "count": len(cooldowns),
        "active_only": active_only
    }

@router.post("/cooldowns/{key}")
async def set_cooldown(
    key: str,
    duration_seconds: int = Query(..., ge=1, le=86400, description="Duration in seconds (1-86400)")
):
    """Set or update a cooldown for a specific key"""
    collection = get_cooldowns_collection()
    expires_at = datetime.utcnow() + timedelta(seconds=duration_seconds)
    
    # Store in Firestore
    doc_ref = collection.document(key)
    doc_ref.set({
        'key': key,
        'expires_at': expires_at,
        'created_at': datetime.utcnow(),
        'duration_seconds': duration_seconds
    })
    
    return {
        "status": "success",
        "key": key,
        "duration_seconds": duration_seconds,
        "expires_at": expires_at.isoformat() + "Z",
        "message": f"Cooldown set for {key}",
        "storage": "firestore"
    }

@router.delete("/cooldowns/{key}")
async def clear_cooldown(key: str):
    """Clear/remove a specific cooldown"""
    collection = get_cooldowns_collection()
    doc_ref = collection.document(key)
    
    # Check if exists
    doc = doc_ref.get()
    if not doc.exists:
        raise HTTPException(status_code=404, detail=f"No cooldown found for key: {key}")
    
    # Delete from Firestore
    doc_ref.delete()
    
    return {
        "status": "success",
        "key": key,
        "message": f"Cooldown cleared for {key}"
    }

@router.get("/cooldowns/{key}")
async def check_cooldown(key: str):
    """Check if a specific cooldown is active"""
    collection = get_cooldowns_collection()
    doc_ref = collection.document(key)
    doc = doc_ref.get()
    
    if not doc.exists:
        return {
            "key": key,
            "active": False,
            "message": "No cooldown set"
        }
    
    data = doc.to_dict()
    now = datetime.utcnow()
    expires_at = data.get('expires_at')
    
    if not expires_at or expires_at.timestamp() <= now.timestamp():
        # Cleanup expired cooldown
        doc_ref.delete()
        return {
            "key": key,
            "active": False,
            "message": "Cooldown expired"
        }
    
    return {
        "key": key,
        "active": True,
        "expires_at": expires_at.isoformat() + "Z",
        "seconds_remaining": int((expires_at.timestamp() - now.timestamp()))
    }
'''

def upgrade_nexus_to_firestore():
    """Replace in-memory Nexus with Firestore version"""
    nexus_file = Path(__file__).parent.parent / "nexus" / "routes.py"
    
    if not nexus_file.exists():
        print("❌ nexus/routes.py not found")
        return
    
    # Backup original
    backup_file = nexus_file.with_suffix('.py.bak')
    with open(nexus_file, 'r') as f:
        original_content = f.read()
    
    with open(backup_file, 'w') as f:
        f.write(original_content)
    
    print(f"✅ Backed up to {backup_file.name}")
    
    # Write Firestore version
    with open(nexus_file, 'w') as f:
        f.write(FIRESTORE_NEXUS_CODE)
    
    print("✅ Upgraded to Firestore storage")
    print("ℹ️  Changes:")
    print("   - In-memory dict → Firestore collection 'nexus_cooldowns'")
    print("   - Persistent across container restarts")
    print("   - Shared across all Cloud Run instances")
    print("   - No additional configuration needed (uses existing Firestore)")

if __name__ == "__main__":
    print("🔧 Upgrading Nexus to Firestore...")
    upgrade_nexus_to_firestore()
    print("✅ Upgrade complete!")
