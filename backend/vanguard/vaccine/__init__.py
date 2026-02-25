"""
Vanguard Vaccine - Chaos Testing + AI Code Fix Generator
========================================================
- ChaosScheduler: Scheduled chaos testing
- TestReporter: Test result reporting
- VaccineGenerator: AI-powered code fix generation from analysis
- VaccinePlanEngine: Incident → structured fix plan
- VaccinePatchApplier: Safe patch application + verification

Phase 5: Hardened imports — non-critical modules load defensively.
"""

# Always available
from .generator import VaccineGenerator, get_vaccine

# Optional modules — may not exist in all deployments
try:
    from .chaos_scheduler import ChaosScheduler
except ImportError:
    ChaosScheduler = None  # type: ignore

try:
    from .test_reporter import TestReporter
except ImportError:
    TestReporter = None  # type: ignore

__all__ = ["ChaosScheduler", "TestReporter", "VaccineGenerator", "get_vaccine"]
