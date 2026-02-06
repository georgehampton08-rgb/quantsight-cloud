"""
Quick test to see if we can connect to Firestore at all
"""
import os
os.environ["GOOGLE_CLOUD_PROJECT"] = "quantsight-cloud-458498663186"

try:
    from google.cloud import firestore
    
    # Try direct connection
    db = firestore.Client(project="quantsight-cloud-458498663186")
    
    # Try to read from teams collection
    teams_ref = db.collection('teams')
    docs = list(teams_ref.limit(1).stream())
    
    print(f"✅ SUCCESS! Connected to Firestore")
    print(f"   Found {len(docs)} documents in teams collection")
    
    # Try to write a test document
    test_ref = db.collection('_test').document('connection_test')
    test_ref.set({'timestamp': firestore.SERVER_TIMESTAMP, 'test': True})
    print(f"✅ Write test successful!")
    
    # Clean up
    test_ref.delete()
    print(f"✅ All Firestore operations working!")
    
except Exception as e:
    print(f"❌ ERROR: {e}")
    print(f"\nThis means we need to either:")
    print(f"1. Set up a service account key file")
    print(f"2. Use a different authentication method")
    print(f"3. Deploy without local testing (test directly on Cloud Run)")
