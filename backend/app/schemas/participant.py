"""
Pydantic schemas for Participant management with strict input validation.
Compatible with both id/name/email and participant_id/recipient_name/recipient_email naming conventions.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ParticipantCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    recipient_name: Optional[str] = Field(None, max_length=150)
    name: Optional[str] = Field(None, max_length=150)
    recipient_email: Optional[str] = None
    email: Optional[str] = None
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def validate_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            name_val = data.get("recipient_name") or data.get("name")
            if not name_val or not str(name_val).strip():
                raise ValueError("Participant name cannot be empty.")
            clean_name = str(name_val).strip()
            if any(ord(c) < 32 for c in clean_name):
                raise ValueError("Participant name contains invalid control characters.")

            email_val = data.get("recipient_email") or data.get("email")
            if not email_val or not str(email_val).strip():
                raise ValueError("Participant email cannot be empty.")
            clean_email = str(email_val).strip().lower()

            data["recipient_name"] = clean_name
            data["name"] = clean_name
            data["recipient_email"] = clean_email
            data["email"] = clean_email
        return data


class ParticipantResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", from_attributes=True)

    id: str
    participant_id: str
    name: str
    recipient_name: str
    email: str
    recipient_email: str
    email_status: str = "queued"
    status: str = "queued"
    attempt_count: int = 0
    gmail_message_id: Optional[str] = None
    certificate_drive_file_id: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    created_at: Optional[str] = None
    sent_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            p_id = str(data.get("participant_id") or data.get("id") or "")
            r_name = str(data.get("recipient_name") or data.get("name") or "")
            r_email = str(data.get("recipient_email") or data.get("email") or "")
            st = str(data.get("email_status") or data.get("status") or "queued")
            data["id"] = p_id
            data["participant_id"] = p_id
            data["name"] = r_name
            data["recipient_name"] = r_name
            data["email"] = r_email
            data["recipient_email"] = r_email
            data["email_status"] = st
            data["status"] = st
        return data


class ParticipantUploadResponse(BaseModel):
    campaign_id: str
    imported_count: int
    skipped_count: int
    total_recipients: int
    message: str
