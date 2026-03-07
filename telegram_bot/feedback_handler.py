# feedback_handler.py

from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

# =============================
# KEYBOARD BUILDER
# =============================
def build_feedback_keyboard(news_id: str) -> InlineKeyboardMarkup:
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
# DB INIT — call once at startup
# =============================
async def init_feedback_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                news_id   TEXT,
                user_id   BIGINT,
                rating    INT,
                timestamp TIMESTAMP,
                PRIMARY KEY (news_id, user_id)
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS news_avg (
                news_id    TEXT PRIMARY KEY,
                avg_rating FLOAT
            )
        """)


# =============================
# RATING HANDLER
# =============================
async def handle_rating(update, context):
    query = update.callback_query
    await query.answer()

    parts = query.data.split("|")
    if parts[0] != "rate" or len(parts) != 3:
        return

    news_id = parts[1]
    rating = int(parts[2])
    user_id = query.from_user.id

    # Use shared pool set in main.py
    pool = context.bot_data["pool"]

    async with pool.acquire() as conn:
        # Upsert user rating
        await conn.execute("""
            INSERT INTO feedback (news_id, user_id, rating, timestamp)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (news_id, user_id) DO UPDATE
            SET rating = $3, timestamp = $4
        """, news_id, user_id, rating, datetime.utcnow())

        # Recalculate average
        rows = await conn.fetch(
            "SELECT rating FROM feedback WHERE news_id = $1", news_id
        )
        avg = round(sum(r["rating"] for r in rows) / len(rows), 2)

        # Upsert average
        await conn.execute("""
            INSERT INTO news_avg (news_id, avg_rating)
            VALUES ($1, $2)
            ON CONFLICT (news_id) DO UPDATE
            SET avg_rating = $2
        """, news_id, avg)

    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(
        f"⭐️ Thanks! You rated this news {rating}/5\n"
        f"📊 Average rating so far: {avg}/5"
    )


# =============================
# RETURN HANDLER
# =============================
def get_callback_handler():
    return CallbackQueryHandler(handle_rating)