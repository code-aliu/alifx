from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.analysis import service as analysis_service
from app.impact import service as impact_service
from app.risk.scorer import compute_atr, detect_market_regime
from app.market_data.service import get_price_history
from app.api.schemas import ApiResponse

router = APIRouter(prefix="/analysis", tags=["Analysis"])


@router.get("", response_model=ApiResponse)
def get_all_analysis(db: Session = Depends(get_db)):
    """Return technical analysis for all tracked assets."""
    analysis = analysis_service.analyse_all(db)
    return ApiResponse(success=True, data={"analysis": analysis, "count": len(analysis)})


@router.get("/impact", response_model=ApiResponse)
def get_market_impact(db: Session = Depends(get_db)):
    """Return current event-driven impact scores for all tracked assets."""
    impact = impact_service.get_asset_impact(db, hours=24)
    return ApiResponse(success=True, data={"impact": impact, "count": len(impact)})


@router.get("/risk/{symbol}", response_model=ApiResponse)
def get_asset_risk(symbol: str, db: Session = Depends(get_db)):
    """Return ATR, market regime, and risk score for a single asset."""
    prices = get_price_history(db, symbol.upper(), limit=50)
    if not prices:
        raise HTTPException(status_code=404, detail=f"No price data found for {symbol.upper()}")
    atr    = compute_atr(prices)
    regime = detect_market_regime(prices)
    return ApiResponse(success=True, data={
        "symbol": symbol.upper(),
        "atr":    atr,
        "regime": regime,
    })


@router.get("/correlations", response_model=ApiResponse)
def get_asset_correlations(db: Session = Depends(get_db)):
    """What assets are correlated?

    Returns Pearson correlation of price returns across all tracked assets,
    the full correlation matrix, and top pairs ranked by absolute correlation.
    """
    result = analysis_service.compute_correlations(db)
    return ApiResponse(success=True, data=result)


@router.get("/{symbol}", response_model=ApiResponse)
def get_asset_analysis(symbol: str, db: Session = Depends(get_db)):
    """Return full technical analysis for a single asset."""
    result = analysis_service.analyse_asset(db, symbol.upper())
    if "error" in result and result["error"] == "no_price_data":
        raise HTTPException(status_code=404, detail=f"No price data found for {symbol.upper()}")
    return ApiResponse(success=True, data=result)
