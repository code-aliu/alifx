"""
Signal timing quality evaluation.

Measures how early signals arrived relative to the price move:
  - early_signal_rate : winning signals resolved within first 25% of expected window
  - stale_rate        : signals that expired without triggering TP or SL
  - avg_timing_score  : 0–100 score weighting early resolution of winning signals

Timing score logic:
  A win resolved in the first quarter of its window scores 100.
  A win resolved late (near expiry) scores ~60.
  Losses and expired signals score lower to reflect timing failure.
"""
from __future__ import annotations
import statistics
from sqlalchemy.orm import Session

from app.signal_tracking.models import SignalOutcome
from app.core.logging import get_logger

logger = get_logger(__name__)

_EXPECTED_HOURS: dict[str, float] = {
    "scalp":   1.0,
    "intraday": 4.0,
    "swing":   24.0,
    "macro":   72.0,
}


def compute_timing_quality(db: Session) -> dict:
    outcomes = (
        db.query(SignalOutcome)
        .filter(SignalOutcome.direction.in_(["BUY", "SELL"]))
        .all()
    )
    if not outcomes:
        return _empty()

    timing_scores: list[float] = []
    lead_hours: list[float] = []
    early_wins = 0
    stale_count = 0
    wins_total = 0

    for o in outcomes:
        if o.status == "expired":
            stale_count += 1
            timing_scores.append(25.0)
            continue

        if o.created_at is None or o.resolved_at is None:
            continue

        hours = (o.resolved_at - o.created_at).total_seconds() / 3600
        expected = _EXPECTED_HOURS.get(o.time_horizon or "swing", 24.0)
        ratio = hours / max(expected, 0.01)

        if o.outcome == "win":
            wins_total += 1
            # Earlier win = higher score: ratio 0 → 100, ratio 1 → 60
            score = max(60.0, 100.0 - ratio * 40.0)
            if ratio <= 0.25:
                early_wins += 1
        elif o.outcome == "loss":
            score = max(0.0, 50.0 - ratio * 30.0)
        else:
            score = 30.0

        timing_scores.append(score)
        lead_hours.append(hours)

    avg_score = round(statistics.mean(timing_scores), 1) if timing_scores else None
    avg_hours = round(statistics.mean(lead_hours), 1)    if lead_hours   else None

    return {
        "total_directional":      len(outcomes),
        "stale_count":            stale_count,
        "stale_rate":             _pct(stale_count, len(outcomes)),
        "early_signal_count":     early_wins,
        "early_signal_rate":      _pct(early_wins, wins_total),
        "avg_hours_to_resolution": avg_hours,
        "avg_timing_score":       avg_score,
    }


def _empty() -> dict:
    return {
        "total_directional":       0,
        "stale_count":             0,
        "stale_rate":              0.0,
        "early_signal_count":      0,
        "early_signal_rate":       0.0,
        "avg_hours_to_resolution": None,
        "avg_timing_score":        None,
    }


def _pct(num: int, den: int) -> float:
    return round(num / den * 100, 1) if den > 0 else 0.0
