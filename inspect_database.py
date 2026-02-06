"""
Database Schema Inspector for QuantSight Cloud SQL
Connects to the database and shows all table structures
"""
import psycopg2
import os

# Database connection details
conn_string = "postgresql://quantsight:QSInvest2026$@/nba_data?host=/cloudsql/quantsight-prod:us-central1:quantsight-db"

# For local testing without Cloud SQL Proxy, use this format:
# conn_string = "postgresql://quantsight:QSInvest2026$@127.0.0.1:5432/nba_data"

print("=" * 80)
print("CLOUD SQL DATABASE SCHEMA INSPECTION")
print("=" * 80)

try:
    # Note: This will only work when run from Cloud Run with Cloud SQL connection
    # For local inspection, we need Cloud SQL Proxy running
    print("\n⚠️  This script should be run from Cloud Run environment")
    print("For local inspection, use: gcloud sql instances describe quantsight-db\n")
    
    # Alternative: Use gcloud to execute SQL
    print("Using gcloud to query database schema...\n")
    
    import subprocess
    
    # List all tables
    print("=" * 80)
    print("TABLES IN nba_data DATABASE")
    print("=" * 80)
    
    result = subprocess.run([
        'gcloud', 'sql', 'databases', 'list',
        '--instance=quantsight-db',
        '--format=table(name)'
    ], capture_output=True, text=True)
    
    print(result.stdout)
    
    # Get table list using psql via gcloud
    print("\n" + "=" * 80)
    print("GETTING TABLE SCHEMAS")
    print("=" * 80)
    
    # Tables we need to inspect
    tables_to_check = ['teams', 'players', 'player_rolling_averages', 'game_logs']
    
    for table in tables_to_check:
        print(f"\n\n### Table: {table}")
        print("-" * 80)
        
        # This will fail if not properly configured, but let's try
        try:
            # Use a simple approach - just show what the code expects
            print(f"Expected by backend code:")
            
            if table == 'teams':
                print("Columns: team_id, full_name, tricode, city, state, year_founded")
            elif table == 'players':
                print("Columns: player_id, full_name, team_abbreviation, position, height, weight")
            elif table == 'player_rolling_averages':
                print("Columns: player_id, points_avg, rebounds_avg, assists_avg, fg_pct, three_pct, ft_pct, games_played, last_updated")
            elif table == 'game_logs':
                print("Columns: Used for rolling averages")
                
        except Exception as e:
            print(f"Error: {e}")
    
    print("\n\n" + "=" * 80)
    print("⚠️  ACTUAL SCHEMA VERIFICATION NEEDED")
    print("=" * 80)
    print("\nTo verify actual schema, connect to database and run:")
    print("  1. \\dt  (list all tables)")
    print("  2. \\d teams (describe teams table)")
    print("  3. \\d players (describe players table)")
    print("  4. \\d player_rolling_averages (describe averages table)")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    print("\nThis is expected - we need to connect from Cloud Run or use Cloud SQL Proxy")

print("\n\n" + "=" * 80)
print("RECOMMENDED NEXT STEP")
print("=" * 80)
print("\nRun this from Cloud Shell (which has database access):")
print("\ngcloud sql connect quantsight-db --user=quantsight --database=nba_data")
print("\nThen in psql:")
print("  \\dt")
print("  \\d teams")
print("  \\d players")
print("  \\d player_rolling_averages")
