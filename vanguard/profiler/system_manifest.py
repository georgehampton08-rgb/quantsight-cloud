"""
System Manifest Generator
==========================
Creates infrastructure inventory for RAG grounding.
"""

from typing import TypedDict, List
from ..core.config import get_vanguard_config
from ..utils.logger import get_logger

logger = get_logger(__name__)


class SystemManifest(TypedDict):
    """System manifest structure."""
    platform: str
    database: str
    cache: str
    available_playbooks: List[str]
    recent_deployments: List[dict]
    file_tree: dict


def generate_system_manifest() -> SystemManifest:
    """
    Generate system manifest for LLM grounding.
    
    Returns:
        SystemManifest with infrastructure details
    """
    config = get_vanguard_config()
    
    manifest: SystemManifest = {
        "platform": "Google Cloud Run (serverless)",
        "database": "PostgreSQL (Cloud SQL)",
        "cache": f"Redis ({config.redis_url})",
        "available_playbooks": [
            "Connection Timeout Syndrome",
            "Memory Leak Cascade",
            "Database Integrity Violation",
        ],
        "recent_deployments": [
            # TODO: Fetch from git or deployment logs
            {"timestamp": "2026-02-03", "commit": "latest", "changes": "Vanguard integration"}
        ],
        "file_tree": {
            "backend": {
                "routers": ["public_routes", "admin_routes", "nexus_routes"],
                "services": ["async_pulse_producer_cloud"],
                "shared_core": ["aegis_engine", "vertex_matchup", "usage_vacuum"],
                "vanguard": ["inquisitor", "surgeon", "profiler", "archivist"]
            }
        }
    }
    
    logger.debug("system_manifest_generated")
    return manifest
