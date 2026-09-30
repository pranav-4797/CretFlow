"""
Application configuration loaded from environment variables.
All settings are typed and validated by Pydantic.

NEVER hardcode secrets here — use environment variables.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings.

    All values are loaded from environment variables (or .env file).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    environment: str = "development"
    log_level: str = "INFO"

    # ── URLs ──────────────────────────────────────────────────────────────────
    frontend_url: str = "http://localhost:5173"
    backend_url: str = "http://localhost:8000"

    @property
    def backend_host(self) -> str:
        """Extract hostname from backend URL."""
        from urllib.parse import urlparse
        return urlparse(self.backend_url).netloc

    # ── CORS ──────────────────────────────────────────────────────────────────
    allowed_origins: str = "http://localhost:5173"

    @property
    def allowed_origins_list(self) -> List[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/certflow"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── Security ──────────────────────────────────────────────────────────────
    secret_key: str = "dev-secret-key-change-in-production-32chars!"

    # ── Firebase ──────────────────────────────────────────────────────────────
    firebase_project_id: str = "placeholder"
    firebase_client_email: str = "placeholder@placeholder.iam.gserviceaccount.com"
    firebase_private_key: str = "placeholder"
    firebase_credentials_path: Optional[str] = None

    # ── Google OAuth ──────────────────────────────────────────────────────────
    google_client_id: str = "placeholder.apps.googleusercontent.com"
    google_client_secret: str = "placeholder"
    google_redirect_uri: str = "http://localhost:8000/api/gmail/callback"
    google_client_secrets_path: Optional[str] = "client_secret.json"

    # ── Google Drive / Shared Drive Storage ───────────────────────────────────
    storage_provider: str = "shared_drive"  # "shared_drive", "google_drive", or "r2"
    google_drive_shared_drive_name: str = "CertFlow"
    google_drive_shared_drive_id: Optional[str] = None
    google_drive_folder_id: Optional[str] = None
    google_drive_service_account_path: Optional[str] = None
    google_drive_service_account_email: Optional[str] = None
    google_drive_service_account_private_key: Optional[str] = None

    # ── Cloudflare R2 (Alternative Storage) ───────────────────────────────────
    r2_endpoint: str = "https://placeholder.r2.cloudflarestorage.com"
    r2_access_key_id: str = "placeholder"
    r2_secret_access_key: str = "placeholder"
    r2_bucket: str = "certflow-dev"

    # ── File Limits ───────────────────────────────────────────────────────────
    max_upload_size_mb: int = 50
    max_template_size_mb: int = 20
    allowed_excel_extensions: List[str] = [".xlsx", ".xls", ".csv"]
    allowed_template_extensions: List[str] = [".png", ".jpg", ".jpeg"]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"

    @field_validator("firebase_private_key")
    @classmethod
    def parse_firebase_key(cls, v: str) -> str:
        """Replace escaped newlines from environment variable."""
        return v.replace("\\n", "\n")


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance.

    Using lru_cache ensures settings are loaded only once.
    In tests, clear the cache with get_settings.cache_clear().
    """
    return Settings()


# Module-level singleton for convenient import
settings = get_settings()
