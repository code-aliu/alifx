"""
Spec-compliant endpoint aliases for paper trading.

Maps /paper-trades, /portfolio, /performance to the existing paper trading service.
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.paper_trading import service as pt_service
from app.api.schemas import ApiResponse

router = APIRouter(tags=["Paper Trading"])


@router.get("/paper-trades", response_model=ApiResponse)
def get_paper_trades(
    status: str | None = Query(default=None, description="open | closed"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Return paper trade history."""
    trades = pt_service.get_trade_history(db, limit=limit, status=status)
    return ApiResponse(success=True, data={"trades": trades, "count": len(trades)})


@router.get("/portfolio", response_model=ApiResponse)
def get_portfolio(db: Session = Depends(get_db)):
    """Return current portfolio: balance, equity, open positions, unrealized PnL."""
    summary = pt_service.get_portfolio_summary(db)
    return ApiResponse(success=True, data=summary)


@router.get("/performance", response_model=ApiResponse)
def get_performance(db: Session = Depends(get_db)):
    """Return trading performance: win rate, profit factor, avg win/loss, 7-day PnL."""
    stats = pt_service.get_stats(db)
    return ApiResponse(success=True, data=stats)
