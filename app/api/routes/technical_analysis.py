from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.analysis.indicators import compute_flat, compute_all
from app.analysis.patterns import detect_breakout, detect_trend
from app.market_data.service import get_price_history
from app.risk.scorer import compute_atr, detect_market_regime, score_risk
from app.api.schemas import ApiResponse

router = APIRouter(tags=["Technical Analysis"])


@router.get("/technical-analysis/{asset}", response_model=ApiResponse)
def get_technical_analysis(asset: str, db: Session = Depends(get_db)):
    """Full technical analysis for an asset in the flat spec output format.

    Returns: trend, RSI, EMA-20/50/200, MACD signal, volatility, breakout.
    """
    prices = get_price_history(db, asset.upper(), limit=250)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price data for {asset.upper()}")

    flat      = compute_flat(prices)
    breakout  = detect_breakout(prices)
    regime    = detect_market_regime(prices)

    return ApiResponse(success=True, data={
        "asset":     asset.upper(),
        **flat,
        "breakout":  breakout,
        "regime":    regime.get("regime", "unknown"),
    })


@router.get("/indicators/{asset}", response_model=ApiResponse)
def get_indicators(asset: str, db: Session = Depends(get_db)):
    """Raw indicator values for an asset — all components with full detail."""
    prices = get_price_history(db, asset.upper(), limit=250)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price data for {asset.upper()}")

    indicators = compute_all(prices)
    breakout   = detect_breakout(prices)
    trend      = detect_trend(prices)
    atr        = compute_atr(prices)

    return ApiResponse(success=True, data={
        "asset":      asset.upper(),
        "indicators": indicators,
        "breakout":   breakout,
        "trend":      trend,
        "atr":        atr,
    })


@router.get("/risk-analysis/{asset}", response_model=ApiResponse)
def get_risk_analysis(asset: str, db: Session = Depends(get_db)):
    """Risk assessment for an asset: ATR, volatility, market regime, risk score."""
    prices = get_price_history(db, asset.upper(), limit=50)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price data for {asset.upper()}")

    from app.analysis.indicators import _compute_volatility, _to_dataframe
    import pandas as pd
    df  = _to_dataframe(prices)
    vol = _compute_volatility(df)
    atr = compute_atr(prices)
    regime = detect_market_regime(prices)
    risk   = score_risk(
        volatility_level=vol.get("level", "medium"),
        atr=atr,
        confidence=50.0,
    )

    return ApiResponse(success=True, data={
        "asset":          asset.upper(),
        "risk_score":     risk["risk_score"],
        "risk_level":     risk["risk_level"],
        "volatility":     vol,
        "atr":            atr,
        "market_regime":  regime.get("regime", "unknown"),
        "confidence_adjustment": risk["confidence_adjustment"],
    })
