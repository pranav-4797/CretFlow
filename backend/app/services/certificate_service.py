"""
Certificate Generation Service.

Responsible for:
- Loading certificate background templates (PNG, JPG)
- Rendering participant names and certificate details using bundled Google Fonts
- Supporting precision positioning (percentage-based X, Y for responsive coordinates)
- Generating high-resolution PDFs
- Integrating with Google Shared Drive to store and link certificate PDFs
"""

import base64
import io
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.services.drive_service import drive_service
from app.services.firestore_service import firestore_service

log = structlog.get_logger(__name__)

# Available bundled fonts directory
FONTS_DIR = Path(__file__).parent.parent / "assets" / "fonts"

AVAILABLE_FONTS = {
    "GreatVibes": "GreatVibes.ttf",          # Calligraphy / Script
    "PlayfairDisplay": "PlayfairDisplay.ttf",  # Classic / Luxury Serif
    "Cinzel": "Cinzel.ttf",                  # Academic / Roman Classical
    "Montserrat": "Montserrat.ttf",          # Clean Modern Sans
    "AlexBrush": "AlexBrush.ttf",            # Elegant Cursive Signature
}

DEFAULT_FONT = "PlayfairDisplay"


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    """Convert hex string (e.g. #1e293b or 1e293b) to RGB tuple."""
    hex_clean = hex_color.lstrip("#")
    if len(hex_clean) == 3:
        hex_clean = "".join([c * 2 for c in hex_clean])
    if len(hex_clean) != 6:
        return (30, 41, 59)
    try:
        return tuple(int(hex_clean[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore
    except ValueError:
        return (30, 41, 59)


class CertificateService:
    """Core certificate generation engine using Pillow and ReportLab/PDF."""

    @classmethod
    def get_font_path(cls, font_family: str) -> Optional[Path]:
        """Resolve font file path from bundled fonts."""
        filename = AVAILABLE_FONTS.get(font_family, AVAILABLE_FONTS.get(DEFAULT_FONT))
        if filename:
            path = FONTS_DIR / filename
            if path.exists():
                return path
        # Fallback to any TTF in fonts dir
        if FONTS_DIR.exists():
            for p in FONTS_DIR.glob("*.ttf"):
                return p
        return None

    @classmethod
    def load_font(cls, font_family: str, size: int) -> ImageFont.FreeTypeFont:
        """Load truetype font or fall back gracefully."""
        font_path = cls.get_font_path(font_family)
        if font_path and font_path.exists():
            try:
                return ImageFont.truetype(str(font_path), size)
            except Exception as e:
                log.warning("Failed to load TrueType font, using default", error=str(e), font_family=font_family)
        return ImageFont.load_default()

    @classmethod
    def render_certificate_image(
        cls,
        template_bytes: bytes,
        participant_name: str,
        config: Dict[str, Any],
        certificate_id: Optional[str] = None,
        event_name: Optional[str] = None,
        date_str: Optional[str] = None,
        participant_variables: Optional[Dict[str, Any]] = None,
    ) -> Image.Image:
        """
        Draw dynamic fields onto template background image.
        Coordinates are percentage-based (0 to 100) for resolution-independent placement.
        Supports both modern Canva multi-field layouts and legacy single-name layouts.
        """
        # Load template image
        img = Image.open(io.BytesIO(template_bytes)).convert("RGB")
        width, height = img.size
        draw = ImageDraw.Draw(img)

        # Prepare variable dictionary
        now_date = date_str or datetime.now(timezone.utc).strftime("%B %d, %Y")
        cid_str = certificate_id or "CERT-PREVIEW-001"
        ev_str = event_name or "Certificate Program"

        vars_dict: Dict[str, Any] = {
            "name": participant_name.strip(),
            "recipient_name": participant_name.strip(),
            "student_name": participant_name.strip(),
            "certificate_id": cid_str,
            "cert_id": cid_str,
            "date": now_date,
            "issue_date": now_date,
            "event_date": now_date,
            "event_name": ev_str,
            "event": ev_str,
            "campaign_name": ev_str,
        }
        if participant_variables:
            for k, v in participant_variables.items():
                if v is not None and str(v).strip() and str(v).lower() != "nan":
                    vars_dict[k.lower().strip()] = str(v).strip()

        anchor_map = {
            "center": "mm",
            "left": "lm",
            "right": "rm",
        }

        # Check for modern multi-field Canva configuration
        fields = config.get("fields")
        if fields and len(fields) > 0:
            for f in fields:
                # Handle dictionary or Pydantic model
                field_data = f if isinstance(f, dict) else f.model_dump()
                if not field_data.get("is_enabled", True):
                    continue

                var_key = str(field_data.get("variable_key", "name")).lower().strip()
                # Resolve value
                raw_val = vars_dict.get(var_key)
                if raw_val is None or raw_val == "":
                    raw_val = field_data.get("sample_value") or field_data.get("label") or f"{{{var_key}}}"
                text_to_draw = str(raw_val).strip()
                if not text_to_draw:
                    continue

                x_pct = float(field_data.get("x_percent", 50.0))
                y_pct = float(field_data.get("y_percent", 50.0))
                x_px = int((x_pct / 100.0) * width)
                y_px = int((y_pct / 100.0) * height)

                f_family = field_data.get("font_family", DEFAULT_FONT)
                f_size = int(field_data.get("font_size", 48))
                f_color = field_data.get("font_color", "#1e293b")
                f_align = field_data.get("text_align", "center")

                font = cls.load_font(f_family, f_size)
                rgb_color = _hex_to_rgb(f_color)
                anchor = anchor_map.get(f_align, "mm")

                draw.text(
                    (x_px, y_px),
                    text_to_draw,
                    fill=rgb_color,
                    font=font,
                    anchor=anchor,
                )
            return img

        # Fallback: Legacy single-name layout
        name_x_pct = float(config.get("name_x_percent", 50.0))
        name_y_pct = float(config.get("name_y_percent", 48.0))
        font_family = config.get("font_family", DEFAULT_FONT)
        font_size = int(config.get("font_size", 64))
        font_color = config.get("font_color", "#1e293b")
        text_align = config.get("text_align", "center")

        rgb_color = _hex_to_rgb(font_color)
        font = cls.load_font(font_family, font_size)

        x_px = int((name_x_pct / 100.0) * width)
        y_px = int((name_y_pct / 100.0) * height)
        anchor = anchor_map.get(text_align, "mm")

        draw.text(
            (x_px, y_px),
            participant_name.strip(),
            fill=rgb_color,
            font=font,
            anchor=anchor,
        )

        # Optional Certificate ID placement
        if config.get("show_cert_id", True) and certificate_id:
            cid_x_pct = float(config.get("cert_id_x_percent", 88.0))
            cid_y_pct = float(config.get("cert_id_y_percent", 92.0))
            cid_x = int((cid_x_pct / 100.0) * width)
            cid_y = int((cid_y_pct / 100.0) * height)
            small_font = cls.load_font("Montserrat", max(16, int(font_size * 0.25)))
            draw.text(
                (cid_x, cid_y),
                f"ID: {certificate_id}",
                fill=(100, 116, 139),
                font=small_font,
                anchor="mm",
            )

        # Optional Date placement
        if config.get("show_date", False):
            display_date = date_str or datetime.now(timezone.utc).strftime("%B %d, %Y")
            date_x_pct = float(config.get("date_x_percent", 15.0))
            date_y_pct = float(config.get("date_y_percent", 92.0))
            date_x = int((date_x_pct / 100.0) * width)
            date_y = int((date_y_pct / 100.0) * height)
            date_font = cls.load_font("Montserrat", max(16, int(font_size * 0.25)))
            draw.text(
                (date_x, date_y),
                f"Date: {display_date}",
                fill=(100, 116, 139),
                font=date_font,
                anchor="mm",
            )

        return img

    @classmethod
    def generate_pdf_bytes(
        cls,
        template_bytes: bytes,
        participant_name: str,
        config: Dict[str, Any],
        certificate_id: Optional[str] = None,
        event_name: Optional[str] = None,
        date_str: Optional[str] = None,
        participant_variables: Optional[Dict[str, Any]] = None,
    ) -> bytes:
        """Generate high-resolution PDF bytes for a single participant and cleanly free image memory."""
        img = cls.render_certificate_image(
            template_bytes=template_bytes,
            participant_name=participant_name,
            config=config,
            certificate_id=certificate_id,
            event_name=event_name,
            date_str=date_str,
            participant_variables=participant_variables,
        )
        pdf_buffer = io.BytesIO()
        try:
            img.save(pdf_buffer, format="PDF", resolution=150.0)
            return pdf_buffer.getvalue()
        finally:
            img.close()
            pdf_buffer.close()

    @classmethod
    def generate_preview_base64(
        cls,
        template_bytes: bytes,
        participant_name: str,
        config: Dict[str, Any],
        certificate_id: Optional[str] = "CERT-PREVIEW-001",
        event_name: Optional[str] = None,
        date_str: Optional[str] = None,
        participant_variables: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Render PNG preview and return as base64 data URI for instant web display."""
        img = cls.render_certificate_image(
            template_bytes=template_bytes,
            participant_name=participant_name,
            config=config,
            certificate_id=certificate_id,
            event_name=event_name,
            date_str=date_str,
            participant_variables=participant_variables,
        )
        try:
            # Create web-friendly resized preview (max 1200px width for fast rendering)
            max_preview_width = 1200
            if img.width > max_preview_width:
                aspect = img.height / img.width
                new_height = int(max_preview_width * aspect)
                resized = img.resize((max_preview_width, new_height), Image.Resampling.LANCZOS)
                img.close()
                img = resized

            preview_buf = io.BytesIO()
            try:
                img.save(preview_buf, format="JPEG", quality=85)
                b64 = base64.b64encode(preview_buf.getvalue()).decode("ascii")
                return f"data:image/jpeg;base64,{b64}"
            finally:
                preview_buf.close()
        finally:
            img.close()


certificate_service = CertificateService()
