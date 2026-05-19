"""
Asset-level performance weights.

Each asset's historical win rate and false-positive rate determines a
confidence adjustment applied to all future signals for that asset.

High false-positive rate (signals that moved <0.5% at resolution) indicates
the system generates noise for that asset — penalise accordingly.

Tiers:
  win_rate >= 70%  AND fp_rate < 20%  →  +5   (reliable asset)
  win_rate 55–70%                     →  +2   (above average)
  win_rate 40–55%                     →   0   (neutral)
  win_rate 30–40%  OR fp_rate > 30%   →  -5   (underperforming)
  win_rate  < 30%                     → -10   (poor track record)

Minimum 5 directional outcomes per asset before applying adjustment.
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.signal_tracking.models import SignalOutcome

_MIN_SAMPLE              = 5
_FALSE_POSITIVE_THRESHOLD = 0.5   # % move below this counts as false positive
_FP_PENALTY_THRESHOLD    = 30.0   # fp rate above this adds extra penalty


def get_asset_adjustments(db: Session) -> dict[str, dict]:
    """
    Returns {asset: {adjustment, win_rate, fp_rate, sample_size, direction, reason}}.
    """
    directional = (
        db.query(SignalOutcome)
        .filter(SignalOutcome.direction.in_(["BUY", "SELL"]))
        .all()
    )

    assets: dict[str, dict] = {}
    for o in directional:
        a = o.asset
        if a not in assets:
            assets[a] = {"wins": 0, "losses": 0, "fp": 0, "total": 0}
        assets[a]["total"] += 1
        if o.outcome == "win":
            assets[a]["wins"] += 1
        elif o.outcome == "loss":
            assets[a]["losses"] += 1
        if (
            o.status == "completed"
            and o.price_change_pct is not None
            and abs(o.price_change_pct) < _FALSE_POSITIVE_THRESHOLD
        ):
            assets[a]["fp"] += 1

    result: dict[str, dict] = {}
    for asset, data in assets.items():
        total     = data["total"]
        completed = data["wins"] + data["losses"]

        if total < _MIN_SAMPLE:
            result[asset] = {
                "adjustment":  0.0,
                "win_rate":    None,
                "fp_rate":     None,
                "sample_size": total,
                "direction":   "neutral",
                "reason":      f"Insufficient data ({total} outcomes, need {_MIN_SAMPLE})",
            }
            continue

        win_rate = round(data["wins"] / completed * 100, 1) if completed else 0.0
        fp_rate  = round(data["fp"] / total * 100, 1) if total else 0.0
        adj, direction = _tier(win_rate, fp_rate)

        result[asset] = {
            "adjustment":  adj,
            "win_rate":    win_rate,
            "fp_rate":     fp_rate,
            "sample_size": total,
            "direction":   direction,
            "reason":      _reason(asset, win_rate, fp_rate, adj),
        }

    return result


def get_asset_adjustment(db: Session, asset: str) -> float:
    """Fast single-asset lookup."""
    return get_asset_adjustments(db).get(asset, {}).get("adjustment", 0.0)


def _tier(win_rate: float, fp_rate: float) -> tuple[float, str]:
    if win_rate >= 70.0 and fp_rate < 20.0:
        return 5.0, "boost"
    if win_rate >= 55.0:
        return 2.0, "boost"
    if win_rate >= 40.0:
        return 0.0, "neutral"
    if win_rate >= 30.0 or fp_rate > _FP_PENALTY_THRESHOLD:
        return -5.0, "reduce"
    return -10.0, "reduce"


def _reason(asset: str, win_rate: float, fp_rate: float, adj: float) -> str:
    return (
        f"{asset}: win rate {win_rate}%, false-positive rate {fp_rate}% "
        f"— applying {adj:+.0f} confidence adjustment"
    )
