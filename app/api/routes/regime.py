from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.regime import service as regime_service
from app.api.schemas import ApiResponse

router = APIRouter(prefix="/regime", tags=["Regime"])


@router.get("", response_model=ApiResponse)
def get_global_regime(db: Session = Depends(get_db)):
    """Return the current global market regime across all tracked assets.

    Primary regime is one of: risk_on, risk_off, trending, ranging,
    high_volatility, low_volatility.
    """
    result = regime_service.get_current_regime(db)
    return ApiResponse(success=True, data=result)


@router.get("/{symbol}", response_model=ApiResponse)
def get_asset_regime(symbol: str, db: Session = Depends(get_db)):
    """Return the market regime for a specific asset.

    Volatility and trend signals are computed from that asset's own price bars.
    Event flow and cross-asset signals remain global.
    """
    result = regime_service.get_asset_regime(db, symbol)
    return ApiResponse(success=True, data=result)
