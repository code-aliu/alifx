from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.database import get_db
from app.core import cache
from app.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check(db: Session = Depends(get_db)):
    db_status = "ok"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {e}"

    redis_status = "ok" if cache.ping() else "unavailable"

    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        database=db_status,
        redis=redis_status,
        scheduler="running",
    )
