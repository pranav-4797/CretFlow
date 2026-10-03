"""Pydantic schemas for Google Forms and external automation webhooks."""
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class GoogleFormWebhookPayload(BaseModel):
    recipient_name: str = Field(..., min_length=1, max_length=150, description="Student/Participant full name")
    recipient_email: EmailStr = Field(..., description="Student email address")
    score: float = Field(..., ge=0, description="Achieved score or percentage")
    total_score: Optional[float] = Field(100.0, gt=0, description="Total maximum achievable score")
    passing_score: Optional[float] = Field(None, ge=0, le=100, description="Override passing percentage threshold (0-100)")
    webhook_secret: Optional[str] = Field(None, description="Optional secret token for authentication")


class GoogleFormWebhookResponse(BaseModel):
    status: str = Field(..., description="'issued', 'below_threshold', or 'error'")
    campaign_id: str
    recipient_name: str
    recipient_email: str
    score: float
    total_score: float
    score_percentage: float
    passing_threshold_percentage: float
    passed: bool
    certificate_id: Optional[str] = None
    email_sent: bool = False
    message: str


class CampaignWebhookConfig(BaseModel):
    passing_score: float = Field(60.0, ge=0.0, le=100.0, description="Minimum percentage required to earn certificate")
    auto_email: bool = Field(True, description="Whether to automatically dispatch email with certificate immediately")
    webhook_secret: Optional[str] = Field(None, max_length=64, description="Optional secret token to authenticate incoming submissions")
    quiz_email_subject: Optional[str] = Field(
        None,
        max_length=200,
        description="Custom subject line for quiz certificate emails (supports {{name}}, {{event_name}}, {{score_percentage}})"
    )
    quiz_email_body: Optional[str] = Field(
        None,
        description="Custom message content for the quiz email body (supports {{name}}, {{event_name}}, {{score}}, {{score_percentage}}, {{total_score}}, {{certificate_id}})"
    )
    show_score_in_email: bool = Field(
        True,
        description="Whether to show the student's score and percentage box in the email"
    )
