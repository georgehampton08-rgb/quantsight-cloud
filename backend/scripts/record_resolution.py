#!/usr/bin/env python3
"""
Record a Resolution in Vanguard Learning System
Run this after deploying ANY fix to track effectiveness

Usage:
    python record_resolution.py \
        --pattern "/api/endpoint 404" \
        --description "Created missing endpoint" \
        --files "api/routes.py,main.py" \
        --revision "00087-abc" \
        --incidents-before 50

After 24 hours, run verify script to update effectiveness
"""
import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vanguard.resolution_learner import get_learner

def main():
    parser = argparse.ArgumentParser(description='Record incident resolution for AI learning')
    parser.add_argument('--pattern', required=True, help='Incident pattern, e.g. "/nexus/health 404"')
    parser.add_argument('--description', required=True, help='Fix description')
    parser.add_argument('--files', required=True, help='Files modified (comma-separated)')
    parser.add_argument('--revision', required=True, help='Deployed revision ID')
    parser.add_argument('--incidents-before', type=int, required=True, help='Incident count before fix')
    parser.add_argument('--commit', help='Git commit hash (optional)')
    
    args = parser.parse_args()
    
    print("📝 Recording resolution in Vanguard learning system...")
    print()
    
    learner = get_learner()
    
    # Record the fix
    resolution = learner.record_fix(
        incident_pattern=args.pattern,
        fix_description=args.description,
        fix_files=args.files.split(','),
        deployed_revision=args.revision,
        incidents_before=args.incidents_before,
        fix_commit=args.commit
    )
    
    print("✅ Resolution recorded!")
    print()
    print(f"   Pattern: {resolution.incident_pattern}")
    print(f"   Fix: {resolution.fix_description}")
    print(f"   Files: {', '.join(resolution.fix_files)}")
    print(f"   Revision: {resolution.deployed_revision}")
    print(f"   Incidents before: {resolution.incidents_before}")
    print()
    print("⏳ Verification pending - run verify script after 24 hours")
    print()
    
    # Auto-export for sovereign AI
    print("🤖 Exporting for sovereign AI training...")
    try:
        exports = learner.export_for_sovereign_ai()
        print("✅ Training data exported:")
        for name, path in exports.items():
            print(f"   {name}: {path}")
    except Exception as e:
        print(f"⚠️  Export failed: {e}")
    
    print()
    
    # Show stats
    stats = learner.get_stats()
    print("📊 Learning System Stats:")
    print(f"   Total resolutions: {stats['total_resolutions']}")
    print(f"   Effective fixes: {stats['effective_fixes']}")
    print(f"   Training progress: {stats['training_progress']}")
    
    if stats['sovereign_ai_ready']:
        print()
        print("🟢 SOVEREIGN AI READY - Can begin supervised testing!")
    else:
        print()
        print(f"🔄 Need {stats['resolutions_needed']} more resolutions for sovereign mode")

if __name__ == "__main__":
    main()
