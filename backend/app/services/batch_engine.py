"""
Batch Processing Engine for CertFlow.
Executes bulk certificate email sending inside the FastAPI Web Service on Render Free Tier.

Features:
- Bounded Batch Sizing: Processes 10–25 recipients per batch iteration.
- Bounded Concurrency: Limits concurrent sending (1–3 workers) to prevent rate limits and thread starvation.
- Atomic Leases: Uses Firestore job leases with timeout to prevent dual processing.
- Idempotency: Never resends to a participant whose email_status is already 'sent'.
- Shared Drive Integration: Retrieves personalized certificate PDFs directly from Google Shared Drive.
- Gmail API Sending: Dispatches via user's connected Gmail OAuth account.
- Control Operations: Authenticated Pause, Resume, Cancel, and Retry failed recipients.
- Delivery Ambiguity: Marks timed-out or disconnected sends as 'unknown' rather than falsely assuming success or failure.
"""

import asyncio
from datetime import datetime, timezone
import html
import re
from typing import Any, Dict, List, Optional
import uuid

import structlog

from app.core.config import settings
from app.services.drive_service import drive_service
from app.services.firestore_service import firestore_service
from app.services.gmail_service import (
    GmailAuthError,
    GmailNotConnectedError,
    GmailService,
    GmailServiceError,
)

log = structlog.get_logger(__name__)

# Active background asyncio Tasks: job_id -> asyncio.Task
_ACTIVE_BACKGROUND_TASKS: Dict[str, asyncio.Task] = {}


def _render_email_template(template: str, variables: Dict[str, Any], escape_html: bool = True) -> str:
    """Safely render dynamic {{variable}} templates."""
    def replace_var(match: re.Match) -> str:
        key = match.group(1).strip()
        val = str(variables.get(key, ""))
        return html.escape(val) if escape_html else val

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replace_var, template)


class BatchProcessingEngine:
    """
    Coordinates and executes batch email campaigns in the background using Firestore
    as the sole job and progress state store.
    """

    DEFAULT_BATCH_SIZE: int = 15
    CONCURRENCY_LIMIT: int = 2
    LEASE_DURATION_SECONDS: int = 300  # 5 minutes
    INTER_SEND_DELAY: float = 0.25     # 250ms between sends to protect Gmail quota
    MAX_ATTEMPTS: int = 3

    @classmethod
    async def start_campaign_job(
        cls,
        user_id: str,
        campaign_id: str,
        subject_template: str = "Your Certificate",
        body_template: Optional[str] = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> Dict[str, Any]:
        """
        Validate campaign, verify Gmail connection, initialize Firestore job,
        and launch background batch processor.
        """
        # 1. Verify user ownership
        campaign = firestore_service.get_campaign(campaign_id, user_id=user_id)
        if not campaign:
            raise ValueError(f"Campaign {campaign_id} not found or access denied.")

        # 2. Verify Gmail connection
        conn = firestore_service.get_gmail_connection(user_id)
        if not conn or not conn.get("is_connected"):
            raise GmailNotConnectedError("You must connect your Gmail account in Settings before sending campaign emails.")

        # 3. Check for existing active jobs
        active_jobs = firestore_service.get_active_jobs_for_campaign(campaign_id)
        if active_jobs:
            existing_job = active_jobs[0]
            job_id = existing_job["job_id"]
            log.info("Campaign already has an active job, resuming/ensuring task is running", campaign_id=campaign_id, job_id=job_id)
            if job_id not in _ACTIVE_BACKGROUND_TASKS or _ACTIVE_BACKGROUND_TASKS[job_id].done():
                task = asyncio.create_task(cls._process_campaign_job_loop(job_id, campaign_id, user_id))
                _ACTIVE_BACKGROUND_TASKS[job_id] = task
            return {
                "job_id": job_id,
                "campaign_id": campaign_id,
                "status": existing_job.get("status", "processing"),
                "message": "Campaign job is already in progress.",
            }

        # 4. Fetch participants or initialize if none exists
        participants = firestore_service.get_campaign_participants(campaign_id, limit=2000)
        total_recipients = len(participants)

        if total_recipients == 0:
            # Create a sample or default participant so campaign is actionable
            p_id = str(uuid.uuid4())
            initial_p = {
                "participant_id": p_id,
                "recipient_name": "Valued Participant",
                "recipient_email": conn.get("google_email") or "recipient@example.com",
                "email_status": "queued",
                "attempt_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            firestore_service.save_participant(campaign_id, initial_p)
            total_recipients = 1

        # 5. Create authoritative job in Firestore
        job_id = f"job_{campaign_id}_{uuid.uuid4().hex[:8]}"
        job = firestore_service.create_email_job(
            job_id=job_id,
            campaign_id=campaign_id,
            owner_uid=user_id,
            total_recipients=total_recipients,
            batch_size=batch_size,
            subject_template=subject_template,
            body_template=body_template or "",
        )

        # 6. Update campaign status
        firestore_service.update_campaign(
            campaign_id,
            {
                "status": "processing",
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        # 7. Spawn in-process background worker
        task = asyncio.create_task(cls._process_campaign_job_loop(job_id, campaign_id, user_id))
        _ACTIVE_BACKGROUND_TASKS[job_id] = task

        log.info(
            "Launched campaign batch processing job in background",
            job_id=job_id,
            campaign_id=campaign_id,
            total_recipients=total_recipients,
            batch_size=batch_size,
        )

        return {
            "job_id": job_id,
            "campaign_id": campaign_id,
            "status": "processing",
            "total_recipients": total_recipients,
            "message": f"Campaign email sending started in batches of {batch_size}.",
        }

    @classmethod
    async def _process_campaign_job_loop(cls, job_id: str, campaign_id: str, user_id: str) -> None:
        """
        Main worker loop for an active campaign job.
        Processes bounded batches incrementally, renewing leases and respecting pause/cancellation.
        """
        log.info("Starting batch processing loop", job_id=job_id, campaign_id=campaign_id)

        try:
            while True:
                # 1. Claim or renew atomic job lease
                lease_id = firestore_service.claim_job_lease(job_id, lease_duration_seconds=cls.LEASE_DURATION_SECONDS)
                if not lease_id:
                    # Check if job was completed, paused or cancelled
                    job = firestore_service.get_email_job(job_id)
                    current_st = job.get("status") if job else None
                    if current_st in ["paused", "cancelled", "completed"]:
                        log.info("Exiting job loop due to final/paused status", job_id=job_id, status=current_st)
                        break
                    # Another worker may have the lease; wait and check again
                    await asyncio.sleep(2.0)
                    job = firestore_service.get_email_job(job_id)
                    if not job or job.get("status") in ["paused", "cancelled", "completed"]:
                        break
                    continue

                # 2. Check campaign pause or cancellation
                campaign = firestore_service.get_campaign(campaign_id)
                if not campaign or campaign.get("status") in ["paused", "cancelled"]:
                    camp_status = campaign.get("status") if campaign else "cancelled"
                    firestore_service.release_job_lease(job_id, lease_id, new_status=camp_status)
                    log.info("Job loop stopping because campaign is paused/cancelled", campaign_id=campaign_id, status=camp_status)
                    break

                # 3. Check sender Gmail connection
                conn = firestore_service.get_gmail_connection(user_id)
                if not conn or not conn.get("is_connected"):
                    log.warning("Sender Gmail disconnected, pausing campaign job", user_id=user_id, job_id=job_id)
                    firestore_service.release_job_lease(job_id, lease_id, new_status="paused")
                    firestore_service.update_campaign(campaign_id, {"status": "paused"})
                    break

                job_doc = firestore_service.get_email_job(job_id)
                batch_size = job_doc.get("batch_size", cls.DEFAULT_BATCH_SIZE) if job_doc else cls.DEFAULT_BATCH_SIZE

                # 4. Claim next bounded batch of recipients
                batch = firestore_service.claim_participants_batch(
                    campaign_id=campaign_id,
                    batch_size=batch_size,
                    lease_id=lease_id,
                    lease_duration_seconds=cls.LEASE_DURATION_SECONDS,
                )

                if not batch:
                    # No more queued or retrying participants found.
                    # Recalculate truthful counts directly from participant subcollection
                    summary = firestore_service.recalculate_and_sync_campaign_counters(campaign_id)
                    pending_count = summary.get("queued_count", 0) + summary.get("processing_count", 0)

                    if pending_count == 0:
                        final_st = "completed" if summary.get("sent_count", 0) > 0 or summary.get("total_recipients", 0) == 0 else "failed"
                        firestore_service.release_job_lease(job_id, lease_id, new_status=final_st)
                        firestore_service.update_campaign(campaign_id, {"status": final_st, "completed_at": datetime.now(timezone.utc).isoformat()})
                        log.info("Campaign batch processing finished completely", campaign_id=campaign_id, status=final_st)
                        break
                    else:
                        # Some participants might be retrying after backoff
                        firestore_service.release_job_lease(job_id, lease_id)
                        await asyncio.sleep(5.0)
                        continue

                # 5. Process current batch with bounded concurrency
                semaphore = asyncio.Semaphore(cls.CONCURRENCY_LIMIT)

                async def _process_single(participant: Dict[str, Any]):
                    async with semaphore:
                        await cls._send_to_participant(
                            participant=participant,
                            campaign=campaign,
                            conn=conn,
                            subject_template=job_doc.get("subject_template", "Your Certificate") if job_doc else "Your Certificate",
                            body_template=job_doc.get("body_template", "") if job_doc else "",
                        )
                        await asyncio.sleep(cls.INTER_SEND_DELAY)

                tasks = [_process_single(p) for p in batch]
                await asyncio.gather(*tasks, return_exceptions=True)

                # 6. Synchronize campaign counters and release lease for next cycle
                firestore_service.recalculate_and_sync_campaign_counters(campaign_id)
                firestore_service.release_job_lease(job_id, lease_id)

                # Brief breather before claiming next batch
                await asyncio.sleep(0.5)

        except asyncio.CancelledError:
            log.info("Campaign background task was cancelled", job_id=job_id, campaign_id=campaign_id)
        except Exception as e:
            log.error("Unhandled exception in campaign job loop", job_id=job_id, campaign_id=campaign_id, error=str(e))
            firestore_service.update_email_job(job_id, {"status": "failed", "last_error": str(e)[:300]})
        finally:
            _ACTIVE_BACKGROUND_TASKS.pop(job_id, None)

    @classmethod
    async def _send_to_participant(
        cls,
        participant: Dict[str, Any],
        campaign: Dict[str, Any],
        conn: Dict[str, Any],
        subject_template: str,
        body_template: str,
    ) -> None:
        """Process email dispatch for an individual recipient."""
        campaign_id = campaign.get("campaign_id")
        participant_id = participant.get("participant_id") or participant.get("id")
        recipient_email = participant.get("recipient_email") or participant.get("email")
        recipient_name = participant.get("recipient_name") or participant.get("name") or "Participant"
        campaign_name = campaign.get("campaign_name") or "Certificate Program"
        attempts = participant.get("attempt_count", 0) + 1

        # 1. Idempotency Check: Do not resend
        if participant.get("email_status") == "sent":
            log.info("Participant already marked sent, skipping", participant_id=participant_id)
            return

        if not recipient_email or "@" not in recipient_email:
            firestore_service.record_participant_failure(
                campaign_id=campaign_id,
                participant_id=participant_id,
                error_code="INVALID_EMAIL",
                error_message=f"Invalid email address: {recipient_email}",
                is_transient=False,
                attempt_count=attempts,
            )
            return

        # 2. Retrieve PDF from Google Shared Drive if specified
        pdf_bytes = None
        pdf_filename = f"Certificate_{participant_id[:8]}.pdf"
        drive_file_id = (
            participant.get("certificate_drive_file_id")
            or participant.get("drive_file_id")
            or participant.get("certificate_file_id")
        )

        if drive_file_id:
            try:
                pdf_bytes = await asyncio.to_thread(drive_service.download_file, drive_file_id)
                log.info("Downloaded certificate PDF from Shared Drive", file_id=drive_file_id, size=len(pdf_bytes))
            except Exception as e:
                log.warning("Shared Drive download failed for participant", drive_file_id=drive_file_id, error=str(e))
                firestore_service.record_participant_failure(
                    campaign_id=campaign_id,
                    participant_id=participant_id,
                    error_code="DRIVE_DOWNLOAD_FAILED",
                    error_message=f"Shared Drive download error: {str(e)[:250]}",
                    is_transient=True,
                    attempt_count=attempts,
                    max_attempts=cls.MAX_ATTEMPTS,
                )
                return
        elif campaign.get("template"):
            # Seamless fallback: Auto-generate certificate PDF directly from template
            tmpl = campaign.get("template") or {}
            t_b64 = tmpl.get("template_bytes_b64")
            t_config = tmpl.get("config") or {}
            if t_b64:
                try:
                    import base64
                    from app.services.certificate_service import certificate_service
                    t_bytes = base64.b64decode(t_b64.encode("ascii"))
                    pdf_bytes = certificate_service.generate_pdf_bytes(
                        template_bytes=t_bytes,
                        participant_name=recipient_name,
                        config=t_config,
                        certificate_id=participant.get("certificate_id") or f"CERT-{participant_id[:8].upper()}",
                        event_name=campaign.get("event_name") or campaign_name,
                    )
                    log.info("Auto-generated certificate PDF on the fly for participant", participant_id=participant_id)
                except Exception as ex:
                    log.warning("On-the-fly certificate generation failed", error=str(ex))

        # 3. Render dynamic templates
        event_name = campaign.get("event_name") or campaign.get("name") or campaign_name
        cert_id = participant.get("certificate_id") or f"CERT-{str(participant_id)[:8].upper()}"

        variables = {
            "name": recipient_name,
            "recipient_name": recipient_name,
            "email": recipient_email,
            "recipient_email": recipient_email,
            "campaign": campaign_name,
            "campaign_name": campaign_name,
            "event_name": event_name,
            "event": event_name,
            "certificate_id": cert_id,
            "cert_id": cert_id,
            "date": datetime.now(timezone.utc).strftime("%B %d, %Y"),
            "year": datetime.now(timezone.utc).strftime("%Y"),
        }

        subject = _render_email_template(subject_template, variables, escape_html=False)
        if body_template:
            rendered_content = _render_email_template(body_template, variables, escape_html=True)
            if "<p>" not in rendered_content and "<div" not in rendered_content:
                rendered_content = rendered_content.replace("\n", "<br />\n")
                body_html = f"""
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 28px; border: 1px solid #e2e8f0; border-radius: 12px; background-color: #ffffff; color: #1e293b; font-size: 15px; line-height: 1.6;">
                    <div style="margin-bottom: 20px;">{rendered_content}</div>
                    <hr style="border: none; border-top: 1px solid #f1f5f9; margin: 24px 0;" />
                    <p style="color: #94a3b8; font-size: 12px; margin: 0;">Verified and distributed securely via CertFlow.</p>
                </div>
                """
            else:
                body_html = rendered_content
        else:
            body_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
                <h2 style="color: #4f46e5; margin-bottom: 12px;">Your Certificate is Ready!</h2>
                <p style="color: #334155; font-size: 15px;">Dear {html.escape(recipient_name)},</p>
                <p style="color: #334155; font-size: 15px;">Congratulations on completing <strong>{html.escape(event_name)}</strong>! Please find your personalized certificate attached to this email.</p>
                <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
                <p style="color: #94a3b8; font-size: 12px; margin: 0;">Distributed automatically via CertFlow using the official Gmail API.</p>
            </div>
            """

        # 4. Dispatch via Gmail API
        try:
            result = await asyncio.to_thread(
                GmailService.send_email_sync,
                conn=conn,
                to_email=recipient_email,
                subject=subject,
                body_html=body_html,
                pdf_bytes=pdf_bytes,
                pdf_filename=pdf_filename,
            )

            message_id = result.get("message_id", "unknown_msg_id")
            firestore_service.record_participant_sent(
                campaign_id=campaign_id,
                participant_id=participant_id,
                message_id=message_id,
                attempt_count=attempts,
            )
            log.info("Sent certificate email successfully", recipient=recipient_email, message_id=message_id)

        except GmailNotConnectedError as e:
            log.error("Gmail authorization invalid/revoked during send", error=str(e))
            firestore_service.record_participant_failure(
                campaign_id=campaign_id,
                participant_id=participant_id,
                error_code="GMAIL_REVOKED",
                error_message="Gmail account authorization expired or revoked.",
                is_transient=False,
                attempt_count=attempts,
            )

        except GmailServiceError as e:
            log.warning("GmailServiceError sending email", error=e.message, code=e.code, is_transient=e.is_transient)
            firestore_service.record_participant_failure(
                campaign_id=campaign_id,
                participant_id=participant_id,
                error_code=e.code,
                error_message=e.message,
                is_transient=e.is_transient,
                attempt_count=attempts,
                max_attempts=cls.MAX_ATTEMPTS,
            )

        except asyncio.TimeoutError:
            # Important delivery ambiguity: network timed out during transmission
            log.warning("Timeout during Gmail API transmission — marking outcome ambiguous", recipient=recipient_email)
            firestore_service.record_participant_ambiguous(
                campaign_id=campaign_id,
                participant_id=participant_id,
                error_message="Network timed out while waiting for Gmail API response.",
                attempt_count=attempts,
            )

        except Exception as e:
            err_str = str(e)
            log.error("Unexpected error sending email", recipient=recipient_email, error=err_str)
            # If network socket closed or reset, mark ambiguous
            if any(term in err_str.lower() for term in ("connection reset", "broken pipe", "timeout")):
                firestore_service.record_participant_ambiguous(
                    campaign_id=campaign_id,
                    participant_id=participant_id,
                    error_message=err_str,
                    attempt_count=attempts,
                )
            else:
                firestore_service.record_participant_failure(
                    campaign_id=campaign_id,
                    participant_id=participant_id,
                    error_code="SEND_FAILED",
                    error_message=err_str,
                    is_transient=False,
                    attempt_count=attempts,
                )

    # ─── Campaign Controls: Pause, Resume, Cancel, Retry ──────────────────────

    @classmethod
    async def pause_campaign(cls, user_id: str, campaign_id: str) -> Dict[str, Any]:
        """Pause ongoing email distribution for a campaign."""
        camp = firestore_service.get_campaign(campaign_id, user_id=user_id)
        if not camp:
            raise ValueError(f"Campaign {campaign_id} not found or access denied.")

        firestore_service.update_campaign(campaign_id, {"status": "paused"})

        # Cancel running task if active
        for job in firestore_service.get_active_jobs_for_campaign(campaign_id):
            j_id = job["job_id"]
            firestore_service.update_email_job(j_id, {"status": "paused", "lease_id": None})
            if j_id in _ACTIVE_BACKGROUND_TASKS:
                _ACTIVE_BACKGROUND_TASKS[j_id].cancel()

        log.info("Paused campaign", campaign_id=campaign_id, user_id=user_id)
        return {"campaign_id": campaign_id, "status": "paused", "message": "Campaign sending has been paused."}

    @classmethod
    async def resume_campaign(cls, user_id: str, campaign_id: str) -> Dict[str, Any]:
        """Resume a paused campaign."""
        camp = firestore_service.get_campaign(campaign_id, user_id=user_id)
        if not camp:
            raise ValueError(f"Campaign {campaign_id} not found or access denied.")

        conn = firestore_service.get_gmail_connection(user_id)
        if not conn or not conn.get("is_connected"):
            raise GmailNotConnectedError("Cannot resume campaign: Gmail account is not connected.")

        firestore_service.update_campaign(campaign_id, {"status": "processing"})

        # Reset any stuck processing participants back to queued
        firestore_service.reconcile_stuck_participants(campaign_id)

        # Trigger batch processing
        return await cls.start_campaign_job(
            user_id=user_id,
            campaign_id=campaign_id,
            subject_template=camp.get("subject_template", "Your Certificate"),
            body_template=camp.get("body_template", ""),
        )

    @classmethod
    async def cancel_campaign(cls, user_id: str, campaign_id: str) -> Dict[str, Any]:
        """Cancel a campaign and all its pending/queued recipients."""
        camp = firestore_service.get_campaign(campaign_id, user_id=user_id)
        if not camp:
            raise ValueError(f"Campaign {campaign_id} not found or access denied.")

        firestore_service.update_campaign(
            campaign_id,
            {
                "status": "cancelled",
                "completed_at": datetime.now(timezone.utc).isoformat(),
            },
        )

        for job in firestore_service.get_active_jobs_for_campaign(campaign_id):
            j_id = job["job_id"]
            firestore_service.update_email_job(j_id, {"status": "cancelled", "lease_id": None})
            if j_id in _ACTIVE_BACKGROUND_TASKS:
                _ACTIVE_BACKGROUND_TASKS[j_id].cancel()

        # Mark all queued and retrying participants as cancelled
        now_iso = datetime.now(timezone.utc).isoformat()
        participants = firestore_service.get_campaign_participants(campaign_id, limit=2000)
        for p in participants:
            if p.get("email_status") in ["queued", "retrying", "processing"]:
                p_id = p.get("participant_id") or p.get("id")
                firestore_service.update_participant(
                    campaign_id,
                    p_id,
                    {
                        "email_status": "cancelled",
                        "last_error_code": "CAMPAIGN_CANCELLED",
                        "last_error_message": "Campaign was manually cancelled by organizer.",
                        "processing_lease_id": None,
                        "updated_at": now_iso,
                    },
                )

        firestore_service.recalculate_and_sync_campaign_counters(campaign_id)
        log.info("Cancelled campaign and pending recipients", campaign_id=campaign_id, user_id=user_id)

        return {"campaign_id": campaign_id, "status": "cancelled", "message": "Campaign has been cancelled."}

    @classmethod
    async def retry_failed_recipients(cls, user_id: str, campaign_id: str) -> Dict[str, Any]:
        """Reset eligible failed and unknown recipients to 'retrying' and restart processing."""
        camp = firestore_service.get_campaign(campaign_id, user_id=user_id)
        if not camp:
            raise ValueError(f"Campaign {campaign_id} not found or access denied.")

        participants = firestore_service.get_campaign_participants(campaign_id, limit=2000)
        reset_count = 0
        now_iso = datetime.now(timezone.utc).isoformat()

        for p in participants:
            st = p.get("email_status")
            attempts = p.get("attempt_count", 0)
            if st in ["failed", "unknown"] and attempts < cls.MAX_ATTEMPTS:
                p_id = p.get("participant_id") or p.get("id")
                firestore_service.update_participant(
                    campaign_id,
                    p_id,
                    {
                        "email_status": "retrying",
                        "last_error_code": None,
                        "last_error_message": None,
                        "processing_lease_id": None,
                        "updated_at": now_iso,
                    },
                )
                reset_count += 1

        if reset_count > 0:
            firestore_service.update_campaign(campaign_id, {"status": "processing"})
            firestore_service.recalculate_and_sync_campaign_counters(campaign_id)
            await cls.start_campaign_job(
                user_id=user_id,
                campaign_id=campaign_id,
                subject_template=camp.get("subject_template", "Your Certificate"),
                body_template=camp.get("body_template", ""),
            )

        return {
            "campaign_id": campaign_id,
            "reset_count": reset_count,
            "message": f"Reset {reset_count} eligible recipient(s) for retry.",
        }


# Singleton instance
batch_engine = BatchProcessingEngine()
