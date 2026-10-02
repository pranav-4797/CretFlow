"""
Pydantic schemas for Gmail API integration.
"""

from datetime import datetime
from typing import Any, Dict, Optional
from pydantic import BaseModel, EmailStr, Field


class GmailConnectResponse(BaseModel):
    authorization_url: str = Field(..., description="Google OAuth 2.0 authorization URL")


class GmailStatusResponse(BaseModel):
    is_connected: bool
    google_email: Optional[str] = None
    connected_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    scopes: Optional[str] = None


class GmailDisconnectResponse(BaseModel):
    success: bool
    message: str


class GmailTestEmailRequest(BaseModel):
    recipient_email: EmailStr = Field(..., description="Recipient email address for the test")
    subject: Optional[str] = Field("CertFlow Gmail Integration Test", max_length=200)
    custom_message: Optional[str] = Field(None, max_length=1000)


class GmailTestEmailResponse(BaseModel):
    success: bool
    message: str
    message_id: Optional[str] = None
    sender: str
    recipient: str


class SendPreviewRequest(BaseModel):
    subject_template: str = Field(..., max_length=200)
    body_template: str = Field(..., max_length=5000)
    sample_variables: Dict[str, Any] = Field(default_factory=dict)


class SendPreviewResponse(BaseModel):
    rendered_subject: str
    rendered_html: str
    rendered_text: str


class SendCampaignRequest(BaseModel):
    campaign_id: str
    subject_template: str = Field(..., max_length=200)
    body_template: str = Field(..., max_length=5000)
    confirm: bool = Field(..., description="Explicit confirmation required to trigger bulk sending")


class SendCampaignResponse(BaseModel):
    campaign_id: str
    status: str
    queued_count: int
    message: str
