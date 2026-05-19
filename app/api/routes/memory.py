"""
User memory and preference endpoints — canonical routes for the memory system.

These mirror the /auth/me/* routes and are the public-facing aliases
referenced in the platform specification:
  GET/PUT  /preferences
  GET      /profile
  POST     /update-preferences  (preference update, POST-friendly alias)
  GET      /user-memory
  DELETE   /user-memory
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db, get_current_user
from app.auth.models import User
from app.auth.schemas import PreferencesIn, PreferencesOut, UserOut
from app.auth.service import (
    upsert_preferences,
    get_user_memory_full,
    get_user_memory_summary,
    clear_user_memory,
)

router = APIRouter(tags=["Memory & Preferences"])


# ── Preferences ───────────────────────────────────────────────────────────────

@router.get("/preferences", response_model=PreferencesOut)
def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = current_user.preferences
    if not prefs:
        from app.auth.models import UserPreferences
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs); db.commit(); db.refresh(prefs)
    return prefs


@router.put("/preferences", response_model=PreferencesOut)
def update_preferences_put(
    body: PreferencesIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return upsert_preferences(db, current_user.id, **body.model_dump(exclude_none=True))


@router.post("/update-preferences", response_model=PreferencesOut)
def update_preferences_post(
    body: PreferencesIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """POST-friendly alias for PUT /preferences — identical behaviour."""
    return upsert_preferences(db, current_user.id, **body.model_dump(exclude_none=True))


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/profile", response_model=UserOut)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user


# ── User memory ───────────────────────────────────────────────────────────────

@router.get("/user-memory")
def get_user_memory(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    full = get_user_memory_full(db, current_user.id)
    summary = get_user_memory_summary(db, current_user.id)
    return {
        "summary": summary,
        "entries": full,
        "total":   len(full),
    }


@router.delete("/user-memory")
def clear_memory(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = clear_user_memory(db, current_user.id)
    return {"detail": f"Cleared {count} memory entries", "cleared": count}
