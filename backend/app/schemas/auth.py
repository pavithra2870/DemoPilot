from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import sanitize_text


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=120)

    @field_validator("full_name", mode="before")
    @classmethod
    def _clean(cls, v):
        return sanitize_text(v, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class FounderOut(BaseModel):
    id: str
    email: str
    full_name: str = ""
    created_at: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    founder: FounderOut
