"""
Gmail Integration Service using Cloud Firestore.

Handles:
- Cryptographic OAuth 2.0 state generation and validation (anti-CSRF, single-use, 10 min TTL)
- Authorization URL construction
- Code exchange for tokens and Google account email retrieval
- Token encryption at rest (Fernet AES-128-CBC)
- Persisting Gmail connection in Firestore
- Gmail API client instantiation with token refresh
- MIME message creation with HTML and PDF attachments
- Sending emails via Gmail API (users.messages.send)
- Revocation and disconnection
"""

import base64
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict, Optional, Tuple

import httpx
import structlog
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token
from app.services.firestore_service import firestore_service

log = structlog.get_logger(__name__)

# In-memory single-use nonce tracking with timestamp cleanup
_USED_NONCES: Dict[str, float] = {}
_NONCE_TTL_SECONDS = 600  # 10 minutes


class GmailServiceError(Exception):
    """Base exception for Gmail service errors."""
    def __init__(self, message: str, code: str = "GMAIL_ERROR", is_transient: bool = False):
        super().__init__(message)
        self.message = message
        self.code = code
        self.is_transient = is_transient


class GmailNotConnectedError(GmailServiceError):
    """Raised when user has not connected Gmail or connection is revoked."""
    def __init__(self, message: str = "Gmail account is not connected"):
        super().__init__(message, code="NOT_CONNECTED", is_transient=False)


class GmailAuthError(GmailServiceError):
    """Raised for OAuth authorization, state, or token exchange failures."""
    def __init__(self, message: str, code: str = "AUTH_FAILED"):
        super().__init__(message, code=code, is_transient=False)


class GmailService:
    """Service encapsulating Gmail OAuth and messaging operations using Firestore."""

    @staticmethod
    def generate_oauth_state(user_id: str) -> str:
        """
        Generate a cryptographically secure, signed OAuth state bound to user_id.
        Format: base64url(json({user_id, ts, nonce})) + "." + hmac_sha256_hex
        """
        nonce = secrets.token_hex(16)
        payload = {
            "uid": user_id,
            "ts": int(time.time()),
            "nonce": nonce,
        }
        raw_json = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        b64_payload = base64.urlsafe_b64encode(raw_json).decode("ascii")

        sig = hmac.new(
            settings.secret_key.encode("utf-8"),
            b64_payload.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

        return f"{b64_payload}.{sig}"

    @staticmethod
    def verify_and_consume_oauth_state(state: str) -> str:
        """
        Verify OAuth state integrity, signature, expiration (10 min), and single-use.
        Returns user_id if valid.
        Raises GmailAuthError on any failure.
        """
        if not state or "." not in state:
            raise GmailAuthError("Invalid state format", code="INVALID_STATE")

        parts = state.split(".", 1)
        if len(parts) != 2:
            raise GmailAuthError("Invalid state format", code="INVALID_STATE")

        b64_payload, received_sig = parts

        # Verify signature in constant time
        expected_sig = hmac.new(
            settings.secret_key.encode("utf-8"),
            b64_payload.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(expected_sig, received_sig):
            log.warning("OAuth state signature mismatch")
            raise GmailAuthError("Invalid OAuth state signature", code="INVALID_STATE_SIG")

        try:
            raw_json = base64.urlsafe_b64decode(b64_payload.encode("ascii"))
            payload = json.loads(raw_json.decode("utf-8"))
        except Exception as e:
            log.warning("Failed to decode OAuth state payload", error=str(e))
            raise GmailAuthError("Corrupt OAuth state payload", code="INVALID_STATE_PAYLOAD")

        user_id = payload.get("uid")
        ts = payload.get("ts")
        nonce = payload.get("nonce")

        if not user_id or not ts or not nonce:
            raise GmailAuthError("Incomplete OAuth state payload", code="INVALID_STATE_PAYLOAD")

        now = time.time()
        # Clean expired nonces
        expired_keys = [k for k, exp in _USED_NONCES.items() if exp < now]
        for k in expired_keys:
            _USED_NONCES.pop(k, None)

        # Check expiration (10 minutes)
        if now - ts > _NONCE_TTL_SECONDS or ts > now + 60:
            raise GmailAuthError("OAuth state has expired. Please initiate connection again.", code="STATE_EXPIRED")

        # Check single-use
        if nonce in _USED_NONCES:
            log.warning("OAuth state replay detected", nonce=nonce)
            raise GmailAuthError("OAuth state has already been used", code="STATE_REPLAY")

        # Mark nonce as consumed
        _USED_NONCES[nonce] = ts + _NONCE_TTL_SECONDS

        return user_id

    @staticmethod
    def get_authorization_url(user_id: str, redirect_uri: Optional[str] = None) -> str:
        """
        Generate Google OAuth 2.0 authorization URL.
        """
        state = GmailService.generate_oauth_state(user_id)
        effective_redirect = redirect_uri or settings.effective_gmail_redirect_uri

        from urllib.parse import urlencode

        params = {
            "client_id": settings.google_client_id,
            "redirect_uri": effective_redirect,
            "response_type": "code",
            "scope": " ".join(settings.gmail_scopes_list),
            "access_type": "offline",
            "prompt": "consent",  # Ensures refresh_token is returned
            "include_granted_scopes": "true",
            "state": state,
        }

        auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
        return auth_url

    @staticmethod
    async def exchange_code_for_tokens(
        code: str,
        state: str,
        redirect_uri: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate state, exchange authorization code with Google for tokens,
        retrieve verified Google account email, encrypt refresh token,
        and save/update in Firestore.
        """
        user_id = GmailService.verify_and_consume_oauth_state(state)
        effective_redirect = redirect_uri or settings.effective_gmail_redirect_uri

        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": effective_redirect,
            "grant_type": "authorization_code",
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(token_url, data=data)
            # If mismatch occurred and redirect_uri was customized, retry with default
            if resp.status_code != 200 and redirect_uri and redirect_uri != settings.effective_gmail_redirect_uri:
                data["redirect_uri"] = settings.effective_gmail_redirect_uri
                resp = await client.post(token_url, data=data)

            if resp.status_code != 200:
                log.error("Token exchange failed", status_code=resp.status_code, error=resp.text)
                raise GmailAuthError("Failed to exchange authorization code with Google", code="TOKEN_EXCHANGE_FAILED")

            token_data = resp.json()

        refresh_token = token_data.get("refresh_token")
        access_token = token_data.get("access_token")

        if not access_token:
            raise GmailAuthError("No access token returned by Google", code="NO_ACCESS_TOKEN")

        # Fetch authenticated user profile to get verified email address
        userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        async with httpx.AsyncClient(timeout=10.0) as client:
            userinfo_resp = await client.get(
                userinfo_url,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if userinfo_resp.status_code != 200:
                log.error("Failed to fetch userinfo from Google", status_code=userinfo_resp.status_code)
                raise GmailAuthError("Failed to verify Google account identity", code="IDENTITY_VERIFICATION_FAILED")

            userinfo = userinfo_resp.json()
            google_email = userinfo.get("email")

        if not google_email:
            raise GmailAuthError("Google user profile did not return an email", code="MISSING_EMAIL")

        # Fetch existing connection from Firestore if any
        existing = firestore_service.get_gmail_connection(user_id)

        if not refresh_token:
            if existing and existing.get("encrypted_refresh_token"):
                # Decrypt existing to verify it is valid
                saved_refresh = decrypt_token(existing["encrypted_refresh_token"])
                refresh_token = saved_refresh
            else:
                raise GmailAuthError(
                    "Google did not provide a refresh token. Please revoke access in your Google Account security settings and reconnect.",
                    code="NO_REFRESH_TOKEN",
                )

        granted_scopes = token_data.get("scope", settings.gmail_scopes)

        # Save connection to Firestore with encrypted refresh token
        conn = firestore_service.save_gmail_connection(
            user_id=user_id,
            google_email=google_email,
            refresh_token=refresh_token,
            scopes=granted_scopes,
        )

        log.info(
            "Gmail connection successfully established and persisted in Firestore",
            user_id=user_id,
            google_email=google_email,
        )
        return conn

    @staticmethod
    def get_connection(user_id: str) -> Optional[Dict[str, Any]]:
        """Fetch user's GmailConnection record from Firestore."""
        return firestore_service.get_gmail_connection(user_id)

    @staticmethod
    async def disconnect_gmail(user_id: str) -> bool:
        """
        Disconnect user's Gmail account:
        - Revoke token at Google (best-effort)
        - Update Firestore record to is_connected=False
        - Cancel pending jobs and participants for this user
        """
        conn = firestore_service.get_gmail_connection(user_id)
        if not conn or not conn.get("is_connected"):
            return False

        # Attempt token revocation at Google
        try:
            refresh_token = decrypt_token(conn["encrypted_refresh_token"])
            revoke_url = f"https://oauth2.googleapis.com/revoke?token={refresh_token}"
            async with httpx.AsyncClient(timeout=5.0) as client:
                await client.post(revoke_url)
        except Exception as e:
            log.warning("Token revocation request failed (ignoring)", error=str(e), user_id=user_id)

        # Mark disconnected in Firestore
        firestore_service.disconnect_gmail(user_id)
        # Cancel all queued or retrying jobs for this user
        firestore_service.cancel_pending_user_sends(user_id)

        log.info("Gmail connection disconnected and pending sends cancelled", user_id=user_id)
        return True

    @staticmethod
    def get_google_credentials(conn: Dict[str, Any]) -> Credentials:
        """
        Build and refresh Google OAuth2 credentials from persisted Firestore connection.
        """
        if not conn or not conn.get("is_connected"):
            raise GmailNotConnectedError("User does not have an active Gmail connection")

        refresh_token = decrypt_token(conn["encrypted_refresh_token"])

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            scopes=settings.gmail_scopes_list,
        )

        try:
            creds.refresh(Request())
        except Exception as e:
            err_msg = str(e).lower()
            if "invalid_grant" in err_msg or "revoked" in err_msg:
                log.error("Gmail refresh token revoked or invalid", user_id=conn.get("user_id"), error=str(e))
                # Mark disconnected in Firestore
                user_id = conn.get("user_id")
                if user_id:
                    firestore_service.disconnect_gmail(user_id)
                raise GmailNotConnectedError("Gmail authorization has been revoked or expired. Please reconnect.")
            log.error("Failed to refresh Gmail credentials", error=str(e))
            raise GmailServiceError("Failed to refresh Gmail authorization", code="REFRESH_FAILED", is_transient=True)

        return creds

    @staticmethod
    def create_mime_message(
        sender_email: str,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
        pdf_filename: Optional[str] = None,
    ) -> MIMEMultipart:
        """
        Create a secure MIME email message supporting HTML and optional PDF attachment.
        """
        if pdf_bytes:
            msg = MIMEMultipart("mixed")
            alt_part = MIMEMultipart("alternative")
            msg.attach(alt_part)
        else:
            msg = MIMEMultipart("alternative")
            alt_part = msg

        msg["To"] = to_email
        msg["From"] = sender_email
        msg["Subject"] = subject

        # Plain text fallback
        plain_text = body_text or "Please view this email in an HTML-compatible client."
        alt_part.attach(MIMEText(plain_text, "plain", "utf-8"))

        # HTML part
        alt_part.attach(MIMEText(body_html, "html", "utf-8"))

        # Optional PDF attachment
        if pdf_bytes:
            filename = pdf_filename or "certificate.pdf"
            part = MIMEApplication(pdf_bytes, _subtype="pdf")
            part.add_header(
                "Content-Disposition",
                "attachment",
                filename=filename,
            )
            msg.attach(part)

        return msg

    @classmethod
    def send_email_sync(
        cls,
        conn: Dict[str, Any],
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
        pdf_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synchronously send an email via Gmail API using users.messages.send.
        """
        creds = cls.get_google_credentials(conn)
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)

        mime_msg = cls.create_mime_message(
            sender_email=conn.get("google_email", "me"),
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
        )

        raw_b64 = base64.urlsafe_b64encode(mime_msg.as_bytes()).decode("ascii")

        try:
            result = (
                service.users()
                .messages()
                .send(userId="me", body={"raw": raw_b64})
                .execute()
            )
            # Update last used in Firestore
            user_id = conn.get("user_id")
            if user_id:
                firestore_service.update_gmail_last_used(user_id)

            return {
                "message_id": result.get("id"),
                "thread_id": result.get("threadId"),
                "sender": conn.get("google_email"),
                "recipient": to_email,
            }
        except HttpError as e:
            status_code = e.resp.status if hasattr(e, "resp") else 500
            is_transient = status_code in (429, 500, 502, 503, 504)
            sanitized_reason = e.reason if hasattr(e, "reason") else "Gmail API call failed"
            log.error(
                "Gmail API HttpError while sending email",
                status_code=status_code,
                reason=sanitized_reason,
                is_transient=is_transient,
            )
            raise GmailServiceError(
                f"Gmail API error: {sanitized_reason}",
                code=f"GMAIL_HTTP_{status_code}",
                is_transient=is_transient,
            )
        except Exception as e:
            log.error("Unexpected error sending email via Gmail", error=str(e))
            raise GmailServiceError(
                f"Unexpected error sending email: {str(e)}",
                code="SEND_FAILED",
                is_transient=False,
            )

    @classmethod
    async def send_email_async(
        cls,
        user_id: str,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        pdf_bytes: Optional[bytes] = None,
        pdf_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Asynchronously send an email using user's connected Gmail account.
        """
        conn = cls.get_connection(user_id)
        if not conn or not conn.get("is_connected"):
            raise GmailNotConnectedError()

        result = cls.send_email_sync(
            conn=conn,
            to_email=to_email,
            subject=subject,
            body_html=body_html,
            body_text=body_text,
            pdf_bytes=pdf_bytes,
            pdf_filename=pdf_filename,
        )
        return result
