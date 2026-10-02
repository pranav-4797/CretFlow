"""
Automated unit and integration tests for Gmail OAuth 2.0 and distribution.
All Google APIs and OAuth calls are strictly mocked. No real emails or requests are sent.
"""

import base64
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from cryptography.fernet import InvalidToken
from fastapi import status
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token, get_fernet_key
from app.core.security import AuthenticatedUser, get_current_user
from app.services.gmail_service import (
    GmailAuthError,
    GmailNotConnectedError,
    GmailService,
    GmailServiceError,
)
from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_user():
    return AuthenticatedUser(
        uid="test-firebase-uid-123",
        email="organizer@example.com",
        name="Test Organizer",
    )


@pytest.fixture
async def auth_client(mock_user):
    """Client with mocked Firebase authentication."""
    app.dependency_overrides[get_current_user] = lambda: mock_user
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def anon_client():
    """Client without authentication overrides."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


# ─── 1. Encryption & Decryption Tests ─────────────────────────────────────────

def test_token_encryption_roundtrip():
    """Verify refresh token can be encrypted and decrypted accurately."""
    sample_refresh_token = "1//04random_google_refresh_token_xyz_12345"
    encrypted = encrypt_token(sample_refresh_token)
    assert encrypted != sample_refresh_token
    assert isinstance(encrypted, str)

    decrypted = decrypt_token(encrypted)
    assert decrypted == sample_refresh_token


def test_token_decryption_tamper_detection():
    """Tampered ciphertext must fail to decrypt with an error."""
    encrypted = encrypt_token("secret_token")
    tampered = encrypted[:-5] + "AAAAA"
    with pytest.raises(Exception):
        decrypt_token(tampered)


def test_empty_token_encryption_guard():
    """Empty or None tokens should raise ValueError."""
    with pytest.raises(ValueError):
        encrypt_token("")
    with pytest.raises(ValueError):
        decrypt_token("")


# ─── 2. OAuth State Generation, Signing & Validation Tests ────────────────────

def test_oauth_state_structure_and_signature():
    """OAuth state must be signed and bound to the initiating user ID."""
    user_id = "user_456_test"
    state = GmailService.generate_oauth_state(user_id)
    assert "." in state

    extracted_uid = GmailService.verify_and_consume_oauth_state(state)
    assert extracted_uid == user_id


def test_oauth_state_expiry():
    """OAuth state older than 10 minutes must be rejected."""
    user_id = "user_expired_test"
    # Construct expired state payload
    payload = {
        "uid": user_id,
        "ts": int(time.time()) - 700,  # 700 seconds ago (> 600s TTL)
        "nonce": "old_nonce_1234567890",
    }
    import hashlib
    import hmac
    b64_payload = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    sig = hmac.new(
        settings.secret_key.encode("utf-8"),
        b64_payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    expired_state = f"{b64_payload}.{sig}"

    with pytest.raises(GmailAuthError) as exc_info:
        GmailService.verify_and_consume_oauth_state(expired_state)
    assert exc_info.value.code == "STATE_EXPIRED"


def test_oauth_state_replay_prevention():
    """Consuming an OAuth state twice must fail on the second attempt."""
    user_id = "user_replay_test"
    state = GmailService.generate_oauth_state(user_id)

    # First consumption succeeds
    first_res = GmailService.verify_and_consume_oauth_state(state)
    assert first_res == user_id

    # Second consumption must fail (single-use anti-replay)
    with pytest.raises(GmailAuthError) as exc_info:
        GmailService.verify_and_consume_oauth_state(state)
    assert exc_info.value.code == "STATE_REPLAY"


def test_oauth_state_tampering():
    """Forged or altered state tokens must be rejected."""
    state = GmailService.generate_oauth_state("user_original")
    b64_part, sig = state.split(".", 1)

    # Corrupt the signature
    corrupted_sig = sig[:-4] + "0000"
    with pytest.raises(GmailAuthError) as exc_info:
        GmailService.verify_and_consume_oauth_state(f"{b64_part}.{corrupted_sig}")
    assert exc_info.value.code == "INVALID_STATE_SIG"


# ─── 3. Authorization URL Generation ──────────────────────────────────────────

def test_authorization_url_parameters():
    """Auth URL must contain offline access, prompt=consent, and gmail.send scope."""
    user_id = "user_auth_url_test"
    auth_url = GmailService.get_authorization_url(user_id)

    assert "accounts.google.com/o/oauth2/v2/auth" in auth_url
    assert "response_type=code" in auth_url
    assert "access_type=offline" in auth_url
    assert "prompt=consent" in auth_url
    assert "include_granted_scopes=true" in auth_url
    assert "gmail.send" in auth_url
    assert settings.google_client_id in auth_url


# ─── 4. MIME Formatting & PDF Attachment Tests ────────────────────────────────

def test_mime_message_without_attachment():
    """MIME message with HTML and plain text alternatives."""
    msg = GmailService.create_mime_message(
        sender_email="sender@example.com",
        to_email="recipient@example.com",
        subject="Test Subject",
        body_html="<p>Hello World</p>",
        body_text="Hello World",
    )
    assert msg["To"] == "recipient@example.com"
    assert msg["From"] == "sender@example.com"
    assert msg["Subject"] == "Test Subject"
    assert msg.is_multipart()


def test_mime_message_with_pdf_attachment():
    """MIME message containing PDF binary attachment."""
    dummy_pdf = b"%PDF-1.4 dummy certificate content"
    msg = GmailService.create_mime_message(
        sender_email="sender@example.com",
        to_email="recipient@example.com",
        subject="Your Certificate",
        body_html="<p>Attached is your certificate</p>",
        pdf_bytes=dummy_pdf,
        pdf_filename="cert_001.pdf",
    )
    assert msg["To"] == "recipient@example.com"
    payloads = msg.get_payload()
    assert len(payloads) == 2  # Alternative part + PDF attachment part

    attachment_part = payloads[1]
    assert attachment_part.get_content_type() == "application/pdf"
    assert 'filename="cert_001.pdf"' in attachment_part.get("Content-Disposition", "")


# ─── 5. HTML Escaping and Dynamic Template Rendering ──────────────────────────

def test_dynamic_template_html_escaping():
    """XSS injection payloads in template variables must be escaped."""
    from app.api.endpoints.gmail import _render_template

    template = "Hello {{name}}, welcome to {{event_name}}!"
    xss_variables = {
        "name": "<script>alert('pwned')</script>",
        "event_name": 'Cyber "Summit" & Gala',
    }

    rendered = _render_template(template, xss_variables, escape_html=True)
    assert "<script>" not in rendered
    assert "&lt;script&gt;alert(&#x27;pwned&#x27;)&lt;/script&gt;" in rendered
    assert "&amp; Gala" in rendered


# ─── 6. Mocked Gmail API Send Execution Tests ─────────────────────────────────

def test_mocked_gmail_send_success():
    """Verify send_email_sync communicates with Gmail messages.send correctly."""
    mock_conn = {
        "google_email": "organizer@example.com",
        "user_id": "test-uid",
        "encrypted_refresh_token": encrypt_token("mock_refresh_token"),
        "is_connected": True,
    }

    with patch.object(GmailService, "get_google_credentials") as mock_get_creds:
        mock_get_creds.return_value = MagicMock()
        with patch("app.services.gmail_service.build") as mock_build:
            mock_gmail_client = MagicMock()
            mock_build.return_value = mock_gmail_client
            mock_send_req = MagicMock()
            mock_send_req.execute.return_value = {
                "id": "gmail_msg_id_999",
                "threadId": "thread_888",
            }
            mock_gmail_client.users().messages().send.return_value = mock_send_req

            result = GmailService.send_email_sync(
                conn=mock_conn,
                to_email="attendee@example.com",
                subject="CertFlow Verification",
                body_html="<p>Test</p>",
            )

            assert result["message_id"] == "gmail_msg_id_999"
            assert result["recipient"] == "attendee@example.com"
            assert result["sender"] == "organizer@example.com"


# ─── 7. Endpoint Tests ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_gmail_connect_requires_auth(anon_client: AsyncClient):
    """GET /api/gmail/connect should return 401/403 for unauthenticated requests."""
    response = await anon_client.get("/api/gmail/connect")
    assert response.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)


@pytest.mark.anyio
async def test_gmail_connect_authenticated(auth_client: AsyncClient):
    """GET /api/gmail/connect generates valid auth URL for authenticated user."""
    response = await auth_client.get("/api/gmail/connect")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "authorization_url" in data
    assert "accounts.google.com" in data["authorization_url"]


@pytest.mark.anyio
async def test_gmail_send_preview_endpoint(auth_client: AsyncClient):
    """POST /api/gmail/send-preview renders variables without sending emails."""
    payload = {
        "subject_template": "Certificate for {{name}}",
        "body_template": "<p>Hello {{name}}, you completed {{event}}!</p>",
        "sample_variables": {"name": "Alice Smith", "event": "Web3 Bootcamp"},
    }
    response = await auth_client.post("/api/gmail/send-preview", json=payload)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["rendered_subject"] == "Certificate for Alice Smith"
    assert "Alice Smith" in data["rendered_html"]
    assert "Web3 Bootcamp" in data["rendered_html"]


@pytest.mark.anyio
async def test_send_campaign_requires_explicit_confirmation(auth_client: AsyncClient):
    """POST /api/gmail/send-campaign must reject requests without explicit confirm=True."""
    payload = {
        "campaign_id": "camp_test_123",
        "subject_template": "Your Certificate",
        "body_template": "Hello!",
        "confirm": False,
    }
    response = await auth_client.post("/api/gmail/send-campaign", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "confirmation is required" in response.json()["detail"].lower()
