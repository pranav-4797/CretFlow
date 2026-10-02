"""
CertFlow Backend — Main Application Entry Point

Architecture:
  app/
    core/       — settings, database, security, logging
    models/     — SQLAlchemy ORM models
    schemas/    — Pydantic request/response schemas
    api/        — Route handlers (one file per resource)
    services/   — Business logic layer (Firestore, Gmail, Shared Drive, Batch Engine)
    middleware/ — Custom middleware

This file only wires everything together.
Do NOT put business logic here.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.core.config import settings
from app.core.logging import configure_logging
from app.api.router import api_router

# Configure structured logging before anything else
configure_logging()

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown logic."""
    log.info(
        "CertFlow backend starting",
        environment=settings.environment,
        version="0.1.0",
    )
    if settings.is_production:
        if settings.secret_key == "dev-secret-key-change-in-production-32chars!":
            log.critical("INSECURE CONFIGURATION: Default dev SECRET_KEY detected in production environment!")
            raise RuntimeError("Production deployment requires a unique, secure SECRET_KEY.")

    # Initialize Firebase Admin SDK
    from app.core.firebase import initialize_firebase
    initialize_firebase()

    # Automatic startup reconciliation for interrupted jobs and expired leases
    from app.services.reconciler import reconciler
    await reconciler.reconcile_all_on_startup()

    yield
    log.info("CertFlow backend shutting down gracefully")


def create_application() -> FastAPI:
    """Factory function to create and configure the FastAPI application."""

    app = FastAPI(
        title="CertFlow API",
        description=(
            "CertFlow — Certificate generation and automated distribution platform. "
            "Provides REST APIs for campaigns, participants, certificates, Gmail integration, "
            "and distribution reports."
        ),
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Security Headers Middleware ───────────────────────────────────────────
    @app.middleware("http")
    async def add_security_headers(request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

    # ── Middleware ────────────────────────────────────────────────────────────

    # CORS — restrict to known frontend origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Trusted hosts — prevents Host header injection
    if settings.environment == "production" and settings.backend_host:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[settings.backend_host, "*.onrender.com", "localhost"],
        )

    # ── Routes ────────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api")

    return app


app = create_application()


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """
    Health check endpoint for Render and load balancers.
    Returns 200 OK when the server is running.
    """
    return {
        "status": "ok",
        "service": "certflow-backend",
        "version": "0.1.0",
        "environment": settings.environment,
    }
