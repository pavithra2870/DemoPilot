from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentFounder
from app.schemas.auth import FounderOut, LoginRequest, RegisterRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=201)
def register(payload: RegisterRequest) -> TokenResponse:
    return auth_service.register(
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    return auth_service.login(email=str(payload.email), password=payload.password)


@router.get("/me", response_model=FounderOut)
def me(founder: CurrentFounder) -> FounderOut:
    return FounderOut(
        id=founder["id"],
        email=founder["email"],
        full_name=founder.get("full_name") or "",
        created_at=founder.get("created_at"),
    )
