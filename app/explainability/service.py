"""
Explainability layer — structured answers to "why?" questions.

Three public functions:
  explain_signal(db, symbol)        → full WHY breakdown for an asset's latest signal
  explain_event_impact(db, event_id) → how one event influenced signals across assets
  get_full_market_context(db)       → regime + signal consensus + recent changes
"""
from sqlalchemy.orm import Session

from app.signals.service import get_signals_for_asset, get_latest_signals
from app.events.service import get_events_for_asset, get_recent_changes
from app.events.models import MarketEvent
from app.signals.models import TradingSignal
from app.analysis.service import analyse_asset
from app.market_data.service import get_price_history
from app.risk.scorer import compute_atr
from app.impact.rules import compute_impact_score
from app.validation.service import validate_signal
from app.core.logging import get_logger

logger = get_logger(__name__)

# Keywords that mark each class of reasoning line
_EVENT_KEYWORDS  = ("impact", "news", "event flow", "triggered by", "inflow", "etf")
_TA_KEYWORDS     = ("rsi", "ema", "macd", "trend", "breakout", "momentum", "oversold",
                    "overbought", "golden cross", "death cross", "support", "resistance")
_REGIME_KEYWORDS = ("regime",)
_RISK_KEYWORDS   = ("risk", "volatility", "atr", "stop", "take-profit", "risk/reward")


# ── Public API ────────────────────────────────────────────────────────────────

def explain_signal(db: Session, symbol: str) -> dict:
    """Full explanation of why the current signal exists for an asset.

    Answers:
      • Why BUY/SELL/HOLD?
      • Which events drove it?
      • Which technical factors confirmed it?
      • What is the current regime context?
      • Are there any conflicts or quality issues?
    """
    signals = get_signals_for_asset(db, symbol.upper(), limit=1)
    if not signals:
        return {"asset": symbol.upper(), "error": "no_signal_available"}

    signal   = signals[0]
    analysis = analyse_asset(db, symbol.upper())
    regime   = _safe_regime(db)
    events   = get_events_for_asset(db, symbol.upper(), hours=24)

    # ATR for volatility-adjusted confidence
    prices  = get_price_history(db, symbol.upper(), limit=50)
    atr     = compute_atr(prices) if prices else {"available": False}
    atr_pct = atr.get("pct") if atr.get("available") else None

    validation = validate_signal(signal, db, atr_pct=atr_pct)

    # Categorise reasoning lines
    reasoning       = signal.get("reasoning", [])
    event_lines     = _filter_lines(reasoning, _EVENT_KEYWORDS)
    ta_lines        = _filter_lines(reasoning, _TA_KEYWORDS)
    regime_lines    = _filter_lines(reasoning, _REGIME_KEYWORDS)
    risk_lines      = _filter_lines(reasoning, _RISK_KEYWORDS)

    indicators = analysis.get("indicators", {})

    return {
        "asset":          symbol.upper(),
        "signal":         signal["signal"],
        "confidence":     signal["confidence"],
        "time_horizon":   signal["time_horizon"],
        "risk_level":     signal["risk_level"],
        # Primary narrative
        "primary_drivers":    event_lines + ta_lines,
        # Event context
        "event_drivers":      events[:5],
        "event_reasoning":    event_lines,
        # Technical context
        "technical_factors": {
            "rsi":       indicators.get("rsi", {}),
            "ema":       indicators.get("ema", {}),
            "macd":      indicators.get("macd", {}),
            "volatility":indicators.get("volatility", {}),
            "trend":     analysis.get("trend", {}),
            "breakout":  analysis.get("breakout", {}),
        },
        "ta_reasoning":    ta_lines,
        # Regime context
        "regime_context":  regime,
        "regime_reasoning":regime_lines,
        # Risk
        "risk_assessment": {
            "risk_level":  signal["risk_level"],
            "entry_price": signal.get("entry_price"),
            "stop_loss":   signal.get("stop_loss"),
            "take_profit": signal.get("take_profit"),
            "atr_pct":     atr_pct,
        },
        "risk_reasoning":  risk_lines,
        # Validation
        "validation":      validation,
        # Full chain for transparency
        "full_reasoning":  reasoning,
        "event_ids":       signal.get("event_ids", []),
    }


def explain_event_impact(db: Session, event_id: int) -> dict:
    """Explain how a specific event influenced asset prices and signals.

    Returns:
      • The event itself
      • Per-asset impact score computed from this single event
      • Signals that referenced this event (via event_ids column)
    """
    event = db.query(MarketEvent).filter(MarketEvent.id == event_id).first()
    if not event:
        return {"error": "event_not_found", "event_id": event_id}

    # Compute this event's contribution per affected asset
    impact_per_asset: dict[str, dict] = {}
    for asset in (event.affected_assets or []):
        score     = compute_impact_score(event.sentiment, event.importance)
        direction = "bullish" if score > 0 else "bearish" if score < 0 else "neutral"
        impact_per_asset[asset] = {
            "score":     score,
            "direction": direction,
            "sentiment": event.sentiment,
            "importance":event.importance,
        }

    # Find signals that reference this event
    influenced: list[dict] = []
    recent_signals = (
        db.query(TradingSignal)
        .filter(TradingSignal.event_ids.isnot(None))
        .order_by(TradingSignal.generated_at.desc())
        .limit(100)
        .all()
    )
    for sig in recent_signals:
        if event_id in (sig.event_ids or []):
            influenced.append({
                "asset":        sig.asset,
                "signal":       sig.signal,
                "confidence":   sig.confidence,
                "generated_at": sig.generated_at.isoformat(),
            })

    return {
        "event":             event.to_dict(),
        "impact_per_asset":  impact_per_asset,
        "influenced_signals":influenced,
        "summary": (
            f"{event.category.capitalize()} event classified as {event.sentiment} "
            f"({event.importance} importance), affecting "
            f"{', '.join(event.affected_assets or ['no assets'])}."
        ),
    }


def get_full_market_context(db: Session) -> dict:
    """Rich market context: regime, signal consensus, and recent change summary.

    Answers "what is the overall market picture right now?"
    """
    regime      = _safe_regime(db)
    all_signals = get_latest_signals(db)

    buy_count  = sum(1 for s in all_signals if s["signal"] == "BUY")
    sell_count = sum(1 for s in all_signals if s["signal"] == "SELL")
    hold_count = sum(1 for s in all_signals if s["signal"] == "HOLD")
    total      = len(all_signals)

    if total == 0:
        consensus = "no_data"
    elif buy_count > sell_count and buy_count > hold_count:
        consensus = "bullish"
    elif sell_count > buy_count and sell_count > hold_count:
        consensus = "bearish"
    else:
        consensus = "mixed"

    # Top 3 signals by confidence for a quick dashboard view
    top_signals = sorted(all_signals, key=lambda s: s["confidence"], reverse=True)[:3]

    changes = None
    try:
        changes = get_recent_changes(db, hours=6)
    except Exception as e:
        logger.debug(f"Market changes unavailable: {e}")

    return {
        "regime": regime,
        "signal_summary": {
            "total":     total,
            "buy":       buy_count,
            "sell":      sell_count,
            "hold":      hold_count,
            "consensus": consensus,
        },
        "top_signals":           top_signals,
        "recent_market_changes": changes,
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _filter_lines(reasoning: list[str], keywords: tuple[str, ...]) -> list[str]:
    """Return reasoning lines that contain any of the given keywords (case-insensitive)."""
    return [
        line for line in reasoning
        if any(kw in line.lower() for kw in keywords)
    ]


def _safe_regime(db: Session) -> dict | None:
    try:
        from app.regime.service import get_current_regime
        return get_current_regime(db)
    except Exception as e:
        logger.debug(f"Regime unavailable in explainability: {e}")
        return None
