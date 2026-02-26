"""
Index Doctor — Phase 4 Step 4.7
================================
When Firestore throws FailedPrecondition (missing composite index),
Vanguard detects it, generates the index patch, and opens a GitHub PR.

Constraints (non-negotiable):
  - Vanguard CANNOT merge the PR — human approval required
  - Vanguard CANNOT commit directly to main
  - If GITHUB_TOKEN is not set: log the index patch to stdout as
    structured JSON and post Vanguard incident with patch in metadata

Feature flag gate:
  Only activates when FEATURE_INDEX_DOCTOR=true.
"""

import json
import os
import re
from typing import Optional, Dict, Any
from datetime import datetime, timezone

from ..utils.logger import get_logger

logger = get_logger(__name__)


def is_missing_index_error(exception: Exception) -> bool:
    """
    Check if an exception is a Firestore FailedPrecondition for a missing index.
    """
    try:
        from google.api_core.exceptions import FailedPrecondition
        if isinstance(exception, FailedPrecondition):
            msg = str(exception).lower()
            return "index" in msg
    except ImportError:
        pass

    # Fallback: check error message string
    exc_str = str(exception).lower()
    return "failedprecondition" in exc_str and "index" in exc_str


def extract_index_definition(error_message: str) -> Optional[Dict[str, Any]]:
    """
    Parse a Firestore FailedPrecondition error message to extract the
    index definition.

    Firestore errors typically include a URL like:
    https://console.firebase.google.com/v1/r/project/.../firestore/indexes?create_composite=...

    Returns the index definition dict or None if parsing fails.
    """
    # Try to extract the composite index URL
    url_match = re.search(r'https://console\.firebase\.google\.com/[^\s]+create_composite=([^\s&]+)', error_message)

    # Try to extract collection and field information from the error
    collection_match = re.search(r"collection[:\s]+['\"]?(\w+)['\"]?", error_message, re.IGNORECASE)
    fields_match = re.findall(r"field[:\s]+['\"]?(\w+)['\"]?", error_message, re.IGNORECASE)

    if collection_match:
        collection_id = collection_match.group(1)
    else:
        # Attempt to extract any collection-like name
        collection_id = "unknown_collection"

    index_def = {
        "collectionGroup": collection_id,
        "queryScope": "COLLECTION",
        "fields": [],
    }

    if fields_match:
        for field_name in fields_match:
            index_def["fields"].append({
                "fieldPath": field_name,
                "order": "ASCENDING",
            })
    else:
        # If we can't parse fields, store the raw error for manual review
        index_def["_raw_error"] = error_message[:500]

    # Add the raw URL if found (most useful for one-click creation)
    if url_match:
        index_def["_console_url"] = url_match.group(0)

    return index_def


async def handle_missing_index(error_detail: str, error_fingerprint: str = "") -> Dict[str, Any]:
    """
    Handle a detected missing Firestore index.

    1. Parse the index definition from the error
    2. Read current firestore.indexes.json
    3. Create a GitHub PR with the fix (if GITHUB_TOKEN set)
    4. Post Vanguard incident

    Returns:
        Result dict with status, pr_url (if created), and index definition
    """
    result: Dict[str, Any] = {
        "status": "unknown",
        "index_definition": None,
        "pr_url": None,
        "fingerprint": error_fingerprint,
    }

    # Check feature flag
    try:
        from ..core.feature_flags import flag
        if not flag("FEATURE_INDEX_DOCTOR"):
            logger.info("index_doctor_disabled_by_flag")
            result["status"] = "disabled"
            return result
    except ImportError:
        pass

    # Parse index definition
    index_def = extract_index_definition(error_detail)
    if index_def is None:
        logger.warning("index_doctor_parse_failed", error=error_detail[:200])
        result["status"] = "parse_failed"
        return result

    result["index_definition"] = index_def
    logger.info("index_doctor_detected", collection=index_def.get("collectionGroup"))

    # Read current firestore.indexes.json
    indexes_path = os.getenv(
        "FIRESTORE_INDEXES_PATH",
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "firestore.indexes.json"),
    )

    current_indexes = {"indexes": [], "fieldOverrides": []}
    try:
        if os.path.exists(indexes_path):
            with open(indexes_path, "r", encoding="utf-8") as f:
                current_indexes = json.load(f)
    except Exception as e:
        logger.warning("index_doctor_read_indexes_failed", error=str(e))

    # Append new index
    updated_indexes = current_indexes.copy()
    if "indexes" not in updated_indexes:
        updated_indexes["indexes"] = []
    updated_indexes["indexes"].append(index_def)

    # Attempt GitHub PR
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        pr_url = await _create_github_pr(
            token=github_token,
            index_def=index_def,
            updated_indexes=updated_indexes,
            fingerprint=error_fingerprint,
        )
        if pr_url:
            result["pr_url"] = pr_url
            result["status"] = "pr_created"
        else:
            result["status"] = "pr_failed"
    else:
        # No token — log the patch as structured JSON
        logger.warning(
            "index_doctor_no_github_token",
            message="Logging index patch to stdout for manual action",
            index_patch=json.dumps(index_def, indent=2),
        )
        result["status"] = "logged_no_token"

    # Post Vanguard incident
    await _post_index_incident(index_def, result)

    return result


async def _create_github_pr(
    token: str,
    index_def: Dict,
    updated_indexes: Dict,
    fingerprint: str,
) -> Optional[str]:
    """
    Create a GitHub PR with the index fix.
    Vanguard CANNOT merge — human approval required.
    Vanguard CANNOT commit to main — creates a feature branch.
    """
    try:
        from ..core.config import get_vanguard_config
        config = get_vanguard_config()
        repo = config.vaccine_repo
        base_branch = config.vaccine_base_branch

        import httpx

        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json",
        }
        api_base = f"https://api.github.com/repos/{repo}"

        async with httpx.AsyncClient(timeout=15.0) as client:
            # 1. Get base branch SHA
            ref_resp = await client.get(
                f"{api_base}/git/ref/heads/{base_branch}",
                headers=headers,
            )
            ref_resp.raise_for_status()
            base_sha = ref_resp.json()["object"]["sha"]

            # 2. Create branch
            branch_name = f"vanguard/index-fix-{fingerprint[:12]}" if fingerprint else f"vanguard/index-fix-{int(datetime.now().timestamp())}"
            await client.post(
                f"{api_base}/git/refs",
                headers=headers,
                json={"ref": f"refs/heads/{branch_name}", "sha": base_sha},
            )

            # 3. Get current file SHA (if exists)
            file_path = "firestore.indexes.json"
            file_resp = await client.get(
                f"{api_base}/contents/{file_path}",
                headers=headers,
                params={"ref": branch_name},
            )
            file_sha = file_resp.json().get("sha") if file_resp.status_code == 200 else None

            # 4. Create/update the file
            import base64
            content_b64 = base64.b64encode(
                json.dumps(updated_indexes, indent=2).encode()
            ).decode()

            put_data = {
                "message": f"[Vanguard] Auto-fix: Missing Firestore index for {index_def.get('collectionGroup', 'unknown')}",
                "content": content_b64,
                "branch": branch_name,
            }
            if file_sha:
                put_data["sha"] = file_sha

            await client.put(
                f"{api_base}/contents/{file_path}",
                headers=headers,
                json=put_data,
            )

            # 5. Open PR
            collection = index_def.get("collectionGroup", "unknown")
            pr_body = (
                f"## [Vanguard] Auto-fix: Missing Firestore Index\n\n"
                f"**Error Fingerprint:** `{fingerprint}`\n\n"
                f"**Collection:** `{collection}`\n\n"
                f"**Proposed Index:**\n```json\n{json.dumps(index_def, indent=2)}\n```\n\n"
                f"⚠️ **This PR was auto-generated by Vanguard Index Doctor.**\n"
                f"Human approval is REQUIRED before merging.\n\n"
                f"[View Vanguard Incident](/vanguard/admin/incidents)\n"
            )

            pr_resp = await client.post(
                f"{api_base}/pulls",
                headers=headers,
                json={
                    "title": f"[Vanguard] Auto-fix: Missing Firestore index ({collection})",
                    "body": pr_body,
                    "head": branch_name,
                    "base": base_branch,
                },
            )
            pr_resp.raise_for_status()
            pr_url = pr_resp.json().get("html_url")

            logger.info("index_doctor_pr_created", pr_url=pr_url, collection=collection)
            return pr_url

    except Exception as e:
        logger.error("index_doctor_pr_failed", error=str(e))
        return None


async def _post_index_incident(index_def: Dict, result: Dict) -> None:
    """Post a Vanguard incident for the index fix attempt."""
    try:
        from ..archivist.storage import get_incident_storage
        from ..inquisitor.fingerprint import generate_error_fingerprint

        storage = get_incident_storage()
        fingerprint = generate_error_fingerprint(
            exception_type="INDEX_FIX_PR_OPENED",
            traceback_lines=[f"Missing index for {index_def.get('collectionGroup', 'unknown')}"],
            endpoint="firestore/index",
        )

        incident = {
            "fingerprint": fingerprint,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "severity": "AMBER",
            "status": "ACTIVE",
            "error_type": "INDEX_FIX_PR_OPENED",
            "error_message": f"Missing Firestore index detected: {index_def.get('collectionGroup', 'unknown')}",
            "endpoint": "firestore/index",
            "request_id": "surgeon-index-doctor",
            "traceback": None,
            "context_vector": {
                "index_definition": index_def,
                "pr_url": result.get("pr_url"),
                "status": result.get("status"),
            },
            "remediation_log": [],
            "resolved_at": None,
        }
        await storage.store(incident)
        logger.info("index_doctor_incident_posted",
                     collection=index_def.get("collectionGroup"),
                     status=result.get("status"))
    except Exception as e:
        logger.error("index_doctor_incident_failed", error=str(e))
