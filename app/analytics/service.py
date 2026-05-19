"""
Analytics service — feedback collection and product intelligence aggregation.

Design principles:
- Non-blocking: all writes are fire-and-forget (caller catches exceptions)
- Privacy-first: no PII stored in analytics tables
- Lightweight: simple counts and aggregates, no complex ML pipelines
"""
from __future__ import annotations
import hashlib
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.analytics.models import FeedbackEvent, AnalyticsEvent


# ── Context key ───────────────────────────────────────────────────────────────

def make_context_key(text: str) -> str:
    """Short non-reversible fingerprint of a question or ID string."""
    return hashlib.sha1(text.encode()).hexdigest()[:10]


# ── Feedback ──────────────────────────────────────────────────────────────────

def submit_feedback(
    db: Session,
    feature: str,
    rating: int,
    user_id: int | None = None,
    context_key: str | None = None,
    intent: str | None = None,
    clarity: int | None = None,
    notes: str | None = None,
) -> FeedbackEvent:
    event = FeedbackEvent(
        user_id=user_id,
        feature=feature,
        context_key=context_key,
        intent=intent,
        rating=rating,
        clarity=clarity,
        notes=notes[:200] if notes else None,
    )
    db.add(event)
    db.commit()
    return event


def get_feedback_summary(db: Session, feature: str | None = None, days: int = 30) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    q = db.query(FeedbackEvent).filter(FeedbackEvent.created_at >= since)
    if feature:
        q = q.filter(FeedbackEvent.feature == feature)
    rows = q.all()

    if not rows:
        return {"total": 0, "useful_pct": None, "avg_clarity": None, "by_feature": {}}

    total   = len(rows)
    positive = sum(1 for r in rows if r.rating > 0)
    clarity_vals = [r.clarity for r in rows if r.clarity is not None]
    avg_clarity  = round(sum(clarity_vals) / len(clarity_vals), 2) if clarity_vals else None

    by_feature: dict[str, dict] = {}
    for r in rows:
        f = r.feature
        if f not in by_feature:
            by_feature[f] = {"total": 0, "positive": 0, "intents": {}}
        by_feature[f]["total"]    += 1
        by_feature[f]["positive"] += 1 if r.rating > 0 else 0
        if r.intent:
            by_feature[f]["intents"][r.intent] = by_feature[f]["intents"].get(r.intent, 0) + 1

    for f, d in by_feature.items():
        d["useful_pct"] = round(d["positive"] / d["total"] * 100, 1) if d["total"] else None

    return {
        "total":       total,
        "useful_pct":  round(positive / total * 100, 1),
        "avg_clarity": avg_clarity,
        "by_feature":  by_feature,
    }


def get_low_trust_intents(db: Session, days: int = 30) -> list[dict]:
    """Intents with below-average usefulness — indicates confusing explanations."""
    since = datetime.utcnow() - timedelta(days=days)
    rows  = db.query(FeedbackEvent).filter(
        FeedbackEvent.created_at >= since,
        FeedbackEvent.intent != None,  # noqa: E711
    ).all()

    intent_stats: dict[str, dict] = {}
    for r in rows:
        i = r.intent
        if i not in intent_stats:
            intent_stats[i] = {"total": 0, "positive": 0}
        intent_stats[i]["total"]    += 1
        intent_stats[i]["positive"] += 1 if r.rating > 0 else 0

    results = []
    for intent, s in intent_stats.items():
        if s["total"] < 2:
            continue
        pct = s["positive"] / s["total"] * 100
        results.append({"intent": intent, "useful_pct": round(pct, 1), "total": s["total"]})

    return sorted(results, key=lambda x: x["useful_pct"])


# ── Interaction events ────────────────────────────────────────────────────────

def track_event(
    db: Session,
    event_type: str,
    user_id: int | None = None,
    metadata: dict | None = None,
) -> None:
    db.add(AnalyticsEvent(event_type=event_type, user_id=user_id, event_data=metadata or {}))
    db.commit()


# ── Product analytics aggregates ──────────────────────────────────────────────

def get_event_counts(db: Session, days: int = 30) -> dict:
    since = datetime.utcnow() - timedelta(days=days)
    rows  = (
        db.query(AnalyticsEvent.event_type, func.count(AnalyticsEvent.id))
        .filter(AnalyticsEvent.created_at >= since)
        .group_by(AnalyticsEvent.event_type)
        .all()
    )
    return {r[0]: r[1] for r in rows}


def get_retention_indicators(db: Session) -> dict:
    """Users active in last 7 days vs 30 days (from analytics_events)."""
    now  = datetime.utcnow()
    d7   = now - timedelta(days=7)
    d30  = now - timedelta(days=30)

    active_7d  = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(
        AnalyticsEvent.created_at >= d7,
        AnalyticsEvent.user_id != None,  # noqa: E711
    ).scalar() or 0
    active_30d = db.query(func.count(func.distinct(AnalyticsEvent.user_id))).filter(
        AnalyticsEvent.created_at >= d30,
        AnalyticsEvent.user_id != None,  # noqa: E711
    ).scalar() or 0

    return {"active_7d": active_7d, "active_30d": active_30d}


def get_daily_event_trend(db: Session, days: int = 14) -> list[dict]:
    """Daily event counts for the last N days — useful for trend charts."""
    since = datetime.utcnow() - timedelta(days=days)
    rows  = db.query(AnalyticsEvent).filter(AnalyticsEvent.created_at >= since).all()

    daily: dict[str, int] = {}
    for r in rows:
        day = r.created_at.strftime("%Y-%m-%d")
        daily[day] = daily.get(day, 0) + 1

    return [{"date": d, "events": c} for d, c in sorted(daily.items())]
