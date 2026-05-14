from sqlalchemy.orm import Session
from app.news.base import BaseNewsProvider, Article
from app.news.models import NewsArticle
from app.news.providers.newsapi import NewsApiProvider
from app.news.providers.rss import RssProvider
from app.core.logging import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)


def _build_providers() -> list[BaseNewsProvider]:
    return [NewsApiProvider(), RssProvider()]


def fetch_and_store_all(db: Session) -> int:
    """Fetch news from all providers, deduplicate, persist unprocessed articles.

    Returns number of new articles stored.
    """
    stored = 0
    for provider in _build_providers():
        try:
            articles = provider.fetch_articles()
            for article in articles:
                if _is_new(db, article.external_id):
                    _persist(db, article)
                    stored += 1
        except Exception as e:
            logger.error(f"News: provider {provider.name} failed: {e}")
    db.commit()
    logger.info(f"News: stored {stored} new articles")
    return stored


def _is_new(db: Session, external_id: str | None) -> bool:
    if not external_id:
        return True
    exists = db.query(NewsArticle).filter(NewsArticle.external_id == external_id).first()
    return exists is None


def _persist(db: Session, article: Article) -> None:
    row = NewsArticle(
        external_id=article.external_id,
        title=article.title,
        description=article.description,
        content=article.content,
        url=article.url,
        source_name=article.source_name,
        provider=article.provider,
        published_at=article.published_at,
        fetched_at=datetime.utcnow(),
        processed=False,
    )
    db.add(row)


def get_unprocessed(db: Session, limit: int = 50) -> list[NewsArticle]:
    """Return articles that have not yet been processed by the event extractor."""
    return (
        db.query(NewsArticle)
        .filter(NewsArticle.processed == False)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
        .all()
    )


def get_recent(db: Session, hours: int = 24, limit: int = 100) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(NewsArticle)
        .filter(NewsArticle.fetched_at >= cutoff)
        .order_by(NewsArticle.published_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in rows]
