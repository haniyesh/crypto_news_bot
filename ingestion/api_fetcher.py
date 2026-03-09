# api_fetcher.py

import requests
import os
from datetime import datetime

# ==============================
# FREE CRYPTO NEWS API (no key needed)
# ==============================
FREE_API_URL = "https://cryptocurrency.cv/api/news?limit=15"

def fetch_free_api() -> list:
    """Fetch from cryptocurrency.cv — completely free, no API key needed."""
    news = []
    try:
        response = requests.get(FREE_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        for item in data.get("articles", []):
            news.append({
                "title": item.get("title"),
                "url": item.get("link"),
                "source": item.get("source", "Crypto News"),
                "publishedAt": item.get("pubDate", datetime.now().isoformat())
            })
    except Exception as e:
        print(f"❌ Free API fetch error: {e}")
    return news

# ==============================
# CRYPTOPANIC API (optional, needs key)
# ==============================
CRYPTOPANIC_URL = "https://cryptopanic.com/api/v1/posts/"

def fetch_cryptopanic(api_key=None, limit=15) -> list:
    """Fetch from CryptoPanic — requires API key."""
    news = []
    api_key = api_key or os.getenv("CRYPTOPANIC_API_KEY")
    if not api_key:
        return news

    params = {
        "auth_token": api_key,
        "public": True,
        "currencies": "BTC,ETH",
        "kind": "news",
        "filter": "rising"
    }
    try:
        response = requests.get(CRYPTOPANIC_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        for item in data.get("results", [])[:limit]:
            news.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "source": "CryptoPanic API",
                "publishedAt": item.get("published_at", datetime.now().isoformat())
            })
    except Exception as e:
        print(f"❌ CryptoPanic fetch error: {e}")
    return news

# ==============================
# MAIN FETCH FUNCTION
# ==============================
def fetch_api(api_key=None, limit=15) -> list:
    """Fetch from all available APIs."""
    news = []

    # Always try free API first
    news.extend(fetch_free_api())

    # Try CryptoPanic if key is available
    news.extend(fetch_cryptopanic(api_key=api_key, limit=limit))

    return news