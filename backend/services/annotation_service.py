"""
Annotation Service — Phase 8 Step 8.4
=======================================
Collaborative annotation layer for shared notes on players, incidents, and games.
Annotations are stored in Firestore and broadcast to WebSocket subscribers in real time.

Firestore collection structure:
  player_annotations/{player_id}/notes/{note_id}
  incident_annotations/{fingerprint}/notes/{note_id}
  game_annotations/{game_id}/notes/{note_id}

Each note document:
  { note_id, author_token, content, created_at, edited_at,
    pinned, reactions: { "👍": 0, "🔥": 0, "⚠️": 0 } }
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────
MAX_CONTENT_LENGTH = 500
MAX_NOTES_PER_CONTEXT = 100
ALLOWED_REACTIONS = {"👍", "🔥", "⚠️"}
VALID_CONTEXT_TYPES = {"player", "incident", "game"}


def _get_firestore_client():
    """Get Firestore client (lazy import to avoid import-time crashes)."""
    try:
        import firebase_admin
        from firebase_admin import firestore as fs

        # Ensure Firebase is initialized
        try:
            firebase_admin.get_app()
        except ValueError:
            return None

        return fs.client()
    except Exception:
        return None


class AnnotationService:
    """
    Manages collaborative annotations stored in Firestore.
    Thread-safe — Firestore client handles concurrency.
    """

    async def add_annotation(
        self,
        context_type: str,
        context_id: str,
        session_token: str,
        content: str,
    ) -> dict:
        """
        Create a new annotation note.
        Raises ValueError for validation failures.
        Returns the created note dict.
        """
        # Validate
        if context_type not in VALID_CONTEXT_TYPES:
            raise ValueError(f"context_type must be one of {VALID_CONTEXT_TYPES}")

        if not content or not content.strip():
            raise ValueError("content cannot be empty")

        if len(content) > MAX_CONTENT_LENGTH:
            raise ValueError(f"Annotation exceeds {MAX_CONTENT_LENGTH} chars")

        if not context_id:
            raise ValueError("context_id is required")

        # Check note count limit
        count = await self._count_notes(context_type, context_id)
        if count >= MAX_NOTES_PER_CONTEXT:
            raise ValueError(
                f"Annotation limit reached ({MAX_NOTES_PER_CONTEXT}) for this context"
            )

        note_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        note = {
            "note_id": note_id,
            "author_token": session_token[:8] + "...",
            "content": content.strip(),
            "created_at": now,
            "edited_at": None,
            "pinned": False,
            "reactions": {
                "👍": 0,
                "🔥": 0,
                "⚠️": 0,
            },
        }

        # Write to Firestore
        db = _get_firestore_client()
        if db is None:
            logger.warning("annotation_firestore_unavailable")
            # Still return the note for WebSocket broadcast (ephemeral)
            return note

        try:
            collection = f"{context_type}_annotations"
            doc_ref = (
                db.collection(collection)
                .document(context_id)
                .collection("notes")
                .document(note_id)
            )
            doc_ref.set(note)
            logger.info(
                "annotation_created",
                extra={
                    "context_type": context_type,
                    "context_id": context_id,
                    "note_id": note_id,
                },
            )
        except Exception as e:
            logger.error(f"annotation_write_failed: {e}")
            # Still return note for WS broadcast (best-effort persistence)

        return note

    async def get_annotations(
        self,
        context_type: str,
        context_id: str,
        limit: int = 50,
    ) -> list:
        """
        Get annotations for a context, ordered by created_at desc.
        Returns empty list if Firestore unavailable.
        """
        db = _get_firestore_client()
        if db is None:
            return []

        try:
            collection = f"{context_type}_annotations"
            query = (
                db.collection(collection)
                .document(context_id)
                .collection("notes")
                .order_by("created_at", direction="DESCENDING")
                .limit(limit)
            )
            docs = query.stream()
            return [doc.to_dict() for doc in docs]
        except Exception as e:
            logger.error(f"annotation_read_failed: {e}")
            return []

    async def add_reaction(
        self,
        context_type: str,
        context_id: str,
        note_id: str,
        reaction: str,
    ):
        """
        Increment a reaction count atomically.
        Raises ValueError if reaction is not allowed.
        """
        if reaction not in ALLOWED_REACTIONS:
            raise ValueError(f"Reaction must be one of {ALLOWED_REACTIONS}")

        db = _get_firestore_client()
        if db is None:
            logger.warning("reaction_firestore_unavailable")
            return

        try:
            from google.cloud.firestore_v1 import Increment

            collection = f"{context_type}_annotations"
            doc_ref = (
                db.collection(collection)
                .document(context_id)
                .collection("notes")
                .document(note_id)
            )
            doc_ref.update({f"reactions.{reaction}": Increment(1)})
            logger.info(
                "reaction_added",
                extra={
                    "note_id": note_id,
                    "reaction": reaction,
                },
            )
        except Exception as e:
            logger.error(f"reaction_write_failed: {e}")

    async def _count_notes(
        self,
        context_type: str,
        context_id: str,
    ) -> int:
        """Count existing notes for a context."""
        db = _get_firestore_client()
        if db is None:
            return 0

        try:
            collection = f"{context_type}_annotations"
            query = (
                db.collection(collection)
                .document(context_id)
                .collection("notes")
            )
            # Use aggregation count if available, otherwise stream
            docs = list(query.limit(MAX_NOTES_PER_CONTEXT + 1).stream())
            return len(docs)
        except Exception as e:
            logger.error(f"annotation_count_failed: {e}")
            return 0


# ── Global singleton ─────────────────────────────────────────────────────────
_service: Optional[AnnotationService] = None


def get_annotation_service() -> AnnotationService:
    """Get or create the global annotation service."""
    global _service
    if _service is None:
        _service = AnnotationService()
    return _service
