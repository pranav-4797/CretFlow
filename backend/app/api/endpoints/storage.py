"""
Storage management and Google Shared Drive diagnostic endpoints.
"""

import time
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.config import settings
from app.core.security import get_current_user, AuthenticatedUser
from app.services.drive_service import drive_service

router = APIRouter()


class CampaignFolderProvisionRequest(BaseModel):
    campaign_name: str


class StorageStatusResponse(BaseModel):
    storage_provider: str
    shared_drive_name: str
    service_account_configured: bool
    service_account_email: str


@router.get("/info", response_model=StorageStatusResponse, summary="Storage system information")
async def get_storage_info() -> StorageStatusResponse:
    """Returns safe public/authenticated info regarding current storage provider."""
    client_email = settings.google_drive_service_account_email or settings.firebase_client_email
    return StorageStatusResponse(
        storage_provider=settings.storage_provider,
        shared_drive_name=settings.google_drive_shared_drive_name,
        service_account_configured=bool(client_email and client_email != "placeholder@placeholder.iam.gserviceaccount.com"),
        service_account_email=client_email if client_email else "not_configured",
    )


@router.post(
    "/campaigns/{campaign_id}/provision-folders",
    summary="Provision Shared Drive folder structure for a campaign",
)
async def provision_campaign_folders(
    campaign_id: str,
    payload: CampaignFolderProvisionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """
    Creates the required directory structure in the Shared Drive:
    Campaigns/{campaign_id}-{name}/
      ├── participants/
      ├── template/
      ├── certificates/
      └── reports/
    """
    try:
        folder_map = drive_service.ensure_campaign_folders(
            campaign_id=campaign_id,
            campaign_name=payload.campaign_name,
        )
        return {
            "success": True,
            "campaign_id": campaign_id,
            "folders": folder_map,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to provision campaign folders: {str(exc)}",
        )


@router.get("/test-drive", summary="Execute automated integration test for Google Shared Drive")
async def test_drive_integration() -> Dict[str, Any]:
    """
    Automated integration check for Google Shared Drive:
    1. Authenticates service account
    2. Validates Shared Drive discovery
    3. Verifies base folder structure (Templates, Campaigns, Reports)
    4. Uploads a safe temporary test file
    5. Reads back metadata
    6. Deletes the test file
    """
    report = {
        "service_account_authentication": "pending",
        "shared_drive_discovery": "pending",
        "folder_structure_check": "pending",
        "test_file_upload": "pending",
        "test_file_metadata": "pending",
        "test_file_deletion": "pending",
        "all_passed": False,
        "details": {},
        "troubleshooting": None,
    }

    test_file_id = None
    try:
        # Step 1: Service Account
        creds = drive_service.get_service_account_credentials()
        report["service_account_authentication"] = "passed"
        report["details"]["service_account_email"] = creds.service_account_email

        # Step 2: Shared Drive Discovery
        drive_obj = drive_service.get_shared_drive()
        report["shared_drive_discovery"] = "passed"
        report["details"]["shared_drive_id"] = drive_obj["id"]
        report["details"]["shared_drive_name"] = drive_obj["name"]

        # Step 3: Base Folder Structure
        base_folders = drive_service.ensure_base_folder_structure()
        report["folder_structure_check"] = "passed"
        report["details"]["base_folders"] = base_folders

        # Step 4: Test File Upload (safe txt probe)
        timestamp = int(time.time())
        test_content = f"CertFlow Shared Drive integration check - {timestamp}".encode("utf-8")
        upload_res = drive_service.upload_file(
            file_content=test_content,
            filename=f"probe_test_{timestamp}.txt",
            mime_type="text/plain",
            parent_folder_id=base_folders["Reports"],
            description="Temporary test file created by CertFlow health probe.",
        )
        test_file_id = upload_res["drive_file_id"]
        report["test_file_upload"] = "passed"
        report["details"]["uploaded_file_id"] = test_file_id
        report["details"]["uploaded_file_url"] = upload_res.get("drive_web_url")

        # Step 5: Read metadata
        meta = drive_service.get_file_metadata(test_file_id)
        report["test_file_metadata"] = "passed"
        report["details"]["verified_metadata"] = {
            "name": meta.get("file_name"),
            "size": meta.get("size"),
            "mime_type": meta.get("mime_type"),
        }

        # Step 6: Delete test file
        drive_service.delete_file(test_file_id)
        report["test_file_deletion"] = "passed"
        test_file_id = None

        report["all_passed"] = True
        return report

    except Exception as exc:
        error_msg = str(exc)
        report["error"] = error_msg

        # Provide actionable troubleshooting advice
        if "accessNotConfigured" in error_msg or "has not been used in project" in error_msg:
            report["troubleshooting"] = (
                "The Google Drive API is not enabled in your Google Cloud Project. "
                "Enable it at: https://console.developers.google.com/apis/api/drive.googleapis.com/overview?project=certflow-ab935"
            )
        elif "Shared Drive" in error_msg and "not found" in error_msg:
            report["troubleshooting"] = (
                f"The Shared Drive '{settings.google_drive_shared_drive_name}' was not found. "
                f"Ensure the Shared Drive exists in Google Drive and that the service account email "
                f"({creds.service_account_email if 'creds' in locals() else 'your service account'}) "
                "is added as a 'Content manager'."
            )
        elif "insufficientPermissions" in error_msg:
            report["troubleshooting"] = (
                "The service account does not have write access to this Shared Drive. "
                "Make sure its role is 'Content manager' or 'Manager', not 'Viewer'."
            )

        # Clean up test file if it was created before error
        if test_file_id:
            try:
                drive_service.delete_file(test_file_id)
            except Exception:
                pass

        return report
