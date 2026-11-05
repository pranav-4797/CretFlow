"""Pydantic schemas for certificate template configuration and generation."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CertificateField(BaseModel):
    """A dynamic visual field placed on the certificate background."""
    id: str = Field(..., description="Unique field identifier, e.g. field_name_1")
    label: str = Field(..., description="Human-readable label, e.g. Participant Name")
    variable_key: str = Field(..., description="Dynamic variable tag, e.g. name, college, date, rank")
    x_percent: float = Field(50.0, ge=0.0, le=100.0, description="Horizontal center position (0-100%)")
    y_percent: float = Field(50.0, ge=0.0, le=100.0, description="Vertical center position (0-100%)")
    font_family: str = Field("PlayfairDisplay", description="Bundled font family name")
    font_size: int = Field(48, ge=2, le=300, description="Font size in points")
    font_color: str = Field("#1e293b", description="Hex font color code")
    text_align: str = Field("center", description="Text alignment: center, left, right")
    is_enabled: bool = Field(True, description="Whether this field is visible and rendered")
    sample_value: Optional[str] = Field(None, description="Sample preview value")


class TemplateConfig(BaseModel):
    """Certificate layout configuration with support for multiple dynamic fields."""
    # Modern Canva-style multi-field layout
    fields: Optional[List[CertificateField]] = Field(default_factory=list)

    # Legacy attributes maintained for 100% backwards compatibility with earlier campaigns
    font_family: str = Field("PlayfairDisplay", description="Bundled font family name")
    font_size: int = Field(64, ge=2, le=300, description="Font size in points")
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

    def get_effective_fields(self) -> List[CertificateField]:
        """
        Return the list of active fields. If modern `fields` list is empty,
        seamlessly converts legacy single-name config into field objects.
        """
        if self.fields and len(self.fields) > 0:
            return self.fields

        # Legacy fallback
        generated: List[CertificateField] = [
            CertificateField(
                id="field_name",
                label="Participant Name",
                variable_key="name",
                x_percent=self.name_x_percent,
                y_percent=self.name_y_percent,
                font_family=self.font_family,
                font_size=self.font_size,
                font_color=self.font_color,
                text_align=self.text_align,
                is_enabled=True,
                sample_value="Jane Doe",
            )
        ]
        if self.show_cert_id:
            generated.append(
                CertificateField(
                    id="field_cert_id",
                    label="Certificate ID",
                    variable_key="certificate_id",
                    x_percent=self.cert_id_x_percent,
                    y_percent=self.cert_id_y_percent,
                    font_family="Montserrat",
                    font_size=max(16, int(self.font_size * 0.25)),
                    font_color="#64748b",
                    text_align="center",
                    is_enabled=True,
                    sample_value="CERT-2026-001",
                )
            )
        if self.show_date:
            generated.append(
                CertificateField(
                    id="field_date",
                    label="Issue Date",
                    variable_key="date",
                    x_percent=self.date_x_percent,
                    y_percent=self.date_y_percent,
                    font_family="Montserrat",
                    font_size=max(16, int(self.font_size * 0.25)),
                    font_color="#64748b",
                    text_align="center",
                    is_enabled=True,
                    sample_value="November 05, 2026",
                )
            )
        return generated


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
    sample_name: Optional[str] = Field("Jane Doe", max_length=100)
    sample_variables: Optional[Dict[str, Any]] = Field(default_factory=dict)
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
