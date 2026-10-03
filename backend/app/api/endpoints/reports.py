"""
Reports & Analytics API Endpoints.
Provides dashboard metrics, campaign performance stats, and CSV exports.
"""
import csv
import io
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from app.core.security import AuthenticatedUser, get_current_user
from app.services.firestore_service import firestore_service

router = APIRouter()


@router.get("/dashboard", summary="Get overall user dashboard analytics")
async def get_dashboard_analytics(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Returns aggregated dashboard metrics:
    - total_campaigns
    - total_participants
    - certificates_generated
    - emails_sent
    - recent_campaigns
    """
    return firestore_service.get_user_analytics(current_user.uid)


@router.get("/{campaign_id}", summary="Get campaign distribution report")
async def get_campaign_report(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retrieve detailed distribution breakdown for a specific campaign."""
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found.",
        )

    participants = firestore_service.get_campaign_participants(campaign_id, limit=200)

    total_recipients = len(participants) or int(campaign.get("total_recipients", 0))
    sent_count = sum(1 for p in participants if p.get("email_status") == "sent")
    failed_count = sum(1 for p in participants if p.get("email_status") == "failed")
    queued_count = sum(1 for p in participants if p.get("email_status") in ["queued", "pending"])
    cert_count = sum(1 for p in participants if p.get("certificate_id") or p.get("status") == "generated")

    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign.get("campaign_name") or campaign.get("name"),
        "status": campaign.get("status", "draft"),
        "total_recipients": total_recipients,
        "sent_count": sent_count,
        "failed_count": failed_count,
        "queued_count": queued_count,
        "certificates_generated": cert_count,
        "delivery_rate": round((sent_count / total_recipients * 100.0), 1) if total_recipients > 0 else 0.0,
        "created_at": campaign.get("created_at"),
    }


@router.get("/{campaign_id}/export", summary="Export report as CSV")
async def export_report(
    campaign_id: str,
    format: str = Query("csv", pattern="^(csv|json)$"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Export campaign participants and issuance data as a CSV download."""
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found.",
        )

    participants = firestore_service.get_campaign_participants(campaign_id, limit=1000)

    if format == "json":
        return {"campaign_id": campaign_id, "participants": participants}

    # Generate CSV in-memory
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Recipient Name",
        "Recipient Email",
        "Certificate ID",
        "Status",
        "Email Status",
        "Score",
        "Sent At",
        "Drive Link",
    ])

    for p in participants:
        writer.writerow([
            p.get("recipient_name", ""),
            p.get("recipient_email", ""),
            p.get("certificate_id", ""),
            p.get("status", ""),
            p.get("email_status", ""),
            f"{p.get('score', '')}%" if p.get("score") is not None else "",
            p.get("sent_at", ""),
            p.get("drive_web_view_link", ""),
        ])

    csv_data = output.getvalue()
    filename = f"report_{campaign_id}.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
