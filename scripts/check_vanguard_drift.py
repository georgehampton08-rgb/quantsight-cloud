"""
Vanguard Duplicate Tree Drift Guard
=====================================
Compares vanguard/ (primary) and backend/vanguard/ (deployed copy)
file-by-file.  Reports: IDENTICAL, MODIFIED, PRIMARY_ONLY, BACKEND_ONLY.

Usage:
    python scripts/check_vanguard_drift.py
"""
import difflib
import sys
import io
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
PRIMARY = ROOT / "vanguard"
BACKEND = ROOT / "backend" / "vanguard"

# Files / directories that are expected to differ (not a drift concern)
KNOWN_DIFFS = {
    # backend has an extra config import in ai_analyzer.py
    "__init__.py",  # package inits may differ
}


def collect_py_files(base: Path):
    """Return set of relative .py file paths under base."""
    return {p.relative_to(base) for p in base.rglob("*.py")}


def files_match(a: Path, b: Path) -> bool:
    """Return True if file contents are identical."""
    return a.read_bytes() == b.read_bytes()


def show_diff_summary(a: Path, b: Path, rel: Path):
    """Print a short unified diff summary (max 20 lines)."""
    try:
        a_lines = a.read_text(encoding="utf-8", errors="replace").splitlines()
        b_lines = b.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        print(f"    (could not read files for diff)")
        return

    diff = list(difflib.unified_diff(
        a_lines, b_lines,
        fromfile=f"vanguard/{rel}",
        tofile=f"backend/vanguard/{rel}",
        lineterm=""
    ))
    if not diff:
        return
    for line in diff[:20]:
        print(f"    {line}")
    if len(diff) > 20:
        print(f"    ... ({len(diff) - 20} more diff lines)")


def main():
    if not PRIMARY.is_dir():
        print(f"ERROR: Primary tree not found: {PRIMARY}")
        sys.exit(1)
    if not BACKEND.is_dir():
        print(f"ERROR: Backend tree not found: {BACKEND}")
        sys.exit(1)

    primary_files = collect_py_files(PRIMARY)
    backend_files = collect_py_files(BACKEND)

    all_files = sorted(primary_files | backend_files)

    identical = []
    modified = []
    primary_only = []
    backend_only = []

    for rel in all_files:
        p = PRIMARY / rel
        b = BACKEND / rel

        if p.exists() and b.exists():
            if files_match(p, b):
                identical.append(rel)
            else:
                modified.append(rel)
        elif p.exists():
            primary_only.append(rel)
        else:
            backend_only.append(rel)

    # Report
    print("=" * 70)
    print("VANGUARD DRIFT GUARD REPORT")
    print(f"Primary:  {PRIMARY}")
    print(f"Backend:  {BACKEND}")
    print(f"Total .py files: {len(all_files)}")
    print("=" * 70)

    print(f"\n  IDENTICAL:     {len(identical)}")
    print(f"  MODIFIED:      {len(modified)}")
    print(f"  PRIMARY_ONLY:  {len(primary_only)}")
    print(f"  BACKEND_ONLY:  {len(backend_only)}")

    if modified:
        print(f"\n--- MODIFIED files (drift detected) ---")
        for rel in modified:
            known = rel.name in KNOWN_DIFFS
            tag = " [KNOWN]" if known else " [UNEXPECTED]"
            print(f"  {rel}{tag}")
            if not known:
                show_diff_summary(PRIMARY / rel, BACKEND / rel, rel)

    if primary_only:
        print(f"\n--- PRIMARY_ONLY (missing from backend) ---")
        for rel in primary_only:
            print(f"  {rel}")

    if backend_only:
        print(f"\n--- BACKEND_ONLY (missing from primary) ---")
        for rel in backend_only:
            print(f"  {rel}")

    # Exit code: 0 if no unexpected drift
    unexpected = [r for r in modified if r.name not in KNOWN_DIFFS]
    if unexpected or primary_only or backend_only:
        print(f"\nDRIFT DETECTED: {len(unexpected)} unexpected modifications, "
              f"{len(primary_only)} primary-only, {len(backend_only)} backend-only")
        return 1
    else:
        print(f"\nNO UNEXPECTED DRIFT. All {len(identical)} shared files are identical.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
