"""
Authentication endpoints.
Phase 2: Will add Firebase token verification, user profile management.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter()


class UserProfileResponse(BaseModel):
    uid: str
    email: str
    name: str | None = None


@router.get("/me", response_model=UserProfileResponse, summary="Get current user profile")
async def get_me(current_user: AuthenticatedUser = Depends(get_current_user)) -> UserProfileResponse:
    """
    Returns the authenticated user's profile.
    Requires a valid Firebase ID token in the Authorization header.
    """
    return UserProfileResponse(
        uid=current_user.uid,
        email=current_user.email,
        name=current_user.name,
    )


@router.get("/status", summary="Check authentication status (public)")
async def auth_status() -> dict:
    """Public endpoint to check if the auth service is operational."""
    from app.core.firebase import is_firebase_configured
    configured = is_firebase_configured()
    return {
        "auth_service": "operational" if configured else "not_configured",
        "firebase_configured": configured,
        "message": (
            "Firebase Auth is ready."
            if configured
            else "Firebase credentials are not configured. Phase 2 required."
        ),
    }
