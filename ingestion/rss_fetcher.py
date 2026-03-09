# rss_fetcher.py

import feedparser
from datetime import datetime

RSS_FEEDS = [
    # Bitcoin & Ethereum specific
    "https://cryptonews.com/rss/bitcoin.xml",
    "https://cryptonews.com/rss/ethereum.xml",
    # Major crypto news sites
    "https://cointelegraph.com/rss",
    "https://coindesk.com/arc/outboundfeeds/rss/",
    "https://decrypt.co/feed",
    "https://bitcoinmagazine.com/.rss/full/",
    "https://theblock.co/rss.xml",
]



def fetch_rss() -> list:
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
                    "source": feed.feed.get("title", url),
                    "publishedAt": published_dt
                })
        except Exception as e:
            print(f"❌ RSS fetch error for {url}: {e}")
    return news