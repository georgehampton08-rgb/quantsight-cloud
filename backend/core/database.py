"""
Database Configuration for Cloud Backend - FIRESTORE VERSION
============================================================
No SQL dependencies. All data operations use Firestore.
"""
import logging

logger = logging.getLogger(__name__)

# Firestore is imported elsewhere - this file exists for compatibility
# All database operations should use firestore_db.py functions directly

def get_db():
    """Legacy compatibility - returns None since we use Firestore directly."""
    logger.warning("get_db() called but Firestore doesn't use sessions. Use firestore_db functions directly.")
    return None

def get_db_connection():
    """Legacy compatibility - returns None since we use Firestore directly."""
    logger.warning("get_db_connection() called but Firestore doesn't use connections. Use firestore_db functions directly.")
    return None
