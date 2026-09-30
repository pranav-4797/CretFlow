"""Template endpoints — Phase 5 implementation."""
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter()


@router.get("/{campaign_id}", summary="Get certificate template")
async def get_template(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Certificate template management will be implemented in Phase 5 (Certificate Editor).",
    )


@router.post("/{campaign_id}", summary="Upload/save certificate template")
async def save_template(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Certificate template management will be implemented in Phase 5 (Certificate Editor).",
    )
