"""
Endpoint Migration Scanner
==========================
Scans codebase for direct API calls that should use Aegis router or Nexus Hub.

Identifies:
- Direct fetch() calls to NBA API
- Legacy /player/ endpoints that should use /aegis/player
- Simulation calls that should use runPatientSimulation
- Health checks that should use Nexus health
"""

import os
import re
import json
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass, asdict

@dataclass
class EndpointIssue:
    file: str
    line: int
    column: int
    issue_type: str
    current_code: str
    suggested_fix: str
    severity: str  # 'high', 'medium', 'low'
    reason: str

class EndpointMigrationScanner:
    """Scans for legacy endpoint usage"""
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.issues: List[EndpointIssue] = []
        
        # Patterns to detect
        self.patterns = {
            # Direct NBA API calls (should go through Aegis/Nexus)
            'direct_nba_api': {
                'pattern': r'fetch\([\'"]https?://stats\.nba\.com',
                'severity': 'high',
                'suggestion': 'Use AegisApi with circuit breaker protection'
            },
            
            # Legacy player endpoints
            'legacy_player': {
                'pattern': r'fetch\([\'"].*?/player/\{?[\w_]+\}?[\'"]',
                'severity': 'high',
                'suggestion': 'Replace with /aegis/player/{player_id}'
            },
            
            # Direct simulation without patience
            'legacy_simulation': {
                'pattern': r'\.runSimulation\(',
                'severity': 'medium',
                'suggestion': 'Consider using runPatientSimulation for better UX'
            },
            
            # Health checks not using Nexus
            'legacy_health': {
                'pattern': r'fetch\([\'"].*?/health[\'"]',
                'severity': 'low',
                'suggestion': 'Consider using NexusApi.getHealth() for unified monitoring'
            },
            
            # Rate limit unprotected calls
            'no_rate_limit': {
                'pattern': r'fetch\([\'"].*?/simulate',
                'severity': 'high',
                'suggestion': 'Wrap in try-catch and check for 429 response'
            },
            
            # Missing error handlers
            'missing_catch': {
                'pattern': r'await fetch\([^\)]+\)[^;]*;(?!\s*\.catch|\s*}\s*catch)',
                'severity': 'medium',
                'suggestion': 'Add .catch() or try-catch for error handling'
            }
        }
    
    def scan(self) -> Dict[str, any]:
        """Scan all relevant files"""
        print("🔍 Scanning codebase for endpoint migration issues...\n")
        
        # Scan TypeScript/JavaScript files
        for ext in ['ts', 'tsx', 'js', 'jsx']:
            for file_path in self.root_dir.rglob(f'*.{ext}'):
                if 'node_modules' in str(file_path) or '.next' in str(file_path):
                    continue
                self._scan_file(file_path)
        
        # Scan Python files for backend
        for file_path in self.root_dir.rglob('*.py'):
            if 'venv' in str(file_path) or '__pycache__' in str(file_path):
                continue
            self._scan_python_file(file_path)
        
        return self._generate_report()
    
    def _scan_file(self, file_path: Path):
        """Scan a single TypeScript/JavaScript file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            for pattern_name, pattern_info in self.patterns.items():
                matches = re.finditer(pattern_info['pattern'], content, re.MULTILINE)
                
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    col = match.start() - content[:match.start()].rfind('\n')
                    
                    # Get surrounding context
                    start_line = max(0, line_num - 2)
                    end_line = min(len(lines), line_num + 2)
                    context = '\n'.join(lines[start_line:end_line])
                    
                    self.issues.append(EndpointIssue(
                        file=str(file_path.relative_to(self.root_dir)),
                        line=line_num,
                        column=col,
                        issue_type=pattern_name,
                        current_code=match.group(0),
                        suggested_fix=pattern_info['suggestion'],
                        severity=pattern_info['severity'],
                        reason=f"Line {line_num}: {pattern_name}"
                    ))
        
        except Exception as e:
            print(f"⚠️  Error scanning {file_path}: {e}")
    
    def _scan_python_file(self, file_path: Path):
        """Scan Python file for direct API calls"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Check for direct requests without circuit breaker
            pattern = r'requests\.(get|post)\([\'"]https?://stats\.nba\.com'
            matches = re.finditer(pattern, content, re.MULTILINE)
            
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                
                # Check if circuit breaker is used nearby
                start = max(0, match.start() - 500)
                end = min(len(content), match.end() + 500)
                context = content[start:end]
                
                if '@breaker.call()' not in context and 'circuit_breaker' not in context:
                    self.issues.append(EndpointIssue(
                        file=str(file_path.relative_to(self.root_dir)),
                        line=line_num,
                        column=0,
                        issue_type='no_circuit_breaker',
                        current_code=match.group(0),
                        suggested_fix='Wrap NBA API calls with circuit breaker (@breaker.call())',
                        severity='high',
                        reason=f'Direct NBA API call without circuit breaker protection'
                    ))
        
        except Exception as e:
            print(f"⚠️  Error scanning {file_path}: {e}")
    
    def _generate_report(self) -> Dict:
        """Generate migration report"""
        # Group by severity
        by_severity = {
            'high': [i for i in self.issues if i.severity == 'high'],
            'medium': [i for i in self.issues if i.severity == 'medium'],
            'low': [i for i in self.issues if i.severity == 'low']
        }
        
        # Group by type
        by_type = {}
        for issue in self.issues:
            if issue.issue_type not in by_type:
                by_type[issue.issue_type] = []
            by_type[issue.issue_type].append(issue)
        
        report = {
            'total_issues': len(self.issues),
            'by_severity': {
                'high': len(by_severity['high']),
                'medium': len(by_severity['medium']),
                'low': len(by_severity['low'])
            },
            'by_type': {k: len(v) for k, v in by_type.items()},
            'issues': [asdict(i) for i in self.issues]
        }
        
        return report
    
    def print_summary(self, report: Dict):
        """Print human-readable summary"""
        print("=" * 70)
        print("ENDPOINT MIGRATION SCAN RESULTS")
        print("=" * 70)
        print(f"\nTotal Issues Found: {report['total_issues']}\n")
        
        print("By Severity:")
        print(f"  🔴 High:   {report['by_severity']['high']}")
        print(f"  🟡 Medium: {report['by_severity']['medium']}")
        print(f"  🟢 Low:    {report['by_severity']['low']}")
        
        print("\nBy Type:")
        for issue_type, count in report['by_type'].items():
            print(f"  • {issue_type}: {count}")
        
        print("\n" + "=" * 70)
        
        # Show first 10 high severity issues
        high_issues = [i for i in self.issues if i.severity == 'high'][:10]
        if high_issues:
            print("\nTop High-Severity Issues:\n")
            for i, issue in enumerate(high_issues, 1):
                print(f"{i}. {issue.file}:{issue.line}")
                print(f"   Type: {issue.issue_type}")
                print(f"   Code: {issue.current_code}")
                print(f"   Fix:  {issue.suggested_fix}\n")


def main():
    """Run endpoint migration scan"""
    root = Path(__file__).parent.parent
    scanner = EndpointMigrationScanner(root)
    
    report = scanner.scan()
    scanner.print_summary(report)
    
    # Save detailed report
    output_file = Path(__file__).parent / "endpoint_migration_report.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {output_file}")
    
    return report


if __name__ == "__main__":
    main()
