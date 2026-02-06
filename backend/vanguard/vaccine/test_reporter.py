"""
Test Reporter
=============
Generate pass/fail reports for chaos tests.
"""

import json
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

from ..core.config import get_vanguard_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class TestReport(Dict[str, Any]):
    """Test report structure."""
    pass


class TestReporter:
    """Generates and stores chaos test reports."""
    
    def __init__(self):
        config = get_vanguard_config()
        self.reports_path = Path(config.storage_path) / "vaccine_reports"
        self.reports_path.mkdir(parents=True, exist_ok=True)
    
    def generate_report(
        self,
        scenario: str,
        detected: bool,
        remediation_time_ms: float,
        passed: bool,
        details: Dict[str, Any]
    ) -> TestReport:
        """
        Generate a test report.
        
        Args:
            scenario: Scenario name
            detected: Whether Vanguard detected the injected failure
            remediation_time_ms: Time to remediate in milliseconds
            passed: Overall pass/fail
            details: Additional details
        
        Returns:
            TestReport dictionary
        """
        report: TestReport = {
            "scenario": scenario,
            "timestamp": datetime.utcnow().isoformat(),
            "detected": detected,
            "remediation_time_ms": remediation_time_ms,
            "passed": passed,
            "details": details
        }
        
        # Save report
        self._save_report(report)
        
        logger.info(
            "test_report_generated",
            scenario=scenario,
            passed=passed,
            detected=detected
        )
        
        return report
    
    def _save_report(self, report: TestReport) -> None:
        """Save report to disk."""
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = f"{report['scenario']}_{timestamp}.json"
        filepath = self.reports_path / filename
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)
        
        logger.debug("test_report_saved", filename=filename)
    
    def get_recent_reports(self, limit: int = 10) -> List[TestReport]:
        """Get recent test reports."""
        report_files = sorted(
            self.reports_path.glob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )[:limit]
        
        reports = []
        for filepath in report_files:
            with open(filepath, "r") as f:
                reports.append(json.load(f))
        
        return reports
    
    def calculate_pass_rate(self, days: int = 30) -> float:
        """Calculate pass rate for recent tests."""
        reports = self.get_recent_reports(limit=100)
        
        if not reports:
            return 0.0
        
        passed = sum(1 for r in reports if r.get("passed"))
        total = len(reports)
        
        return (passed / total) * 100 if total > 0 else 0.0
