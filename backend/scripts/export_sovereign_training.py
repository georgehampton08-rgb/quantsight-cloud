#!/usr/bin/env python3
"""
Export Vanguard Data for Sovereign AI Training
Run this to prepare training dataset for autonomous operations
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from vanguard.sovereign_exporter import get_exporter, IncidentResolution, IncidentPattern, ResolutionAction
from vanguard.archivist import VanguardArchivist
from vanguard.resolution_learner import get_learner
from datetime import datetime

def main():
    print("🤖 Exporting Vanguard data for Sovereign AI training...")
    print()
    
    # Get all incidents
    archivist = VanguardArchivist()
    incidents = archivist.get_recent_incidents(hours=72, limit=1000)
    
    print(f"📊 Found {len(incidents)} incidents in last 72 hours")
    
    # Get all resolutions
    learner = get_learner()
    
    # Convert learner resolutions to training format
    training_resolutions = []
    for res in learner.resolutions:
        # Create incident pattern
        pattern = IncidentPattern(
            pattern_id=res.incident_pattern.replace(" ", "_"),
            endpoint=res.incident_pattern.split()[0],
            error_type=res.incident_pattern.split()[-1] if len(res.incident_pattern.split()) > 1 else "unknown",
            http_status=404,  # Most common
            severity="high",
            occurrences=res.incidents_before,
            first_seen=res.timestamp,
            last_seen=res.timestamp,
            example_error_message=res.fix_description
        )
        
        # Create resolution actions
        actions = [
            ResolutionAction(
                action_type="code_change",
                description=res.fix_description,
                files_modified=res.fix_files,
                code_diff=None,  # Not captured yet
                commit_hash=res.fix_commit,
                deployment_id=res.deployed_revision
            )
        ]
        
        # Determine effectiveness
        if res.reduction_percentage >= 80:
            effectiveness = "EFFECTIVE"
        elif res.reduction_percentage >= 50:
            effectiveness = "PARTIAL"
        else:
            effectiveness = "INEFFECTIVE"
        
        # Create full resolution
        training_res = IncidentResolution(
            incident_pattern=pattern,
            resolution_actions=actions,
            incidents_before=res.incidents_before,
            incidents_after=res.incidents_after if res.incidents_after != -1 else res.incidents_before,
            reduction_percentage=res.reduction_percentage,
            time_to_resolve_minutes=120,  # Estimate
            verification_period_hours=res.verification_period_hours,
            effectiveness_rating=effectiveness,
            ai_learnings=[
                f"Pattern: {res.incident_pattern}",
                f"Solution: {res.fix_description}",
                f"Files: {', '.join(res.fix_files)}"
            ],
            timestamp=res.timestamp
        )
        
        training_resolutions.append(training_res)
    
    print(f"📚 Found {len(training_resolutions)} verified resolutions")
    print()
    
    # Export all training data
    exporter = get_exporter()
    
    # Convert incidents to dict format
    incident_dicts = []
    for inc in incidents:
        incident_dicts.append({
            'endpoint': inc.endpoint if hasattr(inc, 'endpoint') else 'unknown',
            'error_type': inc.error_type if hasattr(inc, 'error_type') else 'unknown',
            'http_status': inc.http_status if hasattr(inc, 'http_status') else 0,
            'severity': inc.severity if hasattr(inc, 'severity') else 'medium',
            'count': inc.count if hasattr(inc, 'count') else 1,
            'first_seen': inc.first_seen.isoformat() if hasattr(inc, 'first_seen') else datetime.utcnow().isoformat(),
            'last_occurred': inc.last_occurred.isoformat() if hasattr(inc, 'last_occurred') else datetime.utcnow().isoformat(),
            'error_message': inc.error_message if hasattr(inc, 'error_message') else ''
        })
    
    exports = exporter.export_all(incident_dicts, training_resolutions)
    
    print("✅ Export complete!")
    print()
    print("📁 Training data files:")
    for name, path in exports.items():
        print(f"   {name}: {path}")
    
    print()
    print("🎓 Sovereign AI Training Status:")
    print(f"   Incidents catalogued: {len(incident_dicts)}")
    print(f"   Resolutions learned: {len(training_resolutions)}")
    print(f"   Training completeness: {min(100, len(training_resolutions) * 2)}%")
    print()
    
    if len(training_resolutions) < 50:
        print("⚠️  Need 50+ resolutions for sovereign mode")
        print(f"   Progress: {len(training_resolutions)}/50")
    else:
        print("🟢 Ready for supervised learning phase!")
    
    print()
    print("📋 Next Steps:")
    print("   1. Continue fixing incidents and recording resolutions")
    print("   2. Run this script after each deployment")
    print("   3. At 50 resolutions, begin supervised code generation testing")
    print("   4. Introduce controlled breakages to test AI fixes")
    print("   5. Gradually increase autonomy based on success rate")

if __name__ == "__main__":
    main()
