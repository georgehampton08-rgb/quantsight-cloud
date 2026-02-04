#!/usr/bin/env python3
"""
Verify Resolution Effectiveness
Run this 24 hours after deploying a fix to calculate effectiveness

Usage:
    python verify_resolution.py --pattern "/api/endpoint 404" --incidents-after 0
"""
import sys
import os
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vanguard.resolution_learner import get_learner

def main():
    parser = argparse.ArgumentParser(description='Verify resolution effectiveness after 24h')
    parser.add_argument('--pattern', required=True, help='Incident pattern that was fixed')
    parser.add_argument('--incidents-after', type=int, required=True, help='Current incident count')
    
    args = parser.parse_args()
    
    print(f"🔍 Verifying resolution for: {args.pattern}")
    print()
    
    learner = get_learner()
    
    # Verify the fix
    resolution = learner.verify_fix(args.pattern, args.incidents_after)
    
    if not resolution:
        print(f"❌ No resolution found for pattern: {args.pattern}")
        return
    
    print("✅ Verification complete!")
    print()
    print(f"   Pattern: {resolution.incident_pattern}")
    print(f"   Incidents before: {resolution.incidents_before}")
    print(f"   Incidents after: {resolution.incidents_after}")
    print(f"   Reduction: {resolution.reduction_percentage}%")
    print()
    
    # Determine effectiveness
    if resolution.reduction_percentage >= 80:
        print("🟢 EFFECTIVE - Fix resolved the issue!")
    elif resolution.reduction_percentage >= 50:
        print("🟡 PARTIAL - Some improvement but incidents remain")
    else:
        print("🔴 INEFFECTIVE - Issue persists or worsened")
    
    print()
    
    # Auto-export updated training data
    print("🤖 Updating sovereign AI training data...")
    try:
        exports = learner.export_for_sovereign_ai()
        print("✅ Training data updated")
    except Exception as e:
        print(f"⚠️  Export failed: {e}")
    
    print()
    
    # Show updated stats
    stats = learner.get_stats()
    print("📊 Updated Stats:")
    print(f"   Total resolutions: {stats['total_resolutions']}")
    print(f"   Effective fixes: {stats['effective_fixes']}")
    print(f"   Average reduction: {stats['average_reduction']}%")
    print(f"   Training progress: {stats['training_progress']}")

if __name__ == "__main__":
    main()
