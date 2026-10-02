"""
Email delivery status tracking, campaign email progress, batch control, and retry endpoints with Firestore persistence.
Zero SQLAlchemy, Celery, or Redis dependencies.
"""

from typing import Any, Dict, List, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.email import CampaignEmailStatusResponse, EmailLogResponse
from app.services.batch_engine import batch_engine
from app.services.firestore_service import firestore_service
from app.services.gmail_service import GmailNotConnectedError, GmailService
from app.services.reconciler import reconciler

log = structlog.get_logger(__name__)

router = APIRouter()


class SendCampaignEmailsRequest(BaseModel):
    subject_template: Optional[str] = Field("Your Certificate", max_length=200)
    body_template: Optional[str] = Field(None, max_length=5000)
    batch_size: Optional[int] = Field(15, ge=1, le=50, description="Recipients per batch")
    confirm: bool = Field(True, description="Explicit confirmation to send campaign emails")


@router.post("/{campaign_id}/send", summary="Trigger bulk email send for campaign")
async def send_campaign_emails(
    campaign_id: str,
    request: Optional[SendCampaignEmailsRequest] = None,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Trigger bulk email sending for a campaign:
    - Verifies user ownership and authentication
    - Verifies connected Gmail account
    - Launches bounded batch processing inside web service
    - Records persistent job and progress in Firestore
    """
    conn = GmailService.get_connection(current_user.uid)
    if not conn or not conn.get("is_connected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must connect your Gmail account in Settings before sending campaign emails.",
        )

    sub_tmpl = request.subject_template if request and request.subject_template else "Your Certificate"
    body_tmpl = request.body_template if request else ""
    batch_sz = request.batch_size if request and request.batch_size else 15

    try:
        result = await batch_engine.start_campaign_job(
            user_id=current_user.uid,
            campaign_id=campaign_id,
            subject_template=sub_tmpl,
            body_template=body_tmpl,
            batch_size=batch_sz,
        )
        return result
    except GmailNotConnectedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        log.error("Failed to start campaign email send", campaign_id=campaign_id, error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{campaign_id}/status", response_model=CampaignEmailStatusResponse, summary="Get campaign email status")
async def get_campaign_email_status(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Get aggregated truthful status counts and recent delivery logs for a campaign from Firestore.
    Reconciles any stuck participants if the service recently woke up from Render sleep.
    Ensures user can only view their own campaign logs.
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )

    # Activity wakeup reconciliation for this campaign
    await reconciler.reconcile_campaign_on_activity(campaign_id)

    stats = firestore_service.get_campaign_stats(campaign_id, current_user.uid)

    return CampaignEmailStatusResponse(
        campaign_id=campaign_id,
        campaign_status=stats.get("campaign_status", "draft"),
        total_count=stats.get("total_count", 0),
        sent_count=stats.get("sent_count", 0),
        failed_count=stats.get("failed_count", 0),
        queued_count=stats.get("queued_count", 0),
        processing_count=stats.get("processing_count", 0),
        retrying_count=stats.get("retrying_count", 0),
        cancelled_count=stats.get("cancelled_count", 0),
        unknown_count=stats.get("unknown_count", 0),
        recent_logs=stats.get("recent_logs", []),
    )


@router.post("/{campaign_id}/pause", summary="Pause ongoing campaign sending")
async def pause_campaign(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Pause an active email campaign."""
    try:
        return await batch_engine.pause_campaign(current_user.uid, campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        log.error("Failed to pause campaign", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{campaign_id}/resume", summary="Resume a paused campaign")
async def resume_campaign(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Resume a paused email campaign."""
    try:
        return await batch_engine.resume_campaign(current_user.uid, campaign_id)
    except GmailNotConnectedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        log.error("Failed to resume campaign", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{campaign_id}/cancel", summary="Cancel campaign sending")
async def cancel_campaign(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Cancel campaign sending and mark pending recipients cancelled."""
    try:
        return await batch_engine.cancel_campaign(current_user.uid, campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        log.error("Failed to cancel campaign", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{campaign_id}/retry", summary="Retry eligible failed campaign emails")
async def retry_failed_emails(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Retry eligible failed email deliveries for a campaign:
    - User ownership verified
    - Only retries emails with status == failed and attempt_count < max_attempts or unknown status
    - Re-queues without duplicate sends
    """
    try:
        return await batch_engine.retry_failed_recipients(current_user.uid, campaign_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        log.error("Failed to retry campaign emails", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/{campaign_id}/reconcile", summary="Explicitly reconcile campaign state")
async def reconcile_campaign(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Force an immediate reconciliation of campaign counters and stuck leases."""
    camp = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not camp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found.")

    await reconciler.reconcile_campaign_on_activity(campaign_id)
    return firestore_service.get_campaign_stats(campaign_id, current_user.uid)
