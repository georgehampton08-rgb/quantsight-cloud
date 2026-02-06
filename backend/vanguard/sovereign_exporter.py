"""
Sovereign AI Training Data Export
Prepares Vanguard incident data for autonomous AI learning

This module exports incident patterns, resolutions, and code changes
in a format suitable for training an autonomous AI system to:
1. Recognize incident patterns
2. Generate code fixes
3. Deploy changes automatically
4. Verify effectiveness
5. Learn from outcomes
"""
from datetime import datetime
from typing import List, Dict, Optional
import json
from pathlib import Path
from dataclasses import dataclass, asdict

@dataclass
class IncidentPattern:
    """Generic incident pattern for AI learning"""
    pattern_id: str
    endpoint: str
    error_type: str
    http_status: int
    severity: str
    occurrences: int
    first_seen: str
    last_seen: str
    example_error_message: str

@dataclass
class ResolutionAction:
    """Action taken to resolve an incident"""
    action_type: str  # 'code_change', 'config_change', 'deployment', 'restart'
    description: str
    files_modified: List[str]
    code_diff: Optional[str]
    commit_hash: Optional[str]
    deployment_id: str

@dataclass
class IncidentResolution:
    """Complete resolution record for AI training"""
    incident_pattern: IncidentPattern
    resolution_actions: List[ResolutionAction]
    incidents_before: int
    incidents_after: int
    reduction_percentage: float
    time_to_resolve_minutes: int
    verification_period_hours: int
    effectiveness_rating: str  # 'EFFECTIVE', 'PARTIAL', 'INEFFECTIVE'
    ai_learnings: List[str]  # Key takeaways for AI
    timestamp: str

class SovereignTrainingExporter:
    """
    Exports Vanguard incident data for sovereign AI training
    Prepares the knowledge base for fully autonomous operations
    """
    
    def __init__(self, export_dir: str = "vanguard/sovereign_training"):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
    
    def export_incident_catalog(self, incidents: List[Dict]) -> str:
        """
        Export all incidents as training catalog
        Format: Pattern recognition dataset
        """
        patterns = []
        
        for inc in incidents:
            pattern = IncidentPattern(
                pattern_id=f"{inc.get('endpoint', 'unknown')}_{inc.get('error_type', 'unknown')}",
                endpoint=inc.get('endpoint', 'unknown'),
                error_type=inc.get('error_type', 'unknown'),
                http_status=inc.get('http_status', 0),
                severity=inc.get('severity', 'medium'),
                occurrences=inc.get('count', 0),
                first_seen=inc.get('first_seen', datetime.utcnow().isoformat()),
                last_seen=inc.get('last_occurred', datetime.utcnow().isoformat()),
                example_error_message=inc.get('error_message', '')
            )
            patterns.append(asdict(pattern))
        
        catalog_path = self.export_dir / "incident_catalog.json"
        with open(catalog_path, 'w') as f:
            json.dump({
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "total_patterns": len(patterns),
                "patterns": patterns
            }, f, indent=2)
        
        return str(catalog_path)
    
    def export_resolution_playbook(self, resolutions: List[IncidentResolution]) -> str:
        """
        Export all resolutions as AI playbook
        Format: Incident → Actions → Outcome mapping
        """
        playbook = []
        
        for resolution in resolutions:
            playbook.append(asdict(resolution))
        
        playbook_path = self.export_dir / "resolution_playbook.json"
        with open(playbook_path, 'w') as f:
            json.dump({
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "total_resolutions": len(playbook),
                "resolutions": playbook,
                "ai_training_notes": [
                    "Each resolution shows the complete fix sequence",
                    "Code diffs show exact changes that fixed the issue",
                    "Effectiveness ratings indicate success probability",
                    "Time to resolve helps estimate fix complexity"
                ]
            }, f, indent=2)
        
        return str(playbook_path)
    
    def export_code_patterns(self, resolutions: List[IncidentResolution]) -> str:
        """
        Extract code change patterns for AI learning
        Teaches AI what kind of code changes fix what problems
        """
        patterns = {
            "route_additions": [],
            "error_handling_additions": [],
            "configuration_changes": [],
            "dependency_updates": [],
            "database_migrations": []
        }
        
        for resolution in resolutions:
            for action in resolution.resolution_actions:
                if action.action_type == 'code_change':
                    # Categorize by change type
                    if 'router' in action.description.lower() or 'endpoint' in action.description.lower():
                        patterns["route_additions"].append({
                            "incident": resolution.incident_pattern.endpoint,
                            "fix": action.description,
                            "files": action.files_modified,
                            "effectiveness": resolution.effectiveness_rating
                        })
                    elif 'error' in action.description.lower() or 'exception' in action.description.lower():
                        patterns["error_handling_additions"].append({
                            "incident": resolution.incident_pattern.endpoint,
                            "fix": action.description,
                            "files": action.files_modified,
                            "effectiveness": resolution.effectiveness_rating
                        })
        
        patterns_path = self.export_dir / "code_patterns.json"
        with open(patterns_path, 'w') as f:
            json.dump({
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "patterns": patterns,
                "ai_training_notes": [
                    "Route additions: Learn when to create new endpoints",
                    "Error handling: Learn when to add try/catch blocks",
                    "Configuration: Learn when to change settings vs code"
                ]
            }, f, indent=2)
        
        return str(patterns_path)
    
    def export_sovereign_capabilities_spec(self) -> str:
        """
        Export specification of what sovereign AI can do
        Defines the autonomous capabilities
        """
        spec = {
            "version": "1.0",
            "capabilities": {
                "pattern_recognition": {
                    "enabled": True,
                    "description": "Identify incident patterns from Vanguard logs",
                    "confidence_threshold": 0.85
                },
                "code_generation": {
                    "enabled": False,  # Not yet trained
                    "description": "Generate code fixes for identified issues",
                    "supported_languages": ["python", "typescript"]
                },
                "deployment": {
                    "enabled": False,  # Not yet trained
                    "description": "Deploy fixes to Cloud Run automatically",
                    "requires_approval": True,
                    "approval_threshold": "high_confidence"
                },
                "verification": {
                    "enabled": True,
                    "description": "Monitor incidents after fix deployment",
                    "verification_period_hours": 24
                },
                "rollback": {
                    "enabled": False,  # Safety feature
                    "description": "Automatic rollback if fix causes more incidents",
                    "trigger_threshold": "20% increase in errors"
                }
            },
            "learning_phases": {
                "phase_1_current": "Supervised learning - track human fixes",
                "phase_2_next": "Pattern matching - suggest fixes for approval",
                "phase_3_future": "Autonomous fixes - deploy with human oversight",
                "phase_4_sovereign": "Full autonomy - self-healing without approval"
            },
            "training_data_requirements": {
                "minimum_resolutions": 50,
                "minimum_success_rate": 0.80,
                "diverse_incident_types": 10
            }
        }
        
        spec_path = self.export_dir / "sovereign_capabilities.json"
        with open(spec_path, 'w') as f:
            json.dump(spec, f, indent=2)
        
        return str(spec_path)
    
    def export_all(self, incidents: List[Dict], resolutions: List[IncidentResolution]) -> Dict[str, str]:
        """Export all training data for sovereign AI"""
        exports = {
            "incident_catalog": self.export_incident_catalog(incidents),
            "resolution_playbook": self.export_resolution_playbook(resolutions),
            "code_patterns": self.export_code_patterns(resolutions),
            "capabilities_spec": self.export_sovereign_capabilities_spec()
        }
        
        # Create index
        index_path = self.export_dir / "index.json"
        with open(index_path, 'w') as f:
            json.dump({
                "version": "1.0",
                "exported_at": datetime.utcnow().isoformat() + "Z",
                "purpose": "Sovereign AI Training Dataset",
                "description": "Complete incident resolution knowledge base for autonomous AI",
                "files": exports,
                "next_steps": [
                    "1. Accumulate 50+ resolution records",
                    "2. Train pattern recognition model",
                    "3. Enable supervised code generation",
                    "4. Test with controlled breakage scenarios",
                    "5. Gradually increase autonomy based on success rate"
                ]
            }, f, indent=2)
        
        return exports


# Global exporter instance
_exporter = None

def get_exporter() -> SovereignTrainingExporter:
    """Get global training exporter"""
    global _exporter
    if _exporter is None:
        _exporter = SovereignTrainingExporter()
    return _exporter
