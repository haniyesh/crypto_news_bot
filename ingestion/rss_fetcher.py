# fetchers/rss_fetcher.py

import feedparser
from datetime import datetime

RSS_FEEDS = [
    "https://cryptonews.com/rss/bitcoin.xml",
    "https://cryptonews.com/rss/ethereum.xml"
]

def fetch_rss():
    news = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                published = getattr(entry, "published", None)
                if published:
                    try:
                        published_dt = datetime(*entry.published_parsed[:6]).isoformat()
                    except Exception:
                        published_dt = datetime.now().isoformat()
                else:
                    published_dt = datetime.now().isoformat()
                news.append({
                    "title": entry.title,
                    "url": entry.link,
                    "source": url,
                    "publishedAt": published_dt
                })
        except Exception as e:
            print(f"❌ RSS fetch error for {url}: {e}")
    return news