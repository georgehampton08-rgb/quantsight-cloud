"""
Code Validation Script - Syntax & Case Sensitivity Check
=========================================================
Validates all Python files for syntax errors and common case-sensitivity issues.
"""
import os
import sys
import ast
import re
from pathlib import Path
from typing import List, Tuple, Dict

# Common case-sensitivity issues to check
CASE_PATTERNS = [
    # Firebase/Firestore
    (r'\bfirebase\b', 'firebase', 'Should be lowercase'),
    (r'\bFireStore\b', 'FireStore', 'Should be Firestore'),
    (r'\bFIRESTORE\b', 'FIRESTORE', 'Should be Firestore'),
    
    # API endpoints
    (r'"/[A-Z][a-z]+/', 'Capitalized path', 'Endpoints should be lowercase'),
    
    # Team abbreviations (should be uppercase)
    (r"team_abbreviation\s*==\s*['\"](?!.*[A-Z])", 'lowercase team', 'Team abbreviations should be uppercase'),
    
    # Boolean values
    (r'\bTrue\b', None, None),  # Correct
    (r'\btrue\b(?!:)', 'true', 'Should be True in Python'),
    (r'\bFalse\b', None, None),  # Correct
    (r'\bfalse\b(?!:)', 'false', 'Should be False in Python'),
    
    # None checks
    (r'\bNone\b', None, None),  # Correct
    (r'\bnull\b', 'null', 'Should be None in Python'),
    (r'\bNULL\b', 'NULL', 'Should be None in Python'),
]

def check_syntax(filepath: str) -> Tuple[bool, str]:
    """Check Python syntax of a file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
        ast.parse(source)
        return True, "OK"
    except SyntaxError as e:
        return False, f"Line {e.lineno}: {e.msg}"
    except Exception as e:
        return False, str(e)

def check_case_sensitivity(filepath: str) -> List[Dict]:
    """Check for common case-sensitivity issues."""
    issues = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        for line_num, line in enumerate(lines, 1):
            # Skip comments
            if line.strip().startswith('#'):
                continue
            
            for pattern, found_text, message in CASE_PATTERNS:
                if message is None:
                    continue  # Pattern is correct, skip
                
                matches = re.findall(pattern, line, re.IGNORECASE)
                if matches:
                    # Check if it's actually wrong case
                    actual_matches = re.findall(pattern, line)
                    if actual_matches:
                        issues.append({
                            'line': line_num,
                            'found': found_text or str(matches[0]),
                            'message': message,
                            'context': line.strip()[:80]
                        })
    except Exception as e:
        issues.append({'line': 0, 'found': 'Error', 'message': str(e), 'context': ''})
    
    return issues

def validate_directory(directory: str, exclude_dirs: List[str] = None) -> Dict:
    """Validate all Python files in a directory."""
    exclude_dirs = exclude_dirs or ['__pycache__', '.git', 'venv', 'node_modules']
    
    results = {
        'syntax_errors': [],
        'case_issues': [],
        'files_checked': 0,
        'files_passed': 0,
    }
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, directory)
                results['files_checked'] += 1
                
                # Check syntax
                syntax_ok, syntax_msg = check_syntax(filepath)
                if not syntax_ok:
                    results['syntax_errors'].append({
                        'file': rel_path,
                        'error': syntax_msg
                    })
                else:
                    # Check case sensitivity only if syntax is OK
                    case_issues = check_case_sensitivity(filepath)
                    if case_issues:
                        results['case_issues'].append({
                            'file': rel_path,
                            'issues': case_issues
                        })
                    else:
                        results['files_passed'] += 1
    
    return results

def main():
    """Run validation on the cloud backend."""
    print("=" * 60)
    print("Code Validation - Syntax & Case Sensitivity Check")
    print("=" * 60)
    
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    print(f"\nScanning: {backend_dir}")
    
    results = validate_directory(backend_dir)
    
    print(f"\n📊 Results:")
    print(f"  Files checked: {results['files_checked']}")
    print(f"  Files passed: {results['files_passed']}")
    print(f"  Syntax errors: {len(results['syntax_errors'])}")
    print(f"  Case issues: {len(results['case_issues'])}")
    
    # Report syntax errors
    if results['syntax_errors']:
        print(f"\n❌ SYNTAX ERRORS ({len(results['syntax_errors'])}):")
        for err in results['syntax_errors']:
            print(f"  {err['file']}: {err['error']}")
    
    # Report case issues
    if results['case_issues']:
        print(f"\n⚠️ CASE SENSITIVITY ISSUES ({len(results['case_issues'])} files):")
        for file_issues in results['case_issues'][:10]:  # Limit output
            print(f"\n  📄 {file_issues['file']}:")
            for issue in file_issues['issues'][:5]:
                print(f"    Line {issue['line']}: {issue['message']}")
                print(f"      Found: {issue['found']}")
    
    # Summary
    if not results['syntax_errors'] and not results['case_issues']:
        print("\n✅ All checks passed!")
        return 0
    else:
        print(f"\n⚠️ Issues found - review and fix above")
        return 1

if __name__ == "__main__":
    sys.exit(main())
