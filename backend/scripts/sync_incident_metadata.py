#!/usr/bin/env python3
"""
Sync Vanguard Incident Metadata
===============================
Resets the metadata counter to match the actual incident count in Firestore.

Usage: python sync_incident_metadata.py
"""
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Load env
from dotenv import load_dotenv
load_dotenv(backend_path.parent / '.env')

import firebase_admin
from firebase_admin import credentials, firestore

def sync_metadata():
    """Sync metadata with actual incident counts."""
    
    # Initialize Firebase if needed
    if not firebase_admin._apps:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
    
    print("=" * 60)
    print("VANGUARD INCIDENT METADATA SYNC")
    print("=" * 60)
    
    # Count actual incidents
    print("\n📊 Counting actual incidents in Firestore...")
    
    active_count = 0
    resolved_count = 0
    total_count = 0
    
    incidents = db.collection('vanguard_incidents').stream()
    for doc in incidents:
        total_count += 1
        data = doc.to_dict()
        status = data.get('status', 'active')
        if status == 'active':
            active_count += 1
        else:
            resolved_count += 1
        print(f"   {doc.id[:16]}... status={status}")
    
    print(f"\n📋 Actual counts:")
    print(f"   Total: {total_count}")
    print(f"   Active: {active_count}")
    print(f"   Resolved: {resolved_count}")
    
    # Get current metadata
    meta_ref = db.collection('vanguard_metadata').document('global')
    meta_doc = meta_ref.get()
    
    if meta_doc.exists:
        current = meta_doc.to_dict()
        print(f"\n📦 Current metadata:")
        print(f"   Total: {current.get('total_incidents', 'N/A')}")
        print(f"   Active: {current.get('active_count', 'N/A')}")
        print(f"   Resolved: {current.get('resolved_count', 'N/A')}")
    else:
        print(f"\n📦 No metadata document found")
        current = {}
    
    # Update metadata
    print(f"\n🔄 Updating metadata to match actual counts...")
    new_metadata = {
        'total_incidents': total_count,
        'active_count': active_count,
        'resolved_count': resolved_count,
        'last_sync': firestore.SERVER_TIMESTAMP
    }
    meta_ref.set(new_metadata, merge=True)
    
    print(f"\n✅ Metadata synced successfully!")
    print(f"   Total: {total_count}")
    print(f"   Active: {active_count}")
    print(f"   Resolved: {resolved_count}")
    print("=" * 60)

if __name__ == '__main__':
    sync_metadata()
