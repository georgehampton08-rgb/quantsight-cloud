"""
Codebase Knowledge Base
========================
Builds AI-readable index of the entire codebase for incident analysis.
"""
import json
import re
import os
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from git import Repo
import logging

logger = logging.getLogger(__name__)

# System architecture summary (hardcoded context)
SYSTEM_ARCHITECTURE_SUMMARY = """
QuantSight System Architecture:
- FastAPI backend on Cloud Run (Python 3.11)
- Vanguard: Autonomous health monitoring with Firestore storage
- Nexus: NBA data pipeline with Redis caching
- Aegis: Context enrichment and intelligent routing layer
- Frontend: React SPA hosted on Firebase
- Data Sources: NBA API, custom analytics engines
- Deployment: Google Cloud Platform (Cloud Run, Firestore, Redis)
"""


class CodebaseKnowledgeBase:
    """
    Creates a unified, AI-readable knowledge base of the codebase.
    Indexes routes, models, dependencies, and recent changes.
    """
    
    def __init__(self, base_path: str = "backend"):
        self.base_path = Path(base_path)
        self.cache_file = Path("/tmp/vanguard/kb_cache.json")
        self.cache_ttl = 3600  # Rebuild every hour
        self._kb_cache: Optional[Dict] = None
    
    def build_knowledge_base(self) -> Dict:
        """
        Build complete system knowledge in AI-friendly JSON format
        """
        logger.info("Building codebase knowledge base...")
        
        kb = {
            "system_overview": {
                "name": "QuantSight",
                "architecture": SYSTEM_ARCHITECTURE_SUMMARY,
                "last_indexed": datetime.utcnow().isoformat() + "Z"
            },
            "routes": self._index_routes(),
            "models": self._index_models(),
            "recent_changes": self._get_recent_changes(days=7)
        }
        
        # Cache to disk
        self._save_cache(kb)
        self._kb_cache = kb
        
        logger.info(f"Knowledge base built: {len(kb['routes'])} routes, {len(kb['models'])} models")
        return kb
    
    def _index_routes(self) -> Dict:
        """Index all FastAPI routes"""
        routes = {}
        
        # Find all route files
        for py_file in self.base_path.rglob("*routes*.py"):
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract @router decorators
                route_pattern = r'@router\.(get|post|put|delete|patch)\(["\']([^"\']+)["\']\)'
                
                for match in re.finditer(route_pattern, content):
                    method, path = match.groups()
                    
                    # Extract function name after decorator
                    func_match = re.search(
                        r'def\s+(\w+)\s*\(',
                        content[match.end():match.end()+200]
                    )
                    
                    handler_name = func_match.group(1) if func_match else "unknown"
                    
                    routes[path] = {
                        "method": method.upper(),
                        "file": str(py_file.relative_to(self.base_path)),
                        "handler": handler_name
                    }
            except Exception as e:
                logger.warning(f"Failed to index {py_file}: {e}")
        
        return routes
    
    def _index_models(self) -> Dict:
        """Index Pydantic models"""
        models = {}
        
        for py_file in self.base_path.rglob("*.py"):
            # Skip __pycache__ and test files
            if "__pycache__" in str(py_file) or "test" in py_file.name:
                continue
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find Pydantic models
                class_pattern = r'class\s+(\w+)\(BaseModel\):'
                
                for match in re.finditer(class_pattern, content):
                    class_name = match.group(1)
                    
                    # Extract fields (basic version)
                    fields = self._extract_model_fields(content, match.end())
                    
                    models[class_name] = {
                        "file": str(py_file.relative_to(self.base_path)),
                        "fields": fields
                    }
            except Exception as e:
                logger.warning(f"Failed to index models in {py_file}: {e}")
        
        return models
    
    def _extract_model_fields(self, content: str, start_pos: int) -> List[str]:
        """Extract field names from Pydantic model"""
        fields = []
        
        # Get next 500 chars
        snippet = content[start_pos:start_pos+500]
        
        # Find field definitions (name: type pattern)
        field_pattern = r'^\s+(\w+):\s*'
        
        for line in snippet.split('\n'):
            match = re.match(field_pattern, line)
            if match:
                fields.append(match.group(1))
            # Stop at next class or function
            if re.match(r'^(class|def)\s+', line):
                break
        
        return fields[:10]  # Limit to first 10 fields
    
    def _get_recent_changes(self, days: int = 7) -> List[Dict]:
        """Get recent git commits"""
        try:
            repo = Repo(".")
            since = datetime.now() - timedelta(days=days)
            
            commits = []
            for commit in repo.iter_commits(since=since.isoformat(), max_count=50):
                # Get changed files
                changed_files = []
                if commit.parents:
                    for item in commit.diff(commit.parents[0]):
                        if item.a_path:
                            changed_files.append(item.a_path)
                
                commits.append({
                    "sha": commit.hexsha[:7],
                    "message": commit.message.strip()[:100],  # Truncate long messages
                    "author": commit.author.name,
                    "date": commit.committed_datetime.isoformat(),
                    "files": changed_files[:10]  # Limit files
                })
            
            return commits
        except Exception as e:
            logger.warning(f"Failed to get git history: {e}")
            return []
    
    def get_context_for_endpoint(self, endpoint: str) -> str:
        """
        Get AI-formatted context for a specific endpoint
        """
        kb = self._load_or_build_kb()
        
        # Find route info
        route = kb.get("routes", {}).get(endpoint)
        
        if not route:
            return f"ENDPOINT: {endpoint}\nSTATUS: Unknown endpoint (not found in route index)\n\n{SYSTEM_ARCHITECTURE_SUMMARY}"
        
        # Find related commits
        related_commits = self._filter_related_commits(
            kb.get("recent_changes", []),
            route["file"]
        )
        
        # Build simple text context
        context = f"""
ENDPOINT: {endpoint}
METHOD: {route['method']}
HANDLER FILE: {route['file']}
HANDLER FUNCTION: {route['handler']}

RECENT CHANGES (Last 7 days):
{self._format_commits(related_commits)}

SYSTEM ARCHITECTURE:
{SYSTEM_ARCHITECTURE_SUMMARY}
"""
        return context.strip()
    
    def _filter_related_commits(self, commits: List[Dict], target_file: str) -> List[Dict]:
        """Filter commits that modified the target file"""
        related = []
        for commit in commits:
            if any(target_file in f for f in commit.get("files", [])):
                related.append(commit)
        return related[:5]  # Max 5 commits
    
    def _format_commits(self, commits: List[Dict]) -> str:
        """Format commits for AI readability"""
        if not commits:
            return "No recent changes detected"
        
        formatted = []
        for commit in commits:
            files_str = ", ".join(commit.get("files", [])[:3])
            formatted.append(
                f"- [{commit['sha']}] {commit['message']} ({commit['author']}) - Files: {files_str}"
            )
        
        return "\n".join(formatted)
    
    def _load_or_build_kb(self) -> Dict:
        """Load cached KB or build new one"""
        # Check memory cache first
        if self._kb_cache:
            return self._kb_cache
        
        # Check disk cache
        if self.cache_file.exists():
            try:
                cache_age = datetime.now() - datetime.fromtimestamp(
                    self.cache_file.stat().st_mtime
                )
                
                if cache_age.seconds < self.cache_ttl:
                    with open(self.cache_file, 'r') as f:
                        self._kb_cache = json.load(f)
                        logger.info("Loaded knowledge base from cache")
                        return self._kb_cache
            except Exception as e:
                logger.warning(f"Failed to load cache: {e}")
        
        # Build new KB
        return self.build_knowledge_base()
    
    def _save_cache(self, kb: Dict):
        """Save KB to disk cache"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, 'w') as f:
                json.dump(kb, f, indent=2)
            logger.info(f"Knowledge base cached to {self.cache_file}")
        except Exception as e:
            logger.warning(f"Failed to save cache: {e}")
