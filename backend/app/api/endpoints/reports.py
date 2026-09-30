"""Reports endpoints — Phase 11 implementation."""
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter()


@router.get("/{campaign_id}", summary="Get campaign distribution report")
async def get_report(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Campaign reports will be implemented in Phase 11.",
    )


@router.get("/{campaign_id}/export", summary="Export report as CSV/XLSX")
async def export_report(
    campaign_id: str,
    format: str = "csv",
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Report export will be implemented in Phase 11.",
    )
