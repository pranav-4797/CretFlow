"""Webhook endpoints for external integrations (Google Forms, Quizzes, LMS)."""
import asyncio
import base64
import html
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

import structlog
from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import settings
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.webhook import (
    CampaignWebhookConfig,
    GoogleFormWebhookPayload,
    GoogleFormWebhookResponse,
)
from app.services.certificate_service import certificate_service
from app.services.drive_service import drive_service
from app.services.firestore_service import firestore_service
from app.services.gmail_service import GmailService

router = APIRouter()
log = structlog.get_logger(__name__)


@router.post(
    "/google-form/{campaign_id}",
    response_model=GoogleFormWebhookResponse,
    summary="Process Google Form Quiz submission and auto-issue certificate",
)
async def process_google_form_submission(
    campaign_id: str,
    payload: GoogleFormWebhookPayload,
):
    """
    Public webhook receiver for Google Forms / Google Apps Script quiz submissions.
    - Evaluates student score against campaign passing threshold
    - If score passes:
        1. Automatically renders personalized certificate PDF
        2. Saves PDF to Google Shared Drive (or fallback storage)
        3. Immediately emails certificate to student via organizer's Gmail account
    - If score fails:
        Records submission without dispatching certificate
    """
    campaign = firestore_service.get_campaign(campaign_id)
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found.",
        )

    # 1. Secret token validation (if campaign requires it)
    required_secret = campaign.get("webhook_secret")
    if required_secret and payload.webhook_secret != required_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook secret token.",
        )

    # 2. Score calculation
    total_score = payload.total_score if payload.total_score > 0 else 100.0
    score_pct = round((payload.score / total_score) * 100.0, 1)

    threshold = (
        payload.passing_score
        if payload.passing_score is not None
        else float(campaign.get("passing_score", 60.0))
    )

    passed = score_pct >= threshold

    participant_id = f"p_{uuid.uuid4().hex[:12]}"
    cert_id = f"CERT-{uuid.uuid4().hex[:8].upper()}"
    event_name = campaign.get("event_name") or campaign.get("name") or campaign.get("campaign_name", "Assessment")

    participant_data: Dict[str, Any] = {
        "participant_id": participant_id,
        "recipient_name": payload.recipient_name,
        "recipient_email": str(payload.recipient_email),
        "score": score_pct,
        "raw_score": payload.score,
        "total_score": total_score,
        "passing_threshold": threshold,
        "passed": passed,
        "source": "google_form",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if not passed:
        participant_data["email_status"] = "not_qualified"
        participant_data["status"] = "below_threshold"
        firestore_service.save_participant(campaign_id, participant_data)
        log.info(
            "Student quiz submission did not meet passing threshold",
            campaign_id=campaign_id,
            student=payload.recipient_name,
            score=score_pct,
            threshold=threshold,
        )
        return GoogleFormWebhookResponse(
            status="below_threshold",
            campaign_id=campaign_id,
            recipient_name=payload.recipient_name,
            recipient_email=str(payload.recipient_email),
            score=payload.score,
            total_score=total_score,
            score_percentage=score_pct,
            passing_threshold_percentage=threshold,
            passed=False,
            certificate_id=None,
            email_sent=False,
            message=f"Score {score_pct}% is below passing threshold of {threshold}%. No certificate issued.",
        )

    # 3. Passed! Generate Certificate PDF
    template_data = campaign.get("template") or {}
    b64_bytes = template_data.get("template_bytes_b64")
    config = template_data.get("config") or {}

    pdf_bytes = None
    if b64_bytes:
        try:
            t_bytes = base64.b64decode(b64_bytes.encode("ascii"))
            pdf_bytes = certificate_service.generate_pdf_bytes(
                template_bytes=t_bytes,
                participant_name=payload.recipient_name,
                config=config,
                certificate_id=cert_id,
                event_name=event_name,
            )
        except Exception as e:
            log.warning("Certificate PDF rendering failed from template", error=str(e))

    # 4. Save to Google Shared Drive (or document storage)
    drive_file_id = None
    web_link = None
    pdf_filename = f"Certificate_{cert_id}_{payload.recipient_name}.pdf"

    if pdf_bytes:
        try:
            folders = drive_service.ensure_campaign_folders(campaign_id, event_name)
            cert_folder_id = folders.get("certificates")
            if cert_folder_id:
                drive_res = drive_service.upload_file(
                    file_content=pdf_bytes,
                    filename=pdf_filename,
                    parent_folder_id=cert_folder_id,
                    mime_type="application/pdf",
                )
                drive_file_id = drive_res.get("id")
                web_link = drive_res.get("webViewLink")
        except Exception as e:
            log.warning("Could not upload certificate to Shared Drive", error=str(e))

    participant_data["certificate_id"] = cert_id
    participant_data["certificate_filename"] = pdf_filename
    participant_data["status"] = "generated"
    if drive_file_id:
        participant_data["certificate_drive_file_id"] = drive_file_id
        participant_data["drive_web_view_link"] = web_link
    elif pdf_bytes:
        participant_data["certificate_bytes_b64"] = base64.b64encode(pdf_bytes).decode("ascii")

    # 5. Automated Email Dispatch via Gmail API
    email_sent = False
    owner_uid = campaign.get("owner_uid") or campaign.get("userId")
    auto_email_enabled = campaign.get("auto_email", True)

    if auto_email_enabled and owner_uid:
        conn = firestore_service.get_gmail_connection(owner_uid)
        if conn and conn.get("is_connected"):
            try:
                custom_subject = campaign.get("quiz_email_subject")
                custom_body = campaign.get("quiz_email_body")
                show_score = campaign.get("show_score_in_email", True)

                placeholders = {
                    "{{name}}": html.escape(payload.recipient_name),
                    "{{event_name}}": html.escape(event_name),
                    "{{score}}": str(payload.score),
                    "{{total_score}}": str(total_score),
                    "{{score_percentage}}": f"{score_pct}%",
                    "{{certificate_id}}": cert_id,
                }

                if custom_subject and custom_subject.strip():
                    subject = custom_subject.strip()
                    for ph, val in placeholders.items():
                        subject = subject.replace(ph, val)
                else:
                    subject = f"Congratulations on Passing {event_name}! Here is your Certificate"

                if custom_body and custom_body.strip():
                    rendered_body = html.escape(custom_body.strip())
                    for ph, val in placeholders.items():
                        rendered_body = rendered_body.replace(ph, val)
                    rendered_body_paragraphs = "".join(
                        f"<p style='font-size: 15px; line-height: 1.6; color: #334155; margin-bottom: 12px;'>{p}</p>"
                        for p in rendered_body.split("\n") if p.strip()
                    )
                else:
                    rendered_body_paragraphs = f"""
                    <p style="font-size: 15px; line-height: 1.6; color: #334155;">
                        You have successfully passed the assessment for <strong>{html.escape(event_name)}</strong>!
                    </p>
                    <p style="font-size: 14px; color: #334155;">
                        Your official certificate has been generated and is attached to this email as a high-resolution PDF.
                    </p>
                    """

                if show_score:
                    score_card_html = f"""
                    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 20px 0;">
                        <p style="margin: 0 0 6px 0; font-size: 14px; color: #64748b;"><strong>Score:</strong> {payload.score} / {total_score} ({score_pct}%)</p>
                        <p style="margin: 0; font-size: 14px; color: #64748b;"><strong>Certificate ID:</strong> {cert_id}</p>
                    </div>
                    """
                else:
                    score_card_html = f"""
                    <div style="background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 16px; margin: 20px 0;">
                        <p style="margin: 0; font-size: 14px; color: #64748b;"><strong>Certificate ID:</strong> {cert_id}</p>
                    </div>
                    """

                body_html = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 12px; background: #ffffff; color: #1e293b;">
                    <h2 style="color: #4f46e5; margin-bottom: 16px;">Congratulations, {html.escape(payload.recipient_name)}! 🎓</h2>
                    {rendered_body_paragraphs}
                    {score_card_html}
                    <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;" />
                    <p style="font-size: 12px; color: #94a3b8; margin: 0;">Verified and distributed automatically via CertFlow.</p>
                </div>
                """
                send_res = await asyncio.to_thread(
                    GmailService.send_email_sync,
                    conn=conn,
                    to_email=str(payload.recipient_email),
                    subject=subject,
                    body_html=body_html,
                    pdf_bytes=pdf_bytes,
                    pdf_filename=pdf_filename,
                )
                email_sent = True
                participant_data["email_status"] = "sent"
                participant_data["gmail_message_id"] = send_res.get("message_id")
                log.info("Dispatched automated quiz certificate email", student=payload.recipient_name, email=payload.recipient_email)
            except Exception as e:
                log.error("Failed to dispatch automated certificate email", error=str(e))
                participant_data["email_status"] = "failed"
                participant_data["email_error"] = str(e)[:250]
        else:
            participant_data["email_status"] = "queued"
    else:
        participant_data["email_status"] = "queued"

    firestore_service.save_participant(campaign_id, participant_data)
    firestore_service.recalculate_and_sync_campaign_counters(campaign_id)

    return GoogleFormWebhookResponse(
        status="issued",
        campaign_id=campaign_id,
        recipient_name=payload.recipient_name,
        recipient_email=str(payload.recipient_email),
        score=payload.score,
        total_score=total_score,
        score_percentage=score_pct,
        passing_threshold_percentage=threshold,
        passed=True,
        certificate_id=cert_id,
        email_sent=email_sent,
        message=f"Congratulations! Certificate issued for {payload.recipient_name} ({score_pct}%). "
        + ("Email sent successfully with PDF attached." if email_sent else "Saved in queue."),
    )


@router.get("/config/{campaign_id}", response_model=CampaignWebhookConfig, summary="Get campaign webhook configuration")
async def get_webhook_config(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    return CampaignWebhookConfig(
        passing_score=float(campaign.get("passing_score", 60.0)),
        auto_email=bool(campaign.get("auto_email", True)),
        webhook_secret=campaign.get("webhook_secret"),
        quiz_email_subject=campaign.get("quiz_email_subject"),
        quiz_email_body=campaign.get("quiz_email_body"),
        show_score_in_email=bool(campaign.get("show_score_in_email", True)),
    )


@router.put("/config/{campaign_id}", summary="Update campaign webhook configuration")
async def update_webhook_config(
    campaign_id: str,
    config: CampaignWebhookConfig,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    firestore_service.update_campaign(
        campaign_id,
        {
            "passing_score": config.passing_score,
            "auto_email": config.auto_email,
            "webhook_secret": config.webhook_secret,
            "quiz_email_subject": config.quiz_email_subject,
            "quiz_email_body": config.quiz_email_body,
            "show_score_in_email": config.show_score_in_email,
        },
    )

    return {"success": True, "message": "Google Forms webhook configuration updated successfully."}
