"""
Pydantic schemas for Email distribution and status tracking in CertFlow.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class EmailLogResponse(BaseModel):
    id: Optional[str] = None
    participant_id: Optional[str] = None
    campaign_id: Optional[str] = None
    recipient_email: str
    recipient_name: Optional[str] = None
    subject: Optional[str] = "Your Certificate"
    status: str = "queued"
    email_status: Optional[str] = None
    attempt_count: int = 0
    max_attempts: int = 3
    gmail_message_id: Optional[str] = None
    drive_file_id: Optional[str] = None
    certificate_drive_file_id: Optional[str] = None
    last_error_code: Optional[str] = None
    last_error_message: Optional[str] = None
    sent_at: Optional[str] = None
    updated_at: Optional[str] = None

    class Config:
        from_attributes = True
        extra = "ignore"


class CampaignEmailStatusResponse(BaseModel):
    campaign_id: str
    campaign_status: str = "draft"
    total_count: int = 0
    sent_count: int = 0
    failed_count: int = 0
    queued_count: int = 0
    processing_count: int = 0
    retrying_count: int = 0
    cancelled_count: int = 0
    unknown_count: int = 0
    recent_logs: List[Dict[str, Any]] = Field(default_factory=list)


class RetryFailedRequest(BaseModel):
    campaign_id: str
