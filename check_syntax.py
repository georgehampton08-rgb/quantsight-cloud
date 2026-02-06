#!/usr/bin/env python3
"""
Comprehensive Python Syntax Checker
Validates all .py files in the codebase for syntax errors
"""

import ast
import os
import sys
from pathlib import Path
from typing import List, Tuple, Dict
import traceback


class SyntaxChecker:
    """Validates Python files for syntax errors"""
    
    def __init__(self, root_dir: str):
        self.root_dir = Path(root_dir)
        self.errors: List[Dict] = []
        self.checked_files = 0
        self.error_files = 0
        
    def check_file(self, file_path: Path) -> bool:
        """
        Check a single Python file for syntax errors
        
        Returns:
            True if file is valid, False if errors found
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                source = f.read()
            
            # Attempt to parse the file
            ast.parse(source, filename=str(file_path))
            return True
            
        except SyntaxError as e:
            self.errors.append({
                'file': str(file_path.relative_to(self.root_dir)),
                'type': 'SyntaxError',
                'line': e.lineno,
                'offset': e.offset,
                'message': e.msg,
                'text': e.text.strip() if e.text else None
            })
            return False
            
        except Exception as e:
            self.errors.append({
                'file': str(file_path.relative_to(self.root_dir)),
                'type': type(e).__name__,
                'line': None,
                'offset': None,
                'message': str(e),
                'text': None
            })
            return False
    
    def scan_directory(self, exclude_dirs: List[str] = None) -> None:
        """
        Recursively scan directory for Python files
        
        Args:
            exclude_dirs: List of directory names to skip
        """
        exclude_dirs = exclude_dirs or [
            '__pycache__', 
            '.git', 
            'node_modules', 
            'venv',
            '.venv',
            'build',
            'dist',
            '.pytest_cache'
        ]
        
        for py_file in self.root_dir.rglob('*.py'):
            # Skip excluded directories
            if any(excluded in py_file.parts for excluded in exclude_dirs):
                continue
            
            self.checked_files += 1
            if not self.check_file(py_file):
                self.error_files += 1
    
    def report(self) -> int:
        """
        Print report and return exit code
        
        Returns:
            0 if no errors, 1 if errors found
        """
        print(f"\n{'='*80}")
        print(f"Python Syntax Check Report")
        print(f"{'='*80}\n")
        print(f"📁 Root directory: {self.root_dir}")
        print(f"✅ Files checked: {self.checked_files}")
        print(f"❌ Files with errors: {self.error_files}")
        print(f"{'='*80}\n")
        
        if not self.errors:
            print("✅ All files passed syntax check!")
            return 0
        
        # Group errors by file
        errors_by_file = {}
        for error in self.errors:
            file = error['file']
            if file not in errors_by_file:
                errors_by_file[file] = []
            errors_by_file[file].append(error)
        
        # Print detailed error report
        for file, file_errors in sorted(errors_by_file.items()):
            print(f"\n❌ {file}")
            print("-" * 80)
            
            for error in file_errors:
                print(f"  Line {error['line']}: {error['type']}")
                print(f"  Message: {error['message']}")
                
                if error['text']:
                    print(f"  Code: {error['text']}")
                    if error['offset']:
                        print(f"        {' ' * (error['offset'] - 1)}^")
                print()
        
        print(f"{'='*80}")
        print(f"❌ Found {len(self.errors)} syntax error(s) in {self.error_files} file(s)")
        print(f"{'='*80}\n")
        
        return 1


def main():
    """Main entry point"""
    # Determine root directory
    if len(sys.argv) > 1:
        root_dir = sys.argv[1]
    else:
        # Default to backend directory
        root_dir = Path(__file__).parent / 'backend'
        if not root_dir.exists():
            root_dir = Path(__file__).parent
    
    print(f"🔍 Checking Python syntax in: {root_dir}")
    print(f"{'='*80}\n")
    
    checker = SyntaxChecker(str(root_dir))
    checker.scan_directory()
    
    return checker.report()


if __name__ == '__main__':
    sys.exit(main())
