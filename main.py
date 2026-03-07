# main.py
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
import asyncio
import logging
from telegram.ext import ApplicationBuilder, CommandHandler
from ingestion.news_fetcher import get_latest_news
from telegram_bot.feedback_handler import get_callback_handler, build_feedback_keyboard
from telegram_bot.deduplicator import is_already_sent, mark_as_sent, generate_news_id

# ==============================
# CONFIG
# ==============================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
FETCH_INTERVAL = 300  # 5 minutes

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("crypto_news_bot")

# ===================
# Start Command
# ===================
async def start(update, context):
    await update.message.reply_text("🚀 Crypto AI News Bot is running!")

# ===================
# News Loop
# ===================
async def news_loop(application):
    while True:
        try:
            # If get_latest_news() is NOT async, remove await
            news_list = get_latest_news(limit=10)
            for news in news_list:
                news_id = generate_news_id(news)
                if not is_already_sent(news_id):
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
                    mark_as_sent(news_id)
                    logger.info(f"Sent news: {news['title']}")
        except Exception as e:
            logger.error(f"Error in news loop: {e}")
        await asyncio.sleep(FETCH_INTERVAL)

# ===================
# Main
# ===================
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Command /start
    app.add_handler(CommandHandler("start", start))

    # Callback (inline feedback)
    app.add_handler(get_callback_handler())

    # Start background news loop
    asyncio.create_task(news_loop(app))

    logger.info("Bot started and listening for feedback...")
    # Run polling
    await app.run_polling()

# ===================
# Entry Point
# ===================
if __name__ == "__main__":
    # For local run, use asyncio.run()
    # On server with existing loop, just await main()
    import asyncio
    try:
        asyncio.run(main())
    except RuntimeError as e:
        logger.warning(f"Asyncio already running, please use 'await main()'. {e}")