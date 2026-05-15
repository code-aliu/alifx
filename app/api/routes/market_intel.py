from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.events.service import get_recent_changes
from app.api.schemas import ApiResponse

router = APIRouter(prefix="/market", tags=["Market Intelligence"])


@router.get("/changes", response_model=ApiResponse)
def get_market_changes(
    hours: int = Query(default=6, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """What changed in the market?

    Compares events from the last `hours` hours against the prior equal-length
    window. Returns category-level sentiment shifts and per-asset momentum
    summaries so callers can surface "what just moved and why."
    """
    result = get_recent_changes(db, hours=hours)
    return ApiResponse(success=True, data=result)
