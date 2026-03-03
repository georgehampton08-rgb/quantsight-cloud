# bootstrap_admin.py — One-shot admin role grant
# Usage:
#   python bootstrap_admin.py --email georgehampton08@gmail.com
#   python bootstrap_admin.py <FIREBASE_UID> [email]
#
# Requires: GOOGLE_APPLICATION_CREDENTIALS env var pointing to service account JSON

import sys
import os


def _init_firebase():
    import firebase_admin
    from firebase_admin import credentials
    if not firebase_admin._apps:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if cred_path and os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)
            firebase_admin.initialize_app(cred)
        else:
            # Fall back to Application Default Credentials (gcloud auth)
            firebase_admin.initialize_app()
            print("[INFO] Using Application Default Credentials (gcloud auth)")


def lookup_uid_by_email(email: str) -> str:
    """Look up Firebase UID from email using Admin SDK."""
    _init_firebase()
    from firebase_admin import auth as fb_auth
    try:
        user = fb_auth.get_user_by_email(email)
        print(f"[PASS] Found user: uid={user.uid} email={user.email} name={user.display_name}")
        return user.uid
    except fb_auth.UserNotFoundError:
        print(f"[FAIL] No Firebase user found for email '{email}'.")
        print("       Sign in to the app with Google first, then re-run this script.")
        sys.exit(1)
    except Exception as e:
        print(f"[FAIL] Error looking up user: {e}")
        sys.exit(1)


def bootstrap_admin(uid: str, email: str = "unknown") -> None:
    if not uid or len(uid) < 10:
        print(f"[FAIL] UID '{uid}' looks invalid. Get it from Firebase Console.")
        sys.exit(1)

    print(f"[INFO] Granting admin role to uid={uid} email={email}")
    _init_firebase()

    try:
        from firebase_admin import firestore
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
        print("Usage:")
        print("  python bootstrap_admin.py --email georgehampton08@gmail.com")
        print("  python bootstrap_admin.py <FIREBASE_UID> [email]")
        sys.exit(1)

    if sys.argv[1] == "--email":
        if len(sys.argv) < 3:
            print("[FAIL] --email requires an email address.")
            sys.exit(1)
        email_addr = sys.argv[2].strip()
        uid = lookup_uid_by_email(email_addr)
        bootstrap_admin(uid, email_addr)
    else:
        uid_arg = sys.argv[1].strip()
        email_arg = sys.argv[2].strip() if len(sys.argv) > 2 else "unknown"
        bootstrap_admin(uid_arg, email_arg)
