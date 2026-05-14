from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.events import service as event_service
from app.news import service as news_service
from app.api.schemas import ApiResponse

router = APIRouter(prefix="/events", tags=["Events"])


@router.get("", response_model=ApiResponse)
def get_recent_events(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Return recent market events extracted from news."""
    events = event_service.get_recent_events(db, hours=hours, limit=limit)
    return ApiResponse(success=True, data={"events": events, "count": len(events)})


@router.get("/asset/{asset}", response_model=ApiResponse)
def get_events_for_asset(
    asset: str,
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    """Return recent events that affect a specific asset."""
    events = event_service.get_events_for_asset(db, asset=asset, hours=hours)
    return ApiResponse(success=True, data={"asset": asset.upper(), "events": events, "count": len(events)})


@router.get("/news", response_model=ApiResponse)
def get_recent_news(
    hours: int = Query(default=24, ge=1, le=168),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Return raw news articles ingested in the last N hours."""
    articles = news_service.get_recent(db, hours=hours, limit=limit)
    return ApiResponse(success=True, data={"articles": articles, "count": len(articles)})


@router.post("/process", response_model=ApiResponse)
def trigger_event_processing(db: Session = Depends(get_db)):
    """Manually trigger event extraction on unprocessed news articles."""
    count = event_service.process_unprocessed_articles(db)
    return ApiResponse(success=True, data={"events_created": count}, message="Event extraction complete")
