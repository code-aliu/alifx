from sqlalchemy.orm import Session
from app.events.extractor import extract_event
from app.events.enricher import enrich_event
from app.events.models import MarketEvent
from app.news.models import NewsArticle
from app.news.service import get_unprocessed
from app.core.logging import get_logger
from datetime import datetime, timedelta

logger = get_logger(__name__)


def process_unprocessed_articles(db: Session) -> int:
    """Extract events from all unprocessed news articles.

    Returns number of events created.
    """
    articles = get_unprocessed(db, limit=50)
    created = 0

    for article in articles:
        try:
            event_data = extract_event(article)

            if event_data:
                # Optional LLM enrichment — never blocks the pipeline
                event_data = enrich_event(article.title, event_data)
                _persist_event(db, event_data)
                created += 1

            # Mark processed regardless of whether an event was extracted
            article.processed = True

        except Exception as e:
            logger.error(f"Event extraction failed for article {article.id}: {e}")
            article.processed = True  # don't reprocess broken articles

    db.commit()
    logger.info(f"Events: extracted {created} events from {len(articles)} articles")
    return created


def _persist_event(db: Session, data: dict) -> None:
    event = MarketEvent(
        news_article_id=data.get("news_article_id"),
        headline=data["headline"],
        category=data["category"],
        sentiment=data["sentiment"],
        importance=data["importance"],
        affected_assets=data["affected_assets"],
        keywords=data.get("keywords", []),
        llm_enriched=data.get("llm_enriched", False),
        extraction_method=data.get("extraction_method", "rule"),
        extracted_at=datetime.utcnow(),
    )
    db.add(event)


def get_recent_events(db: Session, hours: int = 24, limit: int = 50) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(MarketEvent)
        .filter(MarketEvent.extracted_at >= cutoff)
        .order_by(MarketEvent.extracted_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in rows]


def get_events_for_asset(db: Session, asset: str, hours: int = 24) -> list[dict]:
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    rows = (
        db.query(MarketEvent)
        .filter(MarketEvent.extracted_at >= cutoff)
        .all()
    )
    asset_upper = asset.upper()
    return [r.to_dict() for r in rows if asset_upper in (r.affected_assets or [])]
