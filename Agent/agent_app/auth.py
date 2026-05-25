from __future__ import annotations

import secrets

from fastapi import Header, HTTPException

from .config import resolve_token


def require_agent_token(authorization: str | None = Header(default=None)) -> None:
    expected = resolve_token()
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED", "message": "missing agent token"})
    if not secrets.compare_digest(token, expected):
        raise HTTPException(status_code=403, detail={"code": "FORBIDDEN", "message": "invalid agent token"})

