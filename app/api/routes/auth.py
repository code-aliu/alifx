from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_db, get_current_user
from app.auth.models import User
from app.auth.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, RefreshRequest,
    UserOut, PreferencesIn, PreferencesOut,
)
from app.auth.security import create_access_token, create_refresh_token, decode_token
from app.auth.service import (
    authenticate, create_user, create_session, get_session_by_token,
    delete_session, delete_all_sessions, get_user_by_email,
    upsert_preferences, get_user_by_id,
    get_user_memory_full, clear_user_memory, export_user_data,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(body: RegisterRequest, db: Session = Depends(get_db)):
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = create_user(db, email=body.email, name=body.name, password=body.password)
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token, expires_at = create_refresh_token({"sub": str(user.id)})
    create_session(db, user.id, refresh_token, expires_at)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, body.email, body.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token, expires_at = create_refresh_token({"sub": str(user.id)})
    create_session(db, user.id, refresh_token, expires_at)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    session = get_session_by_token(db, body.refresh_token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        user_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")

    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="User not found")

    delete_session(db, body.refresh_token)
    new_access  = create_access_token({"sub": str(user.id)})
    new_refresh, expires_at = create_refresh_token({"sub": str(user.id)})
    create_session(db, user.id, new_refresh, expires_at)
    return TokenResponse(access_token=new_access, refresh_token=new_refresh)


@router.post("/logout")
def logout(body: RefreshRequest, db: Session = Depends(get_db)):
    delete_session(db, body.refresh_token)
    return {"detail": "Logged out"}


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user


@router.get("/me/preferences", response_model=PreferencesOut)
def get_preferences(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    prefs = current_user.preferences
    if not prefs:
        from app.auth.models import UserPreferences
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.put("/me/preferences", response_model=PreferencesOut)
def update_preferences(
    body: PreferencesIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prefs = upsert_preferences(db, current_user.id, **body.model_dump(exclude_none=True))
    return prefs


@router.get("/me/memory")
def get_memory(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"memory": get_user_memory_full(db, current_user.id)}


@router.delete("/me/memory")
def reset_memory(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    count = clear_user_memory(db, current_user.id)
    return {"detail": f"Cleared {count} memory entries"}


@router.get("/me/export")
def export_data(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return export_user_data(db, current_user.id)
