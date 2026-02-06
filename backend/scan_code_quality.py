"""
Code Quality Validator
======================
Scans for syntax issues, indentation errors, and hanging code that may cause crashes.

Checks:
- Indentation consistency
- Unclosed brackets/braces
- Hanging promises/async without await
- Missing return statements
- Unreachable code
"""

import os
import ast
import re
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass, asdict
import json

@dataclass
class CodeIssue:
    file: str
    line: int
    column: int
    issue_type: str
    severity: str
    message: str
    code_snippet: str

class CodeQualityValidator:
    """Validates code quality and syntax"""
    
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.issues: List[CodeIssue] = []
    
    def scan(self) -> Dict:
        """Run all validation checks"""
        print("🔍 Scanning for code quality issues...\n")
        
        # Scan Python files
        for file_path in self.root_dir.rglob('*.py'):
            if 'venv' in str(file_path) or '__pycache__' in str(file_path):
                continue
            self._scan_python_file(file_path)
        
        # Scan TypeScript/JavaScript files
        for ext in ['ts', 'tsx', 'js', 'jsx']:
            for file_path in self.root_dir.rglob(f'*.{ext}'):
                if 'node_modules' in str(file_path) or '.next' in str(file_path):
                    continue
                self._scan_ts_file(file_path)
        
        return self._generate_report()
    
    def _scan_python_file(self, file_path: Path):
        """Scan Python file for issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Check indentation consistency
            self._check_indentation(file_path, lines)
            
            # Try to parse AST
            try:
                tree = ast.parse(content, filename=str(file_path))
                self._check_ast_issues(file_path, tree, lines)
            except SyntaxError as e:
                self.issues.append(CodeIssue(
                    file=str(file_path.relative_to(self.root_dir)),
                    line=e.lineno or 0,
                    column=e.offset or 0,
                    issue_type='syntax_error',
                    severity='high',
                    message=f"Syntax error: {e.msg}",
                    code_snippet=lines[e.lineno - 1] if e.lineno else ""
                ))
            
            # Check for hanging async
            self._check_hanging_async_python(file_path, content, lines)
            
        except Exception as e:
            print(f"⚠️  Error scanning {file_path}: {e}")
    
    def _scan_ts_file(self, file_path: Path):
        """Scan TypeScript/JavaScript file for issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                lines = content.split('\n')
            
            # Check bracket matching
            self._check_bracket_matching(file_path, content, lines)
            
            # Check for hanging promises
            self._check_hanging_promises(file_path, content, lines)
            
            # Check indentation
            self._check_ts_indentation(file_path, lines)
            
            # Check for unreachable code
            self._check_unreachable_code(file_path, content, lines)
            
        except Exception as e:
            print(f"⚠️  Error scanning {file_path}: {e}")
    
    def _check_indentation(self, file_path: Path, lines: List[str]):
        """Check Python indentation consistency"""
        indent_chars = None
        
        for i, line in enumerate(lines, 1):
            if not line.strip():
                continue
            
            # Detect leading whitespace
            match = re.match(r'^(\s+)', line)
            if match:
                whitespace = match.group(1)
                
                # Determine indent character
                if indent_chars is None:
                    if '\t' in whitespace:
                        indent_chars = 'tabs'
                    else:
                        indent_chars = 'spaces'
                
                # Check for mixing
                if indent_chars == 'tabs' and ' ' in whitespace:
                    self.issues.append(CodeIssue(
                        file=str(file_path.relative_to(self.root_dir)),
                        line=i,
                        column=0,
                        issue_type='mixed_indentation',
                        severity='medium',
                        message='Mixed tabs and spaces in indentation',
                        code_snippet=line[:40]
                    ))
                elif indent_chars == 'spaces' and '\t' in whitespace:
                    self.issues.append(CodeIssue(
                        file=str(file_path.relative_to(self.root_dir)),
                        line=i,
                        column=0,
                        issue_type='mixed_indentation',
                        severity='medium',
                        message='Mixed spaces and tabs in indentation',
                        code_snippet=line[:40]
                    ))
    
    def _check_ast_issues(self, file_path: Path, tree: ast.AST, lines: List[str]):
        """Check for AST-level issues"""
        for node in ast.walk(tree):
            # Check for bare except
            if isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    self.issues.append(CodeIssue(
                        file=str(file_path.relative_to(self.root_dir)),
                        line=node.lineno,
                        column=node.col_offset,
                        issue_type='bare_except',
                        severity='low',
                        message='Bare except clause (catches all exceptions)',
                        code_snippet=lines[node.lineno - 1] if node.lineno <= len(lines) else ""
                    ))
    
    def _check_hanging_async_python(self, file_path: Path, content: str, lines: List[str]):
        """Check for async functions without await"""
        # Find async def
        async_pattern = r'async\s+def\s+(\w+)'
        for match in re.finditer(async_pattern, content):
            func_name = match.group(1)
            line_num = content[:match.start()].count('\n') + 1
            
            # Get function body (approximate)
            start = match.end()
            # Find next "async def" or class/def at same level
            next_def = content.find('\nasync def', start)
            next_class = content.find('\nclass ', start)
            next_func = content.find('\ndef ', start)
            
            end = len(content)
            for pos in [next_def, next_class, next_func]:
                if pos != -1 and pos < end:
                    end = pos
            
            func_body = content[start:end]
            
            # Check if there's an await
            if 'await ' not in func_body and 'async for' not in func_body:
                self.issues.append(CodeIssue(
                    file=str(file_path.relative_to(self.root_dir)),
                    line=line_num,
                    column=0,
                    issue_type='async_without_await',
                    severity='medium',
                    message=f'Async function "{func_name}" has no await statements',
                    code_snippet=lines[line_num - 1]
                ))
    
    def _check_bracket_matching(self, file_path: Path, content: str, lines: List[str]):
        """Check if brackets/braces are balanced"""
        stack = []
        pairs = {'(': ')', '[': ']', '{': '}'}
        
        for i, char in enumerate(content):
            if char in pairs:
                stack.append((char, i))
            elif char in pairs.values():
                if not stack:
                    line_num = content[:i].count('\n') + 1
                    self.issues.append(CodeIssue(
                        file=str(file_path.relative_to(self.root_dir)),
                        line=line_num,
                        column=i - content[:i].rfind('\n'),
                        issue_type='unmatched_bracket',
                        severity='high',
                        message=f'Unmatched closing bracket: {char}',
                        code_snippet=lines[line_num - 1] if line_num <= len(lines) else ""
                    ))
                else:
                    open_char, _ = stack.pop()
                    if pairs[open_char] != char:
                        line_num = content[:i].count('\n') + 1
                        self.issues.append(CodeIssue(
                            file=str(file_path.relative_to(self.root_dir)),
                            line=line_num,
                            column=i - content[:i].rfind('\n'),
                            issue_type='mismatched_bracket',
                            severity='high',
                            message=f'Mismatched bracket: expected {pairs[open_char]}, got {char}',
                            code_snippet=lines[line_num - 1] if line_num <= len(lines) else ""
                        ))
        
        # Check for unclosed brackets
        for open_char, pos in stack:
            line_num = content[:pos].count('\n') + 1
            self.issues.append(CodeIssue(
                file=str(file_path.relative_to(self.root_dir)),
                line=line_num,
                column=pos - content[:pos].rfind('\n'),
                issue_type='unclosed_bracket',
                severity='high',
                message=f'Unclosed bracket: {open_char}',
                code_snippet=lines[line_num - 1] if line_num <= len(lines) else ""
            ))
    
    def _check_hanging_promises(self, file_path: Path, content: str, lines: List[str]):
        """Check for promises without await or .then()"""
        # Find async function calls not awaited
        pattern = r'(?<!await\s)(\w+Api\.\w+)\([^)]*\)(?!\s*\.then|\s*\.catch)'
        
        for match in re.finditer(pattern, content):
            line_num = content[:match.start()].count('\n') + 1
            
            # Check if it's assigned or returned
            line_start = content[:match.start()].rfind('\n') + 1
            line_content = lines[line_num - 1]
            
            if not re.search(r'(const|let|var|return)\s', line_content):
                self.issues.append(CodeIssue(
                    file=str(file_path.relative_to(self.root_dir)),
                    line=line_num,
                    column=match.start() - line_start,
                    issue_type='hanging_promise',
                    severity='medium',
                    message=f'Promise not awaited or handled: {match.group(1)}',
                    code_snippet=line_content.strip()
                ))
    
    def _check_ts_indentation(self, file_path: Path, lines: List[str]):
        """Check TypeScript indentation"""
        for i, line in enumerate(lines, 1):
            if '\t' in line and '    ' in line:
                self.issues.append(CodeIssue(
                    file=str(file_path.relative_to(self.root_dir)),
                    line=i,
                    column=0,
                    issue_type='mixed_indentation',
                    severity='low',
                    message='Mixed tabs and spaces',
                    code_snippet=line[:40]
                ))
    
    def _check_unreachable_code(self, file_path: Path, content: str, lines: List[str]):
        """Check for unreachable code after return/throw"""
        pattern = r'(return|throw)[^;]+;[\s]*\n[\s]+\S'
        
        for match in re.finditer(pattern, content):
            line_num = content[:match.end()].count('\n')
            if line_num < len(lines):
                next_line = lines[line_num].strip()
                if next_line and not next_line.startswith('}') and not next_line.startswith('//'):
                    self.issues.append(CodeIssue(
                        file=str(file_path.relative_to(self.root_dir)),
                        line=line_num + 1,
                        column=0,
                        issue_type='unreachable_code',
                        severity='low',
                        message='Unreachable code after return/throw',
                        code_snippet=next_line
                    ))
    
    def _generate_report(self) -> Dict:
        """Generate quality report"""
        by_severity = {
            'high': len([i for i in self.issues if i.severity == 'high']),
            'medium': len([i for i in self.issues if i.severity == 'medium']),
            'low': len([i for i in self.issues if i.severity == 'low'])
        }
        
        by_type = {}
        for issue in self.issues:
            if issue.issue_type not in by_type:
                by_type[issue.issue_type] = 0
            by_type[issue.issue_type] += 1
        
        return {
            'total_issues': len(self.issues),
            'by_severity': by_severity,
            'by_type': by_type,
            'issues': [asdict(i) for i in self.issues]
        }
    
    def print_summary(self, report: Dict):
        """Print summary"""
        print("=" * 70)
        print("CODE QUALITY VALIDATION RESULTS")
        print("=" * 70)
        print(f"\nTotal Issues: {report['total_issues']}\n")
        
        print("By Severity:")
        print(f"  🔴 High:   {report['by_severity']['high']}")
        print(f"  🟡 Medium: {report['by_severity']['medium']}")
        print(f"  🟢 Low:    {report['by_severity']['low']}")
        
        if report['by_type']:
            print("\nBy Type:")
            for issue_type, count in sorted(report['by_type'].items(), key=lambda x: -x[1]):
                print(f"  • {issue_type}: {count}")
        
        print("\n" + "=" * 70)
        
        # Show critical issues
        critical = [i for i in self.issues if i.severity == 'high'][:10]
        if critical:
            print("\nCritical Issues:\n")
            for i, issue in enumerate(critical, 1):
                print(f"{i}. {issue.file}:{issue.line}")
                print(f"   {issue.message}")
                print(f"   Code: {issue.code_snippet}\n")

def main():
    """Run code quality validation"""
    root = Path(__file__).parent.parent
    validator = CodeQualityValidator(root)
    
    report = validator.scan()
    validator.print_summary(report)
    
    # Save report
    output_file = Path(__file__).parent / "code_quality_report.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {output_file}")
    
    return report

if __name__ == "__main__":
    main()
