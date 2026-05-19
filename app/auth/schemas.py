from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str

    @field_validator("password")
    @classmethod
    def password_length(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.lower().strip()


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def email_lower(cls, v: str) -> str:
        return v.lower().strip()


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PreferencesIn(BaseModel):
    user_type:         Optional[str]       = None
    risk_profile:      Optional[str]       = None
    explanation_depth: Optional[str]       = None
    preferred_assets:  Optional[list[str]] = None
    market_interests:  Optional[list[str]] = None
    time_horizon:      Optional[str]       = None
    macro_sensitivity: Optional[str]       = None
    portfolio_style:   Optional[str]       = None
    onboarded:         Optional[bool]      = None


class PreferencesOut(BaseModel):
    user_type:         str
    risk_profile:      str
    explanation_depth: str
    preferred_assets:  list[str]
    market_interests:  list[str]
    time_horizon:      str
    macro_sensitivity: str
    portfolio_style:   str
    onboarded:         bool
    updated_at:        Optional[datetime]

    model_config = {"from_attributes": True}
