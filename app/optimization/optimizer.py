"""
Signal optimizer — orchestrates all adjustments at generation time.

Single entry point: apply_optimizations(db, signal_data, regime)

Returns an OptimizationResult with:
  - total confidence_delta (capped so final confidence stays in [20, 95])
  - quality_score (0–100 pre-outcome composite)
  - per-source adjustment breakdown (calibration, regime, asset)
  - human-readable reason strings appended to signal.reasoning

Design constraints:
  - Every adjustment is named and traceable
  - Adjustments are conservative — each source is individually capped
  - If no historical data exists, all adjustments default to 0 (no-op)
  - The optimizer never changes signal direction — only confidence magnitude
"""
from __future__ import annotations
from dataclasses import dataclass, field
from sqlalchemy.orm import Session

from app.optimization.calibrator   import get_calibration_adjustments, confidence_to_band
from app.optimization.regime_weights import get_regime_adjustment
from app.optimization.asset_weights  import get_asset_adjustment
from app.optimization.signal_quality import compute_quality_score

_CONF_FLOOR = 20.0
_CONF_CAP   = 95.0


@dataclass
class OptimizationResult:
    confidence_delta:   float
    final_confidence:   float
    quality_score:      float
    adjustments: dict = field(default_factory=dict)
    reasons:     list = field(default_factory=list)


def apply_optimizations(
    db: Session,
    signal_data: dict,
    regime: dict | None,
) -> OptimizationResult:
    """
    Compute and apply all optimization adjustments to a signal.

    Args:
      db           — database session
      signal_data  — mutable signal dict (confidence, signal, asset, reasoning)
      regime       — current regime from regime.service.get_current_regime()

    Modifies signal_data["confidence"] in-place and appends to signal_data["reasoning"].
    Returns OptimizationResult with the full adjustment breakdown.
    """
    raw_confidence = float(signal_data.get("confidence", 50.0))
    asset          = signal_data.get("asset", "")
    direction      = signal_data.get("signal", "HOLD")

    # Skip HOLD signals — no confidence adjustment needed
    if direction == "HOLD":
        return OptimizationResult(
            confidence_delta=0.0,
            final_confidence=raw_confidence,
            quality_score=50.0,
            adjustments={},
            reasons=[],
        )

    # ── 1. Calibration adjustment ─────────────────────────────────────────────
    calibration_adj  = _calibration_adjustment(db, raw_confidence)

    # ── 2. Regime adjustment ──────────────────────────────────────────────────
    regime_name = None
    if regime:
        regime_name = regime.get("primary_regime")
    regime_adj = get_regime_adjustment(db, regime_name)

    # ── 3. Asset adjustment ───────────────────────────────────────────────────
    asset_adj = get_asset_adjustment(db, asset)

    # ── 4. Total delta and apply ──────────────────────────────────────────────
    total_delta    = calibration_adj["factor"] + regime_adj + asset_adj
    new_confidence = _clamp(raw_confidence + total_delta)
    actual_delta   = round(new_confidence - raw_confidence, 1)

    # ── 5. Quality score ──────────────────────────────────────────────────────
    quality = compute_quality_score(
        signal_data,
        regime,
        asset_adj,
        calibration_adj["factor"],
    )

    # ── 6. Build reasons (only non-zero adjustments) ──────────────────────────
    reasons: list[str] = []
    if calibration_adj["factor"] != 0.0:
        reasons.append(f"Calibration ({calibration_adj['band']}): {calibration_adj['factor']:+.1f} — {calibration_adj['reason']}")
    if regime_adj != 0.0:
        reasons.append(f"Regime '{regime_name}': {regime_adj:+.0f} confidence adjustment from historical win rate")
    if asset_adj != 0.0:
        reasons.append(f"Asset track record ({asset}): {asset_adj:+.0f} confidence adjustment")
    if actual_delta != 0.0:
        reasons.append(f"Optimizer net adjustment: {actual_delta:+.1f} (raw {raw_confidence:.0f} → {new_confidence:.0f})")

    signal_data["reasoning"].extend(reasons)

    return OptimizationResult(
        confidence_delta=actual_delta,
        final_confidence=new_confidence,
        quality_score=quality,
        adjustments={
            "calibration": {**calibration_adj},
            "regime":      {"factor": regime_adj, "regime": regime_name},
            "asset":       {"factor": asset_adj,  "asset": asset},
        },
        reasons=reasons,
    )


def get_optimization_state(db: Session) -> dict:
    """
    Return the current optimization configuration — all computed adjustment tables.
    Used by the analytics endpoint to show what the optimizer is currently doing.
    """
    from app.optimization.calibrator    import get_calibration_adjustments
    from app.optimization.regime_weights import get_regime_adjustments
    from app.optimization.asset_weights  import get_asset_adjustments
    from app.signal_tracking.models      import SignalOutcome
    from datetime import datetime

    calibration    = get_calibration_adjustments(db)
    regime_weights = get_regime_adjustments(db)
    asset_weights  = get_asset_adjustments(db)

    total_outcomes = db.query(SignalOutcome).count()
    resolved       = db.query(SignalOutcome).filter(SignalOutcome.outcome.in_(["win", "loss"])).count()

    active_calibrations = sum(1 for v in calibration.values()    if v["factor"] != 0.0)
    active_regimes      = sum(1 for v in regime_weights.values() if v["adjustment"] != 0.0)
    active_assets       = sum(1 for v in asset_weights.values()  if v["adjustment"] != 0.0)

    return {
        "calibration_adjustments": calibration,
        "regime_weights":          regime_weights,
        "asset_weights":           asset_weights,
        "data_coverage": {
            "total_outcomes":         total_outcomes,
            "resolved_outcomes":      resolved,
            "active_calibrations":    active_calibrations,
            "active_regime_weights":  active_regimes,
            "active_asset_weights":   active_assets,
        },
        "computed_at": datetime.utcnow().isoformat(),
    }


# ── Internal helpers ──────────────────────────────────────────────────────────

def _calibration_adjustment(db: Session, confidence: float) -> dict:
    """Fetch the calibration factor for the given confidence level."""
    adjustments = get_calibration_adjustments(db)
    band        = confidence_to_band(confidence)
    entry       = adjustments.get(band, {})
    return {
        "factor": entry.get("factor", 0.0),
        "band":   band,
        "reason": entry.get("reason", "no calibration data"),
    }


def _clamp(confidence: float) -> float:
    return round(max(_CONF_FLOOR, min(_CONF_CAP, confidence)), 1)
