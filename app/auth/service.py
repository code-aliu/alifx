from datetime import datetime
from sqlalchemy.orm import Session

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
    # Bootstrap empty preferences
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

VALID_RISK   = {"conservative", "moderate", "aggressive"}
VALID_DEPTH  = {"beginner", "intermediate", "advanced"}

def upsert_preferences(db: Session, user_id: int, **kwargs) -> UserPreferences:
    prefs = db.query(UserPreferences).filter(UserPreferences.user_id == user_id).first()
    if not prefs:
        prefs = UserPreferences(user_id=user_id)
        db.add(prefs)

    if "risk_profile" in kwargs and kwargs["risk_profile"] in VALID_RISK:
        prefs.risk_profile = kwargs["risk_profile"]
    if "explanation_depth" in kwargs and kwargs["explanation_depth"] in VALID_DEPTH:
        prefs.explanation_depth = kwargs["explanation_depth"]
    if "preferred_assets" in kwargs:
        prefs.preferred_assets = kwargs["preferred_assets"]
    if "market_interests" in kwargs:
        prefs.market_interests = kwargs["market_interests"]

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
    else:
        db.add(UserMemory(user_id=user_id, type="frequent_asset", key=asset, value={"count": 1, "last_seen": datetime.utcnow().isoformat()}))
    db.commit()


def get_user_memory_summary(db: Session, user_id: int) -> dict:
    rows = db.query(UserMemory).filter(UserMemory.user_id == user_id).all()
    frequent = sorted(
        [r for r in rows if r.type == "frequent_asset"],
        key=lambda r: r.value.get("count", 0),
        reverse=True,
    )[:5]
    return {
        "frequent_assets": [r.key for r in frequent],
    }
