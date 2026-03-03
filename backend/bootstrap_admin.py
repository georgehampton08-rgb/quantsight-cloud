"""
bootstrap_admin.py — One-shot admin role grant
================================================
Run this ONCE to make YOUR Google account an admin.
After this, the backend require_admin_role will pass for your uid.

Usage:
    python bootstrap_admin.py YOUR_FIREBASE_UID

How to find your UID:
    1. Sign in to the app with Google
    2. Open browser console: firebase.auth().currentUser.uid
    OR:
    1. Go to Firebase Console → Authentication → Users tab
    2. Copy the UID column for your account

Safety:
    - This script ONLY adds to the admins Firestore collection.
    - It does NOT modify any other collections or user data.
    - It is idempotent — safe to run multiple times for the same UID.

Environment:
    - Requires GOOGLE_APPLICATION_CREDENTIALS pointing to service account
      with Firestore write permission (same creds used by Cloud Run).
    - Run from the backend/ directory.

Example:
    set GOOGLE_APPLICATION_CREDENTIALS=C:\\path\\to\\service_account.json
    python bootstrap_admin.py abc123def456
"""

import sys
import os


def bootstrap_admin(uid: str, email: str = "unknown") -> None:
    if not uid or len(uid) < 10:
        print(f"[FAIL] UID '{uid}' looks invalid. Get it from Firebase Console.")
        sys.exit(1)

    print(f"[INFO] Granting admin role to uid={uid} email={email}")

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        # Initialize with service account if not already initialized
        if not firebase_admin._apps:
            cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
            if not cred_path or not os.path.exists(cred_path):
                print("[FAIL] GOOGLE_APPLICATION_CREDENTIALS not set or file not found.")
                print("       Set it to your service account JSON path.")
                sys.exit(1)
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)

        db = firestore.client()
        doc_ref = db.collection("admins").document(uid)

        # Check if already exists
        existing = doc_ref.get()
        if existing.exists and existing.to_dict().get("role") == "admin":
            print(f"[PASS] uid={uid} is already admin. Nothing to do.")
            return

        # Grant role
        doc_ref.set({
            "role": "admin",
            "email": email,
            "granted_at": firestore.SERVER_TIMESTAMP,
            "granted_by": "bootstrap_admin.py",
        }, merge=True)

        print(f"[PASS] Admin role granted to uid={uid}")
        print()
        print("Next steps:")
        print("  1. Sign in to the app with the Google account for this UID")
        print("  2. Navigate to Vanguard Control Room")
        print("  3. Verify you can access stats/incidents without 403")

    except ImportError:
        print("[FAIL] firebase_admin not installed. Run: pip install firebase-admin")
        sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Error granting admin role: {e}")
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python bootstrap_admin.py <FIREBASE_UID> [email]")
        print()
        print("Example:")
        print("  python bootstrap_admin.py abc123def456xyz789 george@example.com")
        sys.exit(1)

    uid_arg = sys.argv[1].strip()
    email_arg = sys.argv[2].strip() if len(sys.argv) > 2 else "unknown"
    bootstrap_admin(uid_arg, email_arg)
