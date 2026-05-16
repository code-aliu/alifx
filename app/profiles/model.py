from __future__ import annotations
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON
from app.database import Base

VALID_MODES = {"beginner", "intermediate", "advanced"}


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id         = Column(Integer, primary_key=True, default=1)
    mode       = Column(String(20), nullable=False, default="intermediate")
    preferences= Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "mode":        self.mode,
            "preferences": self.preferences or {},
            "updated_at":  self.updated_at.isoformat() if self.updated_at else None,
        }
