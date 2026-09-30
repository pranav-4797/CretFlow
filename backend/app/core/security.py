"""
FastAPI security dependencies.

get_current_user: Verifies the Firebase Bearer token and returns the authenticated user.
Phase 1: Returns a stub — Phase 2 wires real Firebase verification.
"""

import structlog
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.firebase import verify_firebase_token

log = structlog.get_logger(__name__)

# Extracts the Bearer token from the Authorization header
bearer_scheme = HTTPBearer(auto_error=False)


class AuthenticatedUser:
    """Represents a verified Firebase user extracted from a token."""

    def __init__(self, uid: str, email: str, name: str | None = None):
        self.uid = uid
        self.email = email
        self.name = name

    def __repr__(self) -> str:
        return f"AuthenticatedUser(uid={self.uid!r}, email={self.email!r})"


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """
    FastAPI dependency that verifies the Firebase ID token.

    Raises HTTP 401 if:
    - No Authorization header is present
    - Token is invalid or expired
    - Firebase is not initialized

    Phase 1: Raises 503 (Service Unavailable) since Firebase is not yet configured.
    Phase 2: Will perform real token verification.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Provide a Firebase ID token in the Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    decoded = await verify_firebase_token(token)

    if decoded is None:
        # Check if we're in development with no Firebase configured
        from app.core.config import settings
        if settings.firebase_project_id == "placeholder":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "Authentication service is not configured. "
                    "Set Firebase credentials to enable authentication."
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthenticatedUser(
        uid=decoded["uid"],
        email=decoded.get("email", ""),
        name=decoded.get("name"),
    )


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser | None:
    """
    Like get_current_user but returns None instead of raising for unauthenticated requests.
    Useful for public endpoints that have optional auth (e.g., certificate verification).
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None
