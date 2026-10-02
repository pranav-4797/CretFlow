"""
Unit and integration tests for Google Forms / external Quiz webhook endpoints.
Verifies passing score evaluation, certificate auto-generation, email dispatching, and secret tokens.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status
from unittest.mock import MagicMock, patch

from main import app
from app.core.security import AuthenticatedUser, get_current_user
from app.services.firestore_service import firestore_service


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def auth_user():
    user = AuthenticatedUser(uid="user_webhook_owner", email="owner@test.com")
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.anyio
async def test_google_form_webhook_below_passing_score(client: AsyncClient, auth_user: AuthenticatedUser):
    # 1. Create a campaign with 70% passing threshold
    camp_payload = {
        "name": "Python Mastery Quiz",
        "event_name": "Python Mastery 2026",
    }
    camp_res = await client.post("/api/campaigns", json=camp_payload)
    assert camp_res.status_code == status.HTTP_201_CREATED
    campaign_id = camp_res.json()["campaign_id"]

    # Configure 70% threshold
    await client.put(
        f"/api/webhooks/config/{campaign_id}",
        json={"passing_score": 70.0, "auto_email": True},
    )

    # 2. Submit student score with 50/100 (50% < 70%)
    webhook_payload = {
        "recipient_name": "Alice Johnson",
        "recipient_email": "alice@example.com",
        "score": 50,
        "total_score": 100,
    }
    wh_res = await client.post(f"/api/webhooks/google-form/{campaign_id}", json=webhook_payload)
    assert wh_res.status_code == status.HTTP_200_OK
    data = wh_res.json()
    assert data["status"] == "below_threshold"
    assert data["passed"] is False
    assert data["score_percentage"] == 50.0
    assert data["certificate_id"] is None
    assert data["email_sent"] is False


@pytest.mark.anyio
async def test_google_form_webhook_passed(client: AsyncClient, auth_user: AuthenticatedUser):
    # 1. Create a campaign with 60% passing threshold
    camp_payload = {
        "name": "Cloud Architecture Assessment",
        "event_name": "Cloud Architecture 2026",
    }
    camp_res = await client.post("/api/campaigns", json=camp_payload)
    campaign_id = camp_res.json()["campaign_id"]

    await client.put(
        f"/api/webhooks/config/{campaign_id}",
        json={"passing_score": 60.0, "auto_email": True},
    )

    # 2. Submit student score with 85/100 (85% >= 60%)
    webhook_payload = {
        "recipient_name": "Bob Smith",
        "recipient_email": "bob@example.com",
        "score": 85,
        "total_score": 100,
    }
    wh_res = await client.post(f"/api/webhooks/google-form/{campaign_id}", json=webhook_payload)
    assert wh_res.status_code == status.HTTP_200_OK
    data = wh_res.json()
    assert data["status"] == "issued"
    assert data["passed"] is True
    assert data["score_percentage"] == 85.0
    assert data["certificate_id"] is not None
    assert data["certificate_id"].startswith("CERT-")


@pytest.mark.anyio
async def test_google_form_webhook_secret_validation(client: AsyncClient, auth_user: AuthenticatedUser):
    camp_payload = {"name": "Secure Certification"}
    camp_res = await client.post("/api/campaigns", json=camp_payload)
    campaign_id = camp_res.json()["campaign_id"]

    # Set webhook secret
    await client.put(
        f"/api/webhooks/config/{campaign_id}",
        json={"passing_score": 50.0, "auto_email": False, "webhook_secret": "my-secret-key-123"},
    )

    # Submit without or wrong secret -> 401
    bad_res = await client.post(
        f"/api/webhooks/google-form/{campaign_id}",
        json={"recipient_name": "Charlie", "recipient_email": "charlie@test.com", "score": 90, "total_score": 100},
    )
    assert bad_res.status_code == status.HTTP_401_UNAUTHORIZED

    # Submit with valid secret -> 200
    good_res = await client.post(
        f"/api/webhooks/google-form/{campaign_id}",
        json={
            "recipient_name": "Charlie",
            "recipient_email": "charlie@test.com",
            "score": 90,
            "total_score": 100,
            "webhook_secret": "my-secret-key-123",
        },
    )
    assert good_res.status_code == status.HTTP_200_OK
    assert good_res.json()["passed"] is True
