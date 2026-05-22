"""
Risk-aware position sizing and portfolio exposure intelligence endpoints.

All outputs are educational — the platform never executes trades.

Endpoints:
  POST /position-sizing         — calculate recommended position size
  GET  /risk-profile            — user's risk profile with guidance
  GET  /portfolio-risk          — full portfolio exposure analysis
  GET  /volatility-analysis     — per-asset or portfolio-wide volatility
  GET  /risk-adjustments        — regime-aware risk adjustment summary
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db, get_optional_user, get_current_user
from app.auth.models import User
from app.api.schemas import ApiResponse
from app.risk.position_sizing   import calculate_position_size
from app.risk.exposure_analyzer  import analyze_portfolio_risk
from app.risk.volatility_analyzer import analyze_asset_volatility, analyze_portfolio_volatility
from app.market_data.service     import get_price_history
from app.risk.scorer             import compute_atr
from app.core.logging            import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="", tags=["Risk Intelligence"])

# ── Schemas ───────────────────────────────────────────────────────────────────

class PositionSizingRequest(BaseModel):
    account_size:  float = Field(..., gt=0, description="Total capital in USD")
    risk_pct:      float = Field(..., gt=0, le=10, description="Risk per trade as % of account")
    entry_price:   float = Field(..., gt=0)
    stop_loss:     float = Field(..., gt=0)
    asset_class:   str   = Field("crypto", pattern="^(crypto|forex|stocks)$")
    take_profit:   float | None = Field(None, gt=0)
    symbol:        str   | None = Field(None, description="Symbol for live ATR lookup")
    atr_pct:       float | None = Field(None, ge=0, description="Override ATR% manually")
    regime:        str   | None = Field(None, description="Market regime override")
    risk_profile:  str         = Field("balanced", pattern="^(conservative|balanced|aggressive)$")


# ── Position sizing ───────────────────────────────────────────────────────────

@router.post("/position-sizing", response_model=ApiResponse)
def position_sizing(
    body: PositionSizingRequest,
    db:   Session = Depends(get_db),
    user: User | None = Depends(get_optional_user),
):
    """
    Calculate recommended position size using fixed-fractional method.

    Automatically enriches with live ATR from database when `symbol` is provided
    and `atr_pct` is not manually set.

    Uses the user's saved risk profile when authenticated (overridden by explicit
    `risk_profile` in the request body — the request always wins).
    """
    # Resolve ATR from live data if symbol provided and atr_pct not overridden
    live_atr_pct: float | None = body.atr_pct
    live_atr_value: float | None = None

    if body.symbol and body.atr_pct is None:
        try:
            prices = get_price_history(db, symbol=body.symbol, limit=30)
            if len(prices) >= 15:
                atr = compute_atr(prices)
                if atr.get("available"):
                    live_atr_pct   = atr["pct"]
                    live_atr_value = atr["value"]
        except Exception as e:
            logger.warning(f"ATR lookup failed for {body.symbol}: {e}")

    # Resolve regime from current signal pipeline state if not provided
    regime = body.regime
    if not regime:
        try:
            from app.regime.service import get_current_regime
            r = get_current_regime(db)
            regime = r.get("regime") if r else None
        except Exception:
            pass

    # Use user's risk profile if authenticated, request body overrides
    risk_profile = body.risk_profile
    if user:
        try:
            prefs = user.preferences
            if prefs and prefs.risk_profile and body.risk_profile == "balanced":
                risk_profile = prefs.risk_profile
        except Exception:
            pass

    try:
        result = calculate_position_size(
            account_size  = body.account_size,
            risk_pct      = body.risk_pct,
            entry_price   = body.entry_price,
            stop_loss     = body.stop_loss,
            asset_class   = body.asset_class,
            take_profit   = body.take_profit,
            atr_pct       = live_atr_pct,
            regime        = regime,
            risk_profile  = risk_profile,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    return ApiResponse(success=True, data={
        "position_size_units":   result.position_size_units,
        "position_size_display": result.position_size_display,
        "dollar_risk":           result.dollar_risk,
        "position_notional":     result.position_notional,
        "portfolio_pct":         result.portfolio_pct,
        "risk_reward":           result.risk_reward,
        "effective_risk_pct":    result.effective_risk_pct,
        "unadjusted_size":       result.unadjusted_size,
        "volatility_multiplier": result.volatility_multiplier,
        "regime_multiplier":     result.regime_multiplier,
        "live_atr_value":        live_atr_value,
        "live_atr_pct":          live_atr_pct,
        "regime_used":           regime,
        "risk_profile_used":     risk_profile,
        "steps":                 result.steps,
        "adjustments":           result.adjustments,
        "education":             result.education,
        "warnings":              result.warnings,
        "disclaimer":            (
            "This calculation is for educational purposes only. "
            "AliFx does not execute trades or manage real funds."
        ),
    })


# ── Risk profile ──────────────────────────────────────────────────────────────

_PROFILE_GUIDANCE = {
    "conservative": {
        "max_risk_pct":  0.8,
        "description":   "Preserves capital — limits loss to 0.8% per trade",
        "suitable_for":  "Long-term investors, capital preservation focus, low drawdown tolerance",
        "typical_use":   "Max 1–2 open positions; focus on high-conviction setups only",
        "stop_guidance": "Wider stops acceptable — size is reduced to compensate",
    },
    "balanced": {
        "max_risk_pct":  2.0,
        "description":   "Standard risk management — limits loss to 2% per trade",
        "suitable_for":  "Active traders, moderate drawdown tolerance",
        "typical_use":   "3–5 open positions; diversified across asset classes",
        "stop_guidance": "Stop should be placed at structural levels, not arbitrary %",
    },
    "aggressive": {
        "max_risk_pct":  3.0,
        "description":   "Higher risk per trade — limits loss to 3% per trade",
        "suitable_for":  "Experienced traders, high conviction setups, short time horizons",
        "typical_use":   "2–3 focused positions; accept higher drawdown for higher return",
        "stop_guidance": "Tight stops with precise entries — wide stops amplify losses",
    },
}

_PROFILE_EDUCATION = {
    "why_fixed_fractional": (
        "Fixed fractional sizing keeps your dollar risk constant regardless of position price. "
        "A 2% account risk on a $10,000 account is always $200 — whether the asset costs $1 or $50,000."
    ),
    "compound_effect": (
        "A 10-trade losing streak at 2% risk per trade leaves ~82% of capital intact. "
        "At 5% per trade, the same streak leaves only ~60%. Profile caps protect against ruin."
    ),
    "stop_placement": (
        "Position size is calculated from the stop distance — a tighter stop means a larger position "
        "for the same dollar risk. Place stops at technically meaningful levels first, then calculate size."
    ),
}


@router.get("/risk-profile", response_model=ApiResponse)
def get_risk_profile(
    user: User | None = Depends(get_optional_user),
):
    """
    Returns the user's risk profile with contextual guidance and education.
    Falls back to 'balanced' for unauthenticated requests.
    """
    profile = "balanced"
    if user:
        try:
            prefs = user.preferences
            if prefs and prefs.risk_profile:
                profile = prefs.risk_profile
        except Exception:
            pass

    guidance = _PROFILE_GUIDANCE.get(profile, _PROFILE_GUIDANCE["balanced"])

    return ApiResponse(success=True, data={
        "profile":       profile,
        "guidance":      guidance,
        "all_profiles":  _PROFILE_GUIDANCE,
        "education":     _PROFILE_EDUCATION,
        "authenticated": user is not None,
        "note": (
            "Update your risk profile in Settings → Preferences to change "
            "the default cap applied by the position sizing calculator."
        ) if not user else None,
    })


# ── Portfolio risk ────────────────────────────────────────────────────────────

@router.get("/portfolio-risk", response_model=ApiResponse)
def portfolio_risk(db: Session = Depends(get_db)):
    """
    Full portfolio exposure analysis for open paper-trading positions.

    Returns volatility clustering, worst-case drawdown projection,
    regime sensitivity, and asset class concentration — all with
    plain-language explanations.
    """
    data = analyze_portfolio_risk(db)
    return ApiResponse(success=True, data=data)


# ── Volatility analysis ───────────────────────────────────────────────────────

@router.get("/volatility-analysis", response_model=ApiResponse)
def volatility_analysis(
    symbol: str | None = Query(None, description="Single asset symbol, e.g. BTC/USD"),
    db:     Session    = Depends(get_db),
):
    """
    Volatility analysis — single asset (if ?symbol=) or full portfolio.

    Returns ATR value, ATR%, volatility tier, historical percentile,
    position size multiplier suggestion, and educational context.
    """
    if symbol:
        data = analyze_asset_volatility(db, symbol.upper())
    else:
        data = analyze_portfolio_volatility(db)
    return ApiResponse(success=True, data=data)


# ── Risk adjustments ──────────────────────────────────────────────────────────

@router.get("/risk-adjustments", response_model=ApiResponse)
def risk_adjustments(db: Session = Depends(get_db)):
    """
    Regime-aware risk adjustment suggestions based on current market state.

    Combines active regime, portfolio volatility, and concentration to produce
    a concrete set of size/stop/exposure recommendations.
    """
    # Get current regime
    regime_name = None
    regime_detail: dict = {}
    try:
        from app.regime.service import get_current_regime
        r = get_current_regime(db)
        regime_name   = r.get("regime") if r else None
        regime_detail = r or {}
    except Exception:
        pass

    # Get portfolio volatility
    port_vol: dict = {}
    try:
        port_vol = analyze_portfolio_volatility(db)
    except Exception:
        pass

    # Build adjustments
    adjustments: list[dict] = []
    size_multiplier = 1.0

    # Regime-driven adjustment
    regime_lower = (regime_name or "").lower()
    if any(k in regime_lower for k in ("risk_off", "contraction", "recession")):
        size_multiplier *= 0.75
        adjustments.append({
            "source":      "regime",
            "multiplier":  0.75,
            "reason":      f"Current regime '{regime_name}' — reduce all position sizes by 25%",
            "action":      "Reduce open positions; prioritise cash or hedges",
        })
    elif "volatile" in regime_lower or "uncertain" in regime_lower:
        size_multiplier *= 0.85
        adjustments.append({
            "source":      "regime",
            "multiplier":  0.85,
            "reason":      f"Current regime '{regime_name}' — reduce position sizes by 15%",
            "action":      "Widen stop buffers; avoid adding new positions",
        })
    elif not regime_name:
        adjustments.append({
            "source":     "regime",
            "multiplier": 1.0,
            "reason":     "Regime undetermined — no adjustment applied",
            "action":     "Wait for regime clarity before adding risk",
        })

    # Volatility-driven adjustment
    summary = port_vol.get("summary") or {}
    overall_tier = summary.get("overall_tier")
    avg_atr = summary.get("avg_atr_pct", 0)

    if overall_tier == "extreme":
        size_multiplier *= 0.60
        adjustments.append({
            "source":     "volatility",
            "multiplier": 0.60,
            "reason":     f"Market-wide extreme volatility (avg ATR {avg_atr:.2f}%) — reduce sizes by 40%",
            "action":     "Only hold highest-conviction positions; significantly reduce size",
        })
    elif overall_tier == "elevated":
        size_multiplier *= 0.80
        adjustments.append({
            "source":     "volatility",
            "multiplier": 0.80,
            "reason":     f"Elevated market volatility (avg ATR {avg_atr:.2f}%) — reduce sizes by 20%",
            "action":     "Widen stops by ~20%; reduce individual position sizes",
        })
    elif overall_tier in (None, "normal", "low") and summary:
        adjustments.append({
            "source":     "volatility",
            "multiplier": 1.0,
            "reason":     f"Market volatility normal (avg ATR {avg_atr:.2f}%)",
            "action":     "Standard sizing applies",
        })

    # High-vol cluster warning
    high_vol_assets = summary.get("high_vol_assets", [])
    if high_vol_assets:
        adjustments.append({
            "source":     "concentration",
            "multiplier": None,
            "reason":     f"High-volatility assets detected: {', '.join(high_vol_assets)}",
            "action":     "Review positions in these assets; ensure stop-losses are set",
        })

    return ApiResponse(success=True, data={
        "current_regime":        regime_name,
        "regime_detail":         regime_detail,
        "portfolio_vol_summary": summary,
        "combined_multiplier":   round(size_multiplier, 3),
        "adjustments":           adjustments,
        "interpretation": (
            f"Apply a combined {round(size_multiplier * 100)}% size multiplier to new positions "
            "based on current regime and volatility conditions."
            if adjustments else
            "No active adjustments — market conditions are within normal parameters."
        ),
        "disclaimer": "Risk adjustments are educational guidance, not financial advice.",
    })
