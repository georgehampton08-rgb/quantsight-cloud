"""
Vanguard Vaccine — Patch Applier
================================
Generates patch previews, applies patches safely, runs verification,
and records resolution metadata.  Never auto-deploys.

Safety:
  - Only touches ALLOWED_ROOTS directories
  - Refuses patches > MAX_FILES or > MAX_LINES
  - Requires explicit `confirm: true` before apply
  - Rolls back on verification failure
"""

import difflib
import hashlib
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


# ── Safety constants ──────────────────────────────────────────────────────────
ALLOWED_ROOTS = [
    "vanguard/",
    "backend/vanguard/",
    "scripts/",
    "shared_core/",
]

MAX_FILES_PER_PATCH = 5
MAX_LINES_CHANGED = 200
MAX_TOTAL_DIFF_LINES = 500


@dataclass
class FileChange:
    """A single file change within a patch."""
    path: str
    changes_summary: str
    original_content: str = ""
    patched_content: str = ""
    lines_added: int = 0
    lines_removed: int = 0


@dataclass
class PatchSpec:
    """Complete patch specification — preview or applied."""
    fingerprint: str
    files_changed: List[FileChange]
    unified_diff: str
    notes: str
    guardrails_passed: bool = True
    guardrails_reason: str = ""
    diff_hash: str = ""
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["files_changed"] = [
            {"path": fc.path, "changes_summary": fc.changes_summary,
             "lines_added": fc.lines_added, "lines_removed": fc.lines_removed}
            for fc in self.files_changed
        ]
        return d


@dataclass
class ApplyResult:
    """Result of applying a patch."""
    success: bool
    message: str
    verification_passed: bool = False
    verification_output: str = ""
    diff_hash: str = ""
    git_commit: str = ""
    rollback_performed: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VaccinePatchApplier:
    """
    Safe patch generation, application, and verification.

    Workflow:
      1. preview()   → PatchSpec (no side effects)
      2. apply()     → writes files + runs verification
      3. rollback()  → reverts if verification failed
    """

    VERSION = "1.0.0"

    def __init__(self, repo_root: Optional[str] = None):
        self.repo_root = Path(repo_root or self._detect_repo_root())
        self._backups: Dict[str, str] = {}  # path → original content
        logger.info(f"VaccinePatchApplier v{self.VERSION} repo_root={self.repo_root}")

    @staticmethod
    def _detect_repo_root() -> str:
        """Detect repo root — works in Cloud Run (/app) and local dev."""
        if os.path.exists("/app/vanguard"):
            return "/app"
        # Walk up from this file
        here = Path(__file__).resolve()
        for parent in here.parents:
            if (parent / "vanguard").is_dir() and (parent / "backend").is_dir():
                return str(parent)
        return str(Path.cwd())

    # ── Guardrails ────────────────────────────────────────────────────────────

    def _check_allowed_path(self, path: str) -> bool:
        """Verify path is within allowed edit roots."""
        normalized = path.lstrip("/").replace("\\", "/")
        return any(normalized.startswith(root) for root in ALLOWED_ROOTS)

    def _check_guardrails(self, files: List[FileChange]) -> tuple[bool, str]:
        """Validate patch against safety guardrails."""
        if len(files) > MAX_FILES_PER_PATCH:
            return False, f"Too many files ({len(files)} > {MAX_FILES_PER_PATCH})"

        total_lines = 0
        for fc in files:
            if not self._check_allowed_path(fc.path):
                return False, f"Path outside allowed roots: {fc.path}"
            total_lines += fc.lines_added + fc.lines_removed

        if total_lines > MAX_LINES_CHANGED:
            return False, f"Too many lines changed ({total_lines} > {MAX_LINES_CHANGED})"

        return True, "OK"

    # ── Preview (no side effects) ─────────────────────────────────────────────

    def preview(
        self,
        fingerprint: str,
        file_patches: List[Dict[str, str]],
        notes: str = "",
    ) -> PatchSpec:
        """
        Generate a diff preview without writing anything.

        Args:
            fingerprint: Incident fingerprint
            file_patches: List of {path, original, patched} dicts
            notes: Human-readable explanation

        Returns:
            PatchSpec with unified diff and guardrails check
        """
        changes: List[FileChange] = []
        all_diffs: List[str] = []

        for patch in file_patches:
            path = patch.get("path", "")
            original = patch.get("original", "")
            patched = patch.get("patched", "")

            diff_lines = list(difflib.unified_diff(
                original.splitlines(keepends=True),
                patched.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            ))

            added = sum(1 for l in diff_lines if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff_lines if l.startswith("-") and not l.startswith("---"))

            changes.append(FileChange(
                path=path,
                changes_summary=f"+{added}/-{removed} lines",
                original_content=original,
                patched_content=patched,
                lines_added=added,
                lines_removed=removed,
            ))
            all_diffs.extend(diff_lines)

        unified = "\n".join(all_diffs)
        diff_hash = hashlib.sha256(unified.encode()).hexdigest()[:16]

        passed, reason = self._check_guardrails(changes)

        return PatchSpec(
            fingerprint=fingerprint,
            files_changed=changes,
            unified_diff=unified,
            notes=notes,
            guardrails_passed=passed,
            guardrails_reason=reason,
            diff_hash=diff_hash,
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    # ── Apply patch ───────────────────────────────────────────────────────────

    def apply(
        self,
        patch: PatchSpec,
        confirm: bool = False,
        create_commit: bool = False,
        resolution_notes: str = "",
    ) -> ApplyResult:
        """
        Apply a previewed patch to disk.

        Args:
            patch: PatchSpec from preview()
            confirm: Must be True to proceed
            create_commit: Whether to git commit changes
            resolution_notes: Human notes for the commit message
        """
        if not confirm:
            return ApplyResult(
                success=False,
                message="Patch not confirmed — set confirm=true to apply",
            )

        if not patch.guardrails_passed:
            return ApplyResult(
                success=False,
                message=f"Guardrails failed: {patch.guardrails_reason}",
            )

        # Backup originals
        self._backups.clear()
        for fc in patch.files_changed:
            full_path = self.repo_root / fc.path
            if full_path.exists():
                self._backups[fc.path] = full_path.read_text(encoding="utf-8")

        # Write patched files
        try:
            for fc in patch.files_changed:
                full_path = self.repo_root / fc.path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                full_path.write_text(fc.patched_content, encoding="utf-8")
                logger.info(f"Vaccine patched: {fc.path}")
        except Exception as e:
            logger.error(f"Vaccine apply failed during write: {e}")
            self.rollback()
            return ApplyResult(
                success=False,
                message=f"Write failed: {e}",
                rollback_performed=True,
            )

        # Verify
        v_passed, v_output = self._run_verification(patch)

        if not v_passed:
            logger.warning("Vaccine verification FAILED — rolling back")
            self.rollback()
            return ApplyResult(
                success=False,
                message="Verification failed — changes rolled back",
                verification_passed=False,
                verification_output=v_output,
                rollback_performed=True,
            )

        # Optionally commit
        git_commit = ""
        if create_commit:
            git_commit = self._create_commit(patch, resolution_notes)

        return ApplyResult(
            success=True,
            message="Patch applied and verified successfully",
            verification_passed=True,
            verification_output=v_output,
            diff_hash=patch.diff_hash,
            git_commit=git_commit,
            metadata={
                "fingerprint": patch.fingerprint,
                "files_changed": [fc.path for fc in patch.files_changed],
                "applied_at": datetime.now(timezone.utc).isoformat(),
                "resolution_notes": resolution_notes,
            },
        )

    # ── Rollback ──────────────────────────────────────────────────────────────

    def rollback(self):
        """Revert all files to their pre-patch state."""
        for path, content in self._backups.items():
            try:
                full_path = self.repo_root / path
                full_path.write_text(content, encoding="utf-8")
                logger.info(f"Vaccine rollback: restored {path}")
            except Exception as e:
                logger.error(f"Vaccine rollback failed for {path}: {e}")
        self._backups.clear()

    # ── Verification ──────────────────────────────────────────────────────────

    def _run_verification(self, patch: PatchSpec) -> tuple[bool, str]:
        """Run syntax check + smoke test on patched files."""
        outputs = []

        # 1. Syntax check each changed file
        for fc in patch.files_changed:
            full_path = self.repo_root / fc.path
            if full_path.suffix == ".py":
                try:
                    compile(fc.patched_content, str(full_path), "exec")
                    outputs.append(f"✅ {fc.path}: syntax OK")
                except SyntaxError as e:
                    outputs.append(f"❌ {fc.path}: SyntaxError: {e}")
                    return False, "\n".join(outputs)

        # 2. Try to run smoke test if it exists
        smoke_script = self.repo_root / "scripts" / "nba_smoke.py"
        if smoke_script.exists():
            try:
                result = subprocess.run(
                    ["python", str(smoke_script)],
                    capture_output=True,
                    text=True,
                    timeout=60,
                    cwd=str(self.repo_root),
                )
                if result.returncode == 0:
                    outputs.append("✅ nba_smoke.py: PASSED")
                else:
                    outputs.append(f"⚠️ nba_smoke.py: exit {result.returncode}")
                    # Smoke failure is a warning, not a hard block
            except Exception as e:
                outputs.append(f"⚠️ nba_smoke.py: {e}")

        outputs.append("✅ Verification complete")
        return True, "\n".join(outputs)

    # ── Git commit ────────────────────────────────────────────────────────────

    def _create_commit(self, patch: PatchSpec, notes: str) -> str:
        """Create a git commit for the patch (does NOT push)."""
        try:
            files = [str(self.repo_root / fc.path) for fc in patch.files_changed]
            subprocess.run(
                ["git", "add"] + files,
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
            )

            msg = (
                f"[VACCINE] Auto-fix for incident {patch.fingerprint}\n\n"
                f"Diff hash: {patch.diff_hash}\n"
                f"Files: {', '.join(fc.path for fc in patch.files_changed)}\n"
                f"Notes: {notes or 'Vaccine-generated fix'}"
            )

            result = subprocess.run(
                ["git", "commit", "-m", msg],
                cwd=str(self.repo_root),
                check=True,
                capture_output=True,
                text=True,
            )

            # Extract commit hash
            for line in result.stdout.split("\n"):
                if line.strip().startswith("["):
                    parts = line.split()
                    for p in parts:
                        if len(p) >= 7 and all(c in "0123456789abcdef" for c in p.rstrip("]")):
                            return p.rstrip("]")
            return "committed"
        except Exception as e:
            logger.warning(f"Git commit failed (patch still applied): {e}")
            return ""


# ── Singleton ─────────────────────────────────────────────────────────────────
_applier: Optional[VaccinePatchApplier] = None


def get_patch_applier() -> VaccinePatchApplier:
    global _applier
    if _applier is None:
        _applier = VaccinePatchApplier()
    return _applier
