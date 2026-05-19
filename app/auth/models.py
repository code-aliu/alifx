from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, index=True)
    email         = Column(String(255), unique=True, nullable=False, index=True)
    name          = Column(String(100), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role          = Column(String(20), nullable=False, default="user")  # "user" | "admin"
    is_active     = Column(Boolean, nullable=False, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    sessions    = relationship("UserSession", back_populates="user", cascade="all, delete-orphan")
    preferences = relationship("UserPreferences", back_populates="user", uselist=False, cascade="all, delete-orphan")
    memory      = relationship("UserMemory", back_populates="user", cascade="all, delete-orphan")


class UserSession(Base):
    __tablename__ = "user_sessions"

    id                 = Column(Integer, primary_key=True, index=True)
    user_id            = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    refresh_token_hash = Column(String(255), nullable=False)
    expires_at         = Column(DateTime, nullable=False)
    created_at         = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="sessions")


class UserPreferences(Base):
    __tablename__ = "user_preferences"

    id                = Column(Integer, primary_key=True, index=True)
    user_id           = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    user_type         = Column(String(20), default="intermediate")  # "beginner" | "intermediate" | "advanced"
    risk_profile      = Column(String(20), default="balanced")      # "conservative" | "balanced" | "aggressive"
    explanation_depth = Column(String(20), default="intermediate")  # "beginner" | "intermediate" | "advanced"
    preferred_assets  = Column(JSON, default=list)                  # ["EUR/USD", "BTC/USD", ...]
    market_interests  = Column(JSON, default=list)                  # ["forex", "crypto", "macro", ...]
    time_horizon      = Column(String(20), default="medium_term")   # "short_term" | "medium_term" | "long_term"
    macro_sensitivity = Column(String(20), default="medium")        # "low" | "medium" | "high"
    portfolio_style   = Column(String(20), default="balanced")      # "growth" | "income" | "balanced" | "speculative"
    onboarded         = Column(Boolean, default=False)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="preferences")


class UserMemory(Base):
    __tablename__ = "user_memory"

    id         = Column(Integer, primary_key=True, index=True)
    user_id    = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type       = Column(String(50), nullable=False)   # "frequent_asset" | "feature_usage" | "copilot_intent"
    key        = Column(String(100), nullable=False)
    value      = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="memory")
