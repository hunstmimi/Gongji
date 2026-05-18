from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.routes import api_router
from .config import API_PREFIX, APP_TITLE, APP_VERSION, resolve_cors_origins, resolve_database_url
from .db import configure_database, init_db
from .errors import AppError, error_response, from_http_exception


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
        _ = exc
        return JSONResponse(
            status_code=422,
            content=error_response("VALIDATION_ERROR", "Request validation failed"),
        )

    return application


app = create_app()
