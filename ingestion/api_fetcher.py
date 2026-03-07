# fetchers/api_fetcher.py

import requests
from datetime import datetime

API_URL = "https://cryptopanic.com/api/v1/posts/"
API_LIMIT = 15

def fetch_api(api_key=None, limit=API_LIMIT):
    news = []
    if api_key is None:
        return news

    params = {
        "auth_token": api_key,
        "public": True,
        "currencies": "BTC,ETH",
        "kind": "news",
        "filter": "rising"
    }

    try:
        response = requests.get(API_URL, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        for item in data.get("results", [])[:limit]:
            published_dt = item.get("published_at", datetime.now().isoformat())
            news.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "source": "CryptoPanic API",
                "publishedAt": published_dt
            })
    except Exception as e:
        print(f"❌ API fetch error: {e}")
    return news