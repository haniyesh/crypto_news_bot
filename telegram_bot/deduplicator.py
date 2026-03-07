# deduplicator.py
# Only generates IDs — DB logic lives in main.py using asyncpg pool

import hashlib

def generate_news_id(news_item: dict) -> str:
    """Generate a short unique ID (48 chars) to fit Telegram's 64-byte
    callback_data limit. Format is: 'rate|<id>|<rating>' = 48 + 7 = 55 bytes."""
    raw = news_item.get("title", "") + news_item.get("publishedAt", "")
    return hashlib.sha256(raw.encode()).hexdigest()[:48]