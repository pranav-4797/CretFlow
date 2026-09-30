"""Email distribution endpoints — Phase 10 implementation."""
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter()


@router.post("/{campaign_id}/send", summary="Trigger bulk email send")
async def send_emails(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Bulk email distribution will be implemented in Phase 10.",
    )


@router.get("/{campaign_id}/status", summary="Get email send status")
async def email_status(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email status tracking will be implemented in Phase 10.",
    )


@router.post("/{campaign_id}/retry", summary="Retry failed emails")
async def retry_failed(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Email retry will be implemented in Phase 10.",
    )
