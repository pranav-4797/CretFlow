"""
Participant management and secure list upload (CSV / Excel) with Firestore persistence.
"""

import io
from typing import List, Optional
import uuid

import pandas as pd
import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.core.security import AuthenticatedUser, get_current_user
from app.schemas.participant import (
    ParticipantCreateRequest,
    ParticipantResponse,
    ParticipantUploadResponse,
)
from app.services.firestore_service import firestore_service

log = structlog.get_logger(__name__)

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB limit


@router.get("/{campaign_id}", response_model=List[ParticipantResponse], summary="List participants in campaign")
@router.get("/campaign/{campaign_id}", response_model=List[ParticipantResponse], include_in_schema=False)
async def list_participants(
    campaign_id: str,
    status_filter: Optional[str] = Query(None, pattern="^(queued|processing|sent|retrying|failed|unknown|cancelled)$"),
    limit: int = Query(200, ge=1, le=1000),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    List participants for a campaign.
    Enforces strict IDOR verification — returns 404 if campaign is not owned by current_user.
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )

    participants = firestore_service.get_campaign_participants(
        campaign_id=campaign_id,
        status_filter=status_filter,
        limit=limit,
    )
    return [ParticipantResponse.model_validate(p) for p in participants]


@router.post("/{campaign_id}/upload", response_model=ParticipantUploadResponse, summary="Securely upload participant list (CSV/Excel)")
async def upload_participants(
    campaign_id: str,
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Upload and parse participant spreadsheet (CSV, XLSX, XLS).
    Security guards:
    - Verifies campaign ownership (IDOR prevention)
    - Validates file extension and MIME type
    - Enforces 10MB max upload size (DoS / memory protection)
    - Sanitizes strings, validates email formats, strips control characters
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )

    # 1. Validate file extension
    filename = file.filename or ""
    lower_name = filename.lower()
    allowed_exts = (".csv", ".xlsx", ".xls")
    if not any(lower_name.endswith(ext) for ext in allowed_exts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only CSV and Excel (.xlsx, .xls) files are supported.",
        )

    # 2. Read and enforce size limit
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum upload size limit ({MAX_UPLOAD_BYTES // (1024 * 1024)} MB).",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # 3. Parse spreadsheet safely using pandas
    try:
        if lower_name.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), dtype=str)
        else:
            df = pd.read_excel(io.BytesIO(content), dtype=str)
    except Exception as e:
        log.warning("Failed to parse participant spreadsheet", filename=filename, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not read or parse spreadsheet. Ensure it is a valid CSV or Excel file.",
        )

    # 4. Normalize column headers
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]

    # Resolve email column
    email_col = next((c for c in df.columns if c in ("email", "recipient_email", "e-mail", "mail")), None)
    name_col = next((c for c in df.columns if c in ("name", "recipient_name", "full_name", "student_name", "participant_name")), None)

    if not email_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spreadsheet must contain an 'email' (or 'recipient_email') column.",
        )

    imported = 0
    skipped = 0

    for _, row in df.iterrows():
        raw_email = str(row.get(email_col, "")).strip().lower()
        # Basic email syntax check
        if not raw_email or "@" not in raw_email or "." not in raw_email.split("@")[-1] or raw_email == "nan":
            skipped += 1
            continue

        raw_name = str(row.get(name_col, "")).strip() if name_col else ""
        if raw_name == "nan" or not raw_name:
            raw_name = raw_email.split("@")[0].replace(".", " ").title()

        # Sanitize control characters
        clean_name = "".join(c for c in raw_name if ord(c) >= 32)[:150]
        clean_email = "".join(c for c in raw_email if ord(c) >= 32)[:250]

        p_id = f"p_{uuid.uuid4().hex[:12]}"
        part_data = {
            "participant_id": p_id,
            "recipient_name": clean_name,
            "recipient_email": clean_email,
            "email_status": "queued",
            "attempt_count": 0,
        }
        firestore_service.save_participant(campaign_id, part_data)
        imported += 1

    summary = firestore_service.recalculate_and_sync_campaign_counters(campaign_id)

    log.info(
        "Imported participants from spreadsheet",
        campaign_id=campaign_id,
        imported=imported,
        skipped=skipped,
        total=summary.get("total_recipients"),
    )

    return ParticipantUploadResponse(
        campaign_id=campaign_id,
        imported_count=imported,
        skipped_count=skipped,
        total_recipients=summary.get("total_recipients", imported),
        message=f"Successfully imported {imported} participant(s). {skipped} invalid rows skipped.",
    )


@router.post("/upload", response_model=ParticipantUploadResponse, include_in_schema=False)
async def upload_participants_query(
    campaign_id: str = Query(...),
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """Query parameter alias for participant list upload."""
    return await upload_participants(
        campaign_id=campaign_id,
        file=file,
        current_user=current_user,
    )


@router.post("/{campaign_id}", response_model=ParticipantResponse, status_code=status.HTTP_201_CREATED, summary="Add single participant")
async def add_participant(
    campaign_id: str,
    payload: ParticipantCreateRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Manually add a participant to a campaign.
    Enforces strict IDOR verification.
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=current_user.uid)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )

    p_id = f"p_{uuid.uuid4().hex[:12]}"
    part_data = {
        "participant_id": p_id,
        "recipient_name": payload.recipient_name,
        "recipient_email": str(payload.recipient_email).lower().strip(),
        "email_status": "queued",
        "attempt_count": 0,
        "variables": payload.variables or {},
    }
    saved = firestore_service.save_participant(campaign_id, part_data)
    firestore_service.recalculate_and_sync_campaign_counters(campaign_id)

    log.info("Added participant to campaign", campaign_id=campaign_id, participant_id=p_id)
    return ParticipantResponse.model_validate(saved)


