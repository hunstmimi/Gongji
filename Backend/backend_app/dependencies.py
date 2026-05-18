from __future__ import annotations

from fastapi import Header

from .errors import AppError
from .services.auth_service import get_current_user_by_token


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise AppError("UNAUTHORIZED", "请先登录", 401)
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("UNAUTHORIZED", "登录凭证无效", 401)
    return token


def get_current_user(authorization: str | None = Header(default=None)) -> dict:
    token = _extract_bearer_token(authorization)
    return get_current_user_by_token(token)


def get_current_token(authorization: str | None = Header(default=None)) -> str:
    return _extract_bearer_token(authorization)
