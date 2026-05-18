from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.auth.dependencies import get_db, require_admin
from app.auth.models import User, UserSession
from app.auth.schemas import UserOut

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/health")
def admin_health(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    user_count    = db.query(func.count(User.id)).scalar()
    session_count = db.query(func.count(UserSession.id)).scalar()
    return {"status": "ok", "users": user_count, "active_sessions": session_count}


@router.get("/users")
def list_users(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    users = db.query(User).order_by(User.created_at.desc()).all()
    return [UserOut.model_validate(u) for u in users]


@router.put("/users/{user_id}/role")
def set_role(
    user_id: int,
    role: str,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if role not in ("user", "admin"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Role must be 'user' or 'admin'")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    db.commit()
    return {"detail": f"User {user_id} role set to {role}"}


@router.get("/analytics")
def analytics(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    from app.auth.models import UserMemory
    from sqlalchemy import text
    total_users  = db.query(func.count(User.id)).scalar()
    active_users = db.query(func.count(User.id)).filter(User.is_active == True).scalar()  # noqa: E712
    total_memory = db.query(func.count(UserMemory.id)).scalar()
    return {
        "total_users": total_users,
        "active_users": active_users,
        "memory_entries": total_memory,
    }
