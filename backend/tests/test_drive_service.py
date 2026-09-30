"""
Unit and integration tests for Google Shared Drive service and endpoints.
"""

import io
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport
from fastapi import status

from main import app
from app.services.drive_service import GoogleDriveService, is_retryable_error
from googleapiclient.errors import HttpError
from httplib2 import Response


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


# ─── Drive Service Unit Tests ──────────────────────────────────────────────────

def test_drive_service_credentials_resolution():
    """Verify service account credentials can be loaded from file or env."""
    service = GoogleDriveService()
    # In test environment with serviceAccountKey.json present, it loads credentials
    creds = service.get_service_account_credentials()
    assert creds is not None
    assert creds.service_account_email is not None


def test_retryable_error_filter():
    """Verify transient error detection for retry decorator."""
    resp_429 = Response({"status": "429"})
    resp_500 = Response({"status": "500"})
    resp_404 = Response({"status": "404"})

    assert is_retryable_error(HttpError(resp_429, b"Rate limit")) is True
    assert is_retryable_error(HttpError(resp_500, b"Internal server error")) is True
    assert is_retryable_error(HttpError(resp_404, b"Not found")) is False
    assert is_retryable_error(ValueError("Some local error")) is False


def test_drive_service_mocked_workflow():
    """Test full Drive workflow: Shared Drive lookup, folder creation, upload, get, delete."""
    from app.core.config import settings
    with patch.object(settings, "google_drive_shared_drive_id", None), \
         patch.object(settings, "google_drive_templates_folder_id", None), \
         patch.object(settings, "google_drive_campaigns_folder_id", None), \
         patch.object(settings, "google_drive_reports_folder_id", None):
        service = GoogleDriveService()

        # Mock the internal google client
        mock_client = MagicMock()
        service._service = mock_client

        # 1. Mock drives().list()
        mock_client.drives().list().execute.return_value = {
            "drives": [
                {"id": "shared_drive_123", "name": "CertFlow"},
                {"id": "other_drive_456", "name": "Other"},
            ]
        }

        drive = service.get_shared_drive("CertFlow")
        assert drive["id"] == "shared_drive_123"
        assert drive["name"] == "CertFlow"

        # 2. Mock folder search & creation
        # First call: not found (empty files list)
        mock_client.files().list().execute.return_value = {"files": []}
        # Create call: returns created folder
        mock_client.files().create().execute.return_value = {
            "id": "folder_templates_123",
            "name": "Templates",
            "parents": ["shared_drive_123"],
        }

        folder = service.create_folder("Templates")
        assert folder["id"] == "folder_templates_123"

        # Verify supportsAllDrives=True was passed
        create_call_kwargs = mock_client.files().create.call_args[1]
        assert create_call_kwargs.get("supportsAllDrives") is True

        # 3. Test base folder structure
        mock_client.files().create().execute.side_effect = [
            {"id": "id_templates", "name": "Templates"},
            {"id": "id_campaigns", "name": "Campaigns"},
            {"id": "id_reports", "name": "Reports"},
        ]
        service._cached_base_folders = {}
        base_folders = service.ensure_base_folder_structure()
        assert "Templates" in base_folders
        assert "Campaigns" in base_folders
        assert "Reports" in base_folders

        # 4. Test campaign folder structure
        mock_client.files().create().execute.side_effect = [
            {"id": "camp_root", "name": "c1-Hackathon"},
            {"id": "camp_parts", "name": "participants"},
            {"id": "camp_templ", "name": "template"},
            {"id": "camp_certs", "name": "certificates"},
            {"id": "camp_reps", "name": "reports"},
        ]
        camp_folders = service.ensure_campaign_folders("c1", "Hackathon")
        assert camp_folders["campaign_folder_id"] == "camp_root"
        assert camp_folders["certificates"] == "camp_certs"

        # 5. Test upload_file
        mock_client.files().create().execute.side_effect = None
        mock_client.files().create().execute.return_value = {
            "id": "file_cert_999",
            "name": "john_doe.pdf",
            "mimeType": "application/pdf",
            "size": "2048",
            "webViewLink": "https://drive.google.com/file/d/file_cert_999/view",
            "webContentLink": "https://drive.google.com/uc?id=file_cert_999",
            "parents": ["camp_certs"],
        }

        upload_res = service.upload_file(
            file_content=b"%PDF-1.4 sample content",
            filename="john_doe.pdf",
            mime_type="application/pdf",
            parent_folder_id="camp_certs",
        )
        assert upload_res["drive_file_id"] == "file_cert_999"
        assert upload_res["drive_web_url"] == "https://drive.google.com/file/d/file_cert_999/view"

        # 6. Test get_file_metadata
        mock_client.files().get().execute.return_value = {
            "id": "file_cert_999",
            "name": "john_doe.pdf",
            "mimeType": "application/pdf",
            "size": 2048,
            "webViewLink": "https://drive.google.com/file/d/file_cert_999/view",
            "parents": ["camp_certs"],
        }
        meta = service.get_file_metadata("file_cert_999")
        assert meta["drive_file_id"] == "file_cert_999"
        assert meta["file_name"] == "john_doe.pdf"

        # 7. Test delete_file
        mock_client.files().delete().execute.return_value = None
        assert service.delete_file("file_cert_999") is True
        del_kwargs = mock_client.files().delete.call_args[1]
        assert del_kwargs.get("supportsAllDrives") is True


# ─── API Endpoint Tests ────────────────────────────────────────────────────────

@pytest.mark.anyio
async def test_storage_info_endpoint(client: AsyncClient):
    """Test public storage info endpoint."""
    response = await client.get("/api/storage/info")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["storage_provider"] == "shared_drive"
    assert data["shared_drive_name"] == "CertFlow"
    assert data["service_account_configured"] is True


@pytest.mark.anyio
async def test_storage_test_drive_endpoint_response_structure(client: AsyncClient):
    """
    Test diagnostic /api/storage/test-drive endpoint returns structured JSON report.
    Even if Google Drive API is not yet enabled in the cloud project,
    the endpoint handles the error gracefully and outputs diagnostic troubleshooting info.
    """
    response = await client.get("/api/storage/test-drive")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "service_account_authentication" in data
    assert "all_passed" in data
    assert "details" in data
    # Service account itself is authenticated locally
    assert data["service_account_authentication"] == "passed"
