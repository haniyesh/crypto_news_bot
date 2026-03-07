# fetchers/telegram_fetcher.py
from dotenv import load_dotenv
import os
load_dotenv()
from telethon.sync import TelegramClient
from datetime import datetime
# Replace with your Telegram API ID/Hash
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
CHANNELS = ["cointelegraph", "the_block_crypto"]  # usernames
NEWS_LIMIT = 10

async def fetch_telegram():
    news = []
    try:
        async with TelegramClient("session_name", API_ID, API_HASH) as client:
            for channel in CHANNELS:
                messages = await client.get_messages(channel, limit=NEWS_LIMIT)
                for msg in messages:
                    if msg.message:
                        news.append({
                            "title": msg.message[:100] + ("..." if len(msg.message) > 100 else ""),
                            "url": f"https://t.me/{channel}/{msg.id}",
                            "source": f"Telegram: {channel}",
                            "publishedAt": msg.date.isoformat()
                        })
    except Exception as e:
        print(f"❌ Telegram fetch error: {e}")
    return news