import sqlite3

conn = sqlite3.connect('database.db')

test_data = [
    ('paru',     5, 'absolutely delicious food loved the chicken rice',   '😀', 'Overall Experience'),
    ('pournamy', 1, 'terrible food very disappointed with the quality',   '☹️', 'Pricing'),
    ('sreedev',  4, 'good food nice taste will come again tomorrow',      '🙂', 'Quality'),
    ('nihadh',   3, 'food was okay nothing very special today',           '😐', 'Service'),
    ('sreepriya',5, 'excellent quality and fast service outstanding',     '😀', 'Quality'),
    ('arjun',    2, 'food was cold and not fresh very unhappy today',     '☹️', 'Delivery'),
    ('meera',    4, 'tasty porotta and curry enjoyed it very much',       '😀', 'Quality'),
    ('rahul',    1, 'worst canteen food horrible experience today',       '☹️', 'Overall Experience'),
]

conn.execute("DELETE FROM feedback")  # clear empty ones
for name, rating, comment, emoji, category in test_data:
    conn.execute(
        "INSERT INTO feedback (customer_name, rating, comment, emoji, category) VALUES (?, ?, ?, ?, ?)",
        (name, rating, comment, emoji, category)
    )

conn.commit()
conn.close()
print("Done! Added", len(test_data), "feedback entries with comments.")