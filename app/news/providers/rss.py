from datetime import datetime
import hashlib
import feedparser
from app.news.base import BaseNewsProvider, Article
from app.core.logging import get_logger

logger = get_logger(__name__)

# Free, no-key financial RSS feeds
RSS_FEEDS = [
    ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
    ("Reuters Markets", "https://feeds.reuters.com/reuters/financialNews"),
    ("Investing.com News", "https://www.investing.com/rss/news.rss"),
    ("CoinDesk",          "https://www.coindesk.com/arc/outboundfeeds/rss/"),
]


class RssProvider(BaseNewsProvider):
    @property
    def name(self) -> str:
        return "rss"

    def fetch_articles(self) -> list[Article]:
        articles = []
        for source_name, url in RSS_FEEDS:
            try:
                batch = self._parse_feed(url, source_name)
                articles.extend(batch)
                logger.debug(f"RSS: {source_name} → {len(batch)} articles")
            except Exception as e:
                logger.warning(f"RSS: failed to parse {source_name}: {e}")
        logger.info(f"RSS: fetched {len(articles)} total articles")
        return articles

    def _parse_feed(self, url: str, source_name: str) -> list[Article]:
        feed = feedparser.parse(url)
        articles = []
        for entry in feed.entries[:15]:  # cap per feed to avoid flooding
            title = entry.get("title", "")
            link = entry.get("link", "")
            external_id = hashlib.md5(link.encode()).hexdigest() if link else hashlib.md5(title.encode()).hexdigest()

            published_at = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    published_at = datetime(*entry.published_parsed[:6])
                except Exception:
                    pass

            articles.append(Article(
                external_id=external_id,
                title=title,
                description=entry.get("summary"),
                content=None,
                url=link,
                source_name=source_name,
                provider=self.name,
                published_at=published_at,
            ))
        return articles
