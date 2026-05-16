from __future__ import annotations
from sqlalchemy.orm import Session

from app.profiles.model import UserProfile, VALID_MODES
from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_PROFILE = {
    "mode": "intermediate",
    "preferences": {
        "show_educational_context": True,
        "show_uncertainty_warnings": True,
        "signal_detail_level": "standard",   # minimal | standard | detailed
        "macro_focus": True,
    },
}


def get_active_profile(db: Session) -> dict:
    profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
    if not profile:
        return _DEFAULT_PROFILE.copy()
    return profile.to_dict()


def upsert_profile(db: Session, mode: str, preferences: dict | None = None) -> dict:
    if mode not in VALID_MODES:
        raise ValueError(f"Invalid mode '{mode}'. Must be one of {VALID_MODES}")

    profile = db.query(UserProfile).filter(UserProfile.id == 1).first()
    if not profile:
        profile = UserProfile(id=1, mode=mode, preferences=preferences or {})
        db.add(profile)
    else:
        profile.mode = mode
        if preferences is not None:
            existing = profile.preferences or {}
            existing.update(preferences)
            profile.preferences = existing

    db.commit()
    db.refresh(profile)
    logger.info(f"User profile updated: mode={mode}")
    return profile.to_dict()
