"""
Regime-specific confidence adjustments.

If signals generated in the 'risk_off' regime historically win only 42%
of the time, confidence for new signals in that regime is reduced by up to 10.

If 'risk_on' has a 68% win rate, signals in that regime get a +5 boost.

Thresholds:
  win_rate >= 65%  →  +5   (regime is historically favorable)
  win_rate 50–65%  →   0   (neutral — no adjustment)
  win_rate 40–50%  →  -5   (regime underperforms — caution)
  win_rate  < 40%  → -10   (regime significantly underperforms)

Minimum 5 resolved outcomes per regime before applying any adjustment.
Regimes with fewer outcomes return 0 (neutral).
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.signal_tracking.models import SignalOutcome

_MIN_SAMPLE       = 5
_BOOST_THRESHOLD  = 65.0
_NEUTRAL_THRESHOLD = 50.0
_CAUTION_THRESHOLD = 40.0


def get_regime_adjustments(db: Session) -> dict[str, dict]:
    """
    Returns {regime_name: {adjustment, win_rate, sample_size, direction, reason}}.
    Adjustment is added to confidence when a signal is generated in that regime.
    """
    outcomes = (
        db.query(SignalOutcome)
        .filter(
            SignalOutcome.outcome.in_(["win", "loss"]),
            SignalOutcome.market_regime.is_not(None),
        )
        .all()
    )

    regimes: dict[str, dict] = {}
    for o in outcomes:
        r = o.market_regime or "unknown"
        if r not in regimes:
            regimes[r] = {"wins": 0, "total": 0}
        regimes[r]["total"] += 1
        if o.outcome == "win":
            regimes[r]["wins"] += 1

    result: dict[str, dict] = {}
    for regime, data in regimes.items():
        total = data["total"]
        wins  = data["wins"]

        if total < _MIN_SAMPLE:
            result[regime] = {
                "adjustment":  0.0,
                "win_rate":    None,
                "sample_size": total,
                "direction":   "neutral",
                "reason":      f"Insufficient data ({total} outcomes, need {_MIN_SAMPLE})",
            }
            continue

        win_rate = round(wins / total * 100, 1)
        adj, direction = _adjustment(win_rate)

        result[regime] = {
            "adjustment":  adj,
            "win_rate":    win_rate,
            "sample_size": total,
            "direction":   direction,
            "reason":      f"Historical win rate {win_rate}% in '{regime}' regime — applying {adj:+.0f}",
        }

    return result


def get_regime_adjustment(db: Session, regime_name: str | None) -> float:
    """Fast single-regime lookup — returns the adjustment factor for one regime."""
    if not regime_name:
        return 0.0
    adjustments = get_regime_adjustments(db)
    return adjustments.get(regime_name, {}).get("adjustment", 0.0)


def _adjustment(win_rate: float) -> tuple[float, str]:
    if win_rate >= _BOOST_THRESHOLD:
        return 5.0, "boost"
    if win_rate >= _NEUTRAL_THRESHOLD:
        return 0.0, "neutral"
    if win_rate >= _CAUTION_THRESHOLD:
        return -5.0, "reduce"
    return -10.0, "reduce"
