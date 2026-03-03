from flask import Flask, render_template, request, redirect, session
import os
import pickle
import sys
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"

# ─────────────────────────────────────────────────────────────────────────────
#  DATABASE HELPER  — auto-detects PostgreSQL (Railway) or SQLite (local)
# ─────────────────────────────────────────────────────────────────────────────

DATABASE_URL = os.environ.get("DATABASE_URL")  # set automatically by Railway

def get_db_connection():
    if DATABASE_URL:
        import psycopg2
        import psycopg2.extras
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = False
        return conn
    else:
        import sqlite3
        conn = sqlite3.connect("database.db")
        conn.row_factory = sqlite3.Row
        return conn

def db_execute(conn, sql, params=()):
    """Run INSERT / UPDATE / DELETE — works for both SQLite and PostgreSQL."""
    if DATABASE_URL:
        import psycopg2.extras
        sql = sql.replace("?", "%s")
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    else:
        cur = conn.cursor()
    cur.execute(sql, params)
    return cur

def db_fetchall(conn, sql, params=()):
    """Run SELECT and return list of dict-like rows."""
    if DATABASE_URL:
        import psycopg2.extras
        sql = sql.replace("?", "%s")
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return cur.fetchall()
    else:
        cur = conn.execute(sql, params)
        return cur.fetchall()

def db_fetchone(conn, sql, params=()):
    """Run SELECT and return one dict-like row."""
    if DATABASE_URL:
        import psycopg2.extras
        sql = sql.replace("?", "%s")
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, params)
        return cur.fetchone()
    else:
        cur = conn.execute(sql, params)
        return cur.fetchone()

def db_commit(conn):
    conn.commit()

def db_close(conn):
    conn.close()

# ─────────────────────────────────────────────────────────────────────────────
#  INIT DB  — creates tables if they don't exist
# ─────────────────────────────────────────────────────────────────────────────

def init_db():
    os.makedirs("static/feedback_images", exist_ok=True)

    if DATABASE_URL:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL)
        cur  = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id       SERIAL PRIMARY KEY,
                email    TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name     TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS menu_items (
                id        SERIAL PRIMARY KEY,
                name      TEXT NOT NULL,
                price     REAL NOT NULL,
                quantity  INTEGER NOT NULL DEFAULT 0,
                available INTEGER NOT NULL DEFAULT 1
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id            SERIAL PRIMARY KEY,
                customer_name TEXT NOT NULL,
                item_id       INTEGER NOT NULL,
                quantity      INTEGER NOT NULL,
                status        TEXT NOT NULL DEFAULT 'Pending',
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id            SERIAL PRIMARY KEY,
                customer_name TEXT NOT NULL,
                rating        INTEGER NOT NULL,
                comment       TEXT,
                emoji         TEXT,
                category      TEXT,
                image_path    TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        cur.close()
        conn.close()
        print("PostgreSQL tables ready")
    else:
        import sqlite3
        conn = sqlite3.connect("database.db")
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS customers (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                email    TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name     TEXT
            );
            CREATE TABLE IF NOT EXISTS menu_items (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                name      TEXT NOT NULL,
                price     REAL NOT NULL,
                quantity  INTEGER NOT NULL DEFAULT 0,
                available INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS orders (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                item_id       INTEGER NOT NULL,
                quantity      INTEGER NOT NULL,
                status        TEXT NOT NULL DEFAULT 'Pending',
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (item_id) REFERENCES menu_items(id)
            );
            CREATE TABLE IF NOT EXISTS feedback (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                rating        INTEGER NOT NULL,
                comment       TEXT,
                emoji         TEXT,
                category      TEXT,
                image_path    TEXT,
                created_at    DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
        print("SQLite tables ready")


# ─────────────────────────────────────────────────────────────────────────────
#  CUSTOMER ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route('/')
def home():
    return render_template("index.html")

@app.route('/custlogin', methods=['GET', 'POST'])
def custlogin():
    if request.method == 'POST':
        email    = request.form['email']
        password = request.form['password']
        if email and password:
            session["customer_name"] = email
            return redirect("/customer_dashboard")
        else:
            return render_template("custlogin.html", error="Please enter email and password")
    return render_template("custlogin.html")

@app.route('/custlogout')
def custlogout():
    session.pop("customer_name", None)
    return redirect("/")

@app.route("/customer_dashboard")
def customer_dashboard():
    if "customer_name" not in session:
        return redirect("/custlogin")
    return render_template("customer_dashboard.html")

@app.route("/menu")
def menu():
    conn  = get_db_connection()
    items = db_fetchall(conn, "SELECT * FROM menu_items WHERE available = 1 AND quantity > 0")
    db_close(conn)
    return render_template("menu.html", items=items)

@app.route('/place_order_single', methods=['POST'])
def place_order_single():
    if 'customer_name' not in session:
        return redirect('/custlogin')
    item_id = int(request.form['item_id'])
    qty     = int(request.form['quantity'])
    conn    = get_db_connection()
    item    = db_fetchone(conn, "SELECT quantity, price FROM menu_items WHERE id = ?", (item_id,))
    if not item:
        db_close(conn)
        return "Item not found", 404
    if item["quantity"] < qty:
        db_close(conn)
        return "Not enough stock", 400
    db_execute(conn,
        "INSERT INTO orders (customer_name, item_id, quantity, status) VALUES (?, ?, ?, 'Pending')",
        (session["customer_name"], item_id, qty))
    db_execute(conn,
        "UPDATE menu_items SET quantity = quantity - ? WHERE id = ?", (qty, item_id))
    db_commit(conn)
    db_close(conn)
    return redirect('/my_orders')

@app.route("/my_orders")
def my_orders():
    if "customer_name" not in session:
        return redirect("/custlogin")
    conn   = get_db_connection()
    orders = db_fetchall(conn, """
        SELECT o.id AS order_id, m.name, o.quantity, o.status
        FROM orders o JOIN menu_items m ON o.item_id = m.id
        WHERE o.customer_name = ? ORDER BY o.id DESC
    """, (session["customer_name"],))
    db_close(conn)
    return render_template("my_orders.html", orders=orders)

@app.route("/cancel_order/<int:order_id>")
def cancel_order(order_id):
    if "customer_name" not in session:
        return redirect("/custlogin")
    conn  = get_db_connection()
    order = db_fetchone(conn,
        "SELECT item_id, quantity, status FROM orders WHERE id = ? AND customer_name = ?",
        (order_id, session["customer_name"]))
    if order and order["status"] == "Pending":
        db_execute(conn, "UPDATE menu_items SET quantity = quantity + ? WHERE id = ?",
            (order["quantity"], order["item_id"]))
        db_execute(conn, "DELETE FROM orders WHERE id = ?", (order_id,))
        db_commit(conn)
    db_close(conn)
    return redirect("/my_orders")

@app.route("/wishlist")
def wishlist():
    if "customer_name" not in session:
        return redirect("/custlogin")
    return render_template("wishlist.html")

@app.route("/trending")
def trending():
    if "customer_name" not in session:
        return redirect("/custlogin")
    conn  = get_db_connection()
    items = db_fetchall(conn, """
        SELECT m.name, m.price, COUNT(o.id) AS order_count
        FROM orders o JOIN menu_items m ON o.item_id = m.id
        GROUP BY o.item_id, m.name, m.price ORDER BY order_count DESC LIMIT 10
    """)
    db_close(conn)
    return render_template("trending.html", items=items)

@app.route("/give_feedback")
def give_feedback():
    if "customer_name" not in session:
        return redirect("/custlogin")
    return render_template("give_feedback.html")

@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    if "customer_name" not in session:
        return redirect("/custlogin")
    rating        = request.form["rating"]
    comment       = request.form["comment"]
    emoji         = request.form.get("emoji")
    category      = request.form["category"]
    customer_name = session["customer_name"]
    image         = request.files.get("image")
    image_path    = None
    if image and image.filename != "":
        filename   = secure_filename(image.filename)
        image_path = os.path.join("static/feedback_images", filename)
        image.save(image_path)
    conn = get_db_connection()
    db_execute(conn, """
        INSERT INTO feedback (customer_name, rating, comment, emoji, category, image_path)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (customer_name, rating, comment, emoji, category, image_path))
    db_commit(conn)
    db_close(conn)
    return redirect("/my_feedback")

@app.route("/my_feedback")
def my_feedback():
    if "customer_name" not in session:
        return redirect("/custlogin")
    conn     = get_db_connection()
    feedback = db_fetchall(conn,
        "SELECT * FROM feedback WHERE customer_name = ? ORDER BY id DESC",
        (session["customer_name"],))
    db_close(conn)
    return render_template("my_feedback.html", feedback=feedback)


# ─────────────────────────────────────────────────────────────────────────────
#  SHOPKEEPER ROUTES
# ─────────────────────────────────────────────────────────────────────────────

@app.route("/shopkeeper_login", methods=["GET", "POST"])
def shopkeeper_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        if username == "shop" and password == "123":
            session["shopkeeper"] = True
            return redirect("/shopkeeper_home")
        else:
            return render_template("shopkeeper_login.html", error="Invalid login")
    return render_template("shopkeeper_login.html")

@app.route("/shopkeeper_logout")
def shopkeeper_logout():
    session.pop("shopkeeper", None)
    return redirect("/")

@app.route('/shopkeeper_home')
def shopkeeper_home():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    return render_template("shopkeeper_home.html")

@app.route("/shopkeeper_dashboard")
def shopkeeper_dashboard():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    conn  = get_db_connection()
    items = db_fetchall(conn, "SELECT * FROM menu_items")
    db_close(conn)
    return render_template("shopkeeper_dashboard.html", items=items)

@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    if request.method == "POST":
        name     = request.form["name"]
        price    = request.form["price"]
        quantity = request.form["quantity"]
        conn     = get_db_connection()
        db_execute(conn,
            "INSERT INTO menu_items (name, price, quantity) VALUES (?, ?, ?)",
            (name, price, quantity))
        db_commit(conn)
        db_close(conn)
        return redirect("/shopkeeper_dashboard")
    return render_template("add_item.html")

@app.route("/edit_item/<int:item_id>", methods=["GET", "POST"])
def edit_item(item_id):
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    conn = get_db_connection()
    if request.method == "POST":
        quantity = request.form["quantity"]
        price    = request.form["price"]
        db_execute(conn,
            "UPDATE menu_items SET quantity = ?, price = ? WHERE id = ?",
            (quantity, price, item_id))
        db_commit(conn)
        db_close(conn)
        return redirect("/shopkeeper_dashboard")
    item = db_fetchone(conn, "SELECT * FROM menu_items WHERE id = ?", (item_id,))
    db_close(conn)
    return render_template("edit_item.html", item=item)

@app.route("/update_availability/<int:item_id>/<int:status>")
def update_availability(item_id, status):
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    conn = get_db_connection()
    db_execute(conn, "UPDATE menu_items SET available = ? WHERE id = ?", (status, item_id))
    db_commit(conn)
    db_close(conn)
    return redirect("/shopkeeper_dashboard")

@app.route('/shopkeeper/orders')
def view_orders():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    conn   = get_db_connection()
    orders = db_fetchall(conn, """
        SELECT o.id AS order_id, o.customer_name, m.name AS item_name, o.quantity, o.status
        FROM orders o JOIN menu_items m ON o.item_id = m.id
        ORDER BY o.id DESC
    """)
    db_close(conn)
    return render_template('shopkeeper_orders.html', orders=orders)

@app.route("/update_order_status/<int:order_id>", methods=["POST"])
def update_order_status(order_id):
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    new_status = request.form["status"]
    conn       = get_db_connection()
    db_execute(conn, "UPDATE orders SET status = ? WHERE id = ?", (new_status, order_id))
    db_commit(conn)
    db_close(conn)
    return redirect("/shopkeeper/orders")

@app.route("/reviews")
def reviews():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    conn     = get_db_connection()
    feedback = db_fetchall(conn, "SELECT * FROM feedback ORDER BY id DESC")
    db_close(conn)
    return render_template("reviews.html", feedback=feedback)

@app.route("/analytics")
def analytics():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    conn       = get_db_connection()
    top_items  = db_fetchall(conn, """
        SELECT m.name, SUM(o.quantity) AS total_ordered
        FROM orders o JOIN menu_items m ON o.item_id = m.id
        GROUP BY o.item_id, m.name ORDER BY total_ordered DESC LIMIT 5
    """)
    total_orders = db_fetchone(conn, "SELECT COUNT(*) AS cnt FROM orders")
    avg_rating   = db_fetchone(conn, "SELECT ROUND(AVG(rating),1) AS avg FROM feedback")
    db_close(conn)
    return render_template("analytics.html", top_items=top_items,
                           total_orders=total_orders, avg_rating=avg_rating)


# ─────────────────────────────────────────────────────────────────────────────
#  ML ROUTES
# ─────────────────────────────────────────────────────────────────────────────

def load_ml_models():
    ml_dir = os.path.join(os.path.dirname(__file__), 'ml')
    models = {}
    try:
        with open(os.path.join(ml_dir, 'stock_model.pkl'), 'rb') as f:
            models['stock'] = pickle.load(f)
        with open(os.path.join(ml_dir, 'sentiment_model.pkl'), 'rb') as f:
            models['sentiment'] = pickle.load(f)
        with open(os.path.join(ml_dir, 'tfidf_vectorizer.pkl'), 'rb') as f:
            models['vectorizer'] = pickle.load(f)
    except FileNotFoundError:
        models = {}
    return models

ML_MODELS = load_ml_models()

@app.route("/ml_dashboard")
def ml_dashboard():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    return render_template("ml_dashboard.html")

@app.route("/ml/stock_prediction")
def ml_stock_prediction():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    if not ML_MODELS:
        return render_template("ml_stock.html",
            error="Models not trained yet. Run: python ml/train_models.py",
            predictions=None, items_info={})

    import pandas as pd
    from datetime import datetime, timedelta

    model             = ML_MODELS["stock"]
    tomorrow          = datetime.now() + timedelta(days=1)
    dow, dom, mon     = tomorrow.weekday(), tomorrow.day, tomorrow.month

    conn  = get_db_connection()
    items = db_fetchall(conn, "SELECT id, name, quantity, price FROM menu_items")
    db_close(conn)

    predictions = []
    for item in items:
        X = pd.DataFrame([[item["id"], dow, dom, mon]],
                         columns=["item_id", "day_of_week", "day_of_month", "month"])
        pred_qty       = max(1, int(round(model.predict(X)[0])))
        current_stock  = item["quantity"]
        reorder_needed = max(0, pred_qty - current_stock)
        status         = "OK" if current_stock >= pred_qty else "LOW"
        predictions.append({
            "item_id": item["id"], "name": item["name"],
            "current_stock": current_stock, "predicted_demand": pred_qty,
            "reorder_needed": reorder_needed, "status": status
        })

    predictions.sort(key=lambda x: x["reorder_needed"], reverse=True)
    return render_template("ml_stock.html", predictions=predictions,
                           tomorrow=tomorrow.strftime("%A, %d %B %Y"), error=None)

@app.route("/ml/retrain", methods=["POST"])
def ml_retrain():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    import subprocess
    script = os.path.join(os.path.dirname(__file__), "ml", "train_models.py")
    subprocess.run([sys.executable, script], capture_output=True)
    global ML_MODELS
    ML_MODELS = load_ml_models()
    return redirect("/ml_dashboard")

@app.route("/ml/sentiment_analysis")
def ml_sentiment_analysis():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")

    empty_stats = {"total": 0, "correct": 0, "accuracy": 0,
                   "avg_actual": 0, "avg_predicted": 0}

    if not ML_MODELS:
        return render_template("ml_sentiment.html",
            error="Models not trained yet. Run: python ml/train_models.py",
            results=[], stats=empty_stats)

    conn      = get_db_connection()
    feedbacks = db_fetchall(conn,
        "SELECT * FROM feedback WHERE comment IS NOT NULL AND comment != '' ORDER BY id DESC")
    db_close(conn)

    model      = ML_MODELS["sentiment"]
    vectorizer = ML_MODELS["vectorizer"]
    results    = []

    for fb in feedbacks:
        comment = fb["comment"] or ""
        if comment.strip():
            X                = vectorizer.transform([comment])
            predicted_rating = int(model.predict(X)[0])
            proba            = model.predict_proba(X)[0]
            confidence       = round(float(max(proba)) * 100, 1)
            actual           = int(fb["rating"])
            match            = "✅" if predicted_rating == actual else "❌"
            results.append({
                "customer": fb["customer_name"],
                "comment": comment[:80] + ("..." if len(comment) > 80 else ""),
                "actual_rating": actual,
                "predicted_rating": predicted_rating,
                "confidence": confidence,
                "match": match,
                "category": fb["category"]
            })

    total         = len(results)
    correct       = sum(1 for r in results if r["match"] == "✅")
    accuracy      = round(correct / total * 100, 1) if total > 0 else 0
    avg_actual    = round(sum(r["actual_rating"]    for r in results) / total, 2) if total > 0 else 0
    avg_predicted = round(sum(r["predicted_rating"] for r in results) / total, 2) if total > 0 else 0

    stats = {"total": total, "correct": correct, "accuracy": accuracy,
             "avg_actual": avg_actual, "avg_predicted": avg_predicted}

    return render_template("ml_sentiment.html", results=results, stats=stats, error=None)

@app.route("/ml/predict_rating", methods=["GET", "POST"])
def ml_predict_rating():
    if not session.get("shopkeeper"):
        return redirect("/shopkeeper_login")
    result = None
    if request.method == "POST":
        text = request.form.get("review_text", "").strip()
        if text and ML_MODELS:
            X          = ML_MODELS["vectorizer"].transform([text])
            rating     = int(ML_MODELS["sentiment"].predict(X)[0])
            proba      = ML_MODELS["sentiment"].predict_proba(X)[0]
            confidence = round(float(max(proba)) * 100, 1)
            result     = {"text": text, "rating": rating, "confidence": confidence,
                          "stars": "⭐" * rating}
    return render_template("ml_predict_rate.html", result=result)

@app.route('/admin_help')
def admin_help():
    return "Admin Help Page (coming soon)"


# ─────────────────────────────────────────────────────────────────────────────
#  STARTUP
# ─────────────────────────────────────────────────────────────────────────────

init_db()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)