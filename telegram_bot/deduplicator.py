# deduplicator.py
# Only generates IDs — DB logic lives in main.py using asyncpg pool

import hashlib

def generate_news_id(news_item: dict) -> str:
    """Generate a unique SHA256 hash for a news item based on title + publishedAt."""
    raw = news_item.get("title", "") + news_item.get("publishedAt", "")
    return hashlib.sha256(raw.encode()).hexdigest()