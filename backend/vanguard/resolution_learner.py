"""
Vanguard Resolution Learning System
Automatically tracks what fixes resolved which incidents for continuous learning
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
import json
from pathlib import Path

@dataclass
class ResolutionRecord:
    """Record of what fixed an incident"""
    incident_pattern: str  # e.g., "/nexus/health 404"
    fix_description: str
    fix_files: List[str]
    fix_commit: Optional[str]
    deployed_revision: str
    timestamp: str
    incidents_before: int
    incidents_after: int
    reduction_percentage: float
    verification_period_hours: int = 24

class VanguardResolutionLearner:
    """
    Intelligent system that learns from incident resolutions
    Stores what fixed what for future reference and automated healing
    """
    
    def __init__(self, storage_path: str = "vanguard/resolutions.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.resolutions: List[ResolutionRecord] = self._load_resolutions()
    
    def _load_resolutions(self) -> List[ResolutionRecord]:
        """Load past resolutions from storage"""
        if not self.storage_path.exists():
            return []
        
        try:
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                return [ResolutionRecord(**r) for r in data]
        except Exception as e:
            print(f"⚠️ Failed to load resolutions: {e}")
            return []
    
    def _save_resolutions(self):
        """Persist resolutions to storage"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump([asdict(r) for r in self.resolutions], f, indent=2)
        except Exception as e:
            print(f"❌ Failed to save resolutions: {e}")
    
    def record_fix(
        self,
        incident_pattern: str,
        fix_description: str,
        fix_files: List[str],
        deployed_revision: str,
        incidents_before: int,
        fix_commit: Optional[str] = None
    ) -> ResolutionRecord:
        """
        Record a fix deployment
        This is called RIGHT AFTER deploying a fix
        """
        record = ResolutionRecord(
            incident_pattern=incident_pattern,
            fix_description=fix_description,
            fix_files=fix_files,
            fix_commit=fix_commit,
            deployed_revision=deployed_revision,
            timestamp=datetime.utcnow().isoformat() + "Z",
            incidents_before=incidents_before,
            incidents_after=-1,  # Will be updated after verification
            reduction_percentage=0.0,
            verification_period_hours=24
        )
        
        self.resolutions.append(record)
        self._save_resolutions()
        
        print(f"""
✅ Resolution recorded for: {incident_pattern}
   Fix: {fix_description}
   Files: {', '.join(fix_files)}
   Revision: {deployed_revision}
   Incidents before: {incidents_before}
   ⏳ Awaiting 24h verification...
        """)
        
        return record
    
    def auto_track_all_incidents(self) -> Dict:
        """
        Automatically track ALL incidents from Vanguard
        Called periodically to build knowledge base
        
        Returns summary of what was tracked
        """
        from vanguard.archivist import VanguardArchivist
        
        archivist = VanguardArchivist()
        
        # Get all incidents from last 72 hours
        all_incidents = archivist.get_recent_incidents(hours=72, limit=1000)
        
        patterns_tracked = {}
        new_patterns = 0
        
        for incident in all_incidents:
            # Create pattern key
            endpoint = incident.endpoint if hasattr(incident, 'endpoint') else 'unknown'
            error_type = incident.error_type if hasattr(incident, 'error_type') else 'unknown'
            http_status = incident.http_status if hasattr(incident, 'http_status') else 0
            
            pattern = f"{endpoint} {http_status} {error_type}"
            
            if pattern not in patterns_tracked:
                patterns_tracked[pattern] = {
                    'endpoint': endpoint,
                    'error_type': error_type,
                    'http_status': http_status,
                    'count': incident.count if hasattr(incident, 'count') else 1,
                    'severity': incident.severity if hasattr(incident, 'severity') else 'medium',
                    'first_seen': incident.first_seen if hasattr(incident, 'first_seen') else None,
                    'last_occurred': incident.last_occurred if hasattr(incident, 'last_occurred') else None
                }
                new_patterns += 1
        
        return {
            'total_incidents': len(all_incidents),
            'unique_patterns': len(patterns_tracked),
            'new_patterns': new_patterns,
            'patterns': patterns_tracked,
            'timestamp': datetime.utcnow().isoformat() + "Z"
        }
    
    def verify_fix(
        self,
        incident_pattern: str,
        incidents_after: int
    ) -> Optional[ResolutionRecord]:
        """
        Update resolution record after verification period
        This is called 24 hours AFTER deployment
        """
        # Find the most recent unverified fix for this pattern
        for record in reversed(self.resolutions):
            if (record.incident_pattern == incident_pattern and 
                record.incidents_after == -1):
                
                record.incidents_after = incidents_after
                record.reduction_percentage = (
                    ((record.incidents_before - incidents_after) / record.incidents_before * 100)
                    if record.incidents_before > 0 else 0.0
                )
                
                self._save_resolutions()
                
                print(f"""
📊 Verification complete for: {incident_pattern}
   Before: {record.incidents_before} incidents
   After: {incidents_after} incidents
   Reduction: {record.reduction_percentage:.1f}%
   Status: {'✅ EFFECTIVE' if record.reduction_percentage > 80 else '⚠️ PARTIAL' if record.reduction_percentage > 50 else '❌ INEFFECTIVE'}
                """)
                
                return record
        
        return None
    
    def get_similar_resolutions(self, incident_pattern: str, limit: int = 5) -> List[ResolutionRecord]:
        """
        Find similar past resolutions for an incident pattern
        Useful for suggesting fixes for new incidents
        """
        # Simple keyword matching (can be enhanced with ML later)
        keywords = incident_pattern.lower().split()
        
        matches = []
        for record in self.resolutions:
            if record.incidents_after == -1:
                continue  # Skip unverified fixes
            
            pattern_keywords = record.incident_pattern.lower().split()
            match_score = sum(1 for kw in keywords if kw in pattern_keywords)
            
            if match_score > 0:
                matches.append((match_score, record))
        
        # Sort by match score and effectiveness
        matches.sort(key=lambda x: (x[0], x[1].reduction_percentage), reverse=True)
        
        return [record for _, record in matches[:limit]]
    
    def suggest_fix(self, incident_pattern: str) -> Optional[str]:
        """
        Suggest a fix based on similar past resolutions
        This is the "smart healing" feature
        """
        similar = self.get_similar_resolutions(incident_pattern, limit=1)
        
        if not similar:
            return None
        
        best = similar[0]
        
        if best.reduction_percentage > 80:
            return f"""
🔍 Similar incident found with effective fix ({best.reduction_percentage:.1f}% reduction):

Pattern: {best.incident_pattern}
Fix: {best.fix_description}
Files modified: {', '.join(best.fix_files)}
Deployed: {best.deployed_revision}

Suggestion: Apply similar fix to current incident
            """
        
        return None
    
    def export_for_sovereign_ai(self) -> Dict[str, str]:
        """
        Export all resolution data for sovereign AI training
        Integrates with SovereignTrainingExporter
        
        Returns paths to exported files
        """
        from vanguard.sovereign_exporter import get_exporter, IncidentResolution, IncidentPattern, ResolutionAction
        
        exporter = get_exporter()
        
        # Get all incidents
        incident_data = self.auto_track_all_incidents()
        
        # Convert to training format
        incidents_list = [
            {
                'endpoint': p['endpoint'],
                'error_type': p['error_type'],
                'http_status': p['http_status'],
                'severity': p['severity'],
                'count': p['count'],
                'first_seen': p['first_seen'].isoformat() if p['first_seen'] else datetime.utcnow().isoformat(),
                'last_occurred': p['last_occurred'].isoformat() if p['last_occurred'] else datetime.utcnow().isoformat(),
                'error_message': ''
            }
            for pattern, p in incident_data['patterns'].items()
        ]
        
        # Convert resolutions to training format
        training_resolutions = []
        for res in self.resolutions:
            pattern = IncidentPattern(
                pattern_id=res.incident_pattern.replace(" ", "_"),
                endpoint=res.incident_pattern.split()[0],
                error_type=res.incident_pattern.split()[-1] if len(res.incident_pattern.split()) > 1 else "unknown",
                http_status=404,
                severity="high",
                occurrences=res.incidents_before,
                first_seen=res.timestamp,
                last_seen=res.timestamp,
                example_error_message=res.fix_description
            )
            
            actions = [
                ResolutionAction(
                    action_type="code_change",
                    description=res.fix_description,
                    files_modified=res.fix_files,
                    code_diff=None,
                    commit_hash=res.fix_commit,
                    deployment_id=res.deployed_revision
                )
            ]
            
            effectiveness = "EFFECTIVE" if res.reduction_percentage >= 80 else ("PARTIAL" if res.reduction_percentage >= 50 else "INEFFECTIVE")
            
            training_res = IncidentResolution(
                incident_pattern=pattern,
                resolution_actions=actions,
                incidents_before=res.incidents_before,
                incidents_after=res.incidents_after if res.incidents_after != -1 else res.incidents_before,
                reduction_percentage=res.reduction_percentage,
                time_to_resolve_minutes=120,
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
        
        # Export everything
        return exporter.export_all(incidents_list, training_resolutions)
    
    def get_stats(self) -> Dict:
        """Get learning system statistics"""
        verified = [r for r in self.resolutions if r.incidents_after != -1]
        
        if not verified:
            return {
                "total_resolutions": len(self.resolutions),
                "verified": 0,
                "pending_verification": len(self.resolutions),
                "average_reduction": 0.0,
                "effective_fixes": 0
            }
        
        effective = [r for r in verified if r.reduction_percentage > 80]
        
        return {
            "total_resolutions": len(self.resolutions),
            "verified": len(verified),
            "pending_verification": len(self.resolutions) - len(verified),
            "average_reduction": sum(r.reduction_percentage for r in verified) / len(verified),
            "effective_fixes": len(effective),
            "success_rate": len(effective) / len(verified) * 100 if verified else 0
        }


# Global instance 
_learner = None

def get_learner() -> VanguardResolutionLearner:
    """Get global resolution learner instance"""
    global _learner
    if _learner is None:
        _learner = VanguardResolutionLearner()
    return _learner
