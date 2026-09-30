"""
Campaign endpoints — Phase 3 implementation.
Phase 1: Returns 501 Not Implemented stubs so the router loads correctly.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from app.core.security import get_current_user, AuthenticatedUser

router = APIRouter()


def _phase_not_implemented(feature: str):
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=f"{feature} will be implemented in Phase 3 (Neon Database + Campaigns).",
    )


@router.get("/", summary="List campaigns")
async def list_campaigns(current_user: AuthenticatedUser = Depends(get_current_user)):
    _phase_not_implemented("Campaign listing")


@router.post("/", summary="Create campaign", status_code=status.HTTP_201_CREATED)
async def create_campaign(current_user: AuthenticatedUser = Depends(get_current_user)):
    _phase_not_implemented("Campaign creation")


@router.get("/{campaign_id}", summary="Get campaign")
async def get_campaign(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    _phase_not_implemented("Campaign retrieval")


@router.put("/{campaign_id}", summary="Update campaign")
async def update_campaign(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    _phase_not_implemented("Campaign update")


@router.delete("/{campaign_id}", summary="Delete campaign", status_code=status.HTTP_204_NO_CONTENT)
async def delete_campaign(campaign_id: str, current_user: AuthenticatedUser = Depends(get_current_user)):
    _phase_not_implemented("Campaign deletion")
