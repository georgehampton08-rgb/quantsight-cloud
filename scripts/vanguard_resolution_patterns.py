#!/usr/bin/env python3
"""
Vanguard Incident Resolution & Learning Script
===============================================
AI-powered incident analysis with Gemini and smart deduplication.
Only processes each unique incident once to avoid redundant work.

Usage:
    python vanguard_resolution_patterns.py --analyze     # AI analysis of new incidents
    python vanguard_resolution_patterns.py --resolve <fingerprint>
    python vanguard_resolution_patterns.py --list
    python vanguard_resolution_patterns.py --learn
"""

import os
import json
import httpx
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from pathlib import Path

# Cloud Run endpoint
CLOUD_URL = "https://quantsight-cloud-458498663186.us-central1.run.app"

# Storage files
PATTERNS_FILE = Path(__file__).parent / "resolution_patterns.json"
PROCESSED_FILE = Path(__file__).parent / "processed_incidents.json"
ANALYSIS_FILE = Path(__file__).parent / "incident_analysis.json"

# Gemini API for AI summaries
try:
    import google.generativeai as genai
    GEMINI_KEY = os.getenv("GEMINI_API_KEY")
    if GEMINI_KEY:
        genai.configure(api_key=GEMINI_KEY)
        AI_MODEL = genai.GenerativeModel('gemini-1.5-flash')
        HAS_GEMINI = True
    else:
        HAS_GEMINI = False
except ImportError:
    HAS_GEMINI = False


@dataclass
class ResolutionPattern:
    """A learned pattern for resolving similar incidents."""
    error_type: str
    endpoint_pattern: str  # Regex pattern for matching endpoints
    root_cause: str
    fix_description: str
    fix_category: str  # 'endpoint_missing', 'graceful_fallback', 'frontend_bug', 'data_missing'
    auto_resolvable: bool
    code_changes: List[Dict[str, str]]  # List of {file, change_type, description}
    created_at: str
    success_count: int = 0
    

@dataclass
class Incident:
    """A Vanguard incident."""
    fingerprint: str
    service: str
    error_type: str
    endpoint: str
    occurrence_count: int
    last_seen: str
    severity: str


@dataclass
class IncidentAnalysis:
    """AI-generated analysis of an incident."""
    fingerprint: str
    endpoint: str
    error_type: str
    summary: str  # Short human-readable summary
    recommended_action: str  # What should be done
    urgency: str  # 'critical', 'high', 'medium', 'low'
    analyzed_at: str
    

class VanguardResolver:
    """AI-powered Vanguard incident resolver with smart deduplication."""
    
    def __init__(self):
        self.patterns = self._load_patterns()
        self.processed = self._load_processed()
        self.analyses = self._load_analyses()
        
    def _load_patterns(self) -> Dict[str, ResolutionPattern]:
        """Load existing resolution patterns from file."""
        if PATTERNS_FILE.exists():
            with open(PATTERNS_FILE, 'r') as f:
                data = json.load(f)
                return {k: ResolutionPattern(**v) for k, v in data.items()}
        return {}
    
    def _save_patterns(self):
        """Save resolution patterns to file."""
        with open(PATTERNS_FILE, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.patterns.items()}, f, indent=2)
    
    def _load_processed(self) -> Dict[str, dict]:
        """Load processed incident fingerprints (deduplication)."""
        if PROCESSED_FILE.exists():
            with open(PROCESSED_FILE, 'r') as f:
                return json.load(f)
        return {}
    
    def _save_processed(self):
        """Save processed incident fingerprints."""
        with open(PROCESSED_FILE, 'w') as f:
            json.dump(self.processed, f, indent=2)
    
    def _load_analyses(self) -> Dict[str, IncidentAnalysis]:
        """Load AI analyses."""
        if ANALYSIS_FILE.exists():
            with open(ANALYSIS_FILE, 'r') as f:
                data = json.load(f)
                return {k: IncidentAnalysis(**v) for k, v in data.items()}
        return {}
    
    def _save_analyses(self):
        """Save AI analyses."""
        with open(ANALYSIS_FILE, 'w') as f:
            json.dump({k: asdict(v) for k, v in self.analyses.items()}, f, indent=2)
    
    def get_incidents(self) -> List[Incident]:
        """Fetch current incidents from Vanguard."""
        try:
            response = httpx.get(f"{CLOUD_URL}/vanguard/incidents", timeout=10)
            data = response.json()
            return [Incident(**inc) for inc in data.get('incidents', [])]
        except Exception as e:
            print(f"[ERROR] Failed to fetch incidents: {e}")
            return []
    
    def is_processed(self, fingerprint: str) -> bool:
        """Check if incident has been processed (deduplication)."""
        return fingerprint in self.processed
    
    def mark_processed(self, fingerprint: str, action: str):
        """Mark incident as processed to avoid redundant work."""
        self.processed[fingerprint] = {
            "processed_at": datetime.now(datetime.UTC).isoformat(),
            "action": action
        }
        self._save_processed()
    
    def generate_ai_summary(self, incident: Incident) -> Optional[IncidentAnalysis]:
        """Generate AI-powered natural language summary using Gemini."""
        if not HAS_GEMINI:
            return None
        
        try:
            prompt = f"""Analyze this API incident and provide a brief summary:

Endpoint: {incident.endpoint}
Error: {incident.error_type}
Service: {incident.service}
Occurrences: {incident.occurrence_count}
Severity: {incident.severity}

Provide:
1. A SHORT 1-sentence summary (max 20 words)
2. Recommended action (max 30 words)
3. Urgency level (critical/high/medium/low)

Be concise and technical. Format as JSON:
{{"summary": "...", "action": "...", "urgency": "..."}}"""
            
            response = AI_MODEL.generate_content(prompt)
            result = json.loads(response.text.strip().replace('```json', '').replace('```', ''))
            
            return IncidentAnalysis(
                fingerprint=incident.fingerprint,
                endpoint=incident.endpoint,
                error_type=incident.error_type,
                summary=result.get('summary', 'Analysis unavailable'),
                recommended_action=result.get('action', 'Review manually'),
                urgency=result.get('urgency', 'medium'),
                analyzed_at=datetime.now(datetime.UTC).isoformat()
            )
        except Exception as e:
            print(f"[WARN] AI analysis failed: {e}")
            return None
    
    def mark_resolved(self, fingerprint: str, resolution_notes: str) -> bool:
        """
        Mark an incident as resolved in Vanguard.
        
        Note: Vanguard will keep the incident for 7 days for learning,
        then automatically purge it.
        """
        try:
            response = httpx.post(
                f"{CLOUD_URL}/vanguard/incidents/{fingerprint}/resolve",
                json={
                    "resolution_notes": resolution_notes,
                    "resolved_by": "vanguard_resolution_script",
                    "retain_for_learning": True
                },
                timeout=10
            )
            return response.status_code == 200
        except Exception as e:
            print(f"[ERROR] Failed to resolve incident: {e}")
            return False
    
    def learn_pattern(
        self,
        error_type: str,
        endpoint_pattern: str,
        root_cause: str,
        fix_description: str,
        fix_category: str,
        code_changes: List[Dict[str, str]],
        auto_resolvable: bool = False
    ):
        """
        Learn a new resolution pattern for future sovereign mode.
        
        Args:
            error_type: e.g., 'HTTPError404', 'HTTPError503'
            endpoint_pattern: Regex pattern like '/nexus/.*' or '/matchup/analyze'
            root_cause: Human-readable description of what causes this
            fix_description: How to fix it
            fix_category: Category for grouping similar fixes
            code_changes: List of code changes needed
            auto_resolvable: Whether sovereign mode can auto-fix this
        """
        pattern_key = f"{error_type}:{endpoint_pattern}"
        
        self.patterns[pattern_key] = ResolutionPattern(
            error_type=error_type,
            endpoint_pattern=endpoint_pattern,
            root_cause=root_cause,
            fix_description=fix_description,
            fix_category=fix_category,
            auto_resolvable=auto_resolvable,
            code_changes=code_changes,
            created_at=datetime.utcnow().isoformat()
        )
        
        self._save_patterns()
        print(f"[LEARNED] Pattern saved: {pattern_key}")
    
    def find_matching_pattern(self, incident: Incident) -> Optional[ResolutionPattern]:
        """Find a matching resolution pattern for an incident."""
        import re
        
        for key, pattern in self.patterns.items():
            if pattern.error_type == incident.error_type:
                if re.match(pattern.endpoint_pattern, incident.endpoint):
                    return pattern
        return None
    
    def auto_resolve(self, dry_run: bool = True) -> List[str]:
        """
        Attempt to auto-resolve incidents that have STOPPED occurring.
        
        IMPORTANT: Only resolves incidents that:
        1. Match a known pattern
        2. Haven't had new occurrences in the last 24 hours
        3. Are marked as auto_resolvable
        
        This ensures we only mark as resolved when the fix has actually worked.
        
        Args:
            dry_run: If True, only report what would be resolved
            
        Returns:
            List of resolved incident fingerprints
        """
        incidents = self.get_incidents()
        resolved = []
        
        for incident in incidents:
            pattern = self.find_matching_pattern(incident)
            
            if pattern and pattern.auto_resolvable:
                # Check if incident has stopped occurring
                from datetime import datetime, timedelta
                last_seen = datetime.fromisoformat(incident.last_seen.replace('+00:00', ''))
                hours_since_last = (datetime.now(datetime.UTC).replace(tzinfo=None) - last_seen).total_seconds() / 3600
                
                # Only auto-resolve if no occurrences in last 24 hours
                if hours_since_last >= 24:
                    if dry_run:
                        print(f"[DRY RUN] Would resolve: {incident.endpoint} ({incident.error_type})")
                        print(f"          Pattern: {pattern.fix_description}")
                        print(f"          Last seen: {hours_since_last:.1f}h ago ✓")
                    else:
                        success = self.mark_resolved(
                            incident.fingerprint,
                            f"Auto-resolved: No occurrences in {hours_since_last:.1f}h. Pattern: {pattern.fix_description}"
                        )
                        if success:
                            resolved.append(incident.fingerprint)
                            pattern.success_count += 1
                            self._save_patterns()
                else:
                    if dry_run:
                        print(f"[SKIP] {incident.endpoint} - Still occurring (last seen {hours_since_last:.1f}h ago)")
        
        return resolved
    
    def print_status(self):
        """Print current incident status and learned patterns."""
        incidents = self.get_incidents()
        
        print("\n" + "=" * 60)
        print("VANGUARD INCIDENT STATUS")
        print("=" * 60)
        
        if not incidents:
            print("No active incidents!")
        else:
            for inc in incidents:
                pattern = self.find_matching_pattern(inc)
                status = "✅ Pattern Found" if pattern else "❌ No Pattern"
                auto = "(auto)" if pattern and pattern.auto_resolvable else ""
                print(f"\n[{inc.severity.upper()}] {inc.endpoint}")
                print(f"  Error: {inc.error_type} ({inc.occurrence_count}x)")
                print(f"  Status: {status} {auto}")
        
        print("\n" + "-" * 60)
        print(f"LEARNED PATTERNS: {len(self.patterns)}")
        print("-" * 60)
        
        for key, pattern in self.patterns.items():
            auto = "🤖 AUTO" if pattern.auto_resolvable else "👤 MANUAL"
            print(f"  [{auto}] {key}")
            print(f"         Fix: {pattern.fix_description[:50]}...")


# ==================== PRE-DEFINED RESOLUTION PATTERNS ====================

def register_known_patterns(resolver: VanguardResolver):
    """Register known resolution patterns for common issues."""
    
    # Pattern 1: Nexus 404s (graceful stubs exist)
    resolver.learn_pattern(
        error_type="HTTPError404",
        endpoint_pattern=r"/nexus/.*",
        root_cause="Nexus Hub endpoints called before stub routes registered in router",
        fix_description="Ensure /nexus/* stub endpoints in public_routes.py are registered. "
                       "These return graceful degradation messages when Nexus Hub is offline.",
        fix_category="graceful_fallback",
        code_changes=[
            {
                "file": "backend/api/public_routes.py",
                "change_type": "add",
                "description": "Add @router.get('/nexus/health') and /nexus/cooldowns stub endpoints"
            },
            {
                "file": "backend/main.py",
                "change_type": "verify",
                "description": "Ensure public_router is included with app.include_router(public_router)"
            }
        ],
        auto_resolvable=True  # Can mark as resolved since stubs now exist
    )
    
    # Pattern 2: Matchup 503s (engine not initialized)
    resolver.learn_pattern(
        error_type="HTTPError503",
        endpoint_pattern=r"/matchup/analyze.*",
        root_cause="MultiStatConfluenceCloud engine failed to initialize (missing Firestore data or dependencies)",
        fix_description="Add graceful fallback in analyze_matchup() instead of raising HTTPException(503). "
                       "Return empty projections with error flag when engine unavailable.",
        fix_category="graceful_fallback",
        code_changes=[
            {
                "file": "backend/api/public_routes.py",
                "change_type": "modify",
                "description": "Change line 614-615 from raising HTTPException to returning graceful JSON response"
            }
        ],
        auto_resolvable=False  # Requires code change
    )
    
    # Pattern 3: Frontend object serialization
    resolver.learn_pattern(
        error_type="HTTPError404",
        endpoint_pattern=r".*/\[object Object\].*",
        root_cause="Frontend passing JavaScript object instead of string ID in URL path",
        fix_description="In playerApi.ts, ensure opponent parameter is stringified before URL construction. "
                       "Use opponent.id or opponent.abbreviation if object is passed.",
        fix_category="frontend_bug",
        code_changes=[
            {
                "file": "src/services/playerApi.ts",
                "change_type": "modify",
                "description": "Add type guard: const opponentId = typeof opponent === 'object' ? opponent.id : opponent"
            }
        ],
        auto_resolvable=False  # Requires frontend rebuild
    )
    
    # Pattern 4: Live stream 422
    resolver.learn_pattern(
        error_type="HTTPError422",
        endpoint_pattern=r"/live/stream.*",
        root_cause="SSE endpoint receiving malformed request (wrong content-type or body)",
        fix_description="SSE endpoints should not have request body validation. "
                       "Ensure endpoint uses Request type, not Pydantic model.",
        fix_category="endpoint_config",
        code_changes=[
            {
                "file": "backend/api/public_routes.py",
                "change_type": "verify",
                "description": "Ensure live_stats_stream(request: Request) uses Request from fastapi, not a body model"
            }
        ],
        auto_resolvable=True  # Usually client-side issue
    )
    
    # Pattern 5: Player not found (expected)
    resolver.learn_pattern(
        error_type="HTTPError404",
        endpoint_pattern=r"/players/\d+",
        root_cause="Player ID not found in Firestore database - expected for inactive/historical players",
        fix_description="This is expected behavior. Player may not exist in current roster. "
                       "Frontend should handle 404 gracefully with 'Player not found' message.",
        fix_category="expected_behavior",
        code_changes=[],
        auto_resolvable=True  # Not a bug, expected behavior
    )
    
    print(f"[OK] Registered {len(resolver.patterns)} resolution patterns")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Vanguard Incident Resolution & Learning")
    parser.add_argument("--list", action="store_true", help="List current incidents and patterns")
    parser.add_argument("--learn", action="store_true", help="Register known resolution patterns")
    parser.add_argument("--analyze", action="store_true", help="AI analysis of new incidents (with deduplication)")
    parser.add_argument("--auto", action="store_true", help="Auto-resolve incidents with patterns")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually resolve, just show what would happen")
    parser.add_argument("--resolve", type=str, help="Manually resolve a specific incident by fingerprint")
    
    args = parser.parse_args()
    
    resolver = VanguardResolver()
    
    if args.learn:
        register_known_patterns(resolver)
    
    if args.analyze:
        incidents = resolver.get_incidents()
        new_count = 0
        
        print("\n" + "=" * 60)
        print("AI INCIDENT ANALYSIS (NEW INCIDENTS ONLY)")
        print("=" * 60)
        
        for inc in incidents:
            # Skip if already processed
            if resolver.is_processed(inc.fingerprint):
                continue
            
            new_count += 1
            print(f"\n🔍 Analyzing: {inc.endpoint}")
            print(f"   Error: {inc.error_type} ({inc.occurrence_count}x)")
            
            analysis = resolver.generate_ai_summary(inc)
            if analysis:
                print(f"   📊 Summary: {analysis.summary}")
                print(f"   💡 Action: {analysis.recommended_action}")
                print(f"   ⚠️  Urgency: {analysis.urgency.upper()}")
                resolver.analyses[inc.fingerprint] = analysis
                resolver._save_analyses()
            
            # Mark as processed
            resolver.mark_processed(inc.fingerprint, "AI analysis completed")
        
        if new_count == 0:
            print("\n✅ No new incidents to analyze (all already processed)")
        else:
            print(f"\n✅ Analyzed {new_count} new incidents")
    
    if args.list:
        resolver.print_status()
    
    if args.auto:
        resolved = resolver.auto_resolve(dry_run=args.dry_run)
        if resolved:
            print(f"\n[OK] Resolved {len(resolved)} incidents")
    
    if args.resolve:
        success = resolver.mark_resolved(args.resolve, "Manually resolved via script")
        print(f"[{'OK' if success else 'FAILED'}] Resolve {args.resolve}")
