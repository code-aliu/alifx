from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.paper_trading import service as pt_service
from app.paper_trading.executor import open_trade, DEFAULT_TRADE_NOTIONAL
from app.market_data.service import get_latest_prices
from app.api.schemas import ApiResponse

router = APIRouter(prefix="/paper-trading", tags=["Paper Trading"])


class OpenTradeRequest(BaseModel):
    symbol: str
    direction: str          # BUY | SELL
    notional: float = DEFAULT_TRADE_NOTIONAL
    stop_loss: float | None = None
    take_profit: float | None = None


@router.get("/portfolio", response_model=ApiResponse)
def get_portfolio(db: Session = Depends(get_db)):
    """Return current portfolio state including open positions and unrealized PnL."""
    summary = pt_service.get_portfolio_summary(db)
    return ApiResponse(success=True, data=summary)


@router.get("/stats", response_model=ApiResponse)
def get_stats(db: Session = Depends(get_db)):
    """Return win/loss ratio, profit factor, and performance statistics."""
    stats = pt_service.get_stats(db)
    return ApiResponse(success=True, data=stats)


@router.get("/trades", response_model=ApiResponse)
def get_trades(
    status: str | None = Query(default=None, description="Filter by status: open | closed"),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Return trade history, optionally filtered by status."""
    trades = pt_service.get_trade_history(db, limit=limit, status=status)
    return ApiResponse(success=True, data={"trades": trades, "count": len(trades)})


@router.post("/trades/open", response_model=ApiResponse)
def open_manual_trade(request: OpenTradeRequest, db: Session = Depends(get_db)):
    """Manually open a paper trade at the current market price."""
    if request.direction not in ("BUY", "SELL"):
        raise HTTPException(status_code=400, detail="direction must be BUY or SELL")

    latest = {p["symbol"]: p["close"] for p in get_latest_prices(db)}
    price  = latest.get(request.symbol.upper())

    if not price:
        raise HTTPException(status_code=404, detail=f"No current price for {request.symbol.upper()}")

    trade = open_trade(
        db=db,
        symbol=request.symbol.upper(),
        direction=request.direction,
        entry_price=price,
        stop_loss=request.stop_loss,
        take_profit=request.take_profit,
        notional=request.notional,
    )

    if not trade:
        raise HTTPException(status_code=409, detail="Trade not opened — insufficient balance or position already open")

    return ApiResponse(success=True, data=trade.to_dict(price), message="Trade opened")


@router.post("/trades/{trade_id}/close", response_model=ApiResponse)
def close_manual_trade(trade_id: int, db: Session = Depends(get_db)):
    """Manually close an open paper trade at the current market price."""
    latest = {p["symbol"]: p["close"] for p in get_latest_prices(db)}
    trade  = pt_service.manually_close_trade(db, trade_id=trade_id, current_prices=latest)

    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found or already closed")

    return ApiResponse(success=True, data=trade.to_dict(), message="Trade closed")


@router.post("/cycle", response_model=ApiResponse)
def run_cycle(db: Session = Depends(get_db)):
    """Manually trigger one paper trading cycle (monitor positions + auto-execute signals)."""
    result = pt_service.run_paper_trading_cycle(db)
    return ApiResponse(success=True, data=result, message="Paper trading cycle complete")
