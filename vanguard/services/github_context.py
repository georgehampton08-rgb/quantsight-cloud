"""
GitHub Context Service - Smart Code Fetcher for AI Analysis

Fetches only relevant source files from GitHub to enhance incident analysis
while preventing AI hallucinations by grounding responses in actual code.

Design Principles:
- Fetch max 3 files (focused context)
- Include line numbers for precise references
- Truncate large files to relevant sections
- Always verify code exists before analyzing
"""

import os
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass
import requests

logger = logging.getLogger(__name__)


@dataclass
class CodeContext:
    """Container for GitHub code context"""
    file_path: str
    content: str
    start_line: int
    end_line: int
    recent_commits: List[str]
    
    def format_for_prompt(self) -> str:
        """Format code with line numbers for AI prompt"""
        lines = self.content.split('\n')
        numbered = [
            f"{self.start_line + i}: {line}" 
            for i, line in enumerate(lines)
        ]
        return '\n'.join(numbered)


class GitHubContextFetcher:
    """Smart GitHub file fetcher with anti-hallucination measures"""
    
    # File size limits (3x safety margin under Gemini's 32K limit)
    MAX_FILES = 6  # Increased for deeper context understanding
    MAX_LINES_PER_FILE = 150  # Reduced to fit 6 files
    MAX_TOTAL_TOKENS = 10000  # 32K / 3 = safe budget
    
    # Endpoint to file mapping
    ENDPOINT_MAP = {
        '/vanguard/admin/incidents': 'vanguard/api/admin_routes.py',
        '/vanguard/health': 'vanguard/api/health.py',
        '/vanguard/admin/cron': 'vanguard/api/cron_routes.py',
        '/live/stream': 'services/live_pulse_service_cloud.py',
        '/live/leaders': 'api/public_routes.py',
        '/matchup/lab': 'aegis/matchup_engine.py',
    }
    
    def __init__(self):
        self.token = os.getenv('GITHUB_TOKEN')
        self.repo = os.getenv('GITHUB_REPO', 'georgehampton08-rgb/quantsight-cloud')
        self.branch = os.getenv('GITHUB_BRANCH', 'main')
        self.base_url = f'https://api.github.com/repos/{self.repo}'
        
    def fetch_context(self, endpoint: str, error_type: str) -> List[CodeContext]:
        """
        Fetch relevant code context for an incident
        
        Args:
            endpoint: The failing endpoint (e.g., '/vanguard/admin/incidents')
            error_type: Error type (e.g., 'ImportError', '500', '404')
            
        Returns:
            List of CodeContext objects (max 3)
        """
        if not self.token:
            logger.warning("No GITHUB_TOKEN set - skipping code context")
            return []
            
        try:
            # 1. Map endpoint to primary file
            primary_file = self._get_primary_file(endpoint)
            if not primary_file:
                logger.info(f"No file mapping for endpoint: {endpoint}")
                return []
            
            contexts = []
            
            # 2. Fetch primary file
            primary = self._fetch_file(primary_file)
            if primary:
                contexts.append(primary)
            
            # 3. For ImportError, fetch the imported file
            if error_type == 'ImportError' and primary:
                imported = self._extract_failing_import(primary.content)
                if imported:
                    import_context = self._fetch_file(imported)
                    if import_context:
                        contexts.append(import_context)
            
            # 4. Fetch related config (requirements.txt, Dockerfile) for dependency errors
            if 'ModuleNotFoundError' in error_type or 'ImportError' in error_type:
                req_context = self._fetch_file('requirements.txt', max_lines=50)
                if req_context:
                    contexts.append(req_context)
            
            return contexts[:self.MAX_FILES]
            
        except Exception as e:
            logger.error(f"GitHub context fetch failed: {e}")
            return []
    
    def _get_primary_file(self, endpoint: str) -> Optional[str]:
        """Map endpoint to file path"""
        # Exact match
        if endpoint in self.ENDPOINT_MAP:
            return self.ENDPOINT_MAP[endpoint]
        
        # Prefix match (e.g., /vanguard/admin/incidents/abc -> admin_routes)
        for pattern, file_path in self.ENDPOINT_MAP.items():
            if endpoint.startswith(pattern):
                return file_path
        
        return None
    
    def _fetch_file(
        self, 
        file_path: str, 
        max_lines: Optional[int] = None
    ) -> Optional[CodeContext]:
        """
        Fetch file from GitHub with smart truncation
        
        Args:
            file_path: Path to file in repo
            max_lines: Max lines to return (None = use MAX_LINES_PER_FILE)
            
        Returns:
            CodeContext or None if fetch fails
        """
        max_lines = max_lines or self.MAX_LINES_PER_FILE
        
        try:
            url = f'{self.base_url}/contents/{file_path}?ref={self.branch}'
            headers = {
                'Authorization': f'token {self.token}',
                'Accept': 'application/vnd.github.v3.raw'
            }
            
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code != 200:
                logger.warning(f"File not found: {file_path}")
                return None
            
            content = response.text
            lines = content.split('\n')
            
            # Smart truncation: keep function definitions and error-prone sections
            if len(lines) > max_lines:
                # For now, take first N lines (can be enhanced with AST parsing)
                content = '\n'.join(lines[:max_lines])
                end_line = max_lines
            else:
                end_line = len(lines)
            
            # Fetch recent commits for this file
            commits = self._get_recent_commits(file_path, limit=3)
            
            return CodeContext(
                file_path=file_path,
                content=content,
                start_line=1,
                end_line=end_line,
                recent_commits=commits
            )
            
        except Exception as e:
            logger.error(f"Failed to fetch {file_path}: {e}")
            return None
    
    def _get_recent_commits(self, file_path: str, limit: int = 3) -> List[str]:
        """Get recent commits that modified this file"""
        try:
            url = f'{self.base_url}/commits?path={file_path}&per_page={limit}'
            headers = {'Authorization': f'token {self.token}'}
            
            response = requests.get(url, headers=headers, timeout=5)
            
            if response.status_code != 200:
                return []
            
            commits = response.json()
            # Extract commit messages (split on newline outside f-string to avoid syntax error)
            result = []
            for c in commits:
                commit_msg = c['commit']['message'].split('\n')[0]
                result.append(f"{c['sha'][:7]}: {commit_msg}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to fetch commits for {file_path}: {e}")
            return []
    
    def _extract_failing_import(self, code: str) -> Optional[str]:
        """
        Extract the file path from a failing import statement
        
        Example: 'from vanguard.api import admin' -> 'vanguard/api/admin.py'
        """
        # This is a simplified version - can be enhanced with AST parsing
        import_patterns = [
            'from vanguard.',
            'from services.',
            'from api.',
        ]
        
        for line in code.split('\n'):
            for pattern in import_patterns:
                if pattern in line and 'import' in line:
                    # Extract module path
                    parts = line.split('from')[1].split('import')[0].strip()
                    file_path = parts.replace('.', '/') + '.py'
                    return file_path
        
        return None
