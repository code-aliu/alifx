"""
Confidence calibration adjuster.

Reads historical signal outcomes and computes how much to adjust confidence
for each band, based on the gap between expected and actual win rates.

If 70–80% confidence signals only win 52% of the time, they are overconfident
by ~23 points. This module returns a negative adjustment factor for that band.

Rules:
  - Minimum 3 outcomes per band before applying any adjustment
  - Adjustment = -(calibration_error × sensitivity), capped at ±15
  - Sensitivity = 0.5 (conservative — corrects half the error per update cycle)
  - Returns neutral (0) for bands with insufficient data

Every factor is traceable to: observed win rate, expected win rate, sample size.
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.signal_tracking.models import SignalOutcome

_BANDS: list[tuple[str, float, float, float]] = [
    ("40–50", 40.0, 50.0, 45.0),
    ("50–60", 50.0, 60.0, 55.0),
    ("60–70", 60.0, 70.0, 65.0),
    ("70–80", 70.0, 80.0, 75.0),
    ("80+",   80.0, 101.0, 90.0),
]
_MIN_SAMPLE  = 3
_MAX_ADJUST  = 15.0
_SENSITIVITY = 0.5


def get_calibration_adjustments(db: Session) -> dict[str, dict]:
    """
    Returns a dict keyed by band label with calibration factor and metadata.
    Factor is added to raw confidence when a signal falls in that band.
    """
    directional = (
        db.query(SignalOutcome)
        .filter(
            SignalOutcome.direction.in_(["BUY", "SELL"]),
            SignalOutcome.outcome.in_(["win", "loss"]),
            SignalOutcome.confidence.is_not(None),
        )
        .all()
    )

    result: dict[str, dict] = {}
    for label, lo, hi, midpoint in _BANDS:
        bucket = [o for o in directional if lo <= o.confidence < hi]
        wins   = sum(1 for o in bucket if o.outcome == "win")
        total  = len(bucket)

        if total < _MIN_SAMPLE:
            result[label] = {
                "factor":             0.0,
                "actual_win_rate":    None,
                "expected_win_rate":  midpoint,
                "sample_size":        total,
                "direction":          "neutral",
                "reason":             f"Insufficient data ({total} outcomes, need {_MIN_SAMPLE})",
            }
            continue

        actual_win_rate = round(wins / total * 100, 1)
        error           = actual_win_rate - midpoint
        raw_factor      = -(error * _SENSITIVITY)
        factor          = round(max(-_MAX_ADJUST, min(_MAX_ADJUST, raw_factor)), 1)

        result[label] = {
            "factor":            factor,
            "actual_win_rate":   actual_win_rate,
            "expected_win_rate": midpoint,
            "sample_size":       total,
            "direction":         "reduce" if factor < 0 else "boost" if factor > 0 else "neutral",
            "reason": (
                f"Actual win rate {actual_win_rate}% vs expected {midpoint}% "
                f"(error {error:+.1f}pp) — applying {factor:+.1f} adjustment"
            ),
        }

    return result


def confidence_to_band(confidence: float) -> str:
    """Map a confidence value to its calibration band label."""
    for label, lo, hi, _ in _BANDS:
        if lo <= confidence < hi:
            return label
    return "80+"
