"""
Unit and integration tests for Campaigns and Participants endpoints.
Verifies authentication, Firestore data persistence, IDOR isolation, and input validation.
"""

import io
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
    user = AuthenticatedUser(uid="user_campaign_owner", email="owner@example.com")
    app.dependency_overrides[get_current_user] = lambda: user
    yield user
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def other_user():
    user = AuthenticatedUser(uid="user_attacker", email="attacker@example.com")
    return user


@pytest.mark.anyio
async def test_campaign_endpoints_require_auth(client: AsyncClient):
    """Anonymous access to /api/campaigns must return 401."""
    res = await client.get("/api/campaigns")
    assert res.status_code == status.HTTP_401_UNAUTHORIZED

    res_post = await client.post("/api/campaigns", json={"name": "Test"})
    assert res_post.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.anyio
async def test_campaign_crud_flow_and_idor(client: AsyncClient, auth_user: AuthenticatedUser, other_user: AuthenticatedUser):
    """Test campaign creation, retrieval, IDOR protection, and deletion."""
    # 1. Create Campaign
    payload = {
        "name": "Security Audit Workshop 2026",
        "description": "Annual security training",
        "template_id": "tpl_sec_01",
    }
    create_res = await client.post("/api/campaigns", json=payload)
    assert create_res.status_code == status.HTTP_201_CREATED
    data = create_res.json()
    assert data["name"] == payload["name"]
    campaign_id = data["id"]
    assert data["user_id"] == auth_user.uid

    # 2. Get Campaign as Owner
    get_res = await client.get(f"/api/campaigns/{campaign_id}")
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["id"] == campaign_id

    # 3. List Campaigns as Owner
    list_res = await client.get("/api/campaigns")
    assert list_res.status_code == status.HTTP_200_OK
    campaign_ids = [c["id"] for c in list_res.json()]
    assert campaign_id in campaign_ids

    # 4. IDOR Protection: Switch auth override to attacker and attempt to access
    app.dependency_overrides[get_current_user] = lambda: other_user
    idor_res = await client.get(f"/api/campaigns/{campaign_id}")
    assert idor_res.status_code == status.HTTP_404_NOT_FOUND

    idor_del = await client.delete(f"/api/campaigns/{campaign_id}")
    assert idor_del.status_code == status.HTTP_404_NOT_FOUND

    # 5. Restore Owner & Delete
    app.dependency_overrides[get_current_user] = lambda: auth_user
    del_res = await client.delete(f"/api/campaigns/{campaign_id}")
    assert del_res.status_code == status.HTTP_204_NO_CONTENT

    # Verify deleted
    verify_del = await client.get(f"/api/campaigns/{campaign_id}")
    assert verify_del.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.anyio
async def test_participant_upload_validation_and_flow(client: AsyncClient, auth_user: AuthenticatedUser):
    """Test participant file upload with validation, sanitization, and parsing."""
    # Create a parent campaign
    camp = firestore_service.create_campaign({
        "name": "Participant Test Campaign",
        "user_id": auth_user.uid,
    })
    camp_id = camp["id"]

    # 1. Invalid file extension (.exe)
    invalid_file = io.BytesIO(b"binary content")
    res_bad_ext = await client.post(
        f"/api/participants/{camp_id}/upload",
        files={"file": ("malicious.exe", invalid_file, "application/octet-stream")},
    )
    assert res_bad_ext.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid file type" in res_bad_ext.json()["detail"]

    # 2. Valid CSV with custom fields and whitespace to sanitize
    csv_content = (
        "Name,Email,Grade,Role\n"
        "Alice Smith, alice@example.com ,A+,Lead Engineer\n"
        "Bob Jones,bob@example.com,B,Security Analyst\n"
    ).encode("utf-8")
    valid_file = io.BytesIO(csv_content)

    res_upload = await client.post(
        f"/api/participants/{camp_id}/upload",
        files={"file": ("participants.csv", valid_file, "text/csv")},
    )
    assert res_upload.status_code == status.HTTP_200_OK
    upload_data = res_upload.json()
    assert upload_data["imported_count"] == 2
    assert upload_data["skipped_count"] == 0

    # 3. Retrieve participants for the campaign
    res_list = await client.get(f"/api/participants/campaign/{camp_id}")
    assert res_list.status_code == status.HTTP_200_OK
    participants = res_list.json()
    assert len(participants) == 2
    emails = {p["email"] for p in participants}
    assert "alice@example.com" in emails
    assert "bob@example.com" in emails
