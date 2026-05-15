from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.explainability import service as explain_service
from app.api.schemas import ApiResponse

router = APIRouter(tags=["Explainability"])


@router.get("/why/{asset}", response_model=ApiResponse)
def why_asset(asset: str, db: Session = Depends(get_db)):
    """Why is this asset showing a BUY / SELL / HOLD signal?

    Returns a structured explanation covering:
    - The event drivers (which news moved the score)
    - The technical factors that confirmed or denied the signal
    - The regime context that adjusted final confidence
    - Risk levels, stop-loss, take-profit rationale
    - Validation: staleness, conflicts, consistency score
    """
    result = explain_service.explain_signal(db, asset.upper())
    if result.get("error") == "no_signal_available":
        raise HTTPException(
            status_code=404,
            detail=f"No signal found for {asset.upper()}. Run the signal pipeline first.",
        )
    return ApiResponse(success=True, data=result)


@router.get("/market-regime", response_model=ApiResponse)
def market_regime_context(db: Session = Depends(get_db)):
    """What is the current overall market picture?

    Returns the detected primary regime, the cross-asset signal consensus
    (bullish / bearish / mixed), top 3 signals by confidence, and a summary
    of market changes over the last 6 hours.
    """
    result = explain_service.get_full_market_context(db)
    return ApiResponse(success=True, data=result)


@router.get("/event-impact/{event_id}", response_model=ApiResponse)
def event_impact(event_id: int, db: Session = Depends(get_db)):
    """How did a specific event influence the market?

    Returns:
    - The event (headline, category, sentiment, importance)
    - Per-asset impact scores driven by this single event
    - Any signals that were influenced by this event (linked via event_ids)
    """
    result = explain_service.explain_event_impact(db, event_id)
    if result.get("error") == "event_not_found":
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")
    return ApiResponse(success=True, data=result)
