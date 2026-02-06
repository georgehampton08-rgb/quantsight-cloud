import sqlite3
import os

DB_PATH = os.path.join(os.getcwd(), 'backend', 'data', 'nba_data.db')

def inspect_db():
    print(f"Inspecting DB at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("❌ Database file not found!")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = cursor.fetchall()
    
    print(f"\nFound {len(tables)} tables:")
    for table in tables:
        table_name = table[0]
        print(f"\n--- Table: {table_name} ---")
        
        # Get columns
        cursor.execute(f"PRAGMA table_info({table_name});")
        columns = cursor.fetchall()
        for col in columns:
            # cid, name, type, notnull, dflt_value, pk
            print(f"  - {col[1]} ({col[2]})")

    conn.close()

if __name__ == "__main__":
    inspect_db()
