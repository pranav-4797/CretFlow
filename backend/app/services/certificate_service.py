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
    ) -> Image.Image:
        """
        Draw participant name and metadata onto template background image.
        Coordinates are percentage-based (0 to 100) for resolution-independent placement.
        """
        # Load template image
        img = Image.open(io.BytesIO(template_bytes)).convert("RGB")
        width, height = img.size
        draw = ImageDraw.Draw(img)

        # 1. Name placement
        name_x_pct = float(config.get("name_x_percent", 50.0))
        name_y_pct = float(config.get("name_y_percent", 48.0))
        font_family = config.get("font_family", DEFAULT_FONT)
        font_size = int(config.get("font_size", 64))
        font_color = config.get("font_color", "#1e293b")
        text_align = config.get("text_align", "center")  # "center", "left", "right"

        rgb_color = _hex_to_rgb(font_color)
        font = cls.load_font(font_family, font_size)

        # Calculate absolute pixel coordinates
        x_px = int((name_x_pct / 100.0) * width)
        y_px = int((name_y_pct / 100.0) * height)

        # Anchor mapping for PIL
        # "mm" = middle horizontal, middle vertical (center)
        # "lm" = left horizontal, middle vertical
        # "rm" = right horizontal, middle vertical
        anchor_map = {
            "center": "mm",
            "left": "lm",
            "right": "rm",
        }
        anchor = anchor_map.get(text_align, "mm")

        # Draw participant name
        draw.text(
            (x_px, y_px),
            participant_name.strip(),
            fill=rgb_color,
            font=font,
            anchor=anchor,
        )

        # 2. Optional Certificate ID placement
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

        # 3. Optional Date placement
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
    ) -> bytes:
        """Generate high-resolution PDF bytes for a single participant."""
        img = cls.render_certificate_image(
            template_bytes=template_bytes,
            participant_name=participant_name,
            config=config,
            certificate_id=certificate_id,
            event_name=event_name,
            date_str=date_str,
        )
        pdf_buffer = io.BytesIO()
        img.save(pdf_buffer, format="PDF", resolution=300.0)
        return pdf_buffer.getvalue()

    @classmethod
    def generate_preview_base64(
        cls,
        template_bytes: bytes,
        participant_name: str,
        config: Dict[str, Any],
        certificate_id: Optional[str] = "CERT-PREVIEW-001",
    ) -> str:
        """Render PNG preview and return as base64 data URI for instant web display."""
        img = cls.render_certificate_image(
            template_bytes=template_bytes,
            participant_name=participant_name,
            config=config,
            certificate_id=certificate_id,
        )
        # Create web-friendly resized preview (max 1200px width for fast rendering)
        max_preview_width = 1200
        if img.width > max_preview_width:
            aspect = img.height / img.width
            new_height = int(max_preview_width * aspect)
            img = img.resize((max_preview_width, new_height), Image.Resampling.LANCZOS)

        preview_buf = io.BytesIO()
        img.save(preview_buf, format="JPEG", quality=85)
        b64 = base64.b64encode(preview_buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"


certificate_service = CertificateService()
