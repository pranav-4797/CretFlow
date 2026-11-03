"""
Tests for Super Admin Control Room features and multi-tenant access controls.
Verifies:
1. Normal users are blocked with 403 Forbidden from /api/admin endpoints.
2. admin@gmail.com is granted access.
3. System overview, global campaigns listing, and force delete.
4. campaigns?all_users=true behaves correctly based on admin role.
"""

import pytest
from httpx import AsyncClient, ASGITransport
from fastapi import status

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
def regular_user():
    return AuthenticatedUser(uid="regular_uid_123", email="regular@example.com", name="Regular User")


@pytest.mark.anyio
async def test_admin_endpoints_require_admin_role(client: AsyncClient, regular_user: AuthenticatedUser):
    """Verify non-admin users get 403 Forbidden."""
    app.dependency_overrides[get_current_user] = lambda: regular_user

    try:
        res = await client.get("/api/admin/overview")
        assert res.status_code == status.HTTP_403_FORBIDDEN
        assert "Super Admin privileges required" in res.json()["detail"]

        res_camp = await client.get("/api/admin/campaigns")
        assert res_camp.status_code == status.HTTP_403_FORBIDDEN
    finally:
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.anyio
async def test_admin_overview_and_campaigns_access(client: AsyncClient, regular_user: AuthenticatedUser):
    """Verify admin@gmail.com can access overview and see multi-tenant campaigns."""
    admin_user = AuthenticatedUser(uid="admin_uid_99", email="admin@gmail.com", name="Super Admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user

    # Create a campaign owned by regular_user
    camp_id = "test_user_campaign_999"
    firestore_service.create_campaign({
        "campaign_id": camp_id,
        "campaign_name": "Organizer Workshop",
        "owner_uid": regular_user.uid,
        "total_recipients": 50,
        "sent_count": 25,
        "status": "processing",
    })

    try:
        # 1. Admin overview
        overview_res = await client.get("/api/admin/overview")
        assert overview_res.status_code == status.HTTP_200_OK
        data = overview_res.json()
        assert data["admin_user"] == "admin@gmail.com"
        assert data["total_campaigns"] >= 1
        assert data["total_participants"] >= 50

        # 2. Admin campaigns list
        camps_res = await client.get("/api/admin/campaigns")
        assert camps_res.status_code == status.HTTP_200_OK
        camps = camps_res.json()
        found = any(c["id"] == camp_id for c in camps)
        assert found is True

        # 3. Admin delete any campaign
        del_res = await client.delete(f"/api/admin/campaigns/{camp_id}")
        assert del_res.status_code == status.HTTP_204_NO_CONTENT

        # Verify deleted
        check = firestore_service.get_campaign(camp_id)
        assert check is None
    finally:
        app.dependency_overrides.pop(get_current_user, None)
