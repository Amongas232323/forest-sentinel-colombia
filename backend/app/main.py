"""Fábrica de la aplicación FastAPI."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import alerts, auth, monitoring, system
from app.core.config import get_settings
from app.core.errors import RateLimitedError, install_error_handlers
from app.core.logging import configure_logging, log
from app.core.rate_limit import get_limiter

API_PREFIX = "/api/v1"
_DOCS_PATHS = ("/api/docs", "/api/redoc", f"{API_PREFIX}/openapi.json")


def create_app() -> FastAPI:
    s = get_settings()
    configure_logging(json=s.environment != "development")
    show_docs = s.environment != "production"
    app = FastAPI(
        title="Forest Sentinel API",
        version="0.1.0",
        description=(
            "Detección temprana de cambios de cobertura forestal en Guaviare, Sierra Nevada de Santa Marta, Cundinamarca y Amazonas."
        ),
        docs_url="/api/docs" if show_docs else None,
        redoc_url="/api/redoc" if show_docs else None,
        openapi_url=f"{API_PREFIX}/openapi.json" if show_docs else None,
    )
    install_error_handlers(app)

    @app.middleware("http")
    async def security_and_limits(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
        if not request_id.isalnum() or len(request_id) > 64:
            request_id = uuid.uuid4().hex
        structlog.contextvars.bind_contextvars(request_id=request_id)
        started = time.perf_counter()

        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > s.max_request_bytes:
            return JSONResponse({"error": {"code": "payload_too_large", "message": "La solicitud es demasiado grande."}}, status_code=413)
        if request.url.path.startswith(API_PREFIX) and request.method != "OPTIONS":
            try:
                get_limiter().check("global", request.client.host if request.client else "unknown", limit=600, window_s=60)
            except RateLimitedError as exc:
                return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=429, headers={"Retry-After": "60"})

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        response.headers["Cross-Origin-Resource-Policy"] = "same-site"
        if not request.url.path.startswith(_DOCS_PATHS):
            response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        if s.environment == "production":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        if request.url.path.startswith(f"{API_PREFIX}/auth"):
            response.headers["Cache-Control"] = "no-store"
        log.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            ms=round((time.perf_counter() - started) * 1000, 1),
        )
        structlog.contextvars.clear_contextvars()
        return response

    app.add_middleware(
        CORSMiddleware,
        allow_origins=s.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Content-Disposition"],
        max_age=600,
    )

    for router in (auth.router, monitoring.router, alerts.router, system.router):
        app.include_router(router, prefix=API_PREFIX)
    return app


app = create_app()
