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


def get_recent_changes(db: Session, hours: int = 6) -> dict:
    """What changed in the market?

    Compares events from the current window against the prior equal-length
    window. Returns category-level sentiment shifts and per-asset summaries.
    """
    now = datetime.utcnow()
    current_cutoff = now - timedelta(hours=hours)
    prior_cutoff   = now - timedelta(hours=hours * 2)

    current_rows = (
        db.query(MarketEvent)
        .filter(MarketEvent.extracted_at >= current_cutoff)
        .order_by(MarketEvent.extracted_at.desc())
        .all()
    )
    prior_rows = (
        db.query(MarketEvent)
        .filter(
            MarketEvent.extracted_at >= prior_cutoff,
            MarketEvent.extracted_at < current_cutoff,
        )
        .all()
    )

    # Group current events by category
    current_by_cat: dict[str, list] = {}
    for row in current_rows:
        current_by_cat.setdefault(row.category or "other", []).append(row)

    # Aggregate prior sentiment per category
    prior_sentiments: dict[str, list[str]] = {}
    for row in prior_rows:
        prior_sentiments.setdefault(row.category or "other", []).append(row.sentiment)

    category_changes = []
    for cat, events in current_by_cat.items():
        curr_avg  = _avg_sentiment([e.sentiment for e in events])
        prior_avg = _avg_sentiment(prior_sentiments.get(cat, []))
        shift     = curr_avg - prior_avg

        top = sorted(events, key=lambda e: _importance_weight(e.importance), reverse=True)[:3]
        category_changes.append({
            "category":        cat,
            "event_count":     len(events),
            "net_sentiment":   round(curr_avg, 3),
            "sentiment_shift": round(shift, 3),
            "shift_direction": (
                "improving"    if shift > 0.1  else
                "deteriorating" if shift < -0.1 else
                "stable"
            ),
            "top_events": [
                {
                    "headline":        e.headline,
                    "sentiment":       e.sentiment,
                    "importance":      e.importance,
                    "affected_assets": e.affected_assets,
                    "extracted_at":    e.extracted_at.isoformat(),
                }
                for e in top
            ],
        })

    category_changes.sort(key=lambda x: abs(x["sentiment_shift"]), reverse=True)

    # Per-asset summaries from current window
    asset_data: dict[str, dict] = {}
    for row in current_rows:
        for asset in (row.affected_assets or []):
            d = asset_data.setdefault(asset, {
                "sentiments": [], "importance_sum": 0.0,
                "event_count": 0, "headlines": [],
            })
            d["sentiments"].append(row.sentiment)
            d["importance_sum"] += _importance_weight(row.importance)
            d["event_count"]    += 1
            d["headlines"].append(row.headline)

    asset_changes = []
    for asset, d in asset_data.items():
        net = _avg_sentiment(d["sentiments"])
        asset_changes.append({
            "asset":         asset,
            "net_sentiment": round(net, 3),
            "event_count":   d["event_count"],
            "impact_weight": round(d["importance_sum"], 1),
            "direction":     (
                "bullish" if net > 0.15  else
                "bearish" if net < -0.15 else
                "neutral"
            ),
            "top_headlines": d["headlines"][:2],
        })
    asset_changes.sort(key=lambda x: abs(x["net_sentiment"]), reverse=True)

    return {
        "period_hours":        hours,
        "current_event_count": len(current_rows),
        "prior_event_count":   len(prior_rows),
        "computed_at":         now.isoformat(),
        "category_changes":    category_changes,
        "asset_changes":       asset_changes,
        "new_categories":      [
            c for c in current_by_cat if c not in prior_sentiments
        ],
    }


def _avg_sentiment(sentiments: list[str]) -> float:
    if not sentiments:
        return 0.0
    weights = {"bullish": 1.0, "bearish": -1.0, "neutral": 0.0}
    return sum(weights.get(s, 0.0) for s in sentiments) / len(sentiments)


def _importance_weight(importance: str) -> float:
    return {"high": 3.0, "medium": 2.0, "low": 1.0}.get(importance, 1.0)
