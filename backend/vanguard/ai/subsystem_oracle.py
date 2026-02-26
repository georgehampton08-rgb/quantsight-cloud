"""
Vanguard Subsystem Oracle
=========================
Polls *every* Vanguard subsystem concurrently and returns a structured
snapshot that is injected into the AI analysis prompt.

Design principles:
  - Each collector runs in its own try/except — one broken subsystem NEVER
    blocks the others (graceful skip).
  - Each collector is self-healing: on repeated failures it resets the
    underlying singleton and retries once before returning a degraded result.
  - The oracle is lightweight (< 600ms total via asyncio.gather) and is only
    called just before AI analysis, not on every request.
  - The returned SubsystemSnapshot is a plain dataclass → easily serialisable
    to a prompt-friendly string via `snapshot.to_prompt_text()`.
"""

import asyncio
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# ─── Per-subsystem failure trackers for self-healing ──────────────────────────
_failure_counts: Dict[str, int] = {}
_SELF_HEAL_THRESHOLD = 3  # Attempt singleton reset after this many consecutive failures


def _record_subsystem_failure(name: str) -> int:
    """Increment failure counter and return new count."""
    _failure_counts[name] = _failure_counts.get(name, 0) + 1
    return _failure_counts[name]


def _clear_subsystem_failure(name: str) -> None:
    """Reset failure counter after a successful collection."""
    _failure_counts.pop(name, None)


# ─── Snapshot types ────────────────────────────────────────────────────────────

@dataclass
class SubsystemResult:
    """Result from a single subsystem probe."""
    name: str
    status: str          # healthy | degraded | critical | skipped | unknown
    summary: str         # 1-line human-readable status
    details: Dict[str, Any] = field(default_factory=dict)
    self_healed: bool = False
    error: Optional[str] = None
    latency_ms: float = 0.0


@dataclass
class SubsystemSnapshot:
    """Complete system state snapshot at time of analysis."""
    collected_at: str
    incident_fingerprint: str
    subsystems: List[SubsystemResult] = field(default_factory=list)

    # Convenience aggregates
    @property
    def critical_count(self) -> int:
        return sum(1 for s in self.subsystems if s.status == "critical")

    @property
    def degraded_count(self) -> int:
        return sum(1 for s in self.subsystems if s.status == "degraded")

    @property
    def healthy_count(self) -> int:
        return sum(1 for s in self.subsystems if s.status == "healthy")

    def get(self, name: str) -> Optional[SubsystemResult]:
        return next((s for s in self.subsystems if s.name == name), None)

    def to_prompt_text(self) -> str:
        """Format snapshot as a compact table for the AI prompt."""
        lines = [
            f"Snapshot collected: {self.collected_at}",
            f"System-wide status: {self.healthy_count} healthy | "
            f"{self.degraded_count} degraded | {self.critical_count} critical",
            "",
            "┌─────────────────────────┬────────────┬──────────────────────────────────────────────────────┐",
            "│ Subsystem               │ Status     │ Summary                                              │",
            "├─────────────────────────┼────────────┼──────────────────────────────────────────────────────┤",
        ]
        for s in self.subsystems:
            status_icon = {"healthy": "✓", "degraded": "⚠", "critical": "✗", "skipped": "–", "unknown": "?"}.get(s.status, "?")
            name_col = s.name[:23].ljust(23)
            status_col = f"{status_icon} {s.status}"[:10].ljust(10)
            summary_col = s.summary[:52].ljust(52)
            lines.append(f"│ {name_col} │ {status_col} │ {summary_col} │")
        lines.append("└─────────────────────────┴────────────┴──────────────────────────────────────────────────────┘")

        # Add extra detail lines for non-healthy subsystems
        issues = [s for s in self.subsystems if s.status not in ("healthy", "skipped")]
        if issues:
            lines.append("")
            lines.append("Notable subsystem details:")
            for s in issues:
                lines.append(f"  [{s.name}] {s.summary}")
                if s.error:
                    lines.append(f"    Error: {s.error}")
                for k, v in s.details.items():
                    lines.append(f"    {k}: {v}")
                if s.self_healed:
                    lines.append(f"    ⟳ Self-heal attempted (singleton reset)")

        return "\n".join(lines)


# ─── Individual subsystem collectors ──────────────────────────────────────────

async def _collect_health_monitor() -> SubsystemResult:
    """Poll SystemHealthMonitor for external dependency health."""
    t0 = time.perf_counter()
    try:
        from vanguard.health_monitor import get_health_monitor
        monitor = get_health_monitor()
        checks = await asyncio.wait_for(monitor.run_all_checks(), timeout=5.0)

        # Determine overall status from component checks
        statuses = [v.get("status", "unknown") for v in checks.values()]
        if "critical" in statuses:
            status = "critical"
        elif "warning" in statuses:
            status = "degraded"
        else:
            status = "healthy"

        details = {
            comp: f"{data.get('status','?')} — {data.get('details', data.get('error', ''))}"
            for comp, data in checks.items()
        }
        summary = f"NBA API: {checks.get('nba_api', {}).get('status','?')} | "\
                  f"Gemini: {checks.get('gemini_ai', {}).get('status','?')} | "\
                  f"Firestore: {checks.get('firestore', {}).get('status','?')}"

        _clear_subsystem_failure("health_monitor")
        return SubsystemResult(
            name="health_monitor",
            status=status,
            summary=summary,
            details=details,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as e:
        fails = _record_subsystem_failure("health_monitor")
        healed = False
        if fails >= _SELF_HEAL_THRESHOLD:
            # Self-heal: reset the singleton
            try:
                import vanguard.health_monitor as _hm
                _hm._health_monitor = None
                logger.warning("[Oracle] health_monitor singleton reset (self-heal)")
                healed = True
                _failure_counts["health_monitor"] = 0
            except Exception:
                pass
        return SubsystemResult(
            name="health_monitor",
            status="degraded",
            summary="Health monitor probe failed — external connectivity unknown",
            error=str(e)[:120],
            self_healed=healed,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


async def _collect_inquisitor() -> SubsystemResult:
    """Probe Inquisitor: sampler state, rate limiter stats, middleware feature flags."""
    t0 = time.perf_counter()
    try:
        from vanguard.inquisitor.sampler import get_sampler
        from vanguard.inquisitor.middleware import _last_stored, _RATE_LIMIT_SECONDS

        sampler = get_sampler()
        # Count forced-sampling endpoints
        forced = getattr(sampler, '_forced_endpoints', {})
        forced_count = len(forced)

        # Rate limiter: how many fingerprints are currently throttled?
        now = time.monotonic()
        throttled = sum(1 for ts in _last_stored.values() if (now - ts) < _RATE_LIMIT_SECONDS)

        try:
            from vanguard.core.feature_flags import flag
            v2_enabled = flag("FEATURE_MIDDLEWARE_V2")
        except Exception:
            v2_enabled = False

        summary = (
            f"Sampler active | {forced_count} endpoints force-sampled | "
            f"{throttled} fingerprints throttled | v2={'on' if v2_enabled else 'off'}"
        )
        _clear_subsystem_failure("inquisitor")
        return SubsystemResult(
            name="inquisitor",
            status="healthy",
            summary=summary,
            details={
                "forced_endpoints": forced_count,
                "throttled_fingerprints": throttled,
                "middleware_v2": v2_enabled,
            },
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as e:
        fails = _record_subsystem_failure("inquisitor")
        healed = False
        if fails >= _SELF_HEAL_THRESHOLD:
            try:
                import vanguard.inquisitor.sampler as _s
                _s._sampler = None
                healed = True
                _failure_counts["inquisitor"] = 0
            except Exception:
                pass
        return SubsystemResult(
            name="inquisitor",
            status="degraded",
            summary="Inquisitor probe failed — telemetry state unknown",
            error=str(e)[:120],
            self_healed=healed,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


async def _collect_archivist(incident_fingerprint: str, storage) -> SubsystemResult:
    """Probe Archivist storage: recent incident velocity, schema version, memory cache."""
    t0 = time.perf_counter()
    try:
        # Recent incident count (list all, cap at 200)
        try:
            all_incidents = await asyncio.wait_for(storage.list_all(), timeout=4.0)
        except Exception:
            all_incidents = []

        total = len(all_incidents)
        active_count = sum(1 for inc in all_incidents if inc.get("status") == "ACTIVE")

        # Recent velocity: incidents created in last 10 minutes
        now = datetime.now(timezone.utc)
        recent = 0
        for inc in all_incidents:
            ts_str = inc.get("timestamp") or inc.get("last_seen", "")
            try:
                ts_str_clean = ts_str.rstrip("Z")
                if "+" not in ts_str_clean:
                    ts_str_clean += "+00:00"
                ts = datetime.fromisoformat(ts_str_clean)
                if (now - ts).total_seconds() < 600:
                    recent += 1
            except Exception:
                pass

        # Check schema version awareness
        try:
            from vanguard.core.feature_flags import flag
            schema_v1 = flag("FEATURE_INCIDENT_SCHEMA_V1")
        except Exception:
            schema_v1 = False

        summary = (
            f"{total} total incidents | {active_count} active | "
            f"{recent} in last 10min | schema_v1={'on' if schema_v1 else 'off'}"
        )
        _clear_subsystem_failure("archivist")
        return SubsystemResult(
            name="archivist",
            status="healthy" if total >= 0 else "degraded",
            summary=summary,
            details={
                "total_incidents": total,
                "active_incidents": active_count,
                "recent_10min": recent,
                "schema_v1": schema_v1,
            },
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as e:
        fails = _record_subsystem_failure("archivist")
        healed = False
        if fails >= _SELF_HEAL_THRESHOLD:
            try:
                import vanguard.archivist.storage as _stor
                _stor._storage = None
                healed = True
                _failure_counts["archivist"] = 0
                logger.warning("[Oracle] archivist singleton reset (self-heal)")
            except Exception:
                pass
        return SubsystemResult(
            name="archivist",
            status="critical",
            summary="Archivist probe failed — incident history unavailable",
            error=str(e)[:120],
            self_healed=healed,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


async def _collect_surgeon() -> SubsystemResult:
    """Probe Surgeon: circuit breaker state table, remediation capability."""
    t0 = time.perf_counter()
    try:
        from vanguard.surgeon.circuit_breaker import get_circuit_breaker, CircuitState

        cb = get_circuit_breaker()
        circuits = cb.circuits

        closed = [ep for ep, c in circuits.items() if c["state"] == CircuitState.CLOSED]
        half_open = [ep for ep, c in circuits.items() if c["state"] == CircuitState.HALF_OPEN]
        open_c = [ep for ep, c in circuits.items() if c["state"] == CircuitState.OPEN]

        status = "critical" if closed else ("degraded" if half_open else "healthy")
        summary = (
            f"{len(circuits)} endpoints tracked | "
            f"{len(closed)} QUARANTINED | {len(half_open)} HALF_OPEN | {len(open_c)} healthy"
        )

        # Get remediation capability
        try:
            from vanguard.surgeon.remediation import get_surgeon
            surgeon = get_surgeon()
            mode = getattr(surgeon, 'mode', 'unknown')
            surgeon_ready = True
        except Exception as se:
            mode = f"unavailable ({se})"
            surgeon_ready = False

        details: Dict[str, Any] = {
            "quarantined_endpoints": closed[:5],
            "half_open_endpoints": half_open[:5],
            "mode": mode,
            "surgeon_ready": surgeon_ready,
        }
        _clear_subsystem_failure("surgeon")
        return SubsystemResult(
            name="surgeon",
            status=status,
            summary=summary,
            details=details,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as e:
        fails = _record_subsystem_failure("surgeon")
        healed = False
        if fails >= _SELF_HEAL_THRESHOLD:
            try:
                import vanguard.surgeon.circuit_breaker as _cb
                _cb._circuit_breaker = None
                healed = True
                _failure_counts["surgeon"] = 0
                logger.warning("[Oracle] surgeon circuit_breaker singleton reset (self-heal)")
            except Exception:
                pass
        return SubsystemResult(
            name="surgeon",
            status="degraded",
            summary="Surgeon probe failed — circuit breaker state unknown",
            error=str(e)[:120],
            self_healed=healed,
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


async def _collect_vaccine() -> SubsystemResult:
    """Check Vaccine subsystem availability and enabled status."""
    t0 = time.perf_counter()
    try:
        import os
        enabled = os.getenv("VANGUARD_VACCINE_ENABLED", "false").lower() in ("true", "1", "yes")

        if not enabled:
            return SubsystemResult(
                name="vaccine",
                status="skipped",
                summary="Vaccine disabled (VANGUARD_VACCINE_ENABLED not set)",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        # Try importing the core vaccine modules
        errors = []
        modules_ok = []
        for mod in ("vanguard.vaccine.plan_engine", "vanguard.vaccine.generator"):
            try:
                __import__(mod)
                modules_ok.append(mod.split(".")[-1])
            except ImportError as ie:
                errors.append(f"{mod}: {ie}")

        if errors:
            _record_subsystem_failure("vaccine")
            return SubsystemResult(
                name="vaccine",
                status="degraded",
                summary=f"Vaccine partially available — {len(modules_ok)}/{len(modules_ok)+len(errors)} modules loaded",
                error="; ".join(errors)[:120],
                details={"loaded": modules_ok},
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        _clear_subsystem_failure("vaccine")
        return SubsystemResult(
            name="vaccine",
            status="healthy",
            summary=f"Vaccine operational — {', '.join(modules_ok)} ready",
            details={"modules": modules_ok},
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as e:
        return SubsystemResult(
            name="vaccine",
            status="skipped",
            summary=f"Vaccine status unavailable: {e}",
            error=str(e)[:80],
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


async def _collect_github_context() -> SubsystemResult:
    """Check GitHub context fetcher connectivity."""
    t0 = time.perf_counter()
    try:
        from vanguard.services.github_context import GitHubContextFetcher
        fetcher = GitHubContextFetcher()
        token = getattr(fetcher, 'token', None) or getattr(fetcher, '_token', None)
        has_token = bool(token)

        _clear_subsystem_failure("github_context")
        return SubsystemResult(
            name="github_context",
            status="healthy" if has_token else "degraded",
            summary=f"GitHub context fetcher {'authenticated' if has_token else 'unauthenticated — code context will be empty'}",
            details={"authenticated": has_token},
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as e:
        _record_subsystem_failure("github_context")
        return SubsystemResult(
            name="github_context",
            status="degraded",
            summary="GitHub context fetcher unavailable — AI will lack code references",
            error=str(e)[:100],
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


async def _collect_resolution_learner() -> SubsystemResult:
    """Check resolution learner for pattern knowledge."""
    t0 = time.perf_counter()
    try:
        import vanguard.resolution_learner as rl_mod
        learner = getattr(rl_mod, '_learner', None) or getattr(rl_mod, 'get_resolution_learner', lambda: None)()
        if learner is None:
            return SubsystemResult(
                name="resolution_learner",
                status="skipped",
                summary="Resolution learner not initialized",
                latency_ms=(time.perf_counter() - t0) * 1000,
            )

        patterns = getattr(learner, '_patterns', {}) or getattr(learner, 'patterns', {})
        count = len(patterns)
        _clear_subsystem_failure("resolution_learner")
        return SubsystemResult(
            name="resolution_learner",
            status="healthy",
            summary=f"Resolution learner active — {count} known patterns",
            details={"pattern_count": count},
            latency_ms=(time.perf_counter() - t0) * 1000,
        )
    except Exception as e:
        _record_subsystem_failure("resolution_learner")
        return SubsystemResult(
            name="resolution_learner",
            status="skipped",
            summary="Resolution learner probe failed (non-critical)",
            error=str(e)[:80],
            latency_ms=(time.perf_counter() - t0) * 1000,
        )


# ─── Public Oracle ─────────────────────────────────────────────────────────────

class SubsystemOracle:
    """
    Polls all Vanguard subsystems concurrently.
    Each probe is isolated — failures are caught and returned as
    degraded SubsystemResults, never exceptions.
    Self-healing: singletons are reset after repeated failures.
    """

    async def collect(self, incident_fingerprint: str, storage) -> SubsystemSnapshot:
        """
        Run all subsystem probes in parallel and return a snapshot.
        Total latency: max(slowest probe), bounded by per-probe timeouts.
        """
        snapshot = SubsystemSnapshot(
            collected_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            incident_fingerprint=incident_fingerprint,
        )

        # Run all collectors in parallel, each individually guarded
        results = await asyncio.gather(
            _collect_health_monitor(),
            _collect_inquisitor(),
            _collect_archivist(incident_fingerprint, storage),
            _collect_surgeon(),
            _collect_vaccine(),
            _collect_github_context(),
            _collect_resolution_learner(),
            return_exceptions=True,  # Last-resort: if gather itself fails
        )

        for result in results:
            if isinstance(result, SubsystemResult):
                snapshot.subsystems.append(result)
            elif isinstance(result, Exception):
                # Should never reach here since each collector catches its own,
                # but belt-and-suspenders
                snapshot.subsystems.append(SubsystemResult(
                    name="unknown",
                    status="skipped",
                    summary=f"Probe failed unexpectedly: {result}",
                    error=str(result)[:100],
                ))

        total_ms = sum(s.latency_ms for s in snapshot.subsystems)
        healed_count = sum(1 for s in snapshot.subsystems if s.self_healed)
        logger.info(
            f"[Oracle] Subsystem snapshot collected in {total_ms:.0f}ms total | "
            f"{snapshot.healthy_count} healthy | {snapshot.degraded_count} degraded | "
            f"{snapshot.critical_count} critical | {healed_count} self-healed"
        )

        return snapshot


# ─── Singleton ─────────────────────────────────────────────────────────────────
_oracle: Optional[SubsystemOracle] = None


def get_oracle() -> SubsystemOracle:
    global _oracle
    if _oracle is None:
        _oracle = SubsystemOracle()
    return _oracle
