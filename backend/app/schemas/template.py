"""Pydantic schemas for certificate template configuration and generation."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class TemplateConfig(BaseModel):
    font_family: str = Field("PlayfairDisplay", description="Bundled font family name")
    font_size: int = Field(64, ge=12, le=200, description="Font size in points")
    font_color: str = Field("#1e293b", description="Hex font color code")
    name_x_percent: float = Field(50.0, ge=0.0, le=100.0, description="Horizontal center position (0-100%)")
    name_y_percent: float = Field(48.0, ge=0.0, le=100.0, description="Vertical center position (0-100%)")
    text_align: str = Field("center", description="Text alignment: center, left, right")
    show_cert_id: bool = Field(True, description="Whether to display certificate ID")
    cert_id_x_percent: float = Field(88.0, ge=0.0, le=100.0)
    cert_id_y_percent: float = Field(92.0, ge=0.0, le=100.0)
    show_date: bool = Field(False, description="Whether to display issue date")
    date_x_percent: float = Field(15.0, ge=0.0, le=100.0)
    date_y_percent: float = Field(92.0, ge=0.0, le=100.0)


class TemplateUploadResponse(BaseModel):
    campaign_id: str
    message: str
    template_image_url: Optional[str] = None
    template_drive_file_id: Optional[str] = None
    width: int
    height: int
    config: TemplateConfig


class TemplateResponse(BaseModel):
    campaign_id: str
    has_template: bool
    template_image_url: Optional[str] = None
    template_drive_file_id: Optional[str] = None
    config: TemplateConfig


class TemplatePreviewRequest(BaseModel):
    sample_name: str = Field("Jane Doe", max_length=100)
    config: TemplateConfig


class TemplatePreviewResponse(BaseModel):
    preview_data_url: str
    sample_name: str
    config: TemplateConfig


class GenerateCertificatesRequest(BaseModel):
    campaign_id: str
    override_existing: bool = Field(False, description="Regenerate already generated certificates")


class GenerateCertificatesResponse(BaseModel):
    campaign_id: str
    total_participants: int
    generated_count: int
    skipped_count: int
    failed_count: int
    message: str
