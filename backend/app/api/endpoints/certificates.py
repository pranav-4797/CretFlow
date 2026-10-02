"""Certificate generation endpoints."""
import asyncio
import base64
import io
from typing import Any, Dict

import structlog
from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.template import GenerateCertificatesRequest, GenerateCertificatesResponse
from app.services.certificate_service import certificate_service
from app.services.drive_service import drive_service
from app.services.firestore_service import firestore_service

router = APIRouter()
log = structlog.get_logger(__name__)


@router.post("/{campaign_id}/generate", response_model=GenerateCertificatesResponse, summary="Trigger bulk certificate generation")
async def generate_certificates(
    campaign_id: str,
    req: GenerateCertificatesRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    template_data = campaign.get("template") or {}
    b64_bytes = template_data.get("template_bytes_b64")
    config = template_data.get("config") or {}

    template_bytes = None
    if b64_bytes:
        template_bytes = base64.b64decode(b64_bytes.encode("ascii"))
    elif template_data.get("template_drive_file_id"):
        try:
            template_bytes = drive_service.download_file(template_data["template_drive_file_id"])
        except Exception as e:
            log.error("Failed to download template image from Drive", error=str(e))

    if not template_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign does not have a certificate template uploaded. Please upload a template in Certificate Studio first.",
        )

    # Fetch all participants
    participants = firestore_service.get_campaign_participants(campaign_id, limit=3000)
    if not participants:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Campaign has no participants. Please upload a participant spreadsheet first.",
        )

    # Ensure Google Shared Drive folders exist
    cert_folder_id = None
    try:
        folders = drive_service.ensure_campaign_folders(campaign_id, campaign.get("campaign_name", "Campaign"))
        cert_folder_id = folders.get("certificates")
    except Exception as e:
        log.warning("Shared Drive folders could not be verified, will attempt direct upload", error=str(e))

    generated_count = 0
    skipped_count = 0
    failed_count = 0

    event_name = campaign.get("event_name") or campaign.get("name") or campaign.get("campaign_name", "Event")

    for p in participants:
        p_id = p.get("participant_id") or p.get("id")
        p_name = p.get("recipient_name") or p.get("name") or "Participant"
        cert_id = p.get("certificate_id") or f"CERT-{p_id[:8].upper()}"

        # If already generated and not overriding
        if not req.override_existing and p.get("certificate_drive_file_id"):
            skipped_count += 1
            continue

        try:
            # Generate PDF
            pdf_bytes = certificate_service.generate_pdf_bytes(
                template_bytes=template_bytes,
                participant_name=p_name,
                config=config,
                certificate_id=cert_id,
                event_name=event_name,
            )

            # Upload to Google Shared Drive
            clean_pname = "".join(c for c in p_name if c.isalnum() or c in (" ", "_", "-")).strip()
            pdf_filename = f"Certificate_{cert_id}_{clean_pname}.pdf"

            drive_file_id = None
            web_link = None
            try:
                drive_res = drive_service.upload_file(
                    file_content=pdf_bytes,
                    filename=pdf_filename,
                    parent_folder_id=cert_folder_id,
                    mime_type="application/pdf",
                )
                drive_file_id = drive_res.get("id")
                web_link = drive_res.get("webViewLink")
            except Exception as e:
                log.warning("Drive upload failed for single certificate", participant_id=p_id, error=str(e))

            # Update participant in Firestore
            firestore_service.update_participant(
                campaign_id,
                p_id,
                {
                    "certificate_id": cert_id,
                    "certificate_drive_file_id": drive_file_id,
                    "certificate_filename": pdf_filename,
                    "drive_web_view_link": web_link,
                    "status": "generated",
                },
            )
            generated_count += 1
        except Exception as e:
            log.error("Failed to generate certificate for participant", participant_id=p_id, error=str(e))
            failed_count += 1

    return GenerateCertificatesResponse(
        campaign_id=campaign_id,
        total_participants=len(participants),
        generated_count=generated_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        message=f"Successfully generated {generated_count} personalized certificates in Google Shared Drive.",
    )


@router.get("/{campaign_id}/sample-pdf", summary="Download sample generated certificate PDF")
async def download_sample_pdf(
    campaign_id: str,
    name: str = "Jane Doe",
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    template_data = campaign.get("template") or {}
    b64_bytes = template_data.get("template_bytes_b64")
    config = template_data.get("config") or {}

    if not b64_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No certificate template uploaded yet.")

    template_bytes = base64.b64decode(b64_bytes.encode("ascii"))
    event_name = campaign.get("event_name") or campaign.get("campaign_name", "Event")

    pdf_bytes = certificate_service.generate_pdf_bytes(
        template_bytes=template_bytes,
        participant_name=name,
        config=config,
        certificate_id="CERT-SAMPLE-001",
        event_name=event_name,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="Sample_Certificate_{name}.pdf"'},
    )
