"""
Central API router — registers all sub-routers.
Add new resource routers here as new phases are implemented.
"""

from fastapi import APIRouter

from app.api.endpoints import auth, campaigns, participants, templates, certificates, gmail, emails, reports, storage

api_router = APIRouter()

# ── Auth ──────────────────────────────────────────────────────────────────────
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# ── Storage & Shared Drive ────────────────────────────────────────────────────
api_router.include_router(storage.router, prefix="/storage", tags=["Storage"])

# ── Campaigns ─────────────────────────────────────────────────────────────────
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["Campaigns"])

# ── Participants ───────────────────────────────────────────────────────────────
api_router.include_router(participants.router, prefix="/participants", tags=["Participants"])

# ── Templates ─────────────────────────────────────────────────────────────────
api_router.include_router(templates.router, prefix="/templates", tags=["Templates"])

# ── Certificates ──────────────────────────────────────────────────────────────
api_router.include_router(certificates.router, prefix="/certificates", tags=["Certificates"])

# ── Gmail ─────────────────────────────────────────────────────────────────────
api_router.include_router(gmail.router, prefix="/gmail", tags=["Gmail"])

# ── Emails ────────────────────────────────────────────────────────────────────
api_router.include_router(emails.router, prefix="/emails", tags=["Emails"])

# ── Reports ───────────────────────────────────────────────────────────────────
api_router.include_router(reports.router, prefix="/reports", tags=["Reports"])
