"""
Gmail OAuth and API route handlers using Firestore and BatchProcessingEngine.
Zero SQLAlchemy, Celery, or Redis dependencies.
"""

import html
import re
from typing import Any, Dict, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import RedirectResponse

from app.core.config import settings
from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.gmail import (
    GmailConnectResponse,
    GmailDisconnectResponse,
    GmailStatusResponse,
    GmailTestEmailRequest,
    GmailTestEmailResponse,
    SendCampaignRequest,
    SendCampaignResponse,
    SendPreviewRequest,
    SendPreviewResponse,
)
from app.services.batch_engine import batch_engine
from app.services.firestore_service import firestore_service
from app.services.gmail_service import (
    GmailAuthError,
    GmailNotConnectedError,
    GmailService,
    GmailServiceError,
)

log = structlog.get_logger(__name__)

router = APIRouter()


def _render_template(template: str, variables: Dict[str, Any], escape_html: bool = True) -> str:
    """Safely render dynamic {{variable}} templates."""
    def replace_var(match: re.Match) -> str:
        key = match.group(1).strip()
        val = str(variables.get(key, ""))
        return html.escape(val) if escape_html else val

    return re.sub(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}", replace_var, template)


@router.get("/connect", response_model=GmailConnectResponse, summary="Initiate Gmail OAuth flow")
async def gmail_connect(
    request: Request,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Generate a cryptographically secure, signed OAuth state and return
    the Google OAuth 2.0 authorization URL.
    """
    backend_base = str(request.base_url).rstrip("/")
    if request.headers.get("x-forwarded-proto") == "https" and backend_base.startswith("http://"):
        backend_base = backend_base.replace("http://", "https://", 1)

    # If running locally, default to the local callback URL; otherwise use production redirect URI
    if "localhost" in backend_base or "127.0.0.1" in backend_base:
        redirect_uri = f"{backend_base}/api/gmail/callback"
    else:
        redirect_uri = settings.effective_gmail_redirect_uri

    auth_url = GmailService.get_authorization_url(user_id=current_user.uid, redirect_uri=redirect_uri)
    return GmailConnectResponse(authorization_url=auth_url)


@router.get("/callback", summary="Gmail OAuth callback")
@router.get("/oauth/callback", include_in_schema=False)
async def gmail_oauth_callback(
    request: Request,
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """
    Handle Google OAuth 2.0 callback:
    - Validate signed OAuth state
    - Exchange code for tokens
    - Encrypt and store refresh token in Firestore
    - Redirect user back to CertFlow settings
    """
    frontend_base = settings.frontend_url.rstrip("/")

    from urllib.parse import quote

    # User denied consent or error occurred at Google
    if error:
        log.warning("Google OAuth callback returned error", error=error)
        safe_error = quote(error[:100])
        return RedirectResponse(
            url=f"{frontend_base}/settings?gmail_status=error&error_code={safe_error}",
            status_code=status.HTTP_302_FOUND,
        )

    if not code or not state:
        log.warning("OAuth callback missing code or state")
        return RedirectResponse(
            url=f"{frontend_base}/settings?gmail_status=error&error_code=MISSING_PARAMETERS",
            status_code=status.HTTP_302_FOUND,
        )

    # Determine incoming callback URL to ensure exact redirect_uri match with Google
    callback_url = str(request.url).split("?")[0]
    if request.headers.get("x-forwarded-proto") == "https" and callback_url.startswith("http://"):
        callback_url = callback_url.replace("http://", "https://", 1)

    try:
        connection = await GmailService.exchange_code_for_tokens(
            code=code,
            state=state,
            redirect_uri=callback_url,
        )
        google_email = quote(connection.get("google_email", ""))
        return RedirectResponse(
            url=f"{frontend_base}/settings?gmail_status=connected&email={google_email}",
            status_code=status.HTTP_302_FOUND,
        )
    except GmailAuthError as e:
        log.error("OAuth authentication error during code exchange", code=e.code, message=e.message)
        safe_code = quote(str(e.code)[:50])
        return RedirectResponse(
            url=f"{frontend_base}/settings?gmail_status=error&error_code={safe_code}",
            status_code=status.HTTP_302_FOUND,
        )
    except Exception as e:
        log.error("Unexpected error handling OAuth callback", error=str(e))
        return RedirectResponse(
            url=f"{frontend_base}/settings?gmail_status=error&error_code=INTERNAL_ERROR",
            status_code=status.HTTP_302_FOUND,
        )


@router.get("/status", response_model=GmailStatusResponse, summary="Check Gmail connection status")
async def gmail_status(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Check if the authenticated user has an active Gmail integration.
    Never exposes tokens or secrets.
    """
    conn = GmailService.get_connection(current_user.uid)
    if not conn or not conn.get("is_connected"):
        return GmailStatusResponse(is_connected=False)

    return GmailStatusResponse(
        is_connected=True,
        google_email=conn.get("google_email"),
        connected_at=conn.get("connected_at"),
        last_used_at=conn.get("last_used_at"),
        scopes=conn.get("scopes"),
    )


@router.post("/disconnect", response_model=GmailDisconnectResponse, summary="Disconnect Gmail account")
async def gmail_disconnect(
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Disconnect user's Gmail account:
    - Invalidate Google OAuth token
    - Mark connection revoked in Firestore
    - Cancel pending/queued email distribution tasks for this user
    """
    disconnected = await GmailService.disconnect_gmail(current_user.uid)

    if not disconnected:
        return GmailDisconnectResponse(
            success=False,
            message="No active Gmail connection found for this account.",
        )

    return GmailDisconnectResponse(
        success=True,
        message="Gmail account successfully disconnected and revoked.",
    )


@router.post("/test", response_model=GmailTestEmailResponse, summary="Send test email")
async def gmail_send_test(
    request: GmailTestEmailRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Send an explicit test email using the authenticated user's connected Gmail account.
    """
    conn = GmailService.get_connection(current_user.uid)
    if not conn or not conn.get("is_connected"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must connect your Gmail account before sending emails.",
        )

    sender_email = conn.get("google_email", "me")
    subject = f"[CertFlow Test] {request.subject or 'Your Gmail integration is active!'}"
    custom_msg = html.escape(request.custom_message) if request.custom_message else ""

    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto; padding: 24px; border: 1px solid #e2e8f0; border-radius: 8px;">
        <h2 style="color: #4f46e5; margin-bottom: 8px;">CertFlow Gmail Test</h2>
        <p style="color: #334155; font-size: 16px;">This is a test message confirming your Gmail integration with CertFlow is connected and operating properly.</p>
        <div style="background-color: #f8fafc; border-left: 4px solid #4f46e5; padding: 12px 16px; margin: 20px 0;">
            <p style="margin: 0; color: #475569; font-size: 14px;"><strong>Connected Account:</strong> {sender_email}</p>
            <p style="margin: 4px 0 0; color: #475569; font-size: 14px;"><strong>Sender User ID:</strong> {current_user.uid}</p>
        </div>
        {f'<div style="margin-top: 16px; padding: 12px; background-color: #f1f5f9; border-radius: 6px;"><p style="margin: 0; font-size: 14px; color: #1e293b;"><strong>Custom Note:</strong> {custom_msg}</p></div>' if custom_msg else ''}
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 24px 0;" />
        <p style="color: #94a3b8; font-size: 12px; margin: 0;">Sent automatically by CertFlow Certificate Management System.</p>
    </div>
    """

    plain_body = (
        f"CertFlow Gmail Test\n\n"
        f"This is a test message confirming your Gmail integration is active.\n"
        f"Connected Account: {sender_email}\n"
    )
    if custom_msg:
        plain_body += f"\nNote: {request.custom_message}\n"

    try:
        result = await GmailService.send_email_async(
            user_id=current_user.uid,
            to_email=str(request.recipient_email),
            subject=subject,
            body_html=html_body,
            body_text=plain_body,
        )

        return GmailTestEmailResponse(
            success=True,
            message="Test email sent successfully.",
            message_id=result.get("message_id"),
            sender=sender_email,
            recipient=str(request.recipient_email),
        )

    except GmailNotConnectedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except GmailServiceError as e:
        log.error("Test email delivery failed", error=e.message, code=e.code)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send email via Gmail: {e.message}",
        )
    except Exception as e:
        log.error("Unexpected error sending test email", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unexpected error occurred while attempting to send test email.",
        )


@router.post("/send-preview", response_model=SendPreviewResponse, summary="Preview rendered email template")
async def send_preview(
    request: SendPreviewRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Render dynamic email template with sample variables safely (HTML escaped).
    No email is sent.
    """
    rendered_subject = _render_template(
        request.subject_template,
        request.sample_variables,
        escape_html=False,
    )
    rendered_html = _render_template(
        request.body_template,
        request.sample_variables,
        escape_html=True,
    )
    if "<p>" not in rendered_html and "<div" not in rendered_html:
        rendered_html = rendered_html.replace("\n", "<br />\n")

    rendered_text = _render_template(
        request.body_template,
        request.sample_variables,
        escape_html=False,
    )

    return SendPreviewResponse(
        rendered_subject=rendered_subject,
        rendered_html=rendered_html,
        rendered_text=rendered_text,
    )


@router.post("/send-campaign", response_model=SendCampaignResponse, summary="Send certificates for a campaign")
async def send_campaign(
    request: SendCampaignRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Validate Gmail connection, ownership, and explicit confirmation,
    then initiate batch certificate email sending in the background.
    """
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit user confirmation is required to send campaign emails.",
        )

    try:
        result = await batch_engine.start_campaign_job(
            user_id=current_user.uid,
            campaign_id=request.campaign_id,
            subject_template=request.subject_template,
            body_template=request.body_template,
        )

        return SendCampaignResponse(
            campaign_id=request.campaign_id,
            status=result.get("status", "processing"),
            queued_count=result.get("total_recipients", 0),
            message=result.get("message", "Campaign emails batch processing started."),
        )
    except GmailNotConnectedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        log.error("Failed to start campaign emails batch job", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
