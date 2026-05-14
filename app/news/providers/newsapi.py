from datetime import datetime, timezone
import hashlib
import httpx
from app.news.base import BaseNewsProvider, Article
from app.core.logging import get_logger
from app.config import settings

logger = get_logger(__name__)

NEWSAPI_URL = "https://newsapi.org/v2/everything"

# Financial topics to query — broad enough for macro + crypto + equity coverage
QUERY_TERMS = [
    "Federal Reserve interest rates",
    "inflation CPI GDP",
    "Bitcoin Ethereum crypto",
    "S&P 500 NASDAQ stocks",
    "forex EUR USD JPY",
    "oil commodities gold",
]


class NewsApiProvider(BaseNewsProvider):
    @property
    def name(self) -> str:
        return "newsapi"

    def fetch_articles(self) -> list[Article]:
        if not settings.newsapi_key:
            logger.warning("NewsAPI: no API key configured, skipping")
            return []

        articles = []
        seen_ids: set[str] = set()

        for query in QUERY_TERMS:
            try:
                batch = self._fetch_query(query)
                for a in batch:
                    if a.external_id not in seen_ids:
                        seen_ids.add(a.external_id)
                        articles.append(a)
            except Exception as e:
                logger.error(f"NewsAPI: query '{query}' failed: {e}")

        logger.info(f"NewsAPI: fetched {len(articles)} unique articles")
        return articles

    def _fetch_query(self, query: str) -> list[Article]:
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 10,
            "apiKey": settings.newsapi_key,
        }
        with httpx.Client(timeout=15) as client:
            resp = client.get(NEWSAPI_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

        articles = []
        for item in data.get("articles", []):
            title = item.get("title") or ""
            url = item.get("url") or ""
            # stable dedup key
            external_id = hashlib.md5(url.encode()).hexdigest() if url else hashlib.md5(title.encode()).hexdigest()

            published_at = None
            raw_date = item.get("publishedAt")
            if raw_date:
                try:
                    published_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00")).replace(tzinfo=None)
                except ValueError:
                    pass

            articles.append(Article(
                external_id=external_id,
                title=title,
                description=item.get("description"),
                content=item.get("content"),
                url=url,
                source_name=item.get("source", {}).get("name"),
                provider=self.name,
                published_at=published_at,
            ))
        return articles
