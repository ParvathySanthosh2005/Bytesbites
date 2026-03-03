"""
train_models.py  —  ByteBites ML Training Script
=================================================
Run this ONCE before starting Flask:

    python ml/train_models.py

This will:
  1. Load stock_data.csv  → train Random Forest Regressor  → save stock_model.pkl
  2. Load sentiment_data.csv → train TF-IDF + RF Classifier → save sentiment_model.pkl + tfidf_vectorizer.pkl

If your database already has real orders/feedback, it will use THAT data instead
of the CSV files automatically.
"""

import os
import pickle
import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, accuracy_score

# ── PATHS ──────────────────────────────────────────────────────────────────
ML_DIR      = os.path.dirname(os.path.abspath(__file__))
DATASET_DIR = os.path.join(ML_DIR, "datasets")
DB_PATH     = os.path.join(ML_DIR, "..", "database.db")

STOCK_CSV     = os.path.join(DATASET_DIR, "stock_data.csv")
SENTIMENT_CSV = os.path.join(DATASET_DIR, "sentiment_data.csv")

STOCK_MODEL_PATH = os.path.join(ML_DIR, "stock_model.pkl")
SENTIMENT_MODEL_PATH = os.path.join(ML_DIR, "sentiment_model.pkl")
VECTORIZER_PATH = os.path.join(ML_DIR, "tfidf_vectorizer.pkl")


# ── HELPER ─────────────────────────────────────────────────────────────────
def get_db_connection():
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    return None


# ══════════════════════════════════════════════════════════════════════════
#  MODEL 1 — STOCK / DEMAND PREDICTION
# ══════════════════════════════════════════════════════════════════════════
def train_stock_model():
    print("\n📦  Training Stock Prediction Model...")
    print("    Algorithm : Random Forest Regressor")
    print("    Task      : Predict tomorrow's demand for each menu item")

    # Try real database first
    df = None
    conn = get_db_connection()
    if conn:
        try:
            df = pd.read_sql_query("""
                SELECT o.item_id, m.name AS item_name,
                       o.quantity, o.created_at
                FROM orders o
                JOIN menu_items m ON o.item_id = m.id
            """, conn)
            conn.close()
            if len(df) >= 20:
                print(f"    ✅ Using real database data — {len(df)} order records found")
            else:
                print(f"    ⚠  Only {len(df)} real orders — loading CSV dataset instead")
                df = None
        except Exception:
            df = None

    # Fall back to CSV dataset
    if df is None:
        print(f"    📂 Loading: {STOCK_CSV}")
        df = pd.read_csv(STOCK_CSV)
        print(f"    ✅ Loaded {len(df)} rows from stock_data.csv")

    # Feature engineering
    df['created_at'] = pd.to_datetime(df['created_at'], errors='coerce')
    df['created_at'].fillna(pd.Timestamp.now(), inplace=True)
    df['day_of_week']  = df['created_at'].dt.dayofweek   # 0=Mon, 6=Sun
    df['day_of_month'] = df['created_at'].dt.day
    df['month']        = df['created_at'].dt.month

    # Aggregate: total quantity ordered per item per day
    daily = (df.groupby(['item_id', 'day_of_week', 'day_of_month', 'month'])
               ['quantity'].sum()
               .reset_index())
    daily.columns = ['item_id', 'day_of_week', 'day_of_month', 'month', 'total_qty']

    print(f"\n    Dataset summary:")
    print(f"      Unique items  : {daily['item_id'].nunique()}")
    print(f"      Training rows : {len(daily)}")
    print(f"      Qty range     : {daily['total_qty'].min()} – {daily['total_qty'].max()} units/day")

    X = daily[['item_id', 'day_of_week', 'day_of_month', 'month']]
    y = daily['total_qty']

    if len(X) >= 10:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42)
    else:
        X_train, X_test, y_train, y_test = X, X, y, y

    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    mae = mean_absolute_error(y_test, model.predict(X_test))
    print(f"\n    📊 Model Results:")
    print(f"      MAE (Mean Absolute Error) : {mae:.2f} units")
    print(f"      Interpretation: predictions are off by ~{mae:.1f} units on average")

    with open(STOCK_MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    print(f"\n    💾 Saved → {STOCK_MODEL_PATH}")
    return model


# ══════════════════════════════════════════════════════════════════════════
#  MODEL 2 — REVIEW SENTIMENT / RATING PREDICTION
# ══════════════════════════════════════════════════════════════════════════
def train_sentiment_model():
    print("\n💬  Training Review Sentiment Model...")
    print("    Algorithm : TF-IDF Vectorizer + Random Forest Classifier")
    print("    Task      : Predict star rating (1–5) from review text")

    # Try real database first
    df = None
    conn = get_db_connection()
    if conn:
        try:
            df = pd.read_sql_query(
                "SELECT comment, rating FROM feedback WHERE comment IS NOT NULL AND comment != ''",
                conn)
            conn.close()
            if len(df) >= 20:
                print(f"    ✅ Using real database feedback — {len(df)} reviews found")
            else:
                print(f"    ⚠  Only {len(df)} real reviews — loading CSV dataset instead")
                df = None
        except Exception:
            df = None

    # Fall back to CSV dataset
    if df is None:
        print(f"    📂 Loading: {SENTIMENT_CSV}")
        df = pd.read_csv(SENTIMENT_CSV)
        print(f"    ✅ Loaded {len(df)} rows from sentiment_data.csv")

    # Clean data
    df['comment'] = df['comment'].fillna('').str.strip()
    df = df[df['comment'].str.len() > 3]
    df['rating'] = df['rating'].astype(int).clip(1, 5)

    print(f"\n    Dataset summary:")
    print(f"      Total reviews : {len(df)}")
    for r in [5, 4, 3, 2, 1]:
        count = (df['rating'] == r).sum()
        bar   = '█' * count
        print(f"      {r}⭐  {count:>3} reviews  {bar}")

    X = df['comment']
    y = df['rating']

    # TF-IDF vectorization (converts text → numbers)
    vectorizer = TfidfVectorizer(
        max_features=1000,
        ngram_range=(1, 2),
        stop_words='english'
    )
    X_vec = vectorizer.fit_transform(X)

    if len(X) >= 10:
        X_train, X_test, y_train, y_test = train_test_split(
            X_vec, y, test_size=0.2, random_state=42)
    else:
        X_train, X_test, y_train, y_test = X_vec, X_vec, y, y

    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    preds    = model.predict(X_test)
    accuracy = accuracy_score(y_test, preds) * 100

    print(f"\n    📊 Model Results:")
    print(f"      Accuracy  : {accuracy:.1f}%")
    print(f"      Vocabulary: {len(vectorizer.vocabulary_)} unique terms learned")

    with open(SENTIMENT_MODEL_PATH, 'wb') as f:
        pickle.dump(model, f)
    with open(VECTORIZER_PATH, 'wb') as f:
        pickle.dump(vectorizer, f)

    print(f"\n    💾 Saved → {SENTIMENT_MODEL_PATH}")
    print(f"    💾 Saved → {VECTORIZER_PATH}")
    return model, vectorizer


# ══════════════════════════════════════════════════════════════════════════
#  QUICK TEST — runs after training to verify everything works
# ══════════════════════════════════════════════════════════════════════════
def run_quick_test(stock_model, sentiment_model, vectorizer):
    print("\n" + "=" * 55)
    print("  🧪 Quick Test — Verifying Models Work")
    print("=" * 55)

    # Test stock prediction for each item
    tomorrow = datetime.now() + timedelta(days=1)
    dow, dom, mon = tomorrow.weekday(), tomorrow.day, tomorrow.month

    print(f"\n📦 Predicted demand for tomorrow ({tomorrow.strftime('%A %d %b')}):")
    item_names = {1: "Chicken Rice", 2: "Veg Meals", 3: "Egg Roast",
                  4: "Chapathi", 5: "Porotta", 6: "Fish Curry", 7: "Tea"}
    for item_id, name in item_names.items():
        X = pd.DataFrame([[item_id, dow, dom, mon]],
                         columns=['item_id', 'day_of_week', 'day_of_month', 'month'])
        qty = max(1, int(round(stock_model.predict(X)[0])))
        print(f"   {name:<15} → {qty} units")

    # Test sentiment prediction
    test_reviews = [
        ("The food was absolutely delicious today, loved it!", 5),
        ("Food was okay, nothing very special about it",       3),
        ("Terrible quality, very disappointed with the food",  1),
        ("Good taste and service, will come again soon",       4),
        ("Cold food, slow service, not happy at all",          2),
    ]

    print(f"\n💬 Sentiment prediction test:")
    correct = 0
    for review, expected in test_reviews:
        X      = vectorizer.transform([review])
        rating = int(sentiment_model.predict(X)[0])
        proba  = sentiment_model.predict_proba(X)[0]
        conf   = round(float(max(proba)) * 100, 1)
        stars  = "⭐" * rating
        match  = "✅" if rating == expected else "❌"
        print(f"   {match} \"{review[:50]}\"")
        print(f"      Predicted: {stars} ({conf}% confidence)")
        if rating == expected:
            correct += 1

    print(f"\n   Test accuracy: {correct}/{len(test_reviews)} correct")


# ══════════════════════════════════════════════════════════════════════════
#  PREDICTION FUNCTIONS  (imported by app.py)
# ══════════════════════════════════════════════════════════════════════════
def predict_stock_for_tomorrow(model=None):
    """Returns {item_id: predicted_qty_tomorrow}"""
    if model is None:
        with open(STOCK_MODEL_PATH, 'rb') as f:
            model = pickle.load(f)

    tomorrow = datetime.now() + timedelta(days=1)
    dow, dom, mon = tomorrow.weekday(), tomorrow.day, tomorrow.month

    conn = get_db_connection()
    if conn:
        items = pd.read_sql_query("SELECT id FROM menu_items", conn)
        conn.close()
        item_ids = items['id'].tolist() if not items.empty else list(range(1, 8))
    else:
        item_ids = list(range(1, 8))

    rows = [[iid, dow, dom, mon] for iid in item_ids]
    X = pd.DataFrame(rows, columns=['item_id', 'day_of_week', 'day_of_month', 'month'])
    preds = model.predict(X)
    return {int(iid): max(1, int(round(p))) for iid, p in zip(item_ids, preds)}


def predict_rating_from_text(text, model=None, vectorizer=None):
    """Returns (predicted_rating 1-5, confidence %)"""
    if model is None:
        with open(SENTIMENT_MODEL_PATH, 'rb') as f:
            model = pickle.load(f)
    if vectorizer is None:
        with open(VECTORIZER_PATH, 'rb') as f:
            vectorizer = pickle.load(f)

    X = vectorizer.transform([text])
    rating     = int(model.predict(X)[0])
    confidence = round(float(max(model.predict_proba(X)[0])) * 100, 1)
    return rating, confidence


# ══════════════════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 55)
    print("  🍽️  ByteBites — ML Model Training")
    print("=" * 55)

    stock_model                  = train_stock_model()
    sentiment_model, vectorizer  = train_sentiment_model()

    run_quick_test(stock_model, sentiment_model, vectorizer)

    print("\n" + "=" * 55)
    print("  ✅  Training Complete! Files saved:")
    print(f"     📦 {STOCK_MODEL_PATH}")
    print(f"     💬 {SENTIMENT_MODEL_PATH}")
    print(f"     🔤 {VECTORIZER_PATH}")
    print("=" * 55)
    print("\n  ▶  Now run your Flask app:  python app.py")
    print("  🌐  Then go to: Shopkeeper Login → 🤖 ML Analytics\n")