"""
Context retriever — pulls structured DB data based on detected intent.

Every call to retrieve_context() returns a dict with only the fields
relevant to the question. The assembler then converts this to prose.
"""
from __future__ import annotations
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.logging import get_logger

logger = get_logger(__name__)


# ── Public API ────────────────────────────────────────────────────────────────

def retrieve_context(db: Session, intent: str, asset: str | None = None) -> dict:
    """Gather DB context suited to the detected intent.

    Returns a dict of structured data. All sub-calls are individually
    guarded so a failure in one source never breaks the whole response.
    """
    ctx: dict = {
        "intent":     intent,
        "asset":      asset,
        "fetched_at": datetime.utcnow().isoformat(),
    }

    # Regime is always useful
    ctx["regime"] = _safe(lambda: _get_regime(db))

    if intent in ("signal", "asset"):
        _enrich_signal_context(db, ctx, asset or "BTC")

    elif intent == "regime":
        ctx["signals"]        = _safe(lambda: _get_all_signals(db))
        ctx["events"]         = _safe(lambda: _get_recent_events(db, limit=6))

    elif intent == "portfolio":
        ctx["portfolio"]      = _safe(lambda: _get_portfolio_intelligence(db))
        ctx["open_trades"]    = _safe(lambda: _get_open_trades(db))
        ctx["performance"]    = _safe(lambda: _get_performance(db))

    elif intent == "event":
        ctx["events"]         = _safe(lambda: _get_recent_events(db, limit=10))
        ctx["signals"]        = _safe(lambda: _get_all_signals(db))

    elif intent == "performance":
        ctx["performance"]    = _safe(lambda: _get_performance(db))
        ctx["signals"]        = _safe(lambda: _get_all_signals(db))

    elif intent == "narrative":
        ctx["signals"]        = _safe(lambda: _get_all_signals(db))
        ctx["events"]         = _safe(lambda: _get_recent_events(db, limit=8))
        ctx["portfolio"]      = _safe(lambda: _get_portfolio_intelligence(db))
        ctx["performance"]    = _safe(lambda: _get_performance(db))

    return ctx


# ── Intent-specific retrieval ─────────────────────────────────────────────────

def _enrich_signal_context(db: Session, ctx: dict, asset: str) -> None:
    ctx["signal"]   = _safe(lambda: _get_signal_for(db, asset))
    ctx["events"]   = _safe(lambda: _get_events_for(db, asset))
    ctx["analysis"] = _safe(lambda: _get_analysis(db, asset))


# ── Data fetchers ─────────────────────────────────────────────────────────────

def _get_regime(db: Session) -> dict | None:
    from app.regime.service import get_current_regime
    return get_current_regime(db)


def _get_signal_for(db: Session, asset: str) -> dict | None:
    from app.signals.service import get_signals_for_asset
    signals = get_signals_for_asset(db, asset, limit=1)
    return signals[0] if signals else None


def _get_all_signals(db: Session) -> list[dict]:
    from app.signals.service import get_latest_signals
    return get_latest_signals(db)


def _get_events_for(db: Session, asset: str) -> list[dict]:
    from app.events.service import get_events_for_asset
    events = get_events_for_asset(db, asset, hours=24)
    return events[:6]


def _get_recent_events(db: Session, limit: int = 8) -> list[dict]:
    from app.events.models import MarketEvent
    rows = (
        db.query(MarketEvent)
        .order_by(MarketEvent.extracted_at.desc())
        .limit(limit)
        .all()
    )
    return [r.to_dict() for r in rows]


def _get_analysis(db: Session, asset: str) -> dict:
    from app.analysis.service import analyse_asset
    return analyse_asset(db, asset)


def _get_portfolio_intelligence(db: Session) -> dict:
    from app.portfolio_intelligence.service import compute_portfolio_intelligence
    return compute_portfolio_intelligence(db)


def _get_open_trades(db: Session) -> list[dict]:
    from app.paper_trading.models import PaperTrade
    trades = (
        db.query(PaperTrade)
        .filter(PaperTrade.status == "open")
        .all()
    )
    return [t.to_dict() for t in trades]


def _get_performance(db: Session) -> dict:
    from app.performance.service import get_signal_performance
    return get_signal_performance(db)


# ── Guard ─────────────────────────────────────────────────────────────────────

def _safe(fn):
    """Call fn(); return None on any exception so one bad source never crashes context retrieval."""
    try:
        return fn()
    except Exception as e:
        logger.debug(f"Context retrieval partial failure: {e}")
        return None
