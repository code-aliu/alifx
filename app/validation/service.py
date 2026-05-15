"""
Signal validation — four independent checks, composable into a single pass.

Checks:
  1. Staleness        — age vs time_horizon threshold
  2. Conflict flags   — event/TA mismatch + signal/regime mismatch
  3. Volatility penalty — confidence reduction under high-vol environments
  4. Consistency score  — fraction of recent same-asset signals agreeing with current
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.signals.models import TradingSignal
from app.core.logging import get_logger

logger = get_logger(__name__)

# Hours a signal remains fresh per time_horizon
_STALE_HOURS: dict[str, int] = {
    "scalp":    1,
    "intraday": 4,
    "swing":    24,
    "macro":    72,
}


# ── Public API ────────────────────────────────────────────────────────────────

def validate_signal(
    signal: dict,
    db: Session,
    atr_pct: float | None = None,
) -> dict:
    """Run all validation checks and return a single validation summary.

    atr_pct: ATR as a percentage of price (e.g. 2.5 → 2.5%). Pass None if
             price data was unavailable.
    """
    flags: list[str] = []
    warnings: list[str] = []

    # 1 — Staleness
    is_stale, stale_reason = check_staleness(signal)
    if is_stale:
        flags.append("stale_signal")
        if stale_reason:
            warnings.append(stale_reason)

    # 2 — Conflict detection
    conflicts = detect_conflicts(signal, db)
    flags.extend(conflicts)
    if "event_ta_conflict" in conflicts:
        warnings.append("Event sentiment conflicts with technical indicators")
    if "signal_regime_conflict" in conflicts:
        warnings.append("Signal direction conflicts with the current market regime")

    # 3 — Volatility penalty
    vol_penalty = compute_volatility_penalty(signal.get("risk_level", "medium"), atr_pct)

    # 4 — Consistency
    consistency = compute_consistency_score(db, signal["asset"], current_signal=signal.get("signal"))
    if consistency < 0.4:
        flags.append("inconsistent_signals")
        warnings.append("Recent signals for this asset have been inconsistent")

    adjusted_confidence = max(5.0, min(95.0, signal["confidence"] - vol_penalty))

    return {
        "is_stale":            is_stale,
        "stale_reason":        stale_reason,
        "consistency_score":   consistency,
        "conflict_flags":      conflicts,
        "volatility_penalty":  vol_penalty,
        "adjusted_confidence": round(adjusted_confidence, 1),
        "warnings":            warnings,
        "flags":               flags,
        "signal_quality":      _quality_label(adjusted_confidence, flags),
    }


def check_staleness(signal: dict) -> tuple[bool, str | None]:
    """Return (is_stale, reason_string) based on signal age vs time_horizon."""
    generated_at = signal.get("generated_at")
    if not generated_at:
        return True, "Signal has no timestamp"

    if isinstance(generated_at, str):
        try:
            generated_at = datetime.fromisoformat(generated_at)
        except ValueError:
            return True, "Signal timestamp could not be parsed"

    horizon   = signal.get("time_horizon", "swing")
    max_hours = _STALE_HOURS.get(horizon, 24)
    age       = datetime.utcnow() - generated_at

    if age > timedelta(hours=max_hours):
        hours_old = round(age.total_seconds() / 3600, 1)
        return True, (
            f"Signal is {hours_old}h old (freshness limit for {horizon!r} signals: {max_hours}h)"
        )
    return False, None


def detect_conflicts(signal: dict, db: Session) -> list[str]:
    """Return a list of conflict flag strings for this signal.

    Flags:
      event_ta_conflict     — reasoning chain says event and TA disagree
      signal_regime_conflict — signal direction opposes the current primary regime
    """
    conflicts: list[str] = []

    # Event/TA conflict: generator already stamps "conflicting" in reasoning step 5
    reasoning_text = " ".join(signal.get("reasoning", [])).lower()
    if "conflicting" in reasoning_text:
        conflicts.append("event_ta_conflict")

    # Regime conflict: BUY in risk_off, or SELL in risk_on
    sig_dir = signal.get("signal")
    if sig_dir in ("BUY", "SELL"):
        try:
            from app.regime.service import get_current_regime
            regime = get_current_regime(db)
            primary = regime.get("primary_regime") if regime else None
            if sig_dir == "BUY" and primary == "risk_off":
                conflicts.append("signal_regime_conflict")
            elif sig_dir == "SELL" and primary == "risk_on":
                conflicts.append("signal_regime_conflict")
        except Exception as e:
            logger.debug(f"Regime check skipped during conflict detection: {e}")

    return conflicts


def compute_volatility_penalty(
    risk_level: str,
    atr_pct: float | None = None,
) -> float:
    """Return additional confidence penalty (positive = reduction).

    Base penalty from risk level, plus extra if ATR% is abnormally high.
    """
    base = {"low": 0.0, "medium": 2.0, "high": 5.0}.get(risk_level, 2.0)

    atr_extra = 0.0
    if atr_pct is not None and atr_pct > 3.0:
        atr_extra = min(atr_pct - 3.0, 5.0)  # cap extra penalty at 5 pts

    return round(base + atr_extra, 1)


def compute_consistency_score(
    db: Session,
    asset: str,
    current_signal: str | None = None,
    lookback: int = 5,
) -> float:
    """Fraction of recent DB signals for this asset that agree with `current_signal`.

    If `current_signal` is provided (e.g. from the signal being validated),
    all `lookback` DB rows are compared against it.

    If omitted, the most-recent DB signal is treated as the reference and the
    prior `lookback-1` rows are compared against it — the same as before.

    Returns 1.0 when there is insufficient history to draw a comparison.
    """
    rows = (
        db.query(TradingSignal)
        .filter(TradingSignal.asset == asset)
        .order_by(TradingSignal.generated_at.desc())
        .limit(lookback)
        .all()
    )

    if current_signal is not None:
        if not rows:
            return 1.0
        matching = sum(1 for r in rows if r.signal == current_signal)
        return round(matching / len(rows), 2)
    else:
        if len(rows) < 2:
            return 1.0
        reference = rows[0].signal
        matching  = sum(1 for r in rows[1:] if r.signal == reference)
        return round(matching / (len(rows) - 1), 2)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _quality_label(confidence: float, flags: list[str]) -> str:
    if flags:
        return "degraded"
    if confidence >= 70:
        return "strong"
    elif confidence >= 55:
        return "moderate"
    return "weak"
