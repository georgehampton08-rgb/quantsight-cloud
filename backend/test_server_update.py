"""Quick test to verify server has updated ai_insights"""
import requests

try:
    # Test the matchup analyze endpoint
    response = requests.get(
        "http://localhost:5000/matchup/analyze",
        params={"home_team": "BOS", "away_team": "MIA"},
        timeout=15
    )
    
    if response.status_code == 200:
        data = response.json()
        insights = data.get('insights', {})
        summary = insights.get('summary', '')
        
        print("=" * 60)
        print("Current AI Insights Summary:")
        print("=" * 60)
        print(f"\n{summary}\n")
        
        # Check if it mentions defense properly
        if 'without defensive' in summary.lower():
            print("❌ Server still using OLD ai_insights.py")
            print("   Need to restart the backend server")
        elif 'defense' in summary.lower() or 'defensive' in summary.lower():
            print("✅ Server using UPDATED ai_insights.py")
        else:
            print("⚠️  AI may be using different focus (check if it mentions pace or other stats)")
            
    else:
        print(f"❌ API Error: {response.status_code}")
        
except Exception as e:
    print(f"❌ Connection Error: {e}")
    print("   Is the Flask server running?")
