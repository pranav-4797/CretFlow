"""Email sending tasks — Phase 10 implementation."""
from worker.celery_app import celery_app


@celery_app.task(
    name="worker.tasks.emails.send_certificate_email",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_certificate_email(self, email_log_id: str) -> dict:
    """
    Send a certificate email to a single participant.

    Phase 10: Will:
    1. Load email log and participant data.
    2. Check for duplicate sends (idempotency).
    3. Fetch the certificate PDF from R2.
    4. Send via Gmail API.
    5. Update email log status.
    6. Respect Gmail rate limits.
    """
    raise NotImplementedError(
        "Email sending will be implemented in Phase 10."
    )


@celery_app.task(
    name="worker.tasks.emails.send_campaign_emails",
    bind=True,
)
def send_campaign_emails(self, campaign_id: str) -> dict:
    """
    Trigger email sending for all participants in a campaign.
    Phase 10: Will create individual send tasks for each participant.
    Implements duplicate-send prevention using Redis locks.
    """
    raise NotImplementedError(
        "Bulk email sending will be implemented in Phase 10."
    )
