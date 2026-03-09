# telegram_fetcher.py
# Used only for initial bulk fetch on startup.
# Real-time listening is handled by the event listener in main.py

import os
import logging
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv()

logger = logging.getLogger("crypto_news_bot")

API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

CHANNELS = [
    "cointelegraph",
    "the_block_crypto",
    "coindesk",
    "BitcoinMagazineTelegram",
    "cryptoslatenews",
    "wublockchainenglish"
]
NEWS_LIMIT = 10


async def fetch_telegram() -> list:
    """Fetch recent messages from channels — used only on startup."""
    news = []

    if not API_ID or not API_HASH:
        logger.warning("⚠️ TELEGRAM_API_ID or TELEGRAM_API_HASH not set.")
        return news

    try:
        async with TelegramClient("session_name", int(API_ID), API_HASH) as client:
            for channel in CHANNELS:
                try:
                    messages = await client.get_messages(channel, limit=NEWS_LIMIT)
                    for msg in messages:
                        if msg.message:
                            title = msg.message[:100] + ("..." if len(msg.message) > 100 else "")
                            news.append({
                                "title": title,
                                "url": f"https://t.me/{channel}/{msg.id}",
                                "source": f"Telegram: {channel}",
                                "publishedAt": msg.date.isoformat()
                            })
                except Exception as e:
                    logger.error(f"❌ Error fetching from {channel}: {e}")
    except Exception as e:
        logger.error(f"❌ Telegram client error: {e}")

    return news