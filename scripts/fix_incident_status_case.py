#!/usr/bin/env python3
"""
Normalize Vanguard Incident Status
==================================
Fixes case-sensitivity issue by normalizing all status fields to lowercase.

Usage: python fix_incident_status_case.py
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

def fix_status_case():
    """Normalize all incident status fields to lowercase."""
    
    # Initialize Firebase if needed
    if not firebase_admin._apps:
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
    
    db = firestore.client()
    
    print("=" * 60)
    print("VANGUARD INCIDENT STATUS NORMALIZATION")
    print("=" * 60)
    
    # Get all incidents
    print("\n📊 Scanning all incidents...")
    
    fixed_count = 0
    incidents = db.collection('vanguard_incidents').stream()
    
    for doc in incidents:
        data = doc.to_dict()
        current_status = data.get('status', 'active')
        normalized_status = current_status.lower()
        
        if current_status != normalized_status:
            print(f"   🔧 {doc.id[:16]}... {current_status} → {normalized_status}")
            doc.reference.update({'status': normalized_status})
            fixed_count += 1
        else:
            print(f"   ✓ {doc.id[:16]}... {current_status} (OK)")
    
    print(f"\n✅ Fixed {fixed_count} incidents with uppercase status")
    
    # Verify counts
    print("\n📊 Verifying counts after fix...")
    active = 0
    resolved = 0
    incidents = db.collection('vanguard_incidents').stream()
    for doc in incidents:
        status = doc.to_dict().get('status', 'active')
        if status == 'active':
            active += 1
        else:
            resolved += 1
    
    print(f"   Active: {active}")
    print(f"   Resolved: {resolved}")
    
    # Update metadata
    print(f"\n🔄 Updating metadata...")
    meta_ref = db.collection('vanguard_metadata').document('global')
    meta_ref.set({
        'total_incidents': active + resolved,
        'active_count': active,
        'resolved_count': resolved,
        'last_sync': firestore.SERVER_TIMESTAMP
    }, merge=True)
    
    print(f"\n✅ All done! Metadata synced.")
    print("=" * 60)

if __name__ == '__main__':
    fix_status_case()
