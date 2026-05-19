"""
Signal lifecycle tracking.

Creates a SignalOutcome row for every generated signal, then resolves it
each polling cycle by checking current prices against the signal's levels.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.signal_tracking.models import SignalOutcome
from app.market_data.service import get_latest_prices
from app.core.logging import get_logger

logger = get_logger(__name__)

_HORIZON_HOURS: dict[str, int] = {
    "scalp":    1,
    "intraday": 4,
    "swing":    24,
    "macro":    72,
}
_DEFAULT_WIN_PCT  =  3.0  # % price move needed to call a win when no TP set
_DEFAULT_LOSS_PCT = -3.0  # % price move needed to call a loss when no SL set


# ── Public API ────────────────────────────────────────────────────────────────

def create_signal_outcome(db: Session, signal: dict) -> SignalOutcome | None:
    """Persist a new SignalOutcome when a signal is generated.

    Safe to call multiple times — skips if an outcome for this signal already exists.
    """
    signal_id = signal.get("id")
    if not signal_id:
        return None

    regime = _safe_regime(db)

    outcome = SignalOutcome(
        signal_id=signal_id,
        asset=signal["asset"],
        direction=signal["signal"],
        confidence=signal["confidence"],
        time_horizon=signal.get("time_horizon", "swing"),
        status="active",
        price_at_signal=signal.get("entry_price"),
        stop_loss=signal.get("stop_loss"),
        take_profit=signal.get("take_profit"),
        market_regime=regime.get("primary_regime") if regime else None,
        event_ids=signal.get("event_ids") or [],
        performance_score=signal.get("quality_score"),  # pre-outcome quality estimate
        created_at=datetime.utcnow(),
    )
    try:
        db.add(outcome)
        db.commit()
        db.refresh(outcome)
        return outcome
    except IntegrityError:
        db.rollback()
        return db.query(SignalOutcome).filter(
            SignalOutcome.signal_id == signal_id
        ).first()


def resolve_active_outcomes(db: Session) -> int:
    """Evaluate all active outcomes against current prices.

    Called by the scheduler each cycle. Returns number of outcomes resolved.
    """
    active = (
        db.query(SignalOutcome)
        .filter(SignalOutcome.status == "active")
        .all()
    )
    if not active:
        return 0

    prices = {p["symbol"]: p["close"] for p in get_latest_prices(db)}
    resolved = 0

    for outcome in active:
        current_price = prices.get(outcome.asset)
        if not current_price:
            continue

        # Check expiry first
        max_hours = _HORIZON_HOURS.get(outcome.time_horizon, 24)
        if datetime.utcnow() - outcome.created_at > timedelta(hours=max_hours):
            _resolve(db, outcome, current_price, "expired")
            resolved += 1
            continue

        # HOLD signals don't have directional outcomes
        if outcome.direction == "HOLD":
            continue

        result = _check_price_outcome(outcome, current_price)
        if result:
            _resolve(db, outcome, current_price, result)
            resolved += 1

    if resolved:
        logger.info(f"Signal tracking: resolved {resolved} outcomes")
    return resolved


def get_recent_outcomes(
    db: Session,
    limit: int = 100,
    status: str | None = None,
    asset: str | None = None,
) -> list[dict]:
    q = db.query(SignalOutcome)
    if status:
        q = q.filter(SignalOutcome.status == status)
    if asset:
        q = q.filter(SignalOutcome.asset == asset.upper())
    rows = q.order_by(SignalOutcome.created_at.desc()).limit(limit).all()
    return [r.to_dict() for r in rows]


def link_trade_to_outcome(db: Session, signal_id: int, trade_id: int) -> None:
    """Record which PaperTrade was opened for a given signal."""
    outcome = db.query(SignalOutcome).filter(
        SignalOutcome.signal_id == signal_id
    ).first()
    if outcome:
        outcome.trade_id = trade_id
        db.commit()


# ── Internal helpers ──────────────────────────────────────────────────────────

def _check_price_outcome(outcome: SignalOutcome, current_price: float) -> str | None:
    if not outcome.price_at_signal:
        return None

    pct = (current_price - outcome.price_at_signal) / outcome.price_at_signal * 100

    if outcome.direction == "BUY":
        if outcome.take_profit and current_price >= outcome.take_profit:
            return "win"
        if outcome.stop_loss and current_price <= outcome.stop_loss:
            return "loss"
        if pct >= _DEFAULT_WIN_PCT:
            return "win"
        if pct <= _DEFAULT_LOSS_PCT:
            return "loss"

    elif outcome.direction == "SELL":
        if outcome.take_profit and current_price <= outcome.take_profit:
            return "win"
        if outcome.stop_loss and current_price >= outcome.stop_loss:
            return "loss"
        if pct <= -_DEFAULT_WIN_PCT:
            return "win"
        if pct >= -_DEFAULT_LOSS_PCT:
            return "loss"

    return None


def _resolve(
    db: Session,
    outcome: SignalOutcome,
    current_price: float,
    result: str,
) -> None:
    outcome.status      = "completed" if result in ("win", "loss", "neutral") else "expired"
    outcome.outcome     = result
    outcome.price_at_close = current_price
    if outcome.price_at_signal:
        pct = (current_price - outcome.price_at_signal) / outcome.price_at_signal * 100
        outcome.price_change_pct  = round(pct, 4)
        outcome.performance_score = _score(result, abs(pct))
    outcome.resolved_at = datetime.utcnow()
    db.commit()


def _score(outcome: str, magnitude_pct: float) -> float:
    """Map outcome + magnitude to a 0–100 quality score."""
    if outcome == "win":
        return round(min(100.0, 60.0 + magnitude_pct * 5), 1)
    if outcome == "loss":
        return round(max(0.0, 40.0 - magnitude_pct * 5), 1)
    if outcome == "neutral":
        return 50.0
    return 25.0  # expired


def _safe_regime(db: Session) -> dict | None:
    try:
        from app.regime.service import get_current_regime
        return get_current_regime(db)
    except Exception:
        return None
