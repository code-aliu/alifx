from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.schemas import ApiResponse
from app.performance import service as perf_service
from app.signal_tracking.service import get_recent_outcomes

router = APIRouter(prefix="/signal-performance", tags=["Signal Performance"])


@router.get("", response_model=ApiResponse)
def get_performance(db: Session = Depends(get_db)):
    """Full signal performance analytics.

    Returns win rate, average return, max drawdown, simplified Sharpe ratio,
    confidence accuracy correlation, and breakdowns by asset, regime, and direction.
    """
    result = perf_service.get_signal_performance(db)
    return ApiResponse(success=True, data=result)


@router.get("/timeseries", response_model=ApiResponse)
def get_timeseries(
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Cumulative PnL curve for charting — one entry per closed trade."""
    result = perf_service.get_performance_timeseries(db, limit=limit)
    return ApiResponse(success=True, data=result)


@router.get("/outcomes", response_model=ApiResponse)
def get_outcomes(
    status: str | None = Query(default=None, description="active | completed | expired | invalidated"),
    asset:  str | None = Query(default=None),
    limit:  int        = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List signal outcome records with optional filtering."""
    outcomes = get_recent_outcomes(db, limit=limit, status=status, asset=asset)
    return ApiResponse(success=True, data={"outcomes": outcomes, "count": len(outcomes)})
