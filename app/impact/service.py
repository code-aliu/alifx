from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from app.events.models import MarketEvent
from app.impact.mapper import map_events_to_impact, summarize_impact
from app.core.logging import get_logger

logger = get_logger(__name__)


def get_asset_impact(db: Session, hours: int = 24) -> dict[str, dict]:
    """Compute current impact scores for all tracked assets from recent events."""
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    events = (
        db.query(MarketEvent)
        .filter(MarketEvent.extracted_at >= cutoff)
        .all()
    )
    scores = map_events_to_impact(events)
    summary = summarize_impact(scores)
    logger.debug(f"Impact: computed scores for {len(scores)} assets from {len(events)} events")
    return summary


def get_impact_for_asset(db: Session, symbol: str, hours: int = 24) -> dict:
    """Return the impact summary for a single asset."""
    all_impact = get_asset_impact(db, hours=hours)
    return all_impact.get(symbol.upper(), {"score": 0.0, "direction": "neutral", "strength": 0.0})
