from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.api.schemas import ApiResponse
from app.profiles.service import get_active_profile, upsert_profile
from app.profiles.model import VALID_MODES

router = APIRouter(prefix="/profile", tags=["User Profile"])


class ProfileUpdate(BaseModel):
    mode: str = Field(..., description="beginner | intermediate | advanced")
    preferences: dict | None = Field(default=None)


@router.get("", response_model=ApiResponse)
def get_profile(db: Session = Depends(get_db)):
    """Return the active user intelligence profile."""
    profile = get_active_profile(db)
    return ApiResponse(success=True, data=profile)


@router.put("", response_model=ApiResponse)
def update_profile(body: ProfileUpdate, db: Session = Depends(get_db)):
    """Update the user intelligence mode and optional preferences."""
    if body.mode not in VALID_MODES:
        raise HTTPException(status_code=422, detail=f"mode must be one of {sorted(VALID_MODES)}")
    profile = upsert_profile(db, mode=body.mode, preferences=body.preferences)
    return ApiResponse(success=True, data=profile)
