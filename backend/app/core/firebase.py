"""
Firebase Admin SDK initialization and token verification.
Phase 1: Structure only — not connected to Firebase yet.
Phase 2: Will initialize with real credentials.
"""

import os
from pathlib import Path
from typing import Optional
import structlog

log = structlog.get_logger(__name__)

# Firebase Admin app instance (initialized once at startup)
_firebase_app = None


def get_service_account_path() -> Optional[str]:
    """Resolve service account JSON file path if available."""
    from app.core.config import settings

    # 1. Explicit path in settings
    if settings.firebase_credentials_path:
        cand = Path(settings.firebase_credentials_path)
        if cand.is_file():
            return str(cand.resolve())
        # Try relative to backend dir or project root
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        backend_dir = root_dir / "backend"
        for base in [backend_dir, root_dir]:
            p = base / settings.firebase_credentials_path
            if p.is_file():
                return str(p.resolve())

    # 2. Look for conventional filenames or *firebase-adminsdk*.json in backend & root
    root_dir = Path(__file__).resolve().parent.parent.parent.parent
    backend_dir = root_dir / "backend"
    cwd = Path(os.getcwd()).resolve()

    search_dirs = [cwd, backend_dir, root_dir]
    seen_dirs = set()
    for d in search_dirs:
        if d in seen_dirs or not d.is_dir():
            continue
        seen_dirs.add(d)

        # Standard named files first
        for name in ["serviceAccountKey.json", "firebase-service-account.json"]:
            cand = d / name
            if cand.is_file():
                return str(cand.resolve())

        # Any firebase-adminsdk json file
        try:
            for item in d.glob("*firebase-adminsdk*.json"):
                if item.is_file():
                    return str(item.resolve())
        except Exception:
            pass

    return None


def is_firebase_configured() -> bool:
    """Check if Firebase Admin SDK has valid credentials configured."""
    from app.core.config import settings
    if get_service_account_path() is not None:
        return True
    return (
        settings.firebase_private_key != "placeholder"
        and settings.firebase_client_email != "placeholder@placeholder.iam.gserviceaccount.com"
    )


def initialize_firebase() -> None:
    """
    Initialize Firebase Admin SDK.
    Called once during application startup.
    Supports service account JSON file, env vars, or project ID fallback.
    """
    global _firebase_app
    try:
        import firebase_admin
        from firebase_admin import credentials
        from app.core.config import settings

        if _firebase_app is not None:
            log.debug("Firebase already initialized")
            return

        # 1. Try service account JSON file
        sa_path = get_service_account_path()
        if sa_path:
            cred = credentials.Certificate(sa_path)
            _firebase_app = firebase_admin.initialize_app(cred)
            log.info("Firebase Admin SDK initialized with Service Account file", path=sa_path)
            return

        # 2. Skip initialization if no project ID is configured
        if settings.firebase_project_id == "placeholder":
            log.warning(
                "Firebase not initialized — placeholder project ID detected. "
                "Set real Firebase credentials to enable authentication."
            )
            return

        # 3. If individual service account env vars are available
        if settings.firebase_private_key != "placeholder" and settings.firebase_client_email != "placeholder@placeholder.iam.gserviceaccount.com":
            cred = credentials.Certificate({
                "type": "service_account",
                "project_id": settings.firebase_project_id,
                "client_email": settings.firebase_client_email,
                "private_key": settings.firebase_private_key,
                "token_uri": "https://oauth2.googleapis.com/token",
            })
            _firebase_app = firebase_admin.initialize_app(cred)
            log.info("Firebase Admin SDK initialized with Service Account env credentials", project=settings.firebase_project_id)
            return

        # 4. Fallback: Initialize with projectId only (can verify tokens via public Google certs)
        _firebase_app = firebase_admin.initialize_app(options={"projectId": settings.firebase_project_id})
        log.info("Firebase Admin SDK initialized with Project ID (public cert verification mode)", project=settings.firebase_project_id)

    except Exception as exc:
        log.error("Failed to initialize Firebase Admin SDK", error=str(exc))
        # Don't raise — allow the app to start and fail gracefully on auth requests


async def verify_firebase_token(token: str) -> Optional[dict]:
    """
    Verify a Firebase ID token and return the decoded claims.
    Returns None if the token is invalid.
    """
    try:
        from firebase_admin import auth as firebase_auth

        if _firebase_app is None:
            log.warning("Firebase not initialized — cannot verify token")
            return None

        # When service account is present, we can check revocation; otherwise verify signature & expiry
        has_service_account = is_firebase_configured()
        decoded = firebase_auth.verify_id_token(token, check_revoked=has_service_account)
        return decoded

    except Exception as exc:
        log.warning("Firebase token verification failed", error=str(exc))
        return None

