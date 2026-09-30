"""Gmail OAuth endpoints — Phase 8 implementation."""
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter()


@router.get("/status", summary="Check Gmail connection status")
async def gmail_status(current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Gmail integration will be implemented in Phase 8.",
    )


@router.get("/connect", summary="Initiate Gmail OAuth flow")
async def gmail_connect(current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Gmail OAuth will be implemented in Phase 8.",
    )


@router.get("/callback", summary="Gmail OAuth callback (public)")
async def gmail_callback(code: str = "", state: str = ""):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Gmail OAuth callback will be implemented in Phase 8.",
    )


@router.delete("/disconnect", summary="Disconnect Gmail account")
async def gmail_disconnect(current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Gmail integration will be implemented in Phase 8.",
    )
