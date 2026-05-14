from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.market_data import service as market_service
from app.api.schemas import MarketDataResponse, PriceHistoryResponse, ApiResponse

router = APIRouter(prefix="/market-data", tags=["Market Data"])


@router.get("", response_model=ApiResponse)
def get_latest_prices(db: Session = Depends(get_db)):
    """Return the latest price for every tracked asset."""
    prices = market_service.get_latest_prices(db)
    return ApiResponse(success=True, data={"prices": prices, "count": len(prices)})


@router.get("/history/{symbol}", response_model=ApiResponse)
def get_price_history(
    symbol: str,
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """Return historical price bars for a symbol."""
    bars = market_service.get_price_history(db, symbol=symbol, limit=limit)
    if not bars:
        raise HTTPException(status_code=404, detail=f"No price data found for {symbol.upper()}")
    return ApiResponse(success=True, data={"symbol": symbol.upper(), "bars": bars, "count": len(bars)})


@router.post("/refresh", response_model=ApiResponse)
def trigger_market_refresh(db: Session = Depends(get_db)):
    """Manually trigger a market data fetch outside the scheduler."""
    count = market_service.fetch_and_store_all(db)
    return ApiResponse(success=True, data={"bars_stored": count}, message="Market data refreshed")
