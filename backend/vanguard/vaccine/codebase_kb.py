"""
Vanguard Codebase Knowledge Base
=================================
Auto-crawls the QuantSight backend and generates a structured knowledge context
that is injected into every Gemini vaccine/analysis prompt.

Gives the AI:
  - Full understanding of the project architecture
  - Module inventory with purpose summaries
  - All API route signatures (so it knows what endpoints exist)
  - Error handling conventions (so it follows the same patterns)
  - Available dependencies (so it never hallucinates imports)
  - Key data models and schemas
  - Common patterns (Firestore, async, FastAPI decorators)

Usage:
    from vanguard.vaccine.codebase_kb import get_codebase_context
    ctx = await get_codebase_context()     # returns a rich markdown string
    # Inject into Gemini prompt as a SYSTEM block
"""

import os
import ast
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────

_BACKEND_DIRS = [
    "vanguard", "services", "engines", "api", "aegis",
    "nexus", "models", "shared_core", "telemetry",
]

_SKIP_DIRS = {
    "__pycache__", ".pytest_cache", ".git", "node_modules",
    "migrations", ".backup_cache",
}

_SKIP_FILES = {
    "test_", "tests/", "fetch_", "check_", "debug_",
    "populate_", "sync_", "verify_",
}

# Max lines to read from each file for summary extraction
_MAX_LINES = 120

# Cache — rebuilt when stale (6 hours)
_KB_CACHE: Optional[dict] = None
_KB_BUILT_AT: Optional[datetime] = None
_KB_TTL_SECONDS = 6 * 3600


# ── Repo root detection ───────────────────────────────────────────────────────

def _repo_root() -> Path:
    """Find the repo root (contains /backend and /vanguard)."""
    if os.path.exists("/app/vanguard"):
        return Path("/app")
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "vanguard").is_dir() and (parent / "server.py").exists():
            return parent
    return Path.cwd()


# ── AST-based module summariser ───────────────────────────────────────────────

def _summarise_module(file_path: Path) -> dict:
    """
    Parse a Python file with AST and extract:
      - Module docstring
      - Top-level class names + their docstrings
      - Top-level function/async def names + their signatures
      - Imports (to build dependency graph)
    Returns a compact dict — no source code, only structure.
    """
    result = {
        "path":      str(file_path),
        "rel_path":  "",
        "docstring":  "",
        "classes":   [],
        "functions": [],
        "imports":   [],
        "routes":    [],       # FastAPI @router.get/post etc.
        "error":     None,
    }

    try:
        source = file_path.read_text(encoding="utf-8", errors="replace")
        lines  = source.splitlines()
        # Only parse up to _MAX_LINES for performance, but get top-level structure
        try:
            tree = ast.parse(source)
        except SyntaxError as se:
            result["error"] = f"SyntaxError: {se}"
            return result

        # Module docstring
        result["docstring"] = (ast.get_docstring(tree) or "")[:200]

        for node in ast.walk(tree):
            # Imports
            if isinstance(node, ast.Import):
                for a in node.names:
                    result["imports"].append(a.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    result["imports"].append(node.module.split(".")[0])

        # Top-level only
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name for n in ast.iter_child_nodes(node)
                    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and not n.name.startswith("__")
                ]
                result["classes"].append({
                    "name":    node.name,
                    "doc":     (ast.get_docstring(node) or "")[:120],
                    "methods": methods[:20],
                })

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                args = [a.arg for a in node.args.args if a.arg != "self"][:8]
                result["functions"].append({
                    "name": node.name,
                    "args": args,
                    "doc":  (ast.get_docstring(node) or "")[:100],
                    "async": isinstance(node, ast.AsyncFunctionDef),
                })

        # Route detection: scan source text for @router. or @app. decorators
        for i, line in enumerate(lines[:_MAX_LINES]):
            stripped = line.strip()
            for method in ("get", "post", "put", "delete", "patch"):
                if stripped.startswith(f"@router.{method}(") or stripped.startswith(f"@app.{method}("):
                    # Grab the path from the decorator string
                    try:
                        path_start = stripped.index('"') + 1
                        path_end   = stripped.index('"', path_start)
                        route_path = stripped[path_start:path_end]
                    except ValueError:
                        try:
                            path_start = stripped.index("'") + 1
                            path_end   = stripped.index("'", path_start)
                            route_path = stripped[path_start:path_end]
                        except ValueError:
                            route_path = "?"
                    result["routes"].append(f"{method.upper()} {route_path}")

        result["imports"] = list(set(result["imports"]))[:30]

    except Exception as e:
        result["error"] = str(e)

    return result


# ── Main crawler ──────────────────────────────────────────────────────────────

def _crawl_backend(root: Path) -> list[dict]:
    """Walk backend dirs and summarise each .py module."""
    modules = []

    # Priority dirs first
    search_dirs = []
    for d in _BACKEND_DIRS:
        p = root / d
        if p.is_dir():
            search_dirs.append(p)
    # Also include root-level files like server.py
    search_dirs.append(root)

    seen = set()
    for search_dir in search_dirs:
        if search_dir == root:
            # Only top-level .py files, not recursively
            py_files = [f for f in root.glob("*.py") if f.is_file()]
        else:
            py_files = [
                f for f in search_dir.rglob("*.py")
                if f.is_file()
                and not any(skip in str(f) for skip in _SKIP_DIRS)
            ]

        for f in sorted(py_files):
            if str(f) in seen:
                continue
            # Skip test/utility scripts
            if any(f.name.startswith(prefix) for prefix in ("test_", "fetch_", "check_", "debug_", "verify_", "sync_", "populate_")):
                continue
            seen.add(str(f))
            mod = _summarise_module(f)
            try:
                mod["rel_path"] = str(f.relative_to(root))
            except Exception:
                mod["rel_path"] = f.name
            # Drop path (redundant)
            mod.pop("path", None)
            modules.append(mod)

            if len(modules) >= 120:   # cap for prompt size
                break
        if len(modules) >= 120:
            break

    return modules


# ── Route index ───────────────────────────────────────────────────────────────

def _build_route_index(modules: list[dict]) -> list[str]:
    """Collect all discovered routes across all modules."""
    routes = []
    for m in modules:
        for r in m.get("routes", []):
            rel = m.get("rel_path", "?")
            routes.append(f"{r}  [{rel}]")
    return routes


# ── Convention extractor ──────────────────────────────────────────────────────

def _extract_error_patterns(root: Path) -> list[str]:
    """
    Scan server.py and a few key files for common error-handling and
    response patterns — so Gemini can match the project's conventions.
    """
    patterns = []
    candidates = [
        root / "server.py",
        root / "vanguard" / "api" / "admin_routes.py",
        root / "services" / "tracking_data_fetcher.py",
    ]
    for f in candidates:
        if not f.exists():
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
            for i, line in enumerate(lines[:800]):
                stripped = line.strip()
                # HTTPException pattern
                if "raise HTTPException(" in stripped:
                    patterns.append(f"HTTPException pattern: {stripped[:100]}")
                # try/except with logger
                if stripped.startswith("logger.error") or stripped.startswith("logger.warning"):
                    patterns.append(f"Logging pattern: {stripped[:100]}")
                if len(patterns) >= 20:
                    break
        except Exception:
            pass
        if len(patterns) >= 20:
            break

    return list(dict.fromkeys(patterns))[:15]   # deduplicate + cap


# ── Firestore collection scanner ──────────────────────────────────────────────

def _scan_firestore_collections(root: Path) -> list[str]:
    """
    Scan codebase for Firestore collection references:
      db.collection("...")   .collection("...")
    Returns deduplicated list of collection names found.
    """
    import re
    collections = set()
    pattern = re.compile(r'\.collection\(["\']([A-Za-z0-9_-]+)["\']\)')

    search_dirs = [root / d for d in _BACKEND_DIRS if (root / d).is_dir()]
    search_dirs.append(root)

    for d in search_dirs:
        py_files = d.glob("*.py") if d == root else d.rglob("*.py")
        for f in py_files:
            if any(skip in str(f) for skip in _SKIP_DIRS):
                continue
            try:
                src = f.read_text(encoding="utf-8", errors="replace")
                for m in pattern.finditer(src):
                    collections.add(m.group(1))
            except Exception:
                pass

    return sorted(collections)


# ── Router mount scanner ─────────────────────────────────────────────────────

def _scan_router_mounts(root: Path) -> list[str]:
    """
    Scan main.py / server.py for app.include_router() calls to map
    which prefix each router is mounted under.
    Returns lines like: 'admin_router → prefix=/vanguard/admin  [main.py]'
    """
    import re
    mounts = []
    # Match include_router with optional prefix kwarg
    mount_re = re.compile(
        r'app\.include_router\(\s*([\w.]+)(?:\s*,\s*(.+?))?\s*\)',
    )
    prefix_re = re.compile(r'prefix\s*=\s*["\']([^"\']*)["\']')

    for fname in ("main.py", "server.py"):
        f = root / fname
        if not f.exists():
            continue
        try:
            src = f.read_text(encoding="utf-8", errors="replace")
            for m in mount_re.finditer(src):
                router_var = m.group(1).rsplit(".", 1)[-1]
                rest = m.group(2) or ""
                prefix_match = prefix_re.search(rest)
                prefix = prefix_match.group(1) if prefix_match else "(inline)"
                mounts.append(f"{router_var} → prefix={prefix}  [{fname}]")
        except Exception:
            pass
    return mounts


# ── Markdown formatter ────────────────────────────────────────────────────────

def _format_context_markdown(kb: dict) -> str:
    """
    Render the KB as a concise markdown block suitable for injection
    into a Gemini system prompt (target: <2000 tokens).
    """
    lines = [
        "## QuantSight Codebase Context",
        f"_Generated: {kb['built_at']}  |  Backend root: {kb['root']}_\n",

        "### Architecture",
        "- **Runtime**: Python 3.11+, FastAPI + Uvicorn, deployed to Google Cloud Run (serverless)",
        "- **Database**: Google Cloud Firestore (NoSQL, async via `google-cloud-firestore`)",
        "- **AI**: Google Gemini (`google-genai` SDK), model `gemini-2.0-flash` by default",
        "- **Frontend**: React + TypeScript (Vite), communicates via REST/SSE",
        "- **Auth/Config**: Env vars loaded via `python-dotenv`; secrets from Cloud Run env",
        "- **Observability**: OpenTelemetry, structured logging with `structlog`",
        "",

        "### Available Dependencies (from requirements.txt)",
        "```",
    ]
    deps = kb.get("dependencies", [])
    lines.extend(deps[:40])
    lines += ["```", ""]

    # Router Mounts (prefix mapping)
    mounts = kb.get("router_mounts", [])
    if mounts:
        lines.append("### Router Mount Points (from server.py / main.py)")
        lines.append("```")
        lines.extend(mounts)
        lines.append("```")
        lines.append("")

    # API Routes
    routes = kb.get("routes", [])
    if routes:
        lines.append("### Registered API Routes (subset)")
        lines.append("```")
        lines.extend(routes[:40])
        lines.append("```")
        lines.append("")

    # Firestore Collections
    collections = kb.get("firestore_collections", [])
    if collections:
        lines.append("### Firestore Collections (discovered in codebase)")
        lines.append("These are the Firestore collections referenced in the code. Use ONLY these collection names.")
        lines.append("```")
        lines.extend(collections)
        lines.append("```")
        lines.append("")

    # Key modules
    modules = kb.get("modules", [])
    lines.append("### Key Modules")
    for m in modules[:30]:
        rel = m.get("rel_path", "?")
        doc = m.get("docstring", "").replace("\n", " ")[:100]
        classes = ", ".join(c["name"] for c in m.get("classes", []))
        fns = ", ".join(f["name"] for f in m.get("functions", []) if not f["name"].startswith("_"))[:120]
        rts = ", ".join(m.get("routes", []))[:100]

        lines.append(f"**{rel}**")
        if doc:     lines.append(f"  - _Doc_: {doc}")
        if classes: lines.append(f"  - _Classes_: {classes}")
        if fns:     lines.append(f"  - _Functions_: {fns}")
        if rts:     lines.append(f"  - _Routes_: {rts}")
    lines.append("")

    # Error patterns
    patterns = kb.get("error_patterns", [])
    if patterns:
        lines.append("### Observed Error/Response Patterns (match these conventions)")
        lines.append("```python")
        for p in patterns[:10]:
            lines.append(p)
        lines.append("```")
        lines.append("")

    lines += [
        "### Critical Rules for Patches",
        "1. Never modify: `main.py`, `.env`, `config.py`, `requirements.txt`, Dockerfile",
        "2. Always use `async def` for route handlers and storage calls",
        "3. Catch exceptions narrowly — do NOT use bare `except:` in new code",
        "4. Use `logger = logging.getLogger(__name__)` — never `print()` in production code",
        "5. Return dicts from route handlers — Pydantic auto-serializes via FastAPI",
        "6. Firestore is the ONLY persistent store — no PostgreSQL/SQLite references",
        "7. All external HTTP calls use `httpx` or `aiohttp` (async) — never `requests` in async context",
        "8. Do not add new imports for stdlib modules already in scope (os, json, datetime, pathlib, typing)",
        "",
    ]

    return "\n".join(lines)


# ── Public API ────────────────────────────────────────────────────────────────

async def build_kb() -> dict:
    """Build (or rebuild) the full knowledge base. Returns a dict + markdown string."""
    global _KB_CACHE, _KB_BUILT_AT

    root = _repo_root()
    logger.info(f"[QuantSight KB] Building codebase knowledge base from {root}")

    # Run CPU-bound crawl in executor to avoid blocking event loop
    loop = asyncio.get_event_loop()
    modules      = await loop.run_in_executor(None, _crawl_backend, root)
    routes       = await loop.run_in_executor(None, _build_route_index, modules)
    errors       = await loop.run_in_executor(None, _extract_error_patterns, root)
    collections  = await loop.run_in_executor(None, _scan_firestore_collections, root)
    router_mounts = await loop.run_in_executor(None, _scan_router_mounts, root)

    # Read requirements.txt for dependency list
    deps = []
    req_file = root / "backend" / "requirements.txt"
    if not req_file.exists():
        req_file = root / "requirements.txt"
    if req_file.exists():
        for line in req_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                deps.append(line)

    built_at = datetime.now(timezone.utc).isoformat()
    kb = {
        "schema_version": "1.1",
        "built_at":       built_at,
        "root":           str(root),
        "module_count":   len(modules),
        "route_count":    len(routes),
        "collection_count": len(collections),
        "modules":        modules,
        "routes":         routes,
        "error_patterns": errors,
        "dependencies":   deps,
        "firestore_collections": collections,
        "router_mounts":  router_mounts,
    }

    # Generate the formatted markdown context
    kb["markdown"] = _format_context_markdown(kb)

    _KB_CACHE    = kb
    _KB_BUILT_AT = datetime.now(timezone.utc)

    # Optionally persist to disk for cold starts
    try:
        out_dir = root / "data" / "kb"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "codebase_context.json"
        # Write a lightweight version (no full markdown)
        compact = {k: v for k, v in kb.items() if k != "modules"}
        compact["module_count"] = len(modules)
        out_file.write_text(json.dumps(compact, indent=2, default=str), encoding="utf-8")
        logger.info(f"[QuantSight KB] Saved to {out_file} ({out_file.stat().st_size // 1024}KB)")
    except Exception as e:
        logger.debug(f"[QuantSight KB] Could not persist to disk: {e}")

    logger.info(f"[QuantSight KB] Built: {len(modules)} modules, {len(routes)} routes, {len(collections)} collections, {len(deps)} deps")
    return kb


async def get_codebase_context() -> str:
    """
    Return the codebase context as a markdown string, ready to inject into a prompt.
    Builds the KB if it doesn't exist or is older than TTL.
    """
    global _KB_CACHE, _KB_BUILT_AT

    now = datetime.now(timezone.utc)
    stale = (
        _KB_CACHE is None
        or _KB_BUILT_AT is None
        or (now - _KB_BUILT_AT).total_seconds() > _KB_TTL_SECONDS
    )

    if stale:
        # Try loading from disk first (faster than full crawl on cold start)
        if _KB_CACHE is None:
            try:
                root = _repo_root()
                disk_file = root / "data" / "kb" / "codebase_context.json"
                if disk_file.exists():
                    age = (now - datetime.fromtimestamp(disk_file.stat().st_mtime, tz=timezone.utc)).total_seconds()
                    if age < _KB_TTL_SECONDS:
                        raw = json.loads(disk_file.read_text(encoding="utf-8"))
                        raw["markdown"] = _format_context_markdown(raw)
                        _KB_CACHE    = raw
                        _KB_BUILT_AT = datetime.fromtimestamp(disk_file.stat().st_mtime, tz=timezone.utc)
                        stale = False
                        logger.info("[QuantSight KB] Loaded from disk cache")
            except Exception as e:
                logger.debug(f"[QuantSight KB] Disk load failed: {e}")

        if stale:
            try:
                await build_kb()
            except Exception as e:
                logger.error(f"[QuantSight KB] Build failed: {e}")
                return "## QuantSight Codebase Context\n_(KB unavailable — crawl failed)_\n"

    return _KB_CACHE.get("markdown", "") if _KB_CACHE else ""


async def invalidate_kb():
    """Force a rebuild on the next call to get_codebase_context()."""
    global _KB_CACHE, _KB_BUILT_AT
    _KB_CACHE    = None
    _KB_BUILT_AT = None
    logger.info("[QuantSight KB] Cache invalidated — will rebuild on next request")
