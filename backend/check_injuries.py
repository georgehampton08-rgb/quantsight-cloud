import sqlite3
conn = sqlite3.connect('data/nba_data.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Get all columns
c.execute('PRAGMA table_info(injuries)')
cols = [col[1] for col in c.fetchall()]
print("Columns:", cols)

# Get sample data
c.execute('SELECT * FROM injuries LIMIT 2')
for row in c.fetchall():
    print(dict(row))
