"""
Strategy optimization analytics endpoints.

All endpoints are read-only — they show what the optimizer is doing and why.
The optimizer applies adjustments automatically in the signal pipeline;
these routes provide transparency and monitoring.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.schemas import ApiResponse
from app.optimization.optimizer      import get_optimization_state
from app.optimization.calibrator     import get_calibration_adjustments
from app.optimization.regime_weights  import get_regime_adjustments
from app.optimization.asset_weights   import get_asset_adjustments
from app.signal_tracking.models       import SignalOutcome

router = APIRouter(prefix="/optimization", tags=["Strategy Optimization"])


@router.get("", response_model=ApiResponse)
def optimization_overview(db: Session = Depends(get_db)):
    """
    Full optimization state — calibration adjustments, regime weights, and asset weights.
    Shows exactly what the optimizer is applying to signal confidence and why.
    """
    state = get_optimization_state(db)
    return ApiResponse(success=True, data=state)


@router.get("/calibration", response_model=ApiResponse)
def calibration_analysis(db: Session = Depends(get_db)):
    """
    Confidence calibration analysis.

    For each confidence band (40–50, 50–60, etc.), shows:
      - How many signals were generated in that band
      - What the actual win rate was
      - What the expected win rate should be
      - What adjustment factor is applied to future signals in that band
    """
    adjustments = get_calibration_adjustments(db)

    # Summary: overall calibration health
    populated = [v for v in adjustments.values() if v["actual_win_rate"] is not None]
    if populated:
        import statistics
        mae = statistics.mean(
            abs(v["actual_win_rate"] - v["expected_win_rate"]) for v in populated
        )
        calibration_score = round(max(0.0, 100.0 - mae), 1)
    else:
        mae              = None
        calibration_score = 50.0

    return ApiResponse(success=True, data={
        "bands":             adjustments,
        "summary": {
            "calibration_score":      calibration_score,
            "mean_absolute_error_pp": round(mae, 1) if mae else None,
            "bands_with_data":        len(populated),
            "total_bands":            len(adjustments),
            "status": (
                "well_calibrated" if calibration_score >= 75
                else "needs_improvement" if calibration_score >= 50
                else "poorly_calibrated"
            ),
        },
    })


@router.get("/regime-weights", response_model=ApiResponse)
def regime_weight_analysis(db: Session = Depends(get_db)):
    """
    Regime-specific performance and confidence adjustments.

    Shows which market regimes produce reliable signals vs. which ones
    are historically noisy, and what adjustment is applied in each.
    """
    weights = get_regime_adjustments(db)

    boosted  = {k: v for k, v in weights.items() if v["adjustment"] > 0}
    penalised = {k: v for k, v in weights.items() if v["adjustment"] < 0}
    neutral  = {k: v for k, v in weights.items() if v["adjustment"] == 0}

    return ApiResponse(success=True, data={
        "regime_weights": weights,
        "summary": {
            "total_regimes":    len(weights),
            "boosted_regimes":  list(boosted.keys()),
            "penalised_regimes": list(penalised.keys()),
            "neutral_regimes":  list(neutral.keys()),
        },
    })


@router.get("/asset-scores", response_model=ApiResponse)
def asset_quality_scores(db: Session = Depends(get_db)):
    """
    Per-asset performance-based quality scores and confidence adjustments.

    Assets with strong historical win rates and low false-positive rates
    receive confidence boosts. Poor performers receive penalties.
    """
    weights = get_asset_adjustments(db)

    ranked = sorted(
        [
            {"asset": asset, **data}
            for asset, data in weights.items()
            if data.get("win_rate") is not None
        ],
        key=lambda x: x.get("win_rate", 0),
        reverse=True,
    )

    return ApiResponse(success=True, data={
        "asset_weights": weights,
        "ranked":        ranked,
        "summary": {
            "total_assets_tracked":   len(weights),
            "assets_with_boost":      sum(1 for v in weights.values() if v["adjustment"] > 0),
            "assets_with_penalty":    sum(1 for v in weights.values() if v["adjustment"] < 0),
            "assets_insufficient_data": sum(1 for v in weights.values() if v["win_rate"] is None),
        },
    })


@router.get("/signal-quality", response_model=ApiResponse)
def signal_quality_distribution(
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """
    Distribution of pre-outcome quality scores across recent signals.

    Shows whether high-quality signals (pre-resolution) actually correlate
    with better outcomes — a meta-accuracy check on the optimizer itself.
    """
    recent = (
        db.query(SignalOutcome)
        .filter(SignalOutcome.performance_score.is_not(None))
        .order_by(SignalOutcome.created_at.desc())
        .limit(limit)
        .all()
    )

    resolved = [o for o in recent if o.outcome in ("win", "loss")]
    if resolved:
        high_quality = [o for o in resolved if (o.performance_score or 0) >= 65]
        hq_wins      = sum(1 for o in high_quality if o.outcome == "win")
        lq_signals   = [o for o in resolved if (o.performance_score or 0) < 65]
        lq_wins      = sum(1 for o in lq_signals if o.outcome == "win")

        hq_win_rate  = round(hq_wins / len(high_quality) * 100, 1) if high_quality else None
        lq_win_rate  = round(lq_wins / len(lq_signals)  * 100, 1) if lq_signals   else None
        quality_lift = round(hq_win_rate - lq_win_rate, 1) if hq_win_rate and lq_win_rate else None
    else:
        hq_win_rate = lq_win_rate = quality_lift = None

    distribution = []
    for o in recent:
        distribution.append({
            "signal_id":       o.signal_id,
            "asset":           o.asset,
            "direction":       o.direction,
            "confidence":      o.confidence,
            "quality_score":   o.performance_score,
            "outcome":         o.outcome,
            "market_regime":   o.market_regime,
            "created_at":      o.created_at.isoformat(),
        })

    return ApiResponse(success=True, data={
        "distribution": distribution,
        "meta_accuracy": {
            "high_quality_win_rate": hq_win_rate,
            "low_quality_win_rate":  lq_win_rate,
            "quality_lift_pp":       quality_lift,
            "high_quality_signals":  len(high_quality) if resolved else 0,
            "low_quality_signals":   len(lq_signals)   if resolved else 0,
        },
    })
