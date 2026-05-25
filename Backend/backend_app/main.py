from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import api_router
from .config import API_PREFIX, APP_TITLE, APP_VERSION, resolve_cors_origins, resolve_database_url
from .db import configure_database, init_db
from .errors import AppError, error_response, from_http_exception


FIELD_LABELS = {
    "username": "用户名",
    "password": "密码",
    "phone": "手机号",
    "nickname": "昵称",
    "card_type": "卡型",
    "cabinet_type": "机柜类型",
    "card_count": "租用卡数",
    "preferred_cabinet_code": "指定机柜",
    "amount": "金额",
}


def _validation_error_message(error: dict) -> str:
    location = [str(item) for item in error.get("loc", []) if item != "body"]
    field_name = location[-1] if location else ""
    label = FIELD_LABELS.get(field_name, field_name or "字段")
    error_type = error.get("type")
    context = error.get("ctx") or {}

    if error_type == "string_too_short":
        return f"{label}至少需要 {context.get('min_length')} 个字符"
    if error_type == "string_too_long":
        return f"{label}不能超过 {context.get('max_length')} 个字符"
    if error_type == "greater_than_equal":
        return f"{label}不能小于 {context.get('ge')}"
    if error_type == "greater_than":
        return f"{label}必须大于 {context.get('gt')}"
    if error_type == "missing":
        return f"{label}不能为空"
    if error_type in {"int_parsing", "float_parsing"}:
        return f"{label}必须是数字"
    return f"{label}格式不正确"


def create_app(database_path: str | None = None) -> FastAPI:
    configure_database(db_path=database_path, database_url=None if database_path else resolve_database_url())
    init_db()
    application = FastAPI(title=APP_TITLE, version=APP_VERSION)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolve_cors_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router, prefix=API_PREFIX)

    @application.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(exc.code, exc.message),
        )

    @application.exception_handler(HTTPException)
    async def handle_http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content=from_http_exception(exc))

    @application.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        messages = [_validation_error_message(error) for error in exc.errors()]
        detail = "；".join(messages) if messages else "请求参数格式不正确"
        return JSONResponse(
            status_code=422,
            content=error_response("VALIDATION_ERROR", detail),
        )

    return application


app = create_app()
