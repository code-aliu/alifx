from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db, get_optional_user, require_admin
from app.auth.models import User
from app.analytics.service import (
    submit_feedback, get_feedback_summary, get_low_trust_intents,
    track_event, get_event_counts, get_retention_indicators,
    get_daily_event_trend, make_context_key,
)
from app.auth.service import get_feature_usage_totals, get_copilot_intent_totals

router = APIRouter(tags=["Analytics"])


# ── Feedback ──────────────────────────────────────────────────────────────────

class FeedbackIn(BaseModel):
    feature:     str                   # "copilot" | "guidance" | "signal"
    rating:      int                   # 1 or -1
    question:    Optional[str] = None  # hashed — not stored raw
    intent:      Optional[str] = None
    clarity:     Optional[int] = None  # 1–3
    notes:       Optional[str] = None
    context_key: Optional[str] = None  # caller-provided key (e.g. signal_id)


@router.post("/feedback")
def feedback(
    body: FeedbackIn,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    if body.rating not in (1, -1):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="rating must be 1 or -1")
    if body.clarity is not None and body.clarity not in (1, 2, 3):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="clarity must be 1, 2, or 3")

    ctx_key = body.context_key or (make_context_key(body.question) if body.question else None)
    submit_feedback(
        db,
        feature=body.feature,
        rating=body.rating,
        user_id=current_user.id if current_user else None,
        context_key=ctx_key,
        intent=body.intent,
        clarity=body.clarity,
        notes=body.notes,
    )
    return {"detail": "feedback recorded"}


# ── Interaction event (page views, signal views) ──────────────────────────────

class EventIn(BaseModel):
    event_type: str
    metadata:   Optional[dict] = None


@router.post("/analytics/event")
def record_event(
    body: EventIn,
    db: Session = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    allowed = {"page_view", "signal_view", "event_click", "guidance_ask", "summary_view"}
    if body.event_type not in allowed:
        return {"detail": "ignored"}
    try:
        track_event(db, body.event_type, user_id=current_user.id if current_user else None, metadata=body.metadata)
    except Exception:
        pass
    return {"detail": "ok"}


# ── Admin: product intelligence dashboard ────────────────────────────────────

@router.get("/admin/product-analytics")
def product_analytics(
    days: int = 30,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {
        "period_days":       days,
        "feedback":          get_feedback_summary(db, days=days),
        "low_trust_intents": get_low_trust_intents(db, days=days),
        "event_counts":      get_event_counts(db, days=days),
        "retention":         get_retention_indicators(db),
        "daily_trend":       get_daily_event_trend(db, days=min(days, 14)),
        "feature_usage":     get_feature_usage_totals(db),
        "copilot_intents":   get_copilot_intent_totals(db),
    }
