"""
Google Shared Drive Storage Service for CertFlow.
Authenticates using Google Cloud Service Account and provides robust,
retry-backed Drive API operations tailored for Shared Drives.
"""

import io
import os
import re
from pathlib import Path
from typing import BinaryIO, Dict, List, Optional, Union
import structlog
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload

from app.core.config import settings

log = structlog.get_logger(__name__)

# Drive API Scope — Storage operations only
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]


def is_retryable_error(exception: BaseException) -> bool:
    """Retry on rate limits (429) or transient Google server errors (5xx)."""
    if isinstance(exception, HttpError):
        status_code = exception.resp.status if hasattr(exception, "resp") else None
        if status_code in (429, 500, 502, 503, 504):
            return True
    return False


def retry_drive_call(func):
    """Decorator to retry Drive API requests with exponential backoff."""
    return retry(
        reraise=True,
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception(is_retryable_error),
    )(func)


class GoogleDriveService:
    """Service account-authenticated Google Drive service with Shared Drive support."""

    def __init__(self):
        self._service = None
        self._credentials = None
        self._cached_shared_drive_id = None
        self._cached_base_folders = {}

    def get_service_account_credentials(self) -> service_account.Credentials:
        """Resolve service account credentials from file path or environment variables."""
        if self._credentials is not None:
            return self._credentials

        # 1. Check explicit Drive service account path
        candidates = []
        if settings.google_drive_service_account_path:
            candidates.append(settings.google_drive_service_account_path)

        if settings.firebase_credentials_path:
            candidates.append(settings.firebase_credentials_path)

        # Standard file locations
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        backend_dir = root_dir / "backend"
        for d in [os.getcwd(), str(backend_dir), str(root_dir)]:
            candidates.extend([
                os.path.join(d, "serviceAccountKey.json"),
                os.path.join(d, "firebase-service-account.json"),
            ])
            # Check for any *firebase-adminsdk*.json
            try:
                for f in os.listdir(d):
                    if "firebase-adminsdk" in f.lower() and f.endswith(".json"):
                        candidates.append(os.path.join(d, f))
            except OSError:
                pass

        for cand in candidates:
            if cand and os.path.isfile(cand):
                log.info("Loading Drive service account credentials from file", path=cand)
                self._credentials = service_account.Credentials.from_service_account_file(
                    cand, scopes=DRIVE_SCOPES
                )
                return self._credentials

        # 2. Check environment variables
        client_email = (
            settings.google_drive_service_account_email
            or settings.firebase_client_email
        )
        private_key = (
            settings.google_drive_service_account_private_key
            or settings.firebase_private_key
        )

        if (
            private_key != "placeholder"
            and client_email != "placeholder@placeholder.iam.gserviceaccount.com"
        ):
            info = {
                "type": "service_account",
                "project_id": settings.firebase_project_id,
                "client_email": client_email,
                "private_key": private_key.replace("\\n", "\n"),
                "token_uri": "https://oauth2.googleapis.com/token",
            }
            log.info("Loading Drive service account credentials from environment variables", client_email=client_email)
            self._credentials = service_account.Credentials.from_service_account_info(
                info, scopes=DRIVE_SCOPES
            )
            return self._credentials

        raise ValueError(
            "Google Service Account credentials not found. Provide serviceAccountKey.json "
            "or set GOOGLE_DRIVE_SERVICE_ACCOUNT_EMAIL and GOOGLE_DRIVE_SERVICE_ACCOUNT_PRIVATE_KEY."
        )

    @property
    def service(self):
        """Lazy-loaded Google Drive API v3 client."""
        if self._service is None:
            creds = self.get_service_account_credentials()
            self._service = build("drive", "v3", credentials=creds, cache_discovery=False)
        return self._service

    # ─── Shared Drive Management ───────────────────────────────────────────────

    @retry_drive_call
    def get_shared_drive(self, name: Optional[str] = None) -> Dict[str, str]:
        """
        Locate and return the target Shared Drive (CertFlow).
        Uses GOOGLE_DRIVE_SHARED_DRIVE_ID from settings if set, otherwise searches
        the drives list for a match with target name.
        """
        if self._cached_shared_drive_id:
            return {"id": self._cached_shared_drive_id, "name": name or settings.google_drive_shared_drive_name}

        target_name = (name or settings.google_drive_shared_drive_name or "CertFlow").strip()

        # If explicit drive ID is configured, verify and return
        if settings.google_drive_shared_drive_id:
            drive_id = settings.google_drive_shared_drive_id.strip()
            try:
                drive_obj = self.service.drives().get(driveId=drive_id, useDomainAdminAccess=False).execute()
                self._cached_shared_drive_id = drive_id
                return {"id": drive_id, "name": drive_obj.get("name", target_name)}
            except HttpError as exc:
                log.warning("Could not fetch drive by configured ID, falling back to name search", drive_id=drive_id, error=str(exc))

        # Search accessible Shared Drives
        try:
            results = self.service.drives().list(pageSize=50, useDomainAdminAccess=False).execute()
            drives = results.get("drives", [])
        except HttpError as exc:
            log.error("Failed to list Shared Drives", error=str(exc))
            raise

        for d in drives:
            if d.get("name", "").lower() == target_name.lower():
                self._cached_shared_drive_id = d["id"]
                log.info("Discovered Shared Drive", drive_id=d["id"], name=d["name"])
                return {"id": d["id"], "name": d["name"]}

        # If not found by name, check if any drive exists or raise informative error
        available_names = [d.get("name") for d in drives]
        raise RuntimeError(
            f"Shared Drive '{target_name}' not found. "
            f"Available drives for this service account: {available_names}. "
            "Please ensure the service account email is added as 'Content manager' to the Shared Drive."
        )

    def get_shared_drive_id(self) -> str:
        """Helper to get current Shared Drive ID."""
        return self.get_shared_drive()["id"]

    # ─── Folder Management ─────────────────────────────────────────────────────

    @retry_drive_call
    def find_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[Dict[str, str]]:
        """
        Find a folder by name inside the Shared Drive (or inside a specific parent folder).
        """
        shared_drive_id = self.get_shared_drive_id()
        escaped_name = name.replace("'", "\\'")
        q = f"mimeType='application/vnd.google-apps.folder' and trashed=false and name='{escaped_name}'"

        if parent_id:
            q += f" and '{parent_id}' in parents"
        else:
            q += f" and '{shared_drive_id}' in parents"

        res = (
            self.service.files()
            .list(
                q=q,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="drive",
                driveId=shared_drive_id,
                fields="files(id, name, parents, webViewLink)",
                pageSize=1,
            )
            .execute()
        )
        files = res.get("files", [])
        return files[0] if files else None

    @retry_drive_call
    def create_folder(self, name: str, parent_id: Optional[str] = None) -> Dict[str, str]:
        """
        Idempotently create or retrieve a folder in the Shared Drive.
        """
        existing = self.find_folder(name, parent_id)
        if existing:
            return existing

        shared_drive_id = self.get_shared_drive_id()
        parents = [parent_id] if parent_id else [shared_drive_id]

        folder_metadata = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": parents,
        }

        created = (
            self.service.files()
            .create(
                body=folder_metadata,
                supportsAllDrives=True,
                fields="id, name, parents, webViewLink",
            )
            .execute()
        )
        log.info("Created folder in Shared Drive", folder_name=name, folder_id=created["id"])
        return created

    def ensure_base_folder_structure(self) -> Dict[str, str]:
        """
        Ensures the root base folder structure:
        CertFlow/
        ├── Templates/
        ├── Campaigns/
        └── Reports/
        Returns mapping of folder names to IDs.
        """
        if self._cached_base_folders:
            return self._cached_base_folders

        structure = {}

        # Templates
        if settings.google_drive_templates_folder_id:
            structure["Templates"] = settings.google_drive_templates_folder_id
        else:
            folder = self.create_folder("Templates")
            structure["Templates"] = folder["id"]

        # Campaigns
        if settings.google_drive_campaigns_folder_id:
            structure["Campaigns"] = settings.google_drive_campaigns_folder_id
        else:
            folder = self.create_folder("Campaigns")
            structure["Campaigns"] = folder["id"]

        # Reports
        if settings.google_drive_reports_folder_id:
            structure["Reports"] = settings.google_drive_reports_folder_id
        else:
            folder = self.create_folder("Reports")
            structure["Reports"] = folder["id"]

        self._cached_base_folders = structure
        return structure

    def ensure_campaign_folders(self, campaign_id: str, campaign_name: str) -> Dict[str, str]:
        """
        Creates campaign directory structure:
        Campaigns/
        └── {campaign_id}-{safe_campaign_name}/
            ├── participants/
            ├── template/
            ├── certificates/
            └── reports/
        Returns mapping of folder names to IDs.
        """
        base_structure = self.ensure_base_folder_structure()
        campaigns_root_id = base_structure["Campaigns"]

        # Sanitize campaign name for Google Drive folder
        clean_name = re.sub(r"[^\w\-_\. ]", "", campaign_name).strip()
        folder_slug = clean_name if clean_name else f"Campaign_{campaign_id[:8]}"

        # Create or get campaign main folder
        campaign_folder = self.create_folder(folder_slug, parent_id=campaigns_root_id)
        campaign_folder_id = campaign_folder["id"]

        subfolders = ["participants", "template", "certificates", "reports"]
        result = {
            "campaign_folder_id": campaign_folder_id,
            "campaign_folder_name": folder_slug,
        }

        for sub in subfolders:
            sub_folder = self.create_folder(sub, parent_id=campaign_folder_id)
            result[sub] = sub_folder["id"]

        return result

    # ─── File Operations ───────────────────────────────────────────────────────

    @retry_drive_call
    def upload_file(
        self,
        file_content: Optional[Union[bytes, BinaryIO]] = None,
        filename: Optional[str] = None,
        mime_type: str = "application/octet-stream",
        parent_folder_id: Optional[str] = None,
        description: Optional[str] = None,
        file_name: Optional[str] = None,
        folder_id: Optional[str] = None,
        file_bytes: Optional[Union[bytes, BinaryIO]] = None,
    ) -> Dict[str, Union[str, int]]:
        """
        Upload a file to a specific folder in the Shared Drive.
        Accepts raw bytes or a file-like binary stream.
        Supports both filename/file_name, parent_folder_id/folder_id, and file_content/file_bytes.
        """
        effective_content = file_content if file_content is not None else file_bytes
        if effective_content is None:
            raise ValueError("File content (file_content or file_bytes) must be provided.")

        effective_name = filename or file_name or "uploaded_file"
        effective_folder = parent_folder_id or folder_id
        if not effective_folder:
            raise ValueError("Target folder ID (parent_folder_id or folder_id) must be specified.")

        # Sanitize filename (prevent path traversal characters like ../ or control chars)
        safe_name = os.path.basename(effective_name).replace("\r", "").replace("\n", "")

        if isinstance(effective_content, bytes):
            stream = io.BytesIO(effective_content)
            content_size = len(effective_content)
        else:
            stream = effective_content
            try:
                curr = stream.tell()
                stream.seek(0, io.SEEK_END)
                content_size = stream.tell()
                stream.seek(curr)
            except (AttributeError, io.UnsupportedOperation):
                content_size = 0

        file_metadata = {
            "name": safe_name,
            "parents": [effective_folder],
        }
        if description:
            file_metadata["description"] = description[:1000]

        media = MediaIoBaseUpload(stream, mimetype=mime_type, resumable=False)

        uploaded = (
            self.service.files()
            .create(
                body=file_metadata,
                media_body=media,
                supportsAllDrives=True,
                fields="id, name, mimeType, size, webViewLink, webContentLink, parents, createdTime",
            )
            .execute()
        )

        return {
            "drive_file_id": uploaded["id"],
            "drive_folder_id": parent_folder_id,
            "drive_web_url": uploaded.get("webViewLink", ""),
            "drive_content_url": uploaded.get("webContentLink", ""),
            "file_name": uploaded.get("name", filename),
            "mime_type": uploaded.get("mimeType", mime_type),
            "size": int(uploaded.get("size", content_size)),
            "created_time": uploaded.get("createdTime"),
        }

    @retry_drive_call
    def download_file(self, file_id: str) -> bytes:
        """Download a file's binary content from the Shared Drive."""
        request = self.service.files().get_media(fileId=file_id, supportsAllDrives=True)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return fh.getvalue()

    @retry_drive_call
    def delete_file(self, file_id: str) -> bool:
        """Permanently delete a file or folder from the Shared Drive."""
        self.service.files().delete(fileId=file_id, supportsAllDrives=True).execute()
        return True

    @retry_drive_call
    def move_file(self, file_id: str, target_folder_id: str) -> Dict[str, str]:
        """Move a file to a new folder within the Shared Drive."""
        file_obj = (
            self.service.files()
            .get(fileId=file_id, fields="parents", supportsAllDrives=True)
            .execute()
        )
        previous_parents = ",".join(file_obj.get("parents", []))

        updated = (
            self.service.files()
            .update(
                fileId=file_id,
                addParents=target_folder_id,
                removeParents=previous_parents,
                supportsAllDrives=True,
                fields="id, name, parents",
            )
            .execute()
        )
        return updated

    @retry_drive_call
    def list_files(
        self,
        folder_id: Optional[str] = None,
        q: Optional[str] = None,
        page_size: int = 100,
    ) -> List[Dict[str, str]]:
        """List files in the Shared Drive or within a specific folder."""
        shared_drive_id = self.get_shared_drive_id()
        query_parts = ["trashed = false"]

        if folder_id:
            query_parts.append(f"'{folder_id}' in parents")
        if q:
            query_parts.append(q)

        full_query = " and ".join(query_parts)

        res = (
            self.service.files()
            .list(
                q=full_query,
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
                corpora="drive",
                driveId=shared_drive_id,
                fields="files(id, name, mimeType, size, webViewLink, parents, createdTime)",
                pageSize=page_size,
            )
            .execute()
        )
        return res.get("files", [])

    @retry_drive_call
    def get_file_metadata(self, file_id: str) -> Dict[str, Union[str, int]]:
        """Retrieve detailed metadata for a file in the Shared Drive."""
        meta = (
            self.service.files()
            .get(
                fileId=file_id,
                supportsAllDrives=True,
                fields="id, name, mimeType, size, webViewLink, webContentLink, parents, createdTime, description",
            )
            .execute()
        )
        return {
            "drive_file_id": meta["id"],
            "file_name": meta.get("name"),
            "mime_type": meta.get("mimeType"),
            "size": int(meta.get("size", 0)),
            "drive_web_url": meta.get("webViewLink", ""),
            "drive_content_url": meta.get("webContentLink", ""),
            "parents": meta.get("parents", []),
            "created_time": meta.get("createdTime"),
            "description": meta.get("description", ""),
        }


# Module singleton
drive_service = GoogleDriveService()
