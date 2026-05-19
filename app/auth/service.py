from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.auth.models import User, UserSession, UserPreferences, UserMemory
from app.auth.security import hash_password, verify_password, hash_token


# ── User CRUD ─────────────────────────────────────────────────────────────────

def get_user_by_email(db: Session, email: str) -> User | None:
    return db.query(User).filter(User.email == email.lower()).first()


def get_user_by_id(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()


def create_user(db: Session, email: str, name: str, password: str) -> User:
    user = User(
        email=email.lower(),
        name=name,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.flush()
    db.add(UserPreferences(user_id=user.id))
    db.commit()
    db.refresh(user)
    return user


def authenticate(db: Session, email: str, password: str) -> User | None:
    user = get_user_by_email(db, email)
    if not user or not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        return None
    return user


# ── Sessions ──────────────────────────────────────────────────────────────────

def create_session(db: Session, user_id: int, refresh_token: str, expires_at: datetime) -> UserSession:
    session = UserSession(
        user_id=user_id,
        refresh_token_hash=hash_token(refresh_token),
        expires_at=expires_at,
    )
    db.add(session)
    db.commit()
    return session


def get_session_by_token(db: Session, refresh_token: str) -> UserSession | None:
    token_hash = hash_token(refresh_token)
    return (
        db.query(UserSession)
        .filter(
            UserSession.refresh_token_hash == token_hash,
            UserSession.expires_at > datetime.utcnow(),
        )
        .first()
    )


def delete_session(db: Session, refresh_token: str) -> None:
    token_hash = hash_token(refresh_token)
    db.query(UserSession).filter(UserSession.refresh_token_hash == token_hash).delete()
    db.commit()


def delete_all_sessions(db: Session, user_id: int) -> None:
    db.query(UserSession).filter(UserSession.user_id == user_id).delete()
    db.commit()


# ── Preferences ───────────────────────────────────────────────────────────────

VALID_RISK      = {"conservative", "balanced", "aggressive"}
VALID_DEPTH     = {"beginner", "intermediate", "advanced"}
VALID_TYPE      = {"beginner", "intermediate", "advanced"}
VALID_HORIZON   = {"short_term", "medium_term", "long_term"}
VALID_MACRO     = {"low", "medium", "high"}
VALID_PORTFOLIO = {"growth", "income", "balanced", "speculative"}

def upsert_preferences(db: Session, user_id: int, **kwargs) -> UserPreferences:
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)

    if "user_type" in kwargs and kwargs["user_type"] in VALID_TYPE:
        prefs.user_type = kwargs["user_type"]
    if "risk_profile" in kwargs and kwargs["risk_profile"] in VALID_RISK:
        prefs.risk_profile = kwargs["risk_profile"]
    if "explanation_depth" in kwargs and kwargs["explanation_depth"] in VALID_DEPTH:
        prefs.explanation_depth = kwargs["explanation_depth"]
    if "preferred_assets" in kwargs:
        prefs.preferred_assets = kwargs["preferred_assets"]
    if "market_interests" in kwargs:
        prefs.market_interests = kwargs["market_interests"]
    if "time_horizon" in kwargs and kwargs["time_horizon"] in VALID_HORIZON:
        prefs.time_horizon = kwargs["time_horizon"]
    if "macro_sensitivity" in kwargs and kwargs["macro_sensitivity"] in VALID_MACRO:
        prefs.macro_sensitivity = kwargs["macro_sensitivity"]
    if "portfolio_style" in kwargs and kwargs["portfolio_style"] in VALID_PORTFOLIO:
        prefs.portfolio_style = kwargs["portfolio_style"]
    if kwargs.get("onboarded") is True:
        prefs.onboarded = True

    db.commit()
    db.refresh(prefs)
    return prefs


# ── User Memory ───────────────────────────────────────────────────────────────

def record_asset_interaction(db: Session, user_id: int, asset: str) -> None:
    entry = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == user_id, UserMemory.type == "frequent_asset", UserMemory.key == asset)
        .first()
    )
    if entry:
        entry.value = {**entry.value, "count": entry.value.get("count", 0) + 1, "last_seen": datetime.utcnow().isoformat()}
        entry.updated_at = datetime.utcnow()
    else:
        db.add(UserMemory(user_id=user_id, type="frequent_asset", key=asset, value={"count": 1, "last_seen": datetime.utcnow().isoformat()}))
    db.commit()


def track_feature_usage(db: Session, user_id: int, feature: str) -> None:
    """Increment a feature-usage counter in user memory. Used for admin analytics."""
    entry = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == user_id, UserMemory.type == "feature_usage", UserMemory.key == feature)
        .first()
    )
    if entry:
        entry.value = {**entry.value, "count": entry.value.get("count", 0) + 1, "last_used": datetime.utcnow().isoformat()}
        entry.updated_at = datetime.utcnow()
    else:
        db.add(UserMemory(user_id=user_id, type="feature_usage", key=feature, value={"count": 1, "last_used": datetime.utcnow().isoformat()}))
    db.commit()


def track_copilot_intent(db: Session, user_id: int, intent: str) -> None:
    entry = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == user_id, UserMemory.type == "copilot_intent", UserMemory.key == intent)
        .first()
    )
    if entry:
        entry.value = {**entry.value, "count": entry.value.get("count", 0) + 1}
        entry.updated_at = datetime.utcnow()
    else:
        db.add(UserMemory(user_id=user_id, type="copilot_intent", key=intent, value={"count": 1}))
    db.commit()


_FAQ_MAX_LENGTH = 120
_FAQ_KEEP = 10

def track_faq(db: Session, user_id: int, question: str) -> None:
    """Store the question text (truncated) as a recently asked FAQ."""
    key = question.strip()[:_FAQ_MAX_LENGTH]
    entry = (
        db.query(UserMemory)
        .filter(UserMemory.user_id == user_id, UserMemory.type == "faq", UserMemory.key == key)
        .first()
    )
    if entry:
        entry.value = {**entry.value, "count": entry.value.get("count", 0) + 1}
        entry.updated_at = datetime.utcnow()
    else:
        # Prune if already at limit — remove the oldest
        existing = (
            db.query(UserMemory)
            .filter(UserMemory.user_id == user_id, UserMemory.type == "faq")
            .order_by(UserMemory.updated_at)
            .all()
        )
        if len(existing) >= _FAQ_KEEP:
            db.delete(existing[0])
        db.add(UserMemory(user_id=user_id, type="faq", key=key, value={"count": 1}))
    db.commit()


def get_user_memory_summary(db: Session, user_id: int) -> dict:
    rows = db.query(UserMemory).filter(UserMemory.user_id == user_id).all()
    frequent = sorted(
        [r for r in rows if r.type == "frequent_asset"],
        key=lambda r: r.value.get("count", 0),
        reverse=True,
    )[:5]
    top_intents = sorted(
        [r for r in rows if r.type == "copilot_intent"],
        key=lambda r: r.value.get("count", 0),
        reverse=True,
    )[:3]
    recent_faqs = sorted(
        [r for r in rows if r.type == "faq"],
        key=lambda r: r.updated_at or datetime.min,
        reverse=True,
    )[:3]
    return {
        "frequent_assets": [r.key for r in frequent],
        "top_intents":     [r.key for r in top_intents],
        "recent_faqs":     [r.key for r in recent_faqs],
    }


def get_user_memory_full(db: Session, user_id: int) -> list[dict]:
    rows = db.query(UserMemory).filter(UserMemory.user_id == user_id).order_by(UserMemory.updated_at.desc()).all()
    return [
        {"type": r.type, "key": r.key, "value": r.value, "updated_at": r.updated_at.isoformat() if r.updated_at else None}
        for r in rows
    ]


def clear_user_memory(db: Session, user_id: int) -> int:
    count = db.query(UserMemory).filter(UserMemory.user_id == user_id).delete()
    db.commit()
    return count


def export_user_data(db: Session, user_id: int) -> dict:
    user = get_user_by_id(db, user_id)
    if not user:
        return {}
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    memory = get_user_memory_full(db, user_id)
    return {
        "account": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "role": user.role,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },
        "preferences": {
            "user_type":         prefs.user_type         if prefs else None,
            "risk_profile":      prefs.risk_profile      if prefs else None,
            "explanation_depth": prefs.explanation_depth if prefs else None,
            "preferred_assets":  prefs.preferred_assets  if prefs else [],
            "market_interests":  prefs.market_interests  if prefs else [],
            "time_horizon":      prefs.time_horizon      if prefs else None,
            "macro_sensitivity": prefs.macro_sensitivity if prefs else None,
            "portfolio_style":   prefs.portfolio_style   if prefs else None,
        } if prefs else {},
        "memory": memory,
        "exported_at": datetime.utcnow().isoformat() + "Z",
    }


# ── Admin analytics helpers ───────────────────────────────────────────────────

def get_feature_usage_totals(db: Session) -> list[dict]:
    """Aggregate feature usage counts across all users."""
    rows = db.query(UserMemory).filter(UserMemory.type == "feature_usage").all()
    totals: dict[str, int] = {}
    for r in rows:
        totals[r.key] = totals.get(r.key, 0) + r.value.get("count", 0)
    return sorted([{"feature": k, "total_calls": v} for k, v in totals.items()], key=lambda x: -x["total_calls"])


def get_copilot_intent_totals(db: Session) -> list[dict]:
    rows = db.query(UserMemory).filter(UserMemory.type == "copilot_intent").all()
    totals: dict[str, int] = {}
    for r in rows:
        totals[r.key] = totals.get(r.key, 0) + r.value.get("count", 0)
    return sorted([{"intent": k, "count": v} for k, v in totals.items()], key=lambda x: -x["count"])
