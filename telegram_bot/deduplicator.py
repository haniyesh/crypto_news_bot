# deduplicator.py

from datetime import datetime
import os
import psycopg2
import hashlib

# =============================
# CHECK IF SENT
# =============================

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()

# Create table if it doesn't exist
cur.execute("""
CREATE TABLE IF NOT EXISTS sent_news (
    news_id TEXT PRIMARY KEY,
    sent_at TIMESTAMP
)
""")

# =============================
# CHECK IF SENT
# =============================

def is_already_sent(news_id):
    cur.execute("SELECT 1 FROM sent_news WHERE news_id = %s", (news_id,))
    return cur.fetchone() is not None

# =============================
# MARK AS SENT
# =============================

def mark_as_sent(news_id):
    try:
        cur.execute(
            "INSERT INTO sent_news (news_id, sent_at) VALUES (%s, %s)",
            (news_id, datetime.utcnow())
        )
    except psycopg2.errors.UniqueViolation:
        # Already exists
        conn.rollback()

# =============================
# GENERATE NEWS ID
# =============================

def generate_news_id(news_item):
    raw = news_item["title"] + news_item["publishedAt"]
    return hashlib.sha256(raw.encode()).hexdigest()