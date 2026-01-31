
import os
import sys
import ast
import csv
import logging
from pathlib import Path
from typing import List, Dict, Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

class CodebaseIntegrityScanner:
    """
    Scans codebase for syntax errors, missing columns, and dangerous patterns.
    Ensures 'each item gets its own unique check' via modular validators.
    """
    
    FORBIDDEN_PATTERNS = [
        "2024-25", # Should use config.CURRENT_SEASON
        "2023-24",
        "seed=42", # Should be random
    ]
    
    REQUIRED_CSV_COLUMNS = {
        'games.csv': ['game_id', 'game_date', 'pts', 'reb', 'ast'],
        'schedule.csv': ['game_id', 'home', 'away', 'date']
    }
    
    def __init__(self, root_dir: str, output_file: str = "integrity_report.log"):
        self.root_dir = Path(root_dir)
        self.output_file = Path(output_file)
        self.issues = []
        self.stats = {'files_scanned': 0, 'errors_found': 0}

    def scan(self):
        """Run all scan modules"""
        print(f"Starting Integrity Scan on: {self.root_dir}")
        
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                file_path = Path(root) / file
                
                # Skip virtual envs and git
                if 'venv' in str(file_path) or '.git' in str(file_path) or '__pycache__' in str(file_path):
                    continue
                
                self.stats['files_scanned'] += 1
                
                if file.endswith('.py'):
                    self.check_python_syntax(file_path)
                    self.check_forbidden_patterns(file_path)
                elif file.endswith('.csv'):
                    self.check_csv_integrity(file_path)
                    
        self.report()

    def check_python_syntax(self, file_path: Path):
        """Check for syntax errors using AST parse"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            ast.parse(content)
        except SyntaxError as e:
            self.log_issue("SYNTAX_ERROR", f"{file_path}: {e}")
        except Exception as e:
            self.log_issue("READ_ERROR", f"{file_path}: {e}")

    def check_forbidden_patterns(self, file_path: Path):
        """Check for hardcoded strings that should be config variables"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for i, line in enumerate(f, 1):
                    for pattern in self.FORBIDDEN_PATTERNS:
                        if pattern in line:
                            # Allow config.py itself to define strings
                            if 'config.py' in str(file_path): 
                                continue
                            self.log_issue("FORBIDDEN_PATTERN", f"{file_path}:{i} contains '{pattern}'")
        except Exception:
            pass

    def check_csv_integrity(self, file_path: Path):
        """Check for required columns in data files"""
        # Determine strictness based on filename
        expected_cols = None
        for key, cols in self.REQUIRED_CSV_COLUMNS.items():
            if str(file_path).endswith(key):
                expected_cols = cols
                break
        
        if not expected_cols:
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                header = next(reader, None)
                if not header:
                    self.log_issue("EMPTY_CSV", f"{file_path} has no header")
                    return
                
                missing = [c for c in expected_cols if c not in header]
                if missing:
                    self.log_issue("MISSING_COLUMNS", f"{file_path} missing: {missing}")
        except Exception as e:
            self.log_issue("CSV_ERROR", f"{file_path}: {e}")

    def log_issue(self, error_type: str, message: str):
        self.issues.append(f"[{error_type}] {message}")
        self.stats['errors_found'] += 1

    def report(self):
        report_lines = []
        report_lines.append("\n" + "="*50)
        report_lines.append("INTEGRITY SCAN REPORT")
        report_lines.append("="*50)
        report_lines.append(f"Files Scanned: {self.stats['files_scanned']}")
        report_lines.append(f"Issues Found:  {self.stats['errors_found']}")
        report_lines.append("-"*50)
        
        if self.issues:
            for issue in self.issues:
                report_lines.append(issue)
        else:
            report_lines.append("No integrity issues found.")
        report_lines.append("="*50)
        
        # Write to file and print
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            print(f"Report written to {self.output_file}")
        except Exception as e:
            print(f"Failed to write report: {e}")
            
        # Print summary only
        print('\n'.join(report_lines[:6]))
        if self.issues:
            print(f"See {self.output_file} for full details.")

if __name__ == "__main__":
    scanner = CodebaseIntegrityScanner(os.getcwd())
    scanner.scan()
