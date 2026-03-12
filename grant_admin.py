import os
import firebase_admin
from firebase_admin import credentials, auth, firestore

try:
    cred = credentials.ApplicationDefault()
    firebase_admin.initialize_app(cred)

    email = "georgehampton08@gmail.com"
    user = auth.get_user_by_email(email)
    print(f"User UID: {user.uid}")
    
    db = firestore.client()
    db.collection("admins").document(user.uid).set({
        "role": "admin", 
        "email": email, 
        "granted_at": firestore.SERVER_TIMESTAMP
    })
    
    print(f"Successfully granted admin role to {email} (UID: {user.uid})")
except Exception as e:
    print(f"Error: {e}")
