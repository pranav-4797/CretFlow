"""Certificate template endpoints."""
import base64
import io
from typing import Any, Dict

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image

from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.template import (
    TemplateConfig,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateResponse,
    TemplateUploadResponse,
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
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
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
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
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

    # 1. Upload to Google Shared Drive if available
    drive_file_id = None
    try:
        folders = drive_service.ensure_campaign_folders(campaign_id, campaign.get("campaign_name", "Campaign"))
        template_folder_id = folders.get("template")
        drive_res = drive_service.upload_file(
            file_bytes=file_bytes,
            filename=f"template_{campaign_id}_{file.filename}",
            parent_folder_id=template_folder_id,
            mime_type=file.content_type or "image/png",
        )
        drive_file_id = drive_res.get("id")
        log.info("Uploaded template to Google Shared Drive", file_id=drive_file_id)
    except Exception as e:
        log.warning("Could not upload template to Shared Drive, using Firestore base64 backup", error=str(e))

    # Keep compressed base64 for fast client previews
    preview_img = pil_img.copy()
    if preview_img.width > 1400:
        aspect = preview_img.height / preview_img.width
        preview_img = preview_img.resize((1400, int(1400 * aspect)), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    preview_img.save(buf, format="JPEG", quality=80)
    b64_str = base64.b64encode(buf.getvalue()).decode("ascii")

    default_config = TemplateConfig()
    template_data = {
        "template_drive_file_id": drive_file_id,
        "template_bytes_b64": b64_str,
        "filename": file.filename,
        "width": width,
        "height": height,
        "config": default_config.model_dump(),
    }

    firestore_service.update_campaign(campaign_id, {"template": template_data})

    return TemplateUploadResponse(
        campaign_id=campaign_id,
        message="Certificate template uploaded successfully.",
        template_image_url=f"data:image/jpeg;base64,{b64_str}",
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
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
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
    campaign = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
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
