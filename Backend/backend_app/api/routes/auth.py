from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_current_token
from ...schemas import LoginRequest, RegisterRequest
from ...services.auth_service import login_user, logout_user, register_user


router = APIRouter(tags=["auth"])


@router.post("/auth/register")
def register_route(payload: RegisterRequest) -> dict:
    return register_user(
        username=payload.username,
        password=payload.password,
        phone=payload.phone,
        nickname=payload.nickname,
    )


@router.post("/auth/login")
def login_route(payload: LoginRequest) -> dict:
    return login_user(username=payload.username, password=payload.password)


@router.post("/auth/logout")
def logout_route(token: str = Depends(get_current_token)) -> dict:
    return logout_user(token)
