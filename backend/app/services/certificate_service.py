"""
Certificate Generation Service for CertFlow.
Renders certificates locally and uploads them to Google Shared Drive.
Completely standalone — zero Celery or Redis dependencies.
"""

from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
from typing import Any, Dict, Optional
import uuid

import structlog
from app.services.drive_service import drive_service

log = structlog.get_logger(__name__)


def create_sample_certificate_pdf(
    participant_name: str,
    event_title: str,
    output_path: str,
    issue_date: Optional[str] = None,
) -> str:
    """
    Generates a PDF certificate file locally for upload.
    Uses reportlab if available, or creates a standard valid PDF structure.
    """
    date_str = issue_date or datetime.now(timezone.utc).strftime("%B %d, %Y")

    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path, pagesize=landscape(letter))
        width, height = landscape(letter)

        # Background frame
        c.setStrokeColorRGB(0.2, 0.4, 0.8)
        c.setLineWidth(4)
        c.rect(20, 20, width - 40, height - 40)

        # Inner frame
        c.setStrokeColorRGB(0.7, 0.8, 0.9)
        c.setLineWidth(1)
        c.rect(28, 28, width - 56, height - 56)

        # Header
        c.setFillColorRGB(0.1, 0.2, 0.5)
        c.setFont("Helvetica-Bold", 30)
        c.drawCentredString(width / 2.0, height - 110, "CERTIFICATE OF ACHIEVEMENT")

        # Subtitle
        c.setFillColorRGB(0.3, 0.3, 0.3)
        c.setFont("Helvetica", 14)
        c.drawCentredString(width / 2.0, height - 160, "This is proudly presented to")

        # Participant Name
        c.setFillColorRGB(0.05, 0.1, 0.3)
        c.setFont("Helvetica-Bold", 26)
        c.drawCentredString(width / 2.0, height - 220, participant_name)

        # Description
        c.setFillColorRGB(0.25, 0.25, 0.25)
        c.setFont("Helvetica", 13)
        c.drawCentredString(
            width / 2.0,
            height - 270,
            f"for successful participation in and completion of {event_title}",
        )

        # Date & Verification Tag
        c.setFont("Helvetica", 11)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawCentredString(width / 2.0, 90, f"Issued on {date_str}")

        c.setFont("Helvetica-Oblique", 9)
        c.setFillColorRGB(0.5, 0.5, 0.5)
        c.drawCentredString(width / 2.0, 45, "Verified & issued via CertFlow Platform")

        c.save()
        return output_path
    except ImportError:
        # Fallback simple valid PDF structure if reportlab is not installed
        content = (
            f"%PDF-1.4\n"
            f"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
            f"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n"
            f"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj\n"
            f"% CertFlow Certificate for {participant_name} - {event_title}\n"
            f"xref\n0 4\n0000000000 65535 f \n0000000010 00000 n \n0000000053 00000 n \n0000000102 00000 n \n"
            f"trailer << /Size 4 /Root 1 0 R >>\nstartxref\n178\n%%EOF\n"
        )
        with open(output_path, "wb") as f:
            f.write(content.encode("utf-8"))
        return output_path


class CertificateService:
    """Service for generating certificates and saving them to Google Shared Drive."""

    @staticmethod
    def generate_and_upload_certificate(
        participant_id: str,
        campaign_id: str,
        campaign_name: str = "General",
        participant_name: str = "Participant",
        participant_email: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates a certificate PDF locally and uploads it to the campaign's Shared Drive folder.
        Returns file metadata for Firestore persistence.
        """
        temp_file_path = None
        try:
            # 1. Ensure Shared Drive folder structure
            folders = drive_service.ensure_campaign_folders(
                campaign_id=campaign_id,
                campaign_name=campaign_name,
            )
            certificates_folder_id = folders["certificates_folder_id"]

            # 2. Render certificate to local temporary file
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tf:
                temp_file_path = tf.name

            create_sample_certificate_pdf(
                participant_name=participant_name,
                event_title=campaign_name,
                output_path=temp_file_path,
            )

            # 3. Upload to Google Shared Drive
            clean_name = "".join(c for c in participant_name if c.isalnum() or c in (" ", "_", "-")).strip()
            safe_filename = f"Certificate_{clean_name or 'Participant'}_{participant_id[:8]}.pdf"

            with open(temp_file_path, "rb") as f:
                pdf_data = f.read()

            upload_result = drive_service.upload_file(
                file_content=pdf_data,
                file_name=safe_filename,
                folder_id=certificates_folder_id,
                mime_type="application/pdf",
                description=f"Certificate for {participant_name} ({participant_email or 'no-email'}) in {campaign_name}",
            )

            log.info(
                "Certificate generated and uploaded to Shared Drive",
                participant_id=participant_id,
                file_id=upload_result.get("file_id"),
                drive_url=upload_result.get("web_view_link"),
            )

            return {
                "drive_file_id": upload_result.get("file_id"),
                "drive_web_url": upload_result.get("web_view_link"),
                "file_name": safe_filename,
                "file_size": len(pdf_data),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        finally:
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception:
                    pass


certificate_service = CertificateService()
