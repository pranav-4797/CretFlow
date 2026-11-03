import base64
import io
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from PIL import Image
import structlog

from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.template import (
    TemplateConfig,
    TemplateResponse,
    TemplateUploadResponse,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
)
from app.services.certificate_service import certificate_service
from app.services.drive_service import drive_service
from app.services.firestore_service import firestore_service

router = APIRouter()
log = structlog.get_logger(__name__)


@router.get("/{campaign_id}", response_model=TemplateResponse, summary="Get certificate template")
async def get_template(
    campaign_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    uid_check = None if current_user.is_admin else current_user.uid
    campaign = firestore_service.get_campaign(campaign_id, user_id=uid_check)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    template_data = campaign.get("template") or {}
    has_template = bool(template_data.get("template_bytes_b64") or template_data.get("template_drive_file_id"))

    raw_config = template_data.get("config") or {}
    config = TemplateConfig(**raw_config) if raw_config else TemplateConfig()

    image_url = template_data.get("template_image_url")
    # If base64 is stored, return data URL
    if not image_url and template_data.get("template_bytes_b64"):
        image_url = f"data:image/jpeg;base64,{template_data['template_bytes_b64']}"

    return TemplateResponse(
        campaign_id=campaign_id,
        has_template=has_template,
        template_image_url=image_url,
        template_drive_file_id=template_data.get("template_drive_file_id"),
        config=config,
    )


@router.post("/{campaign_id}/upload", response_model=TemplateUploadResponse, summary="Upload certificate template image")
async def upload_template(
    campaign_id: str,
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    uid_check = None if current_user.is_admin else current_user.uid
    campaign = firestore_service.get_campaign(campaign_id, user_id=uid_check)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    # Validate image format
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be an image (PNG, JPG)")

    file_bytes = await file.read()
    if len(file_bytes) > 20 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template image exceeds 20MB limit")

    try:
        pil_img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        width, height = pil_img.size
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid image file: {str(e)}")

    # Compress / resize if extremely high resolution (> 3000px on long edge) to save storage
    max_dim = 3000
    if max(width, height) > max_dim:
        scale = max_dim / max(width, height)
        pil_img = pil_img.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)
        width, height = pil_img.size

    # Convert to JPEG for compact storage in Firestore (and optionally Drive)
    buffer = io.BytesIO()
    pil_img.save(buffer, format="JPEG", quality=88, optimize=True)
    optimized_bytes = buffer.getvalue()

    # Upload to Shared Drive if available
    drive_file_id = None
    try:
        drive_file_id = drive_service.upload_file(
            file_bytes=optimized_bytes,
            filename=f"template_{campaign_id}.jpg",
            mime_type="image/jpeg",
        )
    except Exception as e:
        log.warning("Drive upload failed for template, will rely on Firestore fallback", error=str(e))

    # Base64 string for direct rendering in canvas
    b64_str = base64.b64encode(optimized_bytes).decode("ascii")
    data_url = f"data:image/jpeg;base64,{b64_str}"

    default_config = TemplateConfig()
    template_doc = {
        "template_image_url": data_url,
        "template_bytes_b64": b64_str,
        "template_drive_file_id": drive_file_id,
        "width": width,
        "height": height,
        "config": default_config.model_dump(),
    }

    firestore_service.update_campaign(campaign_id, {"template": template_doc})

    log.info("Certificate template uploaded", campaign_id=campaign_id, width=width, height=height)

    return TemplateUploadResponse(
        campaign_id=campaign_id,
        message="Template uploaded and configured successfully.",
        template_image_url=data_url,
        template_drive_file_id=drive_file_id,
        width=width,
        height=height,
        config=default_config,
    )


@router.put("/{campaign_id}/config", summary="Update template design coordinates and typography")
async def update_template_config(
    campaign_id: str,
    config: TemplateConfig,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    uid_check = None if current_user.is_admin else current_user.uid
    campaign = firestore_service.get_campaign(campaign_id, user_id=uid_check)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    existing_template = campaign.get("template") or {}
    existing_template["config"] = config.model_dump()

    firestore_service.update_campaign(campaign_id, {"template": existing_template})
    return {"success": True, "message": "Template design configuration saved.", "config": config}


@router.post("/{campaign_id}/preview", response_model=TemplatePreviewResponse, summary="Generate live sample preview")
async def preview_template(
    campaign_id: str,
    preview_req: TemplatePreviewRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    uid_check = None if current_user.is_admin else current_user.uid
    campaign = firestore_service.get_campaign(campaign_id, user_id=uid_check)
    if not campaign:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Campaign not found")

    template_data = campaign.get("template") or {}
    b64_bytes = template_data.get("template_bytes_b64")

    if not b64_bytes:
        # Fall back to drive download
        drive_file_id = template_data.get("template_drive_file_id")
        if drive_file_id:
            try:
                raw_bytes = drive_service.download_file(drive_file_id)
            except Exception as e:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Failed to fetch template from Drive: {str(e)}")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No certificate template uploaded yet.")
    else:
        raw_bytes = base64.b64decode(b64_bytes.encode("ascii"))

    preview_url = certificate_service.generate_preview_base64(
        template_bytes=raw_bytes,
        participant_name=preview_req.sample_name,
        config=preview_req.config.model_dump(),
    )

    return TemplatePreviewResponse(
        preview_data_url=preview_url,
        sample_name=preview_req.sample_name,
        config=preview_req.config,
    )
