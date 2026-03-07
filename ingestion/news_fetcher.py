# news_fetcher.py

import logging
from datetime import datetime
from ingestion.rss_fetcher import fetch_rss
from ingestion.api_fetcher import fetch_api
from telegram_bot.telegram_fetcher import fetch_telegram

logger = logging.getLogger("crypto_news_bot")


async def get_latest_news(limit: int = 15) -> list:
    """
    Fetch news from RSS, API, and Telegram sources,
    deduplicate by title, sort by date, return latest items.
    """
    logger.info("👂 Checking for news...")
    all_news = []

    # RSS (sync)
    try:
        all_news.extend(fetch_rss())
    except Exception as e:
        logger.error(f"❌ RSS fetch error: {e}")

    # API (sync)
    try:
        all_news.extend(fetch_api())
    except Exception as e:
        logger.error(f"❌ API fetch error: {e}")

    # Telegram (async)
    try:
        telegram_news = await fetch_telegram()
        if isinstance(telegram_news, list):
            all_news.extend(telegram_news)
    except Exception as e:
        logger.error(f"❌ Telegram fetch error: {e}")

    # Deduplicate by title
    unique_news = {
        item["title"]: item
        for item in all_news
        if item.get("title")
    }

    # Sort by publishedAt descending
    def parse_date(item):
        try:
            return datetime.fromisoformat(item.get("publishedAt", ""))
        except Exception:
            return datetime.min

    sorted_news = sorted(unique_news.values(), key=parse_date, reverse=True)
    logger.info(f"✅ Found {len(sorted_news)} unique news items.")
    return sorted_news[:limit]