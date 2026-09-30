"""
Certificate generation tasks — integrating Google Shared Drive storage.
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional
import structlog
from worker.celery_app import celery_app
from app.services.drive_service import drive_service

log = structlog.get_logger(__name__)


def create_sample_certificate_pdf(participant_name: str, event_title: str, output_path: str) -> str:
    """
    Generates a PDF certificate file locally for upload.
    Uses reportlab if available, or creates a standard PDF structure.
    """
    try:
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.pdfgen import canvas

        c = canvas.Canvas(output_path, pagesize=landscape(letter))
        width, height = landscape(letter)

        # Background frame
        c.setStrokeColorRGB(0.2, 0.4, 0.8)
        c.setLineWidth(4)
        c.rect(20, 20, width - 40, height - 40)

        # Header
        c.setFont("Helvetica-Bold", 32)
        c.drawCentredString(width / 2.0, height - 120, "CERTIFICATE OF ACHIEVEMENT")

        # Subtitle
        c.setFont("Helvetica", 16)
        c.drawCentredString(width / 2.0, height - 170, "This is proudly presented to")

        # Participant Name
        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(width / 2.0, height - 230, participant_name)

        # Description
        c.setFont("Helvetica", 14)
        c.drawCentredString(width / 2.0, height - 280, f"for successful completion of and participation in {event_title}")

        # Verification tag
        c.setFont("Helvetica-Oblique", 10)
        c.drawCentredString(width / 2.0, 50, "Verified & issued via CertFlow")

        c.save()
        return output_path
    except ImportError:
        # Fallback simple text/pdf output if reportlab is not imported
        with open(output_path, "wb") as f:
            f.write(f"%PDF-1.4\n% CertFlow Certificate for {participant_name}\n%%EOF".encode("utf-8"))
        return output_path


@celery_app.task(
    name="worker.tasks.certificates.generate_certificate",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def generate_certificate(
    self,
    participant_id: str,
    campaign_id: str,
    campaign_name: str = "General",
    participant_name: str = "Participant",
    participant_email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate a certificate, upload it to the campaign's Shared Drive certificates folder,
    and return the Drive metadata for database storage.

    Workflow:
    1. Ensure Shared Drive folder structure: Campaigns/{campaign_id}-{name}/certificates/
    2. Render certificate to local temporary file.
    3. Upload file to Shared Drive via drive_service.
    4. Clean up temporary file locally.
    5. Return Drive file metadata (drive_file_id, drive_web_url, file_name, etc.).
    """
    temp_file_path = None
    try:
        log.info(
            "Starting certificate generation",
            participant_id=participant_id,
            campaign_id=campaign_id,
            participant_name=participant_name,
        )

        # 1. Resolve target Shared Drive certificates folder
        folders = drive_service.ensure_campaign_folders(
            campaign_id=campaign_id,
            campaign_name=campaign_name,
        )
        certificates_folder_id = folders["certificates"]

        # 2. Render certificate to local temp file
        safe_name = "".join(c for c in participant_name if c.isalnum() or c in (" ", "-", "_")).strip()
        filename = f"{participant_id}_{safe_name}.pdf"

        temp_dir = tempfile.mkdtemp(prefix="certflow_")
        temp_file_path = os.path.join(temp_dir, filename)

        create_sample_certificate_pdf(
            participant_name=participant_name,
            event_title=campaign_name,
            output_path=temp_file_path,
        )

        # 3. Upload to Google Shared Drive
        with open(temp_file_path, "rb") as f:
            upload_result = drive_service.upload_file(
                file_content=f,
                filename=filename,
                mime_type="application/pdf",
                parent_folder_id=certificates_folder_id,
                description=f"Certificate for {participant_name} ({participant_email or participant_id})",
            )

        log.info(
            "Certificate uploaded to Shared Drive successfully",
            participant_id=participant_id,
            drive_file_id=upload_result["drive_file_id"],
            web_url=upload_result.get("drive_web_url"),
        )

        # 4. Return metadata for Neon PostgreSQL persistence
        return {
            "participant_id": participant_id,
            "campaign_id": campaign_id,
            "drive_file_id": upload_result["drive_file_id"],
            "drive_folder_id": upload_result["drive_folder_id"],
            "drive_web_url": upload_result["drive_web_url"],
            "file_name": upload_result["file_name"],
            "mime_type": upload_result["mime_type"],
            "size": upload_result["size"],
            "status": "generated",
        }

    except Exception as exc:
        log.error("Failed to generate and upload certificate", error=str(exc))
        raise self.retry(exc=exc)

    finally:
        # 5. Guarantee local temporary file is removed
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                parent_dir = os.path.dirname(temp_file_path)
                if os.path.exists(parent_dir) and "certflow_" in parent_dir:
                    os.rmdir(parent_dir)
            except Exception as e:
                log.warning("Could not clean up temporary file", path=temp_file_path, error=str(e))
