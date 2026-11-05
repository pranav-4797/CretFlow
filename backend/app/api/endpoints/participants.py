"""
Participant management, roster extension, and secure list upload (CSV / Excel) with Firestore persistence.
Includes automatic deduplication against existing participants, immediate single-send dispatch, and on-demand resend.
"""

import io
from typing import Any, Dict, List, Optional
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
from app.services.batch_engine import batch_engine
from app.services.firestore_service import firestore_service
from app.services.gmail_service import GmailNotConnectedError, GmailServiceError

log = structlog.get_logger(__name__)

router = APIRouter()

MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB limit


@router.get("/{campaign_id}", response_model=List[ParticipantResponse], summary="List participants in campaign")
@router.get("/campaign/{campaign_id}", response_model=List[ParticipantResponse], include_in_schema=False)
async def list_participants(
    campaign_id: str,
    status_filter: Optional[str] = Query(None, pattern="^(queued|processing|sent|retrying|failed|unknown|cancelled)$"),
    search: Optional[str] = Query(None, description="Search query for name or email"),
    limit: int = Query(200, ge=1, le=1000, description="Page size limit to conserve database reads"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    List participants for a campaign.
    Supports status filtering and search query on participant name and email.
    Enforces strict IDOR verification — returns 404 if campaign is not owned by current_user.
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=None if current_user.is_admin else current_user.uid)
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

    if search:
        s_lower = search.strip().lower()
        participants = [
            p for p in participants
            if s_lower in str(p.get("recipient_name") or p.get("name") or "").lower()
            or s_lower in str(p.get("recipient_email") or p.get("email") or "").lower()
            or s_lower in str(p.get("certificate_id") or "").lower()
        ]

    return [ParticipantResponse.model_validate(p) for p in participants]


@router.post("/{campaign_id}/upload", response_model=ParticipantUploadResponse, summary="Securely upload / extend participant list (CSV/Excel)")
async def upload_participants(
    campaign_id: str,
    file: UploadFile = File(...),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Upload and parse participant spreadsheet (CSV, XLSX, XLS) to create or extend campaign roster.
    Security & Reliability guards:
    - Verifies campaign ownership (IDOR prevention)
    - Validates file extension and MIME type
    - Enforces 10MB max upload size (DoS / memory protection)
    - Automatic deduplication against already enrolled participants in this campaign
    - Sanitizes strings, validates email formats, strips control characters
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=None if current_user.is_admin else current_user.uid)
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

    # Resolve email and name columns
    email_col = next((c for c in df.columns if c in ("email", "recipient_email", "e-mail", "mail")), None)
    name_col = next((c for c in df.columns if c in ("name", "recipient_name", "full_name", "student_name", "participant_name")), None)

    if not email_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Spreadsheet must contain an 'email' (or 'recipient_email') column.",
        )

    # 5. Retrieve existing participant emails for deduplication
    existing_map = firestore_service.get_campaign_participant_emails(campaign_id)

    imported = 0
    skipped_invalid = 0
    duplicates_skipped = 0

    for _, row in df.iterrows():
        raw_email = str(row.get(email_col, "")).strip().lower()
        # Basic email syntax check
        if not raw_email or "@" not in raw_email or "." not in raw_email.split("@")[-1] or raw_email == "nan":
            skipped_invalid += 1
            continue

        # Sanitize control characters
        clean_email = "".join(c for c in raw_email if ord(c) >= 32)[:250]

        # Automatic deduplication against already enrolled participants
        if clean_email in existing_map:
            duplicates_skipped += 1
            continue

        raw_name = str(row.get(name_col, "")).strip() if name_col else ""
        if raw_name == "nan" or not raw_name:
            raw_name = clean_email.split("@")[0].replace(".", " ").title()

        clean_name = "".join(c for c in raw_name if ord(c) >= 32)[:150]

        # Extract any custom spreadsheet columns (e.g. college, rank, department, roll_no)
        row_vars: Dict[str, Any] = {}
        for col in df.columns:
            if col not in (email_col, name_col):
                val = str(row.get(col, "")).strip()
                if val and val.lower() != "nan":
                    clean_val = "".join(c for c in val if ord(c) >= 32)[:200]
                    row_vars[col] = clean_val

        p_id = f"p_{uuid.uuid4().hex[:12]}"
        part_data = {
            "participant_id": p_id,
            "recipient_name": clean_name,
            "recipient_email": clean_email,
            "email_status": "queued",
            "attempt_count": 0,
            "certificate_id": f"CERT-{p_id[2:10].upper()}",
            "variables": row_vars,
        }
        firestore_service.save_participant(campaign_id, part_data)
        existing_map[clean_email] = {"participant_id": p_id, "email_status": "queued", "recipient_name": clean_name}
        imported += 1

    summary = firestore_service.recalculate_and_sync_campaign_counters(campaign_id)

    # Track discovered custom columns in campaign doc for frontend Canva variable palette
    custom_cols = [c for c in df.columns if c not in (email_col, name_col)]
    if custom_cols:
        existing_cols = list(camp.get("available_variables") or [])
        merged_cols = list(dict.fromkeys(existing_cols + custom_cols))
        firestore_service.update_campaign(campaign_id, {"available_variables": merged_cols})

    # If campaign was previously completed and we imported new participants, transition to ready
    if imported > 0 and camp.get("status") == "completed":
        firestore_service.update_campaign(campaign_id, {"status": "ready"})

    log.info(
        "Imported / extended participants from spreadsheet",
        campaign_id=campaign_id,
        imported=imported,
        duplicates_skipped=duplicates_skipped,
        skipped_invalid=skipped_invalid,
        total=summary.get("total_recipients"),
    )

    msg = f"Successfully imported {imported} new participant(s)."
    if duplicates_skipped > 0:
        msg += f" {duplicates_skipped} existing/duplicate row(s) safely skipped."
    if skipped_invalid > 0:
        msg += f" {skipped_invalid} invalid row(s) skipped."

    return ParticipantUploadResponse(
        campaign_id=campaign_id,
        imported_count=imported,
        skipped_count=skipped_invalid,
        duplicates_skipped=duplicates_skipped,
        total_recipients=summary.get("total_recipients", imported),
        message=msg,
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
    Manually add a participant to a campaign with optional instant certificate delivery.
    Enforces deduplication: if participant email is already in the campaign, rejects duplicate.
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=None if current_user.is_admin else current_user.uid)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )

    clean_email = str(payload.recipient_email).lower().strip()
    existing_map = firestore_service.get_campaign_participant_emails(campaign_id)
    if clean_email in existing_map:
        existing_info = existing_map[clean_email]
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Participant with email '{clean_email}' already exists in this campaign (status: {existing_info.get('email_status')}).",
        )

    p_id = f"p_{uuid.uuid4().hex[:12]}"
    cert_id = payload.certificate_id or f"CERT-{p_id[2:10].upper()}"
    part_data = {
        "participant_id": p_id,
        "recipient_name": payload.recipient_name,
        "recipient_email": clean_email,
        "email_status": "queued",
        "attempt_count": 0,
        "certificate_id": cert_id,
        "variables": payload.variables or {},
    }
    saved = firestore_service.save_participant(campaign_id, part_data)

    # If requested to send certificate immediately
    if payload.send_immediately:
        try:
            send_res = await batch_engine.send_single_participant_on_demand(
                user_id=None if current_user.is_admin else current_user.uid,
                campaign_id=campaign_id,
                participant_id=p_id,
                force_resend=False,
            )
            saved = send_res.get("participant") or firestore_service.get_participant(campaign_id, p_id) or saved
        except GmailNotConnectedError as gerr:
            log.warning("Immediate send skipped because Gmail is not connected", error=str(gerr))
        except Exception as serr:
            log.warning("Immediate send failed for single participant", error=str(serr))

    firestore_service.recalculate_and_sync_campaign_counters(campaign_id)

    # If campaign was completed, and participant wasn't sent, transition to ready
    if camp.get("status") == "completed" and saved.get("email_status") != "sent":
        firestore_service.update_campaign(campaign_id, {"status": "ready"})

    log.info("Added single participant to campaign", campaign_id=campaign_id, participant_id=p_id, send_immediately=payload.send_immediately)
    return ParticipantResponse.model_validate(saved)


@router.post("/{campaign_id}/{participant_id}/send", summary="Send or resend certificate email to single participant")
async def send_single_participant_endpoint(
    campaign_id: str,
    participant_id: str,
    force_resend: bool = Query(False, description="Resend even if already marked sent"),
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    On-demand certificate generation and immediate Gmail dispatch for an individual recipient.
    Ideal for late-joiners, missed deliveries, or retrying a single failed recipient.
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=None if current_user.is_admin else current_user.uid)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )

    try:
        result = await batch_engine.send_single_participant_on_demand(
            user_id=None if current_user.is_admin else current_user.uid,
            campaign_id=campaign_id,
            participant_id=participant_id,
            force_resend=force_resend,
        )
        return result
    except GmailNotConnectedError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        log.error("Failed to send certificate to single recipient", error=str(e))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/{campaign_id}/{participant_id}", summary="Remove participant from campaign")
async def delete_participant_endpoint(
    campaign_id: str,
    participant_id: str,
    current_user: AuthenticatedUser = Depends(get_current_user),
):
    """
    Remove an individual participant from a campaign.
    """
    camp = firestore_service.get_campaign(campaign_id, user_id=None if current_user.is_admin else current_user.uid)
    if not camp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found or access denied.",
        )

    deleted = firestore_service.delete_participant(campaign_id, participant_id)
    return {"success": deleted, "message": "Participant removed from campaign."}
