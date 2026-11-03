"""
Super Admin Control Room API endpoints.
Provides system-wide visibility, multi-tenant campaign management,
and live operational telemetry strictly for authorized administrators.
"""

from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.core.security import AuthenticatedUser, require_admin
from app.schemas.campaign import CampaignResponse
from app.services.firestore_service import FirestoreMetrics, firestore_service

log = structlog.get_logger(__name__)

router = APIRouter()


class AdminOverviewResponse(BaseModel):
    total_campaigns: int
    total_participants: int
    total_sent: int
    total_failed: int
    distinct_users_count: int
    firestore_read_metrics: Dict[str, int]
    admin_user: str


class AdminCampaignItem(BaseModel):
    id: str
    campaign_id: str
    name: str
    campaign_name: str
    owner_uid: str
    status: str
    total_recipients: int
    sent_count: int
    failed_count: int
    campaign_type: str = "spreadsheet"
    created_at: Optional[str] = None
    description: Optional[str] = None


@router.get("/overview", response_model=AdminOverviewResponse, summary="Super Admin system-wide overview & telemetry")
async def get_admin_overview(
    admin: AuthenticatedUser = Depends(require_admin),
) -> AdminOverviewResponse:
    """
    Returns platform-wide statistics, recipient counts, and live Firestore read metrics.
    Only accessible by Super Admins (admin@gmail.com).
    """
    all_campaigns = firestore_service.list_all_campaigns(limit=500)
    
    total_participants = sum(int(c.get("total_recipients") or 0) for c in all_campaigns)
    total_sent = sum(int(c.get("sent_count") or 0) for c in all_campaigns)
    total_failed = sum(int(c.get("failed_count") or 0) for c in all_campaigns)
    
    distinct_owners = {c.get("owner_uid") or c.get("userId") for c in all_campaigns if c.get("owner_uid") or c.get("userId")}

    return AdminOverviewResponse(
        total_campaigns=len(all_campaigns),
        total_participants=total_participants,
        total_sent=total_sent,
        total_failed=total_failed,
        distinct_users_count=len(distinct_owners),
        firestore_read_metrics=FirestoreMetrics.get_summary(),
        admin_user=admin.email,
    )


@router.get("/campaigns", response_model=List[AdminCampaignItem], summary="List all platform campaigns across users")
async def get_admin_campaigns(
    limit: int = Query(200, ge=1, le=500),
    user_id_filter: Optional[str] = Query(None, description="Optional user UID to filter by"),
    admin: AuthenticatedUser = Depends(require_admin),
) -> List[AdminCampaignItem]:
    """
    List all campaigns across every organizer on the platform.
    """
    campaigns = firestore_service.list_all_campaigns(limit=limit, user_id_filter=user_id_filter)
    results = []
    for c in campaigns:
        c_id = str(c.get("campaign_id") or c.get("id") or "")
        c_name = str(c.get("campaign_name") or c.get("name") or "Untitled")
        owner = str(c.get("owner_uid") or c.get("userId") or "Unknown")
        results.append(
            AdminCampaignItem(
                id=c_id,
                campaign_id=c_id,
                name=c_name,
                campaign_name=c_name,
                owner_uid=owner,
                status=str(c.get("status") or "draft"),
                total_recipients=int(c.get("total_recipients") or 0),
                sent_count=int(c.get("sent_count") or 0),
                failed_count=int(c.get("failed_count") or 0),
                campaign_type=str(c.get("campaign_type") or "spreadsheet"),
                created_at=c.get("created_at"),
                description=c.get("description"),
            )
        )
    return results


@router.delete("/campaigns/{campaign_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Admin force delete campaign")
async def admin_delete_campaign(
    campaign_id: str,
    admin: AuthenticatedUser = Depends(require_admin),
):
    """
    Super Admin force delete of any campaign and all its subcollections.
    """
    success = firestore_service.delete_campaign(campaign_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found.",
        )
    log.info("Super Admin deleted campaign", campaign_id=campaign_id, admin=admin.email)


@router.post("/metrics/reset", summary="Reset operational telemetry counters")
async def reset_telemetry_metrics(
    admin: AuthenticatedUser = Depends(require_admin),
):
    """
    Reset in-memory Firestore read counters back to 0 for a clean profiling session.
    """
    FirestoreMetrics.reset()
    log.info("Super Admin reset Firestore operational telemetry", admin=admin.email)
    return {"message": "Firestore operational read metrics reset to zero."}
