import sqlite3

connection = sqlite3.connect('database.db')
cursor = connection.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS menu_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    available INTEGER NOT NULL DEFAULT 1
);
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    item_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
""")
cursor.execute("""
CREATE TABLE feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    message TEXT,
    rating INTEGER
);
""")
cursor.execute("""
CREATE TABLE wishlist (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER,
    item_id INTEGER
);
""")

connection.commit()
connection.close()

print("Database created successfully!")