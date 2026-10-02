"""
Pydantic schemas for Campaign management with strict input validation.
Compatible with both id/name/user_id and campaign_id/campaign_name/owner_uid naming conventions.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class CreateCampaignRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    campaign_name: Optional[str] = Field(None, max_length=150, description="Campaign display name")
    name: Optional[str] = Field(None, max_length=150, description="Campaign display name alias")
    description: Optional[str] = Field(None, max_length=1000)
    subject_template: Optional[str] = Field("Your Certificate", max_length=200)
    body_template: Optional[str] = Field(None, max_length=5000)

    @model_validator(mode="before")
    @classmethod
    def validate_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            name_val = data.get("campaign_name") or data.get("name")
            if not name_val or not str(name_val).strip():
                raise ValueError("Campaign name cannot be empty or whitespace.")
            clean = str(name_val).strip()
            if any(ord(c) < 32 for c in clean):
                raise ValueError("Campaign name contains invalid control characters.")
            data["campaign_name"] = clean
            data["name"] = clean
        return data


class UpdateCampaignRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    campaign_name: Optional[str] = Field(None, min_length=1, max_length=150)
    name: Optional[str] = Field(None, min_length=1, max_length=150)
    description: Optional[str] = Field(None, max_length=1000)
    subject_template: Optional[str] = Field(None, max_length=200)
    body_template: Optional[str] = Field(None, max_length=5000)
    status: Optional[str] = Field(None, pattern="^(draft|active|processing|paused|completed|failed|cancelled)$")

    @model_validator(mode="before")
    @classmethod
    def sanitize_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            name_val = data.get("campaign_name") or data.get("name")
            if name_val is not None:
                clean = str(name_val).strip()
                if not clean:
                    raise ValueError("Campaign name cannot be empty.")
                if any(ord(c) < 32 for c in clean):
                    raise ValueError("Campaign name contains invalid control characters.")
                data["campaign_name"] = clean
                data["name"] = clean
        return data


class CampaignResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore", from_attributes=True)

    id: str
    campaign_id: str
    user_id: str
    owner_uid: str
    name: str
    campaign_name: str
    description: Optional[str] = None
    status: str = "draft"
    total_recipients: int = 0
    queued_count: int = 0
    processing_count: int = 0
    sent_count: int = 0
    failed_count: int = 0
    cancelled_count: int = 0
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            c_id = str(data.get("campaign_id") or data.get("id") or "")
            u_id = str(data.get("owner_uid") or data.get("user_id") or data.get("userId") or "")
            c_name = str(data.get("campaign_name") or data.get("name") or "")
            data["id"] = c_id
            data["campaign_id"] = c_id
            data["user_id"] = u_id
            data["owner_uid"] = u_id
            data["name"] = c_name
            data["campaign_name"] = c_name
        return data
