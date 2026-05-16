"""
Signal utility metrics — extends performance/service.py with decision-support quality measures.

New metrics not covered by the existing performance service:
  - false_positive_rate   : directional signals with <0.5% move at resolution
  - hold_accuracy         : HOLD signals where price stayed flat (±1.5%)
  - confidence_calibration: win rate per confidence band (40–50, 50–60, 60–70, 70–80, 80+)
  - stale_ratio           : signals that expired without a meaningful price move
  - calibration_score     : 0–100 measure of how well confidence predicts outcomes
"""
from __future__ import annotations
import statistics
from sqlalchemy.orm import Session

from app.signal_tracking.models import SignalOutcome
from app.core.logging import get_logger

logger = get_logger(__name__)

_FALSE_POSITIVE_THRESHOLD = 0.5   # % — directional signal moved less than this
_FLAT_THRESHOLD = 1.5             # % — HOLD considered accurate within this band


def compute_signal_utility(db: Session) -> dict:
    outcomes = db.query(SignalOutcome).all()
    if not outcomes:
        return _empty()

    directional = [o for o in outcomes if o.direction in ("BUY", "SELL")]
    hold_signals = [o for o in outcomes if o.direction == "HOLD"]

    fp_rate   = _false_positive_rate(directional)
    hold_acc  = _hold_accuracy(hold_signals)
    cal       = _confidence_calibration(directional)
    cal_score = _calibration_score(cal)
    stale     = _stale_ratio(outcomes)

    return {
        "false_positive_rate":    fp_rate,
        "hold_accuracy":          hold_acc,
        "confidence_calibration": cal,
        "calibration_score":      cal_score,
        "stale_ratio":            stale,
        "total_signals":          len(outcomes),
        "directional_signals":    len(directional),
        "hold_signals":           len(hold_signals),
    }


# ── Sub-metrics ───────────────────────────────────────────────────────────────

def _false_positive_rate(directional: list[SignalOutcome]) -> float:
    completed = [o for o in directional if o.status == "completed" and o.price_change_pct is not None]
    fp = [o for o in completed if abs(o.price_change_pct) < _FALSE_POSITIVE_THRESHOLD]
    return _pct(len(fp), len(completed))


def _hold_accuracy(hold_signals: list[SignalOutcome]) -> float:
    resolved = [o for o in hold_signals if o.price_change_pct is not None]
    accurate = [o for o in resolved if abs(o.price_change_pct) <= _FLAT_THRESHOLD]
    return _pct(len(accurate), len(resolved))


def _confidence_calibration(directional: list[SignalOutcome]) -> list[dict]:
    bands = [
        ("40–50", 40, 50,  45),
        ("50–60", 50, 60,  55),
        ("60–70", 60, 70,  65),
        ("70–80", 70, 80,  75),
        ("80+",   80, 101, 90),
    ]
    result = []
    for label, lo, hi, midpoint in bands:
        bucket = [
            o for o in directional
            if o.confidence is not None
            and lo <= o.confidence < hi
            and o.outcome in ("win", "loss")
        ]
        wins = sum(1 for o in bucket if o.outcome == "win")
        actual_win_rate = _pct(wins, len(bucket))
        result.append({
            "bucket":            label,
            "expected_win_rate": midpoint,
            "actual_win_rate":   actual_win_rate,
            "total":             len(bucket),
            "wins":              wins,
        })
    return result


def _calibration_score(cal: list[dict]) -> float:
    """Measure how closely win rates track confidence bands. 100 = perfect calibration."""
    populated = [b for b in cal if b["total"] > 0]
    if not populated:
        return 50.0  # neutral baseline — insufficient data
    deviations = [abs(b["actual_win_rate"] - b["expected_win_rate"]) for b in populated]
    mae = statistics.mean(deviations)
    return round(max(0.0, 100.0 - mae), 1)


def _stale_ratio(outcomes: list[SignalOutcome]) -> float:
    expired = [o for o in outcomes if o.status == "expired"]
    return _pct(len(expired), len(outcomes))


def _empty() -> dict:
    return {
        "false_positive_rate":    0.0,
        "hold_accuracy":          0.0,
        "confidence_calibration": [],
        "calibration_score":      50.0,
        "stale_ratio":            0.0,
        "total_signals":          0,
        "directional_signals":    0,
        "hold_signals":           0,
    }


def _pct(num: int, den: int) -> float:
    return round(num / den * 100, 1) if den > 0 else 0.0
