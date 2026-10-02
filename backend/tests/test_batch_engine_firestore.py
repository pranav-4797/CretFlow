"""
Unit and integration tests for Firestore-Based Batch Processing Engine and Restart Reconciler.
All external services (Google APIs, Gmail, Drive) are strictly mocked. 0 real emails sent.
"""

import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import AuthenticatedUser, get_current_user
from app.services.batch_engine import batch_engine
from app.services.firestore_service import firestore_service
from app.services.gmail_service import GmailService, GmailServiceError
from app.services.reconciler import reconciler
from main import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def mock_user():
    return AuthenticatedUser(
        uid="test-user-batch-123",
        email="organizer@example.com",
        name="Batch Organizer",
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


# ─── 1. Firestore Job & Atomic Lease Tests ────────────────────────────────────

def test_firestore_atomic_job_lease():
    """Verify job lease claim, expiry, and renewal preventing dual processing."""
    job_id = f"job_test_{uuid.uuid4().hex[:8]}"
    campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
    user_id = "test-user-batch-123"

    job = firestore_service.create_email_job(
        job_id=job_id,
        campaign_id=campaign_id,
        owner_uid=user_id,
        total_recipients=20,
        batch_size=10,
    )
    assert job["status"] == "queued"

    # 1. Claim lease
    lease1 = firestore_service.claim_job_lease(job_id, lease_duration_seconds=60)
    assert lease1 is not None

    # 2. Competing worker tries to claim the same job before expiry -> must return None
    competing_lease = firestore_service.claim_job_lease(job_id, lease_duration_seconds=60)
    assert competing_lease is None

    # 3. Renew lease with valid lease_id -> True
    renewed = firestore_service.renew_job_lease(job_id, lease1, lease_duration_seconds=120)
    assert renewed is True

    # 4. Release lease
    firestore_service.release_job_lease(job_id, lease1)
    updated_job = firestore_service.get_email_job(job_id)
    assert updated_job["lease_id"] is None


def test_batch_participant_claiming():
    """Verify claiming a bounded batch marks recipients as 'processing' with lease."""
    campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
    user_id = "test-user-batch-123"

    # Add 5 participants
    for i in range(5):
        firestore_service.save_participant(
            campaign_id,
            {
                "participant_id": f"part_{i}",
                "recipient_name": f"User {i}",
                "recipient_email": f"user{i}@example.com",
                "email_status": "queued",
                "attempt_count": 0,
            },
        )

    # Claim a batch of 3
    batch = firestore_service.claim_participants_batch(
        campaign_id=campaign_id,
        batch_size=3,
        lease_id="test_lease_abc",
        lease_duration_seconds=100,
    )

    assert len(batch) == 3
    for p in batch:
        assert p["email_status"] == "processing"
        assert p["processing_lease_id"] == "test_lease_abc"

    # Claim remaining batch
    remaining_batch = firestore_service.claim_participants_batch(
        campaign_id=campaign_id,
        batch_size=3,
        lease_id="test_lease_def",
        lease_duration_seconds=100,
    )
    assert len(remaining_batch) == 2


# ─── 2. Participant State Transitions & Ambiguity Tests ───────────────────────

def test_participant_state_transitions():
    """Verify sent, transient failure, permanent failure, and ambiguous outcomes."""
    campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
    p_id = f"p_{uuid.uuid4().hex[:8]}"

    firestore_service.save_participant(
        campaign_id,
        {
            "participant_id": p_id,
            "recipient_email": "student@example.com",
            "email_status": "queued",
            "attempt_count": 0,
        },
    )

    # 1. Transient failure -> should become 'retrying'
    firestore_service.record_participant_failure(
        campaign_id=campaign_id,
        participant_id=p_id,
        error_code="RATE_LIMIT_429",
        error_message="Gmail rate limit exceeded",
        is_transient=True,
        attempt_count=1,
        max_attempts=3,
    )
    p = firestore_service.get_campaign_participants(campaign_id)[0]
    assert p["email_status"] == "retrying"
    assert p["last_error_code"] == "RATE_LIMIT_429"

    # 2. Ambiguous outcome (network timeout) -> must record 'unknown'
    firestore_service.record_participant_ambiguous(
        campaign_id=campaign_id,
        participant_id=p_id,
        error_message="Socket timeout awaiting Gmail HTTP response",
        attempt_count=2,
    )
    p = firestore_service.get_campaign_participants(campaign_id)[0]
    assert p["email_status"] == "unknown"
    assert p["last_error_code"] == "AMBIGUOUS_DELIVERY"

    # 3. Success -> marks 'sent' with message ID
    firestore_service.record_participant_sent(
        campaign_id=campaign_id,
        participant_id=p_id,
        message_id="msg_123456",
        attempt_count=3,
    )
    p = firestore_service.get_campaign_participants(campaign_id)[0]
    assert p["email_status"] == "sent"
    assert p["gmail_message_id"] == "msg_123456"


# ─── 3. Restart Reconciler Tests ──────────────────────────────────────────────

@pytest.mark.anyio
async def test_startup_reconciliation_reclaims_expired_leases():
    """Verify startup recovery resets expired jobs and stuck participants safely."""
    campaign_id = f"camp_{uuid.uuid4().hex[:8]}"
    job_id = f"job_{uuid.uuid4().hex[:8]}"
    user_id = "test-user-batch-123"

    firestore_service.create_email_job(
        job_id=job_id,
        campaign_id=campaign_id,
        owner_uid=user_id,
        total_recipients=5,
    )
    # Simulate an expired lease from a dead process / Render sleep
    past_iso = "2020-01-01T00:00:00+00:00"
    firestore_service.update_email_job(
        job_id,
        {
            "status": "processing",
            "lease_id": "dead_worker_lease",
            "lease_expires_at": past_iso,
        },
    )

    # Participant stuck in processing
    firestore_service.save_participant(
        campaign_id,
        {
            "participant_id": "stuck_part_1",
            "recipient_email": "stuck@example.com",
            "email_status": "processing",
            "processing_lease_expires_at": past_iso,
            "attempt_count": 1,
        },
    )

    # Run reconciler
    report = await reconciler.reconcile_all_on_startup()
    assert report["recovered_jobs"] >= 1
    assert report["reconciled_participants"] >= 1

    # Check job is reset to queued
    job = firestore_service.get_email_job(job_id)
    assert job["status"] == "queued"
    assert job["lease_id"] is None

    # Check participant is reset to retrying
    p = firestore_service.get_campaign_participants(campaign_id)[0]
    assert p["email_status"] == "retrying"


# ─── 4. Campaign Batch Controls (Pause, Resume, Cancel, Retry) ────────────────

@pytest.mark.anyio
async def test_campaign_batch_controls():
    """Verify pause, resume, cancel, and retry operations update state truthfully."""
    campaign_id = f"camp_ctl_{uuid.uuid4().hex[:8]}"
    user_id = "test-user-batch-123"

    # Setup campaign
    firestore_service.get_or_create_campaign(campaign_id, user_id=user_id, campaign_name="Spring Graduation")
    firestore_service.save_gmail_connection(user_id, "org@example.com", "fake_ref_token", "gmail.send")

    firestore_service.save_participant(
        campaign_id,
        {
            "participant_id": "p_fail",
            "recipient_email": "failed@example.com",
            "email_status": "failed",
            "attempt_count": 1,
        },
    )

    # 1. Pause campaign
    pause_res = await batch_engine.pause_campaign(user_id, campaign_id)
    assert pause_res["status"] == "paused"
    camp = firestore_service.get_campaign(campaign_id)
    assert camp["status"] == "paused"

    # 2. Retry failed recipients
    retry_res = await batch_engine.retry_failed_recipients(user_id, campaign_id)
    assert retry_res["reset_count"] == 1
    p = firestore_service.get_campaign_participants(campaign_id)[0]
    assert p["email_status"] == "processing" or p["email_status"] == "retrying"

    # 3. Cancel campaign
    cancel_res = await batch_engine.cancel_campaign(user_id, campaign_id)
    assert cancel_res["status"] == "cancelled"
    camp = firestore_service.get_campaign(campaign_id)
    assert camp["status"] == "cancelled"


# ─── 5. API Endpoint Tests ────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_api_send_and_status(auth_client: AsyncClient, mock_user):
    """Test full endpoint flow: /send -> /status -> /pause -> /cancel."""
    campaign_id = f"api_camp_{uuid.uuid4().hex[:8]}"
    firestore_service.get_or_create_campaign(campaign_id, user_id=mock_user.uid, campaign_name="Robotics Expo")
    firestore_service.save_gmail_connection(mock_user.uid, "org@example.com", "fake_token", "gmail.send")

    # Add a participant
    firestore_service.save_participant(
        campaign_id,
        {
            "participant_id": "attendee_1",
            "recipient_email": "attendee1@example.com",
            "recipient_name": "Bob Vance",
            "email_status": "queued",
            "attempt_count": 0,
        },
    )

    # 1. Trigger send endpoint
    with patch.object(GmailService, "send_email_sync") as mock_send:
        mock_send.return_value = {"message_id": "msg_abc_999"}

        send_res = await auth_client.post(
            f"/api/emails/{campaign_id}/send",
            json={"subject_template": "Your Diploma", "batch_size": 10},
        )
        assert send_res.status_code == 200
        send_data = send_res.json()
        assert send_data["status"] == "processing"

        # 2. Check status endpoint
        status_res = await auth_client.get(f"/api/emails/{campaign_id}/status")
        assert status_res.status_code == 200
        st_data = status_res.json()
        assert st_data["campaign_id"] == campaign_id
        assert st_data["total_count"] >= 1

        # 3. Pause endpoint
        pause_res = await auth_client.post(f"/api/emails/{campaign_id}/pause")
        assert pause_res.status_code == 200
        assert pause_res.json()["status"] == "paused"

        # 4. Cancel endpoint
        cancel_res = await auth_client.post(f"/api/emails/{campaign_id}/cancel")
        assert cancel_res.status_code == 200
        assert cancel_res.json()["status"] == "cancelled"
