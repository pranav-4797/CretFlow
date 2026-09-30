"""Certificate endpoints — Phase 6 implementation."""
from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, get_optional_user, AuthenticatedUser

router = APIRouter()


@router.post("/{campaign_id}/generate", summary="Trigger bulk certificate generation")
async def generate_certificates(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Certificate generation will be implemented in Phase 6.",
    )


@router.get("/verify/{certificate_id}", summary="Verify a certificate (public)")
async def verify_certificate(certificate_id: str, user=Depends(get_optional_user)):
    """Public endpoint — no auth required."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Certificate verification will be implemented in Phase 12.",
    )
