from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.signals import service as signal_service
from app.api.schemas import ApiResponse

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("/summary", response_model=ApiResponse)
def get_signal_summary(db: Session = Depends(get_db)):
    """Return a concise summary of actionable signals (BUY/SELL only), sorted by confidence."""
    signals = signal_service.get_latest_signals(db)
    actionable = [s for s in signals if s.get("signal") in ("BUY", "SELL")]
    hold       = [s for s in signals if s.get("signal") in ("HOLD", "WATCH", "NEUTRAL")]
    return ApiResponse(success=True, data={
        "actionable": actionable,
        "hold":       hold,
        "counts": {
            "actionable": len(actionable),
            "hold":       len(hold),
        },
    })


@router.get("", response_model=ApiResponse)
def get_latest_signals(db: Session = Depends(get_db)):
    """Return the latest trading signal for every tracked asset, sorted by confidence."""
    signals = signal_service.get_latest_signals(db)
    return ApiResponse(success=True, data={"signals": signals, "count": len(signals)})


@router.get("/{symbol}", response_model=ApiResponse)
def get_signals_for_asset(
    symbol: str,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
):
    """Return recent signal history for a specific asset."""
    signals = signal_service.get_signals_for_asset(db, symbol=symbol, limit=limit)
    return ApiResponse(success=True, data={"symbol": symbol.upper(), "signals": signals, "count": len(signals)})


@router.post("/generate", response_model=ApiResponse)
def trigger_signal_generation(db: Session = Depends(get_db)):
    """Manually trigger signal generation outside the scheduler."""
    count = signal_service.run_signal_pipeline(db)
    return ApiResponse(success=True, data={"signals_generated": count}, message="Signal pipeline complete")
