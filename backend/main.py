"""
CertFlow Backend — Main Application Entry Point

Architecture:
  app/
    core/       — settings, database, security, logging
    models/     — SQLAlchemy ORM models
    schemas/    — Pydantic request/response schemas
    api/        — Route handlers (one file per resource)
    services/   — Business logic layer
    workers/    — Celery task definitions
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
    # Phase 3: Initialize database connection pool here
    # Phase 2: Initialize Firebase Admin
    from app.core.firebase import initialize_firebase
    initialize_firebase()
    yield
    log.info("CertFlow backend shutting down")


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
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────

    # CORS — restrict to known frontend origins in production
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )

    # Trusted hosts — prevents Host header injection
    if settings.environment == "production":
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[settings.backend_host],
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
