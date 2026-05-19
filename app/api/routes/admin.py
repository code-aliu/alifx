from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from app.auth.dependencies import get_db, require_admin
from app.auth.models import User, UserSession, UserMemory
from app.auth.schemas import UserOut
from app.auth.service import (
    get_feature_usage_totals, get_copilot_intent_totals,
)
from app.core.error_log import get_recent_errors, clear_errors
from app.core.uptime import get_uptime_seconds

router = APIRouter(prefix="/admin", tags=["Admin"])


# ── System health ─────────────────────────────────────────────────────────────

@router.get("/system")
def system_health(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """DB connectivity, table counts, service uptime."""
    from app.database import engine
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    from app.auth.models import UserPreferences
    from app.signals.models import TradingSignal
    from app.news.models import NewsArticle
    from app.market_data.models import PriceBar

    return {
        "status": "ok" if db_status == "ok" else "degraded",
        "uptime_seconds": get_uptime_seconds(),
        "database": db_status,
        "table_counts": {
            "users":           db.query(func.count(User.id)).scalar(),
            "active_sessions": db.query(func.count(UserSession.id))
                                 .filter(UserSession.expires_at > datetime.utcnow()).scalar(),
            "news_articles":   db.query(func.count(NewsArticle.id)).scalar(),
            "price_bars":      db.query(func.count(PriceBar.id)).scalar(),
            "signals":         db.query(func.count(TradingSignal.id)).scalar(),
        },
    }


# ── Ingestion status ──────────────────────────────────────────────────────────

@router.get("/ingestion")
def ingestion_status(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Last fetch times and record counts for news and price data."""
    from app.news.models import NewsArticle
    from app.market_data.models import PriceBar
    from app.events.models import MarketEvent

    last_article = db.query(NewsArticle).order_by(desc(NewsArticle.fetched_at)).first()
    last_price   = db.query(PriceBar).order_by(desc(PriceBar.fetched_at)).first()
    last_event   = db.query(MarketEvent).order_by(desc(MarketEvent.extracted_at)).first()

    unprocessed = db.query(func.count(NewsArticle.id)).filter(NewsArticle.processed == False).scalar()  # noqa: E712
    processed   = db.query(func.count(NewsArticle.id)).filter(NewsArticle.processed == True).scalar()   # noqa: E712

    def _fmt(dt: datetime | None) -> str | None:
        return dt.isoformat() + "Z" if dt else None

    return {
        "news": {
            "last_fetch":  _fmt(last_article.fetched_at if last_article else None),
            "total":       processed + unprocessed,
            "processed":   processed,
            "unprocessed": unprocessed,
        },
        "prices": {
            "last_fetch": _fmt(last_price.fetched_at if last_price else None),
            "total":      db.query(func.count(PriceBar.id)).scalar(),
        },
        "events": {
            "last_extracted": _fmt(last_event.extracted_at if last_event else None),
            "total":          db.query(func.count(MarketEvent.id)).scalar(),
        },
    }


# ── Signal generation status ──────────────────────────────────────────────────

@router.get("/signals")
def signal_status(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Recent signal generation activity."""
    from app.signals.models import TradingSignal

    last_signal = db.query(TradingSignal).order_by(desc(TradingSignal.generated_at)).first()
    since_24h   = datetime.utcnow() - timedelta(hours=24)

    direction_counts = (
        db.query(TradingSignal.signal, func.count(TradingSignal.id))
        .filter(TradingSignal.generated_at >= since_24h)
        .group_by(TradingSignal.signal)
        .all()
    )
    recent_signals = (
        db.query(TradingSignal)
        .order_by(desc(TradingSignal.generated_at))
        .limit(10)
        .all()
    )

    return {
        "last_generated":   last_signal.generated_at.isoformat() + "Z" if last_signal else None,
        "last_24h_by_direction": {d: c for d, c in direction_counts},
        "recent": [
            {
                "asset":        s.asset,
                "signal":       s.signal,
                "confidence":   s.confidence,
                "generated_at": s.generated_at.isoformat() + "Z",
            }
            for s in recent_signals
        ],
    }


# ── API usage ─────────────────────────────────────────────────────────────────

@router.get("/api-usage")
def api_usage(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Feature usage totals and copilot intent breakdown from user memory."""
    return {
        "feature_usage":   get_feature_usage_totals(db),
        "copilot_intents": get_copilot_intent_totals(db),
        "memory_entries":  db.query(func.count(UserMemory.id)).scalar(),
    }


# ── Error log ─────────────────────────────────────────────────────────────────

@router.get("/errors")
def error_log(_: User = Depends(require_admin)):
    return {"errors": get_recent_errors(limit=50)}


@router.delete("/errors")
def clear_error_log(_: User = Depends(require_admin)):
    clear_errors()
    return {"detail": "Error log cleared"}


# ── Analytics summary ─────────────────────────────────────────────────────────

@router.get("/analytics")
def analytics(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    """Aggregated product analytics — internal use only."""
    total_users  = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()  # noqa: E712
    new_7d = db.query(func.count(User.id)).filter(
        User.created_at >= datetime.utcnow() - timedelta(days=7)
    ).scalar()
    return {
        "users": {
            "total":    total_users,
            "active":   active_users,
            "new_7d":   new_7d,
        },
        "feature_usage":   get_feature_usage_totals(db),
        "copilot_intents": get_copilot_intent_totals(db),
    }


# ── User management ───────────────────────────────────────────────────────────

@router.get("/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(desc(User.created_at)).all()
    return [UserOut.model_validate(u) for u in users]


@router.put("/users/{user_id}/role")
def set_role(user_id: int, role: str, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    if role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    return {"detail": f"User {user_id} role set to {role}"}
