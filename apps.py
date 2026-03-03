from flask import Flask, render_template, request, redirect,session
import sqlite3
app = Flask(__name__)
app.secret_key="supersecretkey"
def get_db_connection():
    connection = sqlite3.connect('database.db')
    connection.row_factory = sqlite3.Row
    return connection
@app.route('/')
def home():
    return render_template("index.html")
@app.route('/custlogin', methods=['GET', 'POST'])
def custlogin():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        # TODO: Check credentials in database
        session["customer_name"]=email
        return redirect("/customer_dashboard")
    return render_template("custlogin.html")
@app.route("/customer_dashboard")
def customer_dashboard():
    return render_template("customer_dashboard.html")
@app.route("/menu")
def menu():
    connection = get_db_connection()
    items = connection.execute("""
        SELECT * FROM menu_items
        WHERE available = 1 AND quantity > 0
    """).fetchall()
    connection.close()
    return render_template("menu.html", items=items)
@app.route('/place_order_single', methods=['POST'])
def place_order_single():
    if 'customer_name' not in session:
        return redirect('/custlogin')

    item_id = int(request.form['item_id'])
    qty = int(request.form['quantity'])

    connection = get_db_connection()

    # Fetch item
    item = connection.execute("""
        SELECT quantity, price
        FROM menu_items
        WHERE id = ?
    """, (item_id,)).fetchone()

    if not item:
        connection.close()
        return "Item not found"

    if item["quantity"] < qty:
        connection.close()
        return "Not enough stock"

    # Insert order
    connection.execute("""
        INSERT INTO orders (customer_name, item_id, quantity, status)
        VALUES (?, ?, ?, 'Pending')
    """, (session["customer_name"], item_id, qty))

    # Reduce stock
    connection.execute("""
        UPDATE menu_items
        SET quantity = quantity - ?
        WHERE id = ?
    """, (qty, item_id))

    connection.commit()
    connection.close()

    return redirect('/my_orders')
@app.route("/give_feedback")
def give_feedback():
    if "customer_name" not in session:
        return redirect("/custlogin")
    return render_template("give_feedback.html")
import os
from werkzeug.utils import secure_filename
@app.route("/submit_feedback", methods=["POST"])
def submit_feedback():
    if "customer_name" not in session:
        return redirect("/custlogin")

    rating = request.form["rating"]
    comment = request.form["comment"]
    emoji = request.form.get("emoji")
    category = request.form["category"]
    customer_name = session["customer_name"]

    image = request.files.get("image")
    image_path = None

    if image and image.filename != "":
        filename = secure_filename(image.filename)
        image_path = os.path.join("static/feedback_images", filename)
        image.save(image_path)

    connection = get_db_connection()
    connection.execute("""
        INSERT INTO feedback (customer_name, rating, comment, emoji, category, image_path)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (customer_name, rating, comment, emoji, category, image_path))
    connection.commit()
    connection.close()

    return redirect("/my_feedback")
@app.route("/my_feedback")
def my_feedback():
    if "customer_name" not in session:
        return redirect("/custlogin")

    connection = get_db_connection()
    feedback = connection.execute("""
        SELECT * FROM feedback
        WHERE customer_name = ?
        ORDER BY id DESC
    """, (session["customer_name"],)).fetchall()
    connection.close()

    return render_template("my_feedback.html", feedback=feedback)

@app.route("/my_orders")
def my_orders():
    connection = get_db_connection()
    orders = connection.execute("""
        SELECT o.id AS order_id, m.name, o.quantity, o.status
        FROM orders o
        JOIN menu_items m ON o.item_id = m.id
        WHERE o.customer_name = ?
        ORDER BY o.id DESC
    """, (session["customer_name"],)).fetchall()
    
    connection.close()
    return render_template("my_orders.html", orders=orders)

@app.route("/cancel_order/<int:order_id>")
def cancel_order(order_id):
    connection = get_db_connection()

    # Fetch order details
    order = connection.execute("""
        SELECT item_id, quantity, status
        FROM orders
        WHERE id = ?
    """, (order_id,)).fetchone()

    if order and order["status"] == "Pending":
        
        # Restore stock
        connection.execute("""
            UPDATE menu_items
            SET quantity = quantity + ?
            WHERE id = ?
        """, (order["quantity"], order["item_id"]))

        # Delete order
        connection.execute("""
            DELETE FROM orders
            WHERE id = ?
        """, (order_id,))

        connection.commit()

    connection.close()
    return redirect("/my_orders")
@app.route("/shopkeeper_login", methods=["GET", "POST"])
def shopkeeper_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        # Simple hardcoded login (you can upgrade later)
        if username == "shop" and password == "123":
            return redirect("/shopkeeper_home")
        else:
            return "Invalid login"

    return render_template("shopkeeper_login.html")
@app.route('/shopkeeper_home')
def shopkeeper_home():
    return render_template("shopkeeper_home.html")
@app.route("/add_item", methods=["GET", "POST"])
def add_item():
    if request.method == "POST":
        name = request.form["name"]
        price = request.form["price"]
        quantity = request.form["quantity"]

        connection = get_db_connection()
        connection.execute(
            "INSERT INTO menu_items (name, price, quantity) VALUES (?, ?, ?)",
            (name, price, quantity)
        )
        connection.commit()
        connection.close()

        return redirect("/shopkeeper_dashboard")

    return render_template("add_item.html")
@app.route("/shopkeeper_dashboard")
def shopkeeper_dashboard():
    connection = get_db_connection()
    items = connection.execute("SELECT * FROM menu_items").fetchall()
    connection.close()
    return render_template("shopkeeper_dashboard.html", items=items)
@app.route('/shopkeeper/orders')
def view_orders():
    connection = get_db_connection()
    orders = connection.execute("""
        SELECT o.id AS order_id,
               o.customer_name,
               m.name AS item_name,
               o.quantity,
               o.status
        FROM orders o
        JOIN menu_items m ON o.item_id = m.id
        ORDER BY o.id DESC
    """).fetchall()
    connection.close()
    return render_template('shopkeeper_orders.html', orders=orders)

@app.route('/admin_help')
def admin_help():
    return "Admin Help Page (coming soon)"
if __name__ == "__main__":
    app.run(debug=True)@app.route('/shopkeeper/orders')

