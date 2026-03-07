# main.py
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import asyncio
import logging
import asyncpg
from datetime import datetime, timezone
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler
from telethon import TelegramClient, events
from ingestion.rss_fetcher import fetch_rss
from ingestion.api_fetcher import fetch_api
from telegram_bot.feedback_handler import get_callback_handler, build_feedback_keyboard, init_feedback_tables
from telegram_bot.deduplicator import generate_news_id
from sentiment_analyzer import analyze_sentiment, format_signal

load_dotenv()

# ==============================
# CONFIG
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
DATABASE_URL = os.getenv("DATABASE_URL")
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = os.getenv("TELEGRAM_API_HASH")
FETCH_INTERVAL = 60  # RSS/API polling every 60 seconds

# Telegram channels to listen to in real-time
WATCH_CHANNELS = ["cointelegraph", "the_block_crypto", "coindesk", "BitcoinMagazineTelegram", "cryptoslatenews", "wublockchainenglish"]

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
                news_id    TEXT PRIMARY KEY,
                title      TEXT,
                sentiment  INT,
                sent_at    TIMESTAMP DEFAULT NOW()
            )
        """)
    logger.info("✅ sent_news table ready")

async def is_already_sent(pool: asyncpg.Pool, news_id: str) -> bool:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM sent_news WHERE news_id = $1", news_id)
        return row is not None

async def mark_as_sent(pool: asyncpg.Pool, news_id: str, title: str, sentiment: int):
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO sent_news (news_id, title, sentiment) VALUES ($1, $2, $3) ON CONFLICT DO NOTHING",
            news_id, title, sentiment
        )
def format_time(iso_string: str) -> str:
    try:
        from zoneinfo import ZoneInfo
        dt = datetime.fromisoformat(iso_string.replace("Z", "+00:00"))
        now = datetime.now(ZoneInfo("UTC"))
        diff = now - dt
        seconds = int(diff.total_seconds())

        if seconds < 60:
            return f"🕐 Just now"
        elif seconds < 3600:
            minutes = seconds // 60
            return f"🕐 {minutes} minute{'s' if minutes > 1 else ''} ago"
        elif seconds < 86400:
            hours = seconds // 3600
            return f"🕐 {hours} hour{'s' if hours > 1 else ''} ago"
        else:
            days = seconds // 86400
            return f"🕐 {days} day{'s' if days > 1 else ''} ago"
    except Exception:
        return iso_string
# ==============================
# SEND NEWS HELPER
# ==============================
async def send_news(bot, pool, news: dict):
    """Score, format and send a single news item to the channel."""
    news_id = generate_news_id(news)
    if await is_already_sent(pool, news_id):
        return

    score = await analyze_sentiment(news['title'], pool=pool)
    signal = format_signal(score)

    text = (
        f"📰 {news['title']}\n"
        f"🌍 Source: {news['source']}\n"
        f"⏰ {format_time(news['publishedAt'])}\n"
        f"{signal}\n"
        f"🔗 {news['url']}"
    )
    keyboard = build_feedback_keyboard(news_id)
    await bot.send_message(
        chat_id=CHANNEL_ID,
        text=text,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )
    await mark_as_sent(pool, news_id, news['title'], score)
    logger.info(f"✅ Sent: {news['title']} | Signal: {score}/5")

# ===================
# Start Command
# ===================
async def start(update, context):
    await update.message.reply_text("🚀 Crypto AI News Bot is running!")

# ==============================
# REAL-TIME TELEGRAM LISTENER
# ==============================
async def start_telegram_listener(bot, pool: asyncpg.Pool):
    """Listen to Telegram channels in real-time using Telethon events."""
    client = TelegramClient("session_name", API_ID, API_HASH)
    await client.start()
    logger.info(f"✅ Real-time listener active for: {WATCH_CHANNELS}")

    @client.on(events.NewMessage(chats=WATCH_CHANNELS))
    async def on_new_message(event):
        msg = event.message
        if not msg.message:
            return
        try:
            channel = event.chat.username or str(event.chat_id)
            title = msg.message[:100] + ("..." if len(msg.message) > 100 else "")
            news = {
                "title": title,
                "url": f"https://t.me/{channel}/{msg.id}",
                "source": f"Telegram: {channel}",
                "publishedAt": msg.date.isoformat()
            }
            logger.info(f"⚡ Real-time news from {channel}: {title[:50]}")
            await send_news(bot, pool, news)
        except Exception as e:
            logger.error(f"Error processing real-time message: {e}")

    await client.run_until_disconnected()

# ==============================
# RSS + API POLLING LOOP
# ==============================
async def rss_api_loop(bot, pool: asyncpg.Pool):
    """Poll RSS and CryptoPanic API every 60 seconds."""
    while True:
        try:
            logger.info("👂 Checking RSS and API sources...")
            all_news = []

            # RSS
            try:
                all_news.extend(fetch_rss())
            except Exception as e:
                logger.error(f"❌ RSS error: {e}")

            # API
            try:
                all_news.extend(fetch_api())
            except Exception as e:
                logger.error(f"❌ API error: {e}")

            # Deduplicate and sort
            unique = {item["title"]: item for item in all_news if item.get("title")}
            def parse_date(item):
                try:
                    return datetime.fromisoformat(item.get("publishedAt", ""))
                except Exception:
                    return datetime.min
            sorted_news = sorted(unique.values(), key=parse_date, reverse=True)

            for news in sorted_news[:10]:
                await send_news(bot, pool, news)

        except Exception as e:
            logger.error(f"Error in RSS/API loop: {e}")

        await asyncio.sleep(FETCH_INTERVAL)

# ===================
# Main
# ===================
async def main():
    pool = await asyncpg.create_pool(DATABASE_URL)
    logger.info("✅ Connected to PostgreSQL")

    await init_db(pool)
    await init_feedback_tables(pool)
    logger.info("✅ All tables ready.")

    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.bot_data["pool"] = pool

    app.add_handler(CommandHandler("start", start))
    app.add_handler(get_callback_handler())

    async with app:
        await app.initialize()
        await app.start()

        await asyncio.gather(
            app.updater.start_polling(),
            rss_api_loop(app.bot, pool),          # RSS + API every 60s
            start_telegram_listener(app.bot, pool) # Telegram real-time ⚡
        )

        await app.stop()

# ===================
# Entry Point
# ===================
if __name__ == "__main__":
    asyncio.run(main())