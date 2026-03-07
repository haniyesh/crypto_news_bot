# main.py
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import asyncio
import logging
import asyncpg
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from ingestion.news_fetcher import get_latest_news
from telegram_bot.feedback_handler import get_callback_handler, build_feedback_keyboard, init_feedback_tables
from telegram_bot.deduplicator import generate_news_id

load_dotenv()

# ==============================
# CONFIG
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DATABASE_URL = os.getenv("DATABASE_URL")
FETCH_INTERVAL = 300  # 5 minutes

# Validate required env vars
for name, val in [("BOT_TOKEN", BOT_TOKEN), ("CHANNEL_ID", CHANNEL_ID), ("DATABASE_URL", DATABASE_URL)]:
    if not val:
        raise ValueError(f"❌ {name} is not set! Check your .env file or Railway Variables.")

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("crypto_news_bot")

# ==============================
# DATABASE HELPERS
# ==============================
async def init_db(pool: asyncpg.Pool):
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS sent_news (
                news_id TEXT PRIMARY KEY,
                title   TEXT,
                sent_at TIMESTAMP DEFAULT NOW()
            )
        """)
    logger.info("✅ sent_news table ready")

async def is_already_sent(pool: asyncpg.Pool, news_id: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM sent_news WHERE news_id = $1", news_id)
        return row is not None

async def mark_as_sent(pool: asyncpg.Pool, news_id: str, title: str):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sent_news (news_id, title) VALUES ($1, $2) ON CONFLICT DO NOTHING",
            news_id, title
        )

# ===================
# Start Command
# ===================
async def start(update, context):
    await update.message.reply_text("🚀 Crypto AI News Bot is running!")

# ===================
# News Loop
# ===================
async def news_loop(application, pool: asyncpg.Pool):
    await init_db(pool)
    await init_feedback_tables(pool)
    logger.info("✅ All tables ready. Starting news loop...")

    while True:
        try:
            news_list = await get_latest_news(limit=10)  # async in news_fetcher
            for news in news_list:
                news_id = generate_news_id(news)
                if not await is_already_sent(pool, news_id):
                    text = (
                        f"📰 {news['title']}\n"
                        f"🌍 Source: {news['source']}\n"
                        f"⏰ {news['publishedAt']}\n"
                        f"🔗 {news['url']}"
                    )
                    keyboard = build_feedback_keyboard(news_id)
                    await application.bot.send_message(
                        chat_id=CHANNEL_ID,
                        text=text,
                        reply_markup=keyboard,
                        disable_web_page_preview=True
                    )
                    await mark_as_sent(pool, news_id, news['title'])
                    logger.info(f"✅ Sent: {news['title']}")
        except Exception as e:
            logger.error(f"Error in news loop: {e}")

        await asyncio.sleep(FETCH_INTERVAL)

# ===================
# Main
# ===================
async def main():
    pool = await asyncpg.create_pool(DATABASE_URL)
    logger.info("✅ Connected to PostgreSQL")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.bot_data["pool"] = pool  # share pool with all handlers

    app.add_handler(CommandHandler("start", start))
    app.add_handler(get_callback_handler())

    async with app:
        await app.initialize()
        await app.start()
        await asyncio.gather(
            app.updater.start_polling(),
            news_loop(app, pool),
        )
        await app.stop()

# ===================
# Entry Point
# ===================
if __name__ == "__main__":
    asyncio.run(main())