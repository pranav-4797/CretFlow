"""Participant endpoints — Phase 4 implementation."""
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter()


@router.get("/{campaign_id}", summary="List participants")
async def list_participants(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Participant management will be implemented in Phase 4 (Excel/CSV Processing).",
    )


@router.post("/{campaign_id}/upload", summary="Upload participant list")
async def upload_participants(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Participant upload will be implemented in Phase 4 (Excel/CSV Processing).",
    )
