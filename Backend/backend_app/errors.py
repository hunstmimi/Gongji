from __future__ import annotations

from fastapi import HTTPException


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def error_response(code: str, message: str) -> dict:
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
        },
    }


def from_http_exception(exc: HTTPException) -> dict:
    detail = exc.detail
    if isinstance(detail, dict) and "code" in detail and "message" in detail:
        return error_response(detail["code"], detail["message"])
    if isinstance(detail, str):
        return error_response(detail, detail)
    return error_response("HTTP_ERROR", "Request failed")
