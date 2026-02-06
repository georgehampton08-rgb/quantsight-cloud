#!/usr/bin/env python3
"""
AI Model Update Script
======================
Updates all Gemini model references across the codebase to use a consistent model.

Usage:
    python update_ai_models.py                    # Dry run, shows what would change
    python update_ai_models.py --apply            # Apply changes
    python update_ai_models.py --model gemini-2.0-flash --apply  # Change to specific model
"""
import os
import re
import argparse
from pathlib import Path

# Default target model
DEFAULT_TARGET_MODEL = 'gemini-1.5-flash'

# Patterns to find and replace
MODEL_PATTERNS = [
    # Direct model strings
    (r"'gemini-2\.0-flash-exp'", "'{model}'"),
    (r'"gemini-2\.0-flash-exp"', '"{model}"'),
    (r"'gemini-2\.0-flash'", "'{model}'"),
    (r'"gemini-2\.0-flash"', '"{model}"'),
    (r"'gemini-pro'", "'{model}'"),
    (r'"gemini-pro"', '"{model}"'),
    (r"'gemini-2\.5-flash-lite'", "'{model}'"),
    (r'"gemini-2\.5-flash-lite"', '"{model}"'),
]

# Files to skip
SKIP_FILES = [
    'update_ai_models.py',
    'ai_models.py',
    'list_gemini_models.py',
]

# Directories to skip
SKIP_DIRS = [
    '__pycache__',
    '.git',
    'node_modules',
    'venv',
    '.venv',
]


def find_python_files(root_dir: str) -> list:
    """Find all Python files in the directory tree."""
    py_files = []
    for path in Path(root_dir).rglob('*.py'):
        # Skip certain directories  
        if any(skip in str(path) for skip in SKIP_DIRS):
            continue
        # Skip certain files
        if path.name in SKIP_FILES:
            continue
        py_files.append(path)
    return py_files


def find_model_references(file_path: Path) -> list:
    """Find all model references in a file."""
    matches = []
    try:
        content = file_path.read_text(encoding='utf-8')
        for pattern, _ in MODEL_PATTERNS:
            for match in re.finditer(pattern, content):
                line_num = content[:match.start()].count('\n') + 1
                matches.append({
                    'file': str(file_path),
                    'line': line_num,
                    'match': match.group(),
                    'pattern': pattern
                })
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
    return matches


def update_file(file_path: Path, target_model: str, dry_run: bool = True) -> int:
    """Update model references in a file."""
    changes = 0
    try:
        content = file_path.read_text(encoding='utf-8')
        new_content = content
        
        for pattern, replacement in MODEL_PATTERNS:
            replacement_str = replacement.format(model=target_model)
            new_content, count = re.subn(pattern, replacement_str, new_content)
            changes += count
        
        if changes > 0 and not dry_run:
            file_path.write_text(new_content, encoding='utf-8')
            
    except Exception as e:
        print(f"Error updating {file_path}: {e}")
    
    return changes


def main():
    parser = argparse.ArgumentParser(description='Update AI model references')
    parser.add_argument('--model', default=DEFAULT_TARGET_MODEL, 
                       help=f'Target model (default: {DEFAULT_TARGET_MODEL})')
    parser.add_argument('--apply', action='store_true',
                       help='Apply changes (default is dry run)')
    parser.add_argument('--dir', default='.',
                       help='Root directory to search')
    args = parser.parse_args()
    
    print("=" * 60)
    print("AI MODEL UPDATE SCRIPT")
    print("=" * 60)
    print(f"Target model: {args.model}")
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Directory: {os.path.abspath(args.dir)}")
    print("=" * 60)
    
    # Find all Python files
    py_files = find_python_files(args.dir)
    print(f"\nScanning {len(py_files)} Python files...")
    
    # Find all model references
    all_matches = []
    for f in py_files:
        matches = find_model_references(f)
        all_matches.extend(matches)
    
    if not all_matches:
        print("\n✅ No model references found that need updating!")
        return
    
    # Group by file
    by_file = {}
    for m in all_matches:
        f = m['file']
        if f not in by_file:
            by_file[f] = []
        by_file[f].append(m)
    
    print(f"\nFound {len(all_matches)} references in {len(by_file)} files:\n")
    
    total_changes = 0
    for file_path, matches in by_file.items():
        rel_path = os.path.relpath(file_path, args.dir)
        print(f"📄 {rel_path}")
        for m in matches:
            print(f"   Line {m['line']}: {m['match']}")
        
        if args.apply:
            changes = update_file(Path(file_path), args.model, dry_run=False)
            total_changes += changes
            print(f"   ✅ Updated {changes} reference(s)")
        else:
            print(f"   ⚠️  Would update {len(matches)} reference(s)")
        print()
    
    print("=" * 60)
    if args.apply:
        print(f"✅ DONE: Updated {total_changes} references to {args.model}")
    else:
        print(f"ℹ️  DRY RUN: Would update {len(all_matches)} references")
        print(f"   Run with --apply to make changes")
    print("=" * 60)


if __name__ == '__main__':
    main()
