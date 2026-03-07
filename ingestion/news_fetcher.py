import logging
from datetime import datetime

from ingestion.rss_fetcher import fetch_rss
from ingestion.api_fetcher import fetch_api
from telegram_bot.telegram_fetcher import fetch_telegram

logger = logging.getLogger("crypto_news_bot")


async def get_latest_news(limit: int = 15):
    """
    Fetch news from RSS, API, and Telegram sources,
    remove duplicates, sort by date, and return latest items.
    """

    logger.info("👂 Checking for news...")

    all_news = []

    # =====================
    # RSS (sync)
    # =====================
    try:
        rss_news = fetch_rss()
        if isinstance(rss_news, list):
            all_news.extend(rss_news)
    except Exception as e:
        logger.error(f"❌ RSS fetch error: {e}")

    # =====================
    # API (sync)
    # =====================
    try:
        api_news = fetch_api()
        if isinstance(api_news, list):
            all_news.extend(api_news)
    except Exception as e:
        logger.error(f"❌ API fetch error: {e}")

    # =====================
    # Telegram (async)
    # =====================
    try:
        telegram_news = await fetch_telegram()
        if isinstance(telegram_news, list):
            all_news.extend(telegram_news)
    except Exception as e:
        logger.error(f"❌ Telegram fetch error: {e}")

    # =====================
    # Remove duplicates by title
    # =====================
    unique_news = {
        item.get("title", ""): item
        for item in all_news
        if "title" in item
    }

    # =====================
    # Sort by publishedAt
    # =====================
    def parse_date(item):
        try:
            return datetime.fromisoformat(item.get("publishedAt", ""))
        except Exception:
            return datetime.min

    news_sorted = sorted(
        unique_news.values(),
        key=parse_date,
        reverse=True
    )

    logger.info(f"Found {len(news_sorted)} news items.")

    return news_sorted[:limit]