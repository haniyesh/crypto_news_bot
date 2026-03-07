# callback_handler.py

import os
import asyncpg
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

# =============================
# KEYBOARD BUILDER
# =============================
def build_feedback_keyboard(news_id):
    keyboard = [
        [
            InlineKeyboardButton("1️⃣", callback_data=f"rate|{news_id}|1"),
            InlineKeyboardButton("2️⃣", callback_data=f"rate|{news_id}|2"),
            InlineKeyboardButton("3️⃣", callback_data=f"rate|{news_id}|3"),
            InlineKeyboardButton("4️⃣", callback_data=f"rate|{news_id}|4"),
            InlineKeyboardButton("5️⃣", callback_data=f"rate|{news_id}|5"),
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# =============================
# CALLBACK HANDLER
# =============================
async def handle_rating(update, context):
    query = update.callback_query
    await query.answer()

    data = query.data.split("|")
    if data[0] != "rate":
        return

    news_id = data[1]
    rating = int(data[2])
    user_id = query.from_user.id

    # Connect to PostgreSQL
    conn = await asyncpg.connect(
        user=os.getenv("PG_USER"),
        password=os.getenv("PG_PASSWORD"),
        database=os.getenv("PG_DB"),
        host=os.getenv("PG_HOST"),
        port=int(os.getenv("PG_PORT", 5432))
    )

    # Create feedback table if it doesn't exist
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            news_id TEXT,
            user_id BIGINT,
            rating INT,
            timestamp TIMESTAMP,
            PRIMARY KEY(news_id, user_id)
        )
    """)

    # Insert or update user rating
    await conn.execute("""
        INSERT INTO feedback(news_id, user_id, rating, timestamp)
        VALUES($1, $2, $3, $4)
        ON CONFLICT(news_id, user_id) DO UPDATE
        SET rating = $3, timestamp = $4
    """, news_id, user_id, rating, datetime.utcnow())

    # Calculate average rating for the news
    rows = await conn.fetch("SELECT rating FROM feedback WHERE news_id=$1", news_id)
    avg = round(sum(r["rating"] for r in rows) / len(rows), 2)

    # Store average rating
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS news_avg (
            news_id TEXT PRIMARY KEY,
            avg_rating FLOAT
        )
    """)
    await conn.execute("""
        INSERT INTO news_avg(news_id, avg_rating)
        VALUES($1, $2)
        ON CONFLICT(news_id) DO UPDATE
        SET avg_rating = $2
    """, news_id, avg)

    await conn.close()

    # Reply to the user
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(f"⭐️ Thank you! You rated this news: {rating}/5")


# =============================
# RETURN HANDLER
# =============================
def get_callback_handler():
    return CallbackQueryHandler(handle_rating)