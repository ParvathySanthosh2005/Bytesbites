import sqlite3
conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
rows = conn.execute('SELECT * FROM feedback').fetchall()
print('Total feedback rows:', len(rows))
if rows:
    print('Columns:', list(rows[0].keys()))
    for r in rows[:3]:
        print(dict(r))
conn.close()