"""
Campaign management API endpoints with Firestore persistence and strict tenant ownership verification.
"""

from typing import List, Optional
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.campaign import (
    CampaignResponse,
    CreateCampaignRequest,
    UpdateCampaignRequest,
)
from app.services.firestore_service import firestore_service

log = structlog.get_logger(__name__)

router = APIRouter()


@router.get("", response_model=List[CampaignResponse], summary="List user's campaigns")
@router.get("/", response_model=List[CampaignResponse], include_in_schema=False)
async def list_campaigns(
    limit: int = Query(50, ge=1, le=100),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    List all campaigns owned by the authenticated user.
    Prevents cross-user data leakage.
    """
    campaigns = firestore_service.list_campaigns(current_user.uid, limit=limit)
    return [CampaignResponse.model_validate(c) for c in campaigns]


@router.post("", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED, summary="Create a new campaign")
@router.post("/", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
async def create_campaign(
    payload: CreateCampaignRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Create a new campaign owned strictly by the authenticated user.
    """
    campaign_id = f"camp_{uuid.uuid4().hex[:12]}"
    camp = firestore_service.get_or_create_campaign(
        campaign_id=campaign_id,
        user_id=current_user.uid,
        campaign_name=payload.campaign_name,
    )
    # Apply optional initial fields
    updates = {}
    if payload.description:
        updates["description"] = payload.description
    if payload.subject_template:
        updates["subject_template"] = payload.subject_template
    if payload.body_template:
        updates["body_template"] = payload.body_template

    if updates:
        firestore_service.update_campaign(campaign_id, updates)
        camp.update(updates)

    log.info("Created new campaign", campaign_id=campaign_id, user_id=current_user.uid)
    return CampaignResponse.model_validate(camp)


@router.get("/{campaign_id}", response_model=CampaignResponse, summary="Get campaign by ID")
async def get_campaign(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retrieve single campaign details.
    Enforces strict IDOR protection: returns 404 if campaign is not owned by current_user.
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )
    return CampaignResponse.model_validate(camp)


@router.put("/{campaign_id}", response_model=CampaignResponse, summary="Update campaign")
async def update_campaign(
    campaign_id: str,
    payload: UpdateCampaignRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Update campaign metadata.
    Enforces strict IDOR protection.
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )

    updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items() if v is not None}
    if updates:
        firestore_service.update_campaign(campaign_id, updates)
        camp.update(updates)

    log.info("Updated campaign metadata", campaign_id=campaign_id, user_id=current_user.uid)
    return CampaignResponse.model_validate(camp)


@router.delete("/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete campaign")
async def delete_campaign(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Delete a campaign and its subdocuments.
    Enforces strict IDOR protection.
    """
    success = firestore_service.delete_campaign(campaign_id, user_id=current_user.uid)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )
    log.info("Deleted campaign", campaign_id=campaign_id, user_id=current_user.uid)
