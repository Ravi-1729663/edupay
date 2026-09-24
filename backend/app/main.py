"""FastAPI app + middleware + exception handlers.

Structured logging with `request_id` + `user_id` on every log line.
Uniform JSON error envelope on all raised HTTPExceptions.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.deps import request_id_ctx
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import get_logger, request_id_ctx, setup_logging, user_id_ctx


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    log = get_logger(__name__)
    log.info("app.startup", extra={"env": settings.env, "db_sqlite": settings.is_sqlite})
    yield
    log.info("app.shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url="/docs",
        redoc_url=None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        # request_id is also set by the dependency; doing it here guarantees it
        # exists even on 404/500 before dependency resolution.
        from app.core.logging import new_request_id
        rid = request.headers.get("X-Request-Id") or new_request_id()
        request_id_ctx.set(rid)
        token = user_id_ctx.set("-")
        response = await call_next(request)
        response.headers["X-Request-Id"] = rid
        user_id_ctx.reset(token)
        return response

    @app.exception_handler(HTTPException)
    async def http_exc_handler(request: Request, exc: HTTPException):
        rid = request_id_ctx.get()
        detail = exc.detail if isinstance(exc.detail, dict) else {"error": {"code": "error", "message": str(exc.detail)}}
        if "error" not in detail:
            detail = {"error": detail}
        return JSONResponse(
            status_code=exc.status_code,
            content={**detail, "request_id": rid},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exc_handler(request: Request, exc: RequestValidationError):
        rid = request_id_ctx.get()
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "request validation failed",
                    "details": exc.errors(),
                },
                "request_id": rid,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exc_handler(request: Request, exc: Exception):
        rid = request_id_ctx.get()
        get_logger(__name__).exception("unhandled_exception", extra={"request_id": rid})
        return JSONResponse(
            status_code=500,
            content={
                "error": {"code": "internal_error", "message": "an unexpected error occurred"},
                "request_id": rid,
            },
        )

    app.include_router(api_router)

    return app


app = create_app()
