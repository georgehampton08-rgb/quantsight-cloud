#!/usr/bin/env python3
"""
Batch AI Analysis Generator for Vanguard Incidents
==================================================
Generates AI analysis for all active incidents that don't have one yet.

Usage: python batch_analyze_incidents.py
"""
import os
import sys
import asyncio
from pathlib import Path
from typing import List

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

# Load env
from dotenv import load_dotenv
load_dotenv(backend_path.parent / '.env')

from vanguard.archivist.storage import get_incident_storage
from vanguard.ai.ai_analyzer import VanguardAIAnalyzer


async def batch_analyze_incidents(force: bool = False):
    """
    Generate AI analysis for all active incidents.
    
    Args:
        force: If True, regenerate analysis even if it already exists
    """
    print("=" * 70)
    print("VANGUARD BATCH AI ANALYSIS")
    print("=" * 70)
    
    # Get storage and analyzer
    storage = get_incident_storage()
    analyzer = VanguardAIAnalyzer()
    
    # Get all incidents
    print("\n📋 Fetching active incidents...")
    fingerprints = await storage.list_incidents(limit=2000)
    
    active_incidents = []
    for fp in fingerprints:
        incident = await storage.load(fp)
        if incident and incident.get('status') == 'active':
            active_incidents.append((fp, incident))
    
    print(f"   Found {len(active_incidents)} active incidents")
    
    if not active_incidents:
        print("\n✅ No active incidents to analyze")
        return
    
    # Filter to those without analysis (unless force)
    to_analyze = []
    skipped = 0
    
    for fp, incident in active_incidents:
        has_analysis = 'ai_analysis' in incident or 'ai_analyses' in incident
        
        if force or not has_analysis:
            to_analyze.append((fp, incident))
        else:
            skipped += 1
    
    if skipped > 0:
        print(f"   ⏭️  Skipping {skipped} incidents with existing analysis")
    
    if not to_analyze:
        print("\n✅ All active incidents already have AI analysis!")
        print(f"   Use --force to regenerate")
        return
    
    print(f"\n🤖 Generating AI analysis for {len(to_analyze)} incidents...")
    print()
    
    # Analyze each incident
    succeeded = 0
    failed = 0
    
    for i, (fp, incident) in enumerate(to_analyze, 1):
        endpoint = incident.get('endpoint', 'unknown')
        error_type = incident.get('error_type', 'unknown')
        
        print(f"   [{i}/{len(to_analyze)}] {fp[:16]}... ({endpoint})")
        
        try:
            # Generate analysis
            analysis = await analyzer.analyze_incident(
                fingerprint=fp,
                endpoint=endpoint,
                error_type=error_type,
                incident_data=incident,
                storage=storage
            )
            
            if analysis:
                confidence = analysis.get('confidence', 0)
                ready = "✅" if analysis.get('ready_to_resolve') else "⏳"
                print(f"      {ready} Confidence: {confidence}%")
                succeeded += 1
            else:
                print(f"      ❌ Analysis generation failed")
                failed += 1
                
        except Exception as e:
            print(f"      ❌ Error: {str(e)[:50]}")
            failed += 1
        
        # Small delay to avoid rate limits
        if i < len(to_analyze):
            await asyncio.sleep(1.5)
    
    # Summary
    print()
    print("=" * 70)
    print(f"✅ Analysis complete!")
    print(f"   Succeeded: {succeeded}")
    print(f"   Failed: {failed}")
    print(f"   Total: {len(to_analyze)}")
    print("=" * 70)


async def main():
    """Main entrypoint."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch generate AI analysis for incidents')
    parser.add_argument('--force', action='store_true', 
                       help='Regenerate analysis even if it already exists')
    args = parser.parse_args()
    
    await batch_analyze_incidents(force=args.force)


if __name__ == '__main__':
    asyncio.run(main())
