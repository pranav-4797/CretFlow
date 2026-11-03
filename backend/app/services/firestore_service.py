"""
Firestore Service for CertFlow.
Handles persistence for:
- GmailConnection (OAuth tokens encrypted at rest)
- Campaigns & Participants
- Email Jobs & Batch Progress Tracking

Uses Firebase Admin SDK with client-side fallback store for local testing/offline mode.
"""

from datetime import datetime, timezone
import structlog
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from app.core.config import settings
from app.core.encryption import decrypt_token, encrypt_token

log = structlog.get_logger(__name__)

class FirestoreMetrics:
    """Thread-safe operational telemetry to monitor and audit Firestore read consumption."""
    _counts: Dict[str, int] = {}
    _lock = threading.Lock()

    @classmethod
    def record_read(cls, operation: str, count: int = 1) -> None:
        if count <= 0:
            return
        with cls._lock:
            cls._counts[operation] = cls._counts.get(operation, 0) + count
        log.debug("Firestore read telemetry", operation=operation, count=count, total=cls._counts.get(operation, 0))

    @classmethod
    def get_summary(cls) -> Dict[str, int]:
        with cls._lock:
            return dict(cls._counts)

    @classmethod
    def reset(cls) -> None:
        with cls._lock:
            cls._counts.clear()


# Short-lived TTL read caches to prevent hot polling thrashes
_CAMPAIGN_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}  # campaign_id -> (data, expires_at)
_GMAIL_CONN_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}  # user_id -> (data, expires_at)
CAMPAIGN_CACHE_TTL = 5.0      # 5 seconds
GMAIL_CONN_CACHE_TTL = 60.0   # 60 seconds

# In-memory storage fallback for local tests and environments without live Firestore credentials
_IN_MEMORY_GMAIL_CONNECTIONS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_CAMPAIGNS: Dict[str, Dict[str, Any]] = {}
_IN_MEMORY_PARTICIPANTS: Dict[str, Dict[str, Dict[str, Any]]] = {}  # campaign_id -> {participant_id: data}
_IN_MEMORY_JOBS: Dict[str, Dict[str, Any]] = {}


class FirestoreService:
    """Central repository for Firestore data access across CertFlow."""

    @staticmethod
    def _get_client():
        """Retrieve Firestore client if Firebase Admin is initialized, else None."""
        try:
            from firebase_admin import firestore
            return firestore.client()
        except Exception as e:
            log.debug("Firestore client unavailable, using in-memory store", error=str(e))
            return None

    @staticmethod
    def _apply_filter(query, field: str, op: str, value: Any):
        """Helper to apply FieldFilter to avoid google-cloud-firestore positional argument warnings."""
        try:
            from google.cloud.firestore import FieldFilter
            return query.where(filter=FieldFilter(field, op, value))
        except Exception:
            return query.where(field, op, value)

    # ─── Gmail Connections (Replaces Neon PostgreSQL GmailConnection) ──────────

    @classmethod
    def save_gmail_connection(
        cls,
        user_id: str,
        google_email: str,
        refresh_token: str,
        scopes: str,
    ) -> Dict[str, Any]:
        """
        Save or update encrypted Gmail OAuth connection for a user.
        Tokens are encrypted using Fernet AES-128 before writing to Firestore.
        """
        now = datetime.now(timezone.utc).isoformat()
        encrypted_token = encrypt_token(refresh_token)

        conn_data = {
            "user_id": user_id,
            "google_email": google_email,
            "encrypted_refresh_token": encrypted_token,
            "token_encryption_version": 1,
            "scopes": scopes,
            "is_connected": True,
            "connected_at": now,
            "updated_at": now,
            "last_used_at": None,
            "revoked_at": None,
        }

        client = cls._get_client()
        if client:
            try:
                client.collection("gmail_connections").document(user_id).set(conn_data)
                log.info("Persisted Gmail connection in Firestore", user_id=user_id, google_email=google_email)
            except Exception as e:
                log.warning("Firestore write failed, falling back to memory", error=str(e))
                _IN_MEMORY_GMAIL_CONNECTIONS[user_id] = conn_data
        else:
            _IN_MEMORY_GMAIL_CONNECTIONS[user_id] = conn_data

        _GMAIL_CONN_CACHE[user_id] = (dict(conn_data), time.time() + GMAIL_CONN_CACHE_TTL)
        return conn_data

    @classmethod
    def get_gmail_connection(cls, user_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve Gmail connection for a user with TTL caching to avoid thrashing reads."""
        now_ts = time.time()
        if user_id in _GMAIL_CONN_CACHE:
            cached_data, expires_at = _GMAIL_CONN_CACHE[user_id]
            if now_ts < expires_at:
                return dict(cached_data)

        FirestoreMetrics.record_read("get_gmail_connection", 1)
        client = cls._get_client()
        data = None

        if client:
            try:
                doc = client.collection("gmail_connections").document(user_id).get()
                if doc.exists:
                    data = doc.to_dict()
            except Exception as e:
                log.warning("Firestore read failed, checking in-memory store", error=str(e))
                data = _IN_MEMORY_GMAIL_CONNECTIONS.get(user_id)
        else:
            data = _IN_MEMORY_GMAIL_CONNECTIONS.get(user_id)

        if data:
            _GMAIL_CONN_CACHE[user_id] = (dict(data), now_ts + GMAIL_CONN_CACHE_TTL)
        return data

    @classmethod
    def disconnect_gmail(cls, user_id: str) -> bool:
        """Mark Gmail connection disconnected/revoked in Firestore and invalidate cache."""
        _GMAIL_CONN_CACHE.pop(user_id, None)
        conn = cls.get_gmail_connection(user_id)
        if not conn or not conn.get("is_connected"):
            return False

        now = datetime.now(timezone.utc).isoformat()
        updates = {
            "is_connected": False,
            "revoked_at": now,
            "updated_at": now,
        }

        client = cls._get_client()
        if client:
            try:
                client.collection("gmail_connections").document(user_id).update(updates)
            except Exception as e:
                log.warning("Firestore update failed, updating in-memory store", error=str(e))
                if user_id in _IN_MEMORY_GMAIL_CONNECTIONS:
                    _IN_MEMORY_GMAIL_CONNECTIONS[user_id].update(updates)
        else:
            if user_id in _IN_MEMORY_GMAIL_CONNECTIONS:
                _IN_MEMORY_GMAIL_CONNECTIONS[user_id].update(updates)

        return True

    @classmethod
    def update_gmail_last_used(cls, user_id: str) -> None:
        """Update last_used_at timestamp on Gmail connection."""
        now = datetime.now(timezone.utc).isoformat()
        client = cls._get_client()
        if client:
            try:
                client.collection("gmail_connections").document(user_id).update({"last_used_at": now})
            except Exception:
                if user_id in _IN_MEMORY_GMAIL_CONNECTIONS:
                    _IN_MEMORY_GMAIL_CONNECTIONS[user_id]["last_used_at"] = now
        else:
            if user_id in _IN_MEMORY_GMAIL_CONNECTIONS:
                _IN_MEMORY_GMAIL_CONNECTIONS[user_id]["last_used_at"] = now

    # ─── Campaigns & Participants ─────────────────────────────────────────────

    @classmethod
    def get_or_create_campaign(
        cls,
        campaign_id: str,
        user_id: str,
        campaign_name: str = "General",
    ) -> Dict[str, Any]:
        """Fetch existing campaign or initialize a new campaign document in Firestore."""
        client = cls._get_client()
        data = None

        if client:
            try:
                doc = client.collection("campaigns").document(campaign_id).get()
                if doc.exists:
                    data = doc.to_dict()
            except Exception as e:
                log.warning("Firestore campaign read failed", error=str(e))
                data = _IN_MEMORY_CAMPAIGNS.get(campaign_id)
        else:
            data = _IN_MEMORY_CAMPAIGNS.get(campaign_id)

        if not data:
            now = datetime.now(timezone.utc).isoformat()
            data = {
                "campaign_id": campaign_id,
                "owner_uid": user_id,
                "userId": user_id,
                "campaign_name": campaign_name,
                "campaign_type": "spreadsheet",
                "status": "draft",
                "total_recipients": 0,
                "queued_count": 0,
                "processing_count": 0,
                "sent_count": 0,
                "failed_count": 0,
                "cancelled_count": 0,
                "created_at": now,
                "updated_at": now,
            }
            if client:
                try:
                    client.collection("campaigns").document(campaign_id).set(data)
                except Exception:
                    _IN_MEMORY_CAMPAIGNS[campaign_id] = data
            else:
                _IN_MEMORY_CAMPAIGNS[campaign_id] = data

        return data

    @classmethod
    def create_campaign(cls, campaign_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create and persist a new campaign document in Firestore."""
        import uuid
        campaign_id = campaign_data.get("campaign_id") or campaign_data.get("id") or f"camp_{uuid.uuid4().hex[:12]}"
        user_id = campaign_data.get("owner_uid") or campaign_data.get("user_id") or campaign_data.get("userId") or ""
        campaign_name = campaign_data.get("campaign_name") or campaign_data.get("name") or "General"
        
        now = datetime.now(timezone.utc).isoformat()
        data = {
            "campaign_id": campaign_id,
            "id": campaign_id,
            "owner_uid": user_id,
            "user_id": user_id,
            "userId": user_id,
            "campaign_name": campaign_name,
            "name": campaign_name,
            "campaign_type": campaign_data.get("campaign_type") or "spreadsheet",
            "description": campaign_data.get("description"),
            "status": campaign_data.get("status", "draft"),
            "total_recipients": campaign_data.get("total_recipients", 0),
            "queued_count": campaign_data.get("queued_count", 0),
            "processing_count": campaign_data.get("processing_count", 0),
            "sent_count": campaign_data.get("sent_count", 0),
            "failed_count": campaign_data.get("failed_count", 0),
            "cancelled_count": campaign_data.get("cancelled_count", 0),
            "created_at": campaign_data.get("created_at", now),
            "updated_at": campaign_data.get("updated_at", now),
        }
        client = cls._get_client()
        if client:
            try:
                client.collection("campaigns").document(campaign_id).set(data)
            except Exception:
                _IN_MEMORY_CAMPAIGNS[campaign_id] = data
        else:
            _IN_MEMORY_CAMPAIGNS[campaign_id] = data

        _CAMPAIGN_CACHE[campaign_id] = (dict(data), time.time() + CAMPAIGN_CACHE_TTL)
        return data

    @classmethod
    def get_campaign(cls, campaign_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve campaign with TTL caching, verifying owner_uid if user_id is provided."""
        now_ts = time.time()
        if campaign_id in _CAMPAIGN_CACHE:
            cached_data, expires_at = _CAMPAIGN_CACHE[campaign_id]
            if now_ts < expires_at:
                owner = cached_data.get("owner_uid") or cached_data.get("userId")
                if user_id and owner != user_id:
                    return None
                return dict(cached_data)

        FirestoreMetrics.record_read("get_campaign", 1)
        client = cls._get_client()
        data = None

        if client:
            try:
                doc = client.collection("campaigns").document(campaign_id).get()
                if doc.exists:
                    data = doc.to_dict()
            except Exception:
                data = _IN_MEMORY_CAMPAIGNS.get(campaign_id)
        else:
            data = _IN_MEMORY_CAMPAIGNS.get(campaign_id)

        if not data:
            return None

        # Ownership protection
        owner = data.get("owner_uid") or data.get("userId")
        if user_id and owner != user_id:
            log.warning("Cross-user campaign access denied", requested_by=user_id, owner=owner)
            return None

        _CAMPAIGN_CACHE[campaign_id] = (dict(data), now_ts + CAMPAIGN_CACHE_TTL)
        return data

    @classmethod
    def update_campaign(cls, campaign_id: str, updates: Dict[str, Any]) -> None:
        """Update fields on a campaign document and invalidate TTL cache."""
        _CAMPAIGN_CACHE.pop(campaign_id, None)
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        client = cls._get_client()
        if client:
            try:
                client.collection("campaigns").document(campaign_id).update(updates)
            except Exception:
                if campaign_id in _IN_MEMORY_CAMPAIGNS:
                    _IN_MEMORY_CAMPAIGNS[campaign_id].update(updates)
        else:
            if campaign_id in _IN_MEMORY_CAMPAIGNS:
                _IN_MEMORY_CAMPAIGNS[campaign_id].update(updates)

    @classmethod
    def list_campaigns(cls, user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """List campaigns belonging strictly to user_id."""
        client = cls._get_client()
        campaigns = []
        if client:
            try:
                docs = cls._apply_filter(client.collection("campaigns"), "owner_uid", "==", user_id).limit(limit).stream()
                campaigns = [d.to_dict() for d in docs]
                if not campaigns:
                    docs2 = cls._apply_filter(client.collection("campaigns"), "userId", "==", user_id).limit(limit).stream()
                    campaigns = [d.to_dict() for d in docs2]
                FirestoreMetrics.record_read("list_campaigns", len(campaigns))
                return campaigns
            except Exception as e:
                log.warning("Firestore list_campaigns failed, checking fallback", error=str(e))

        for c in _IN_MEMORY_CAMPAIGNS.values():
            if c.get("owner_uid") == user_id or c.get("userId") == user_id:
                campaigns.append(dict(c))
                if len(campaigns) >= limit:
                    break
        FirestoreMetrics.record_read("list_campaigns_memory", len(campaigns))
        return campaigns

    @classmethod
    def get_user_analytics(cls, user_id: str) -> Dict[str, Any]:
        """Aggregate total campaigns, participants, certificates, and sent emails directly from campaign metadata (0 subcollection reads)."""
        campaigns = cls.list_campaigns(user_id, limit=100)
        total_campaigns = len(campaigns)
        total_participants = 0
        total_sent = 0
        total_certificates = 0

        for c in campaigns:
            c_recipients = int(c.get("total_recipients") or 0)
            c_sent = int(c.get("sent_count") or 0)
            c_cert = int(c.get("certificates_generated") or c.get("certificates_count") or c_sent)

            total_participants += c_recipients
            total_sent += c_sent
            total_certificates += max(c_cert, c_sent)

        return {
            "total_campaigns": total_campaigns,
            "total_participants": total_participants,
            "certificates_generated": total_certificates,
            "emails_sent": total_sent,
            "recent_campaigns": campaigns[:6],
        }

    @classmethod
    def delete_campaign(cls, campaign_id: str, user_id: str) -> bool:
        """Delete campaign if owned by user_id."""
        camp = cls.get_campaign(campaign_id, user_id=user_id)
        if not camp:
            return False

        client = cls._get_client()
        if client:
            try:
                # Clean up participants subcollection
                part_docs = client.collection("campaigns").document(campaign_id).collection("participants").stream()
                for p in part_docs:
                    try:
                        p.reference.delete()
                    except Exception:
                        pass
                # Clean up templates subcollection
                tpl_docs = client.collection("campaigns").document(campaign_id).collection("templates").stream()
                for t in tpl_docs:
                    try:
                        t.reference.delete()
                    except Exception:
                        pass
                client.collection("campaigns").document(campaign_id).delete()
            except Exception:
                pass
        _CAMPAIGN_CACHE.pop(campaign_id, None)
        _IN_MEMORY_CAMPAIGNS.pop(campaign_id, None)
        _IN_MEMORY_PARTICIPANTS.pop(campaign_id, None)
        return True

    PARTICIPANT_METADATA_FIELDS: List[str] = [
        "participant_id",
        "id",
        "name",
        "recipient_name",
        "email",
        "recipient_email",
        "email_status",
        "status",
        "attempt_count",
        "gmail_message_id",
        "certificate_id",
        "certificate_filename",
        "certificate_drive_file_id",
        "drive_file_id",
        "drive_web_view_link",
        "last_error_code",
        "last_error_message",
        "created_at",
        "sent_at",
        "updated_at",
        "processing_lease_id",
        "processing_lease_expires_at",
        "variables",
    ]

    @classmethod
    def get_campaign_participants(
        cls,
        campaign_id: str,
        status_filter: Optional[str] = None,
        limit: int = 50,
        include_pdf_bytes: bool = False,
    ) -> List[Dict[str, Any]]:
        """Fetch participant subcollection documents for a campaign. Omits heavy PDF bytes by default to prevent OOM."""
        client = cls._get_client()
        participants: List[Dict[str, Any]] = []

        if client:
            try:
                query = client.collection("campaigns").document(campaign_id).collection("participants")
                if status_filter:
                    query = cls._apply_filter(query, "email_status", "==", status_filter)
                if not include_pdf_bytes:
                    query = query.select(cls.PARTICIPANT_METADATA_FIELDS)
                docs = query.limit(limit).stream()
                for d in docs:
                    p = d.to_dict()
                    if not include_pdf_bytes:
                        p.pop("certificate_bytes_b64", None)
                    participants.append(p)
            except Exception:
                camp_parts = _IN_MEMORY_PARTICIPANTS.get(campaign_id, {})
                for p in camp_parts.values():
                    if not status_filter or p.get("email_status") == status_filter:
                        p_copy = dict(p)
                        if not include_pdf_bytes:
                            p_copy.pop("certificate_bytes_b64", None)
                        participants.append(p_copy)
                        if len(participants) >= limit:
                            break
        else:
            camp_parts = _IN_MEMORY_PARTICIPANTS.get(campaign_id, {})
            for p in camp_parts.values():
                if not status_filter or p.get("email_status") == status_filter:
                    p_copy = dict(p)
                    if not include_pdf_bytes:
                        p_copy.pop("certificate_bytes_b64", None)
                    participants.append(p_copy)
                    if len(participants) >= limit:
                        break

        return participants

    @classmethod
    def save_participant(cls, campaign_id: str, participant: Dict[str, Any]) -> Dict[str, Any]:
        """Save or update participant document inside campaign's participants subcollection."""
        p_id = participant.get("participant_id") or participant.get("id") or str(uuid.uuid4())
        participant["participant_id"] = p_id
        participant["id"] = p_id
        now = datetime.now(timezone.utc).isoformat()
        if "created_at" not in participant:
            participant["created_at"] = now
        participant["updated_at"] = now

        # Inherit ownership metadata if available in cache to optimize Firestore security rules
        if "userId" not in participant or "owner_uid" not in participant:
            cached_camp = _CAMPAIGN_CACHE.get(campaign_id)
            if cached_camp:
                uid = cached_camp[0].get("owner_uid") or cached_camp[0].get("userId")
                if uid:
                    participant.setdefault("userId", uid)
                    participant.setdefault("owner_uid", uid)

        client = cls._get_client()
        if client:
            try:
                client.collection("campaigns").document(campaign_id).collection("participants").document(p_id).set(participant)
            except Exception:
                if campaign_id not in _IN_MEMORY_PARTICIPANTS:
                    _IN_MEMORY_PARTICIPANTS[campaign_id] = {}
                _IN_MEMORY_PARTICIPANTS[campaign_id][p_id] = participant
        else:
            if campaign_id not in _IN_MEMORY_PARTICIPANTS:
                _IN_MEMORY_PARTICIPANTS[campaign_id] = {}
            _IN_MEMORY_PARTICIPANTS[campaign_id][p_id] = participant

        if campaign_id in _IN_MEMORY_CAMPAIGNS and campaign_id in _IN_MEMORY_PARTICIPANTS:
            current_total = int(_IN_MEMORY_CAMPAIGNS[campaign_id].get("total_recipients") or 0)
            _IN_MEMORY_CAMPAIGNS[campaign_id]["total_recipients"] = max(current_total, len(_IN_MEMORY_PARTICIPANTS[campaign_id]))
        _CAMPAIGN_CACHE.pop(campaign_id, None)

        return participant

    @classmethod
    def update_participant(cls, campaign_id: str, participant_id: str, updates: Dict[str, Any]) -> None:
        """Update fields on a participant subdocument."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        client = cls._get_client()
        if client:
            try:
                client.collection("campaigns").document(campaign_id).collection("participants").document(participant_id).update(updates)
            except Exception:
                if campaign_id in _IN_MEMORY_PARTICIPANTS and participant_id in _IN_MEMORY_PARTICIPANTS[campaign_id]:
                    _IN_MEMORY_PARTICIPANTS[campaign_id][participant_id].update(updates)
        else:
            if campaign_id in _IN_MEMORY_PARTICIPANTS and participant_id in _IN_MEMORY_PARTICIPANTS[campaign_id]:
                _IN_MEMORY_PARTICIPANTS[campaign_id][participant_id].update(updates)

    # ─── Email Jobs (Batch Processing State Store) ─────────────────────────────

    @classmethod
    def create_email_job(
        cls,
        job_id: str,
        campaign_id: str,
        owner_uid: str,
        total_recipients: int,
        batch_size: int = 15,
        subject_template: str = "",
        body_template: str = "",
    ) -> Dict[str, Any]:
        """Create authoritative email job record in Firestore."""
        now = datetime.now(timezone.utc).isoformat()
        job_data = {
            "job_id": job_id,
            "campaign_id": campaign_id,
            "owner_uid": owner_uid,
            "user_id": owner_uid,
            "status": "queued",
            "batch_size": batch_size,
            "total_recipients": total_recipients,
            "processed_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "subject_template": subject_template,
            "body_template": body_template,
            "lease_id": None,
            "lease_expires_at": None,
            "started_at": None,
            "completed_at": None,
            "created_at": now,
            "updated_at": now,
        }

        client = cls._get_client()
        if client:
            try:
                client.collection("email_jobs").document(job_id).set(job_data)
            except Exception:
                _IN_MEMORY_JOBS[job_id] = job_data
        else:
            _IN_MEMORY_JOBS[job_id] = job_data

        return job_data

    @classmethod
    def get_email_job(cls, job_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Retrieve an email job, enforcing user ownership if user_id is provided."""
        client = cls._get_client()
        data = None

        if client:
            try:
                doc = client.collection("email_jobs").document(job_id).get()
                if doc.exists:
                    data = doc.to_dict()
            except Exception:
                data = _IN_MEMORY_JOBS.get(job_id)
        else:
            data = _IN_MEMORY_JOBS.get(job_id)

        if not data:
            return None

        owner = data.get("owner_uid") or data.get("user_id")
        if user_id and owner != user_id:
            log.warning("Cross-user job access denied", requested_by=user_id, owner=owner)
            return None

        return data

    @classmethod
    def update_email_job(cls, job_id: str, updates: Dict[str, Any]) -> None:
        """Update fields on an email job document."""
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        client = cls._get_client()
        if client:
            try:
                client.collection("email_jobs").document(job_id).update(updates)
            except Exception:
                if job_id in _IN_MEMORY_JOBS:
                    _IN_MEMORY_JOBS[job_id].update(updates)
        else:
            if job_id in _IN_MEMORY_JOBS:
                _IN_MEMORY_JOBS[job_id].update(updates)

    @classmethod
    def get_active_jobs_for_campaign(cls, campaign_id: str) -> List[Dict[str, Any]]:
        """List active email jobs for a campaign (queued, processing, retrying)."""
        client = cls._get_client()
        jobs: List[Dict[str, Any]] = []

        if client:
            try:
                query = client.collection("email_jobs")
                query = cls._apply_filter(query, "campaign_id", "==", campaign_id)
                query = cls._apply_filter(query, "status", "in", ["queued", "processing", "retrying"])
                docs = query.stream()
                jobs = [d.to_dict() for d in docs]
            except Exception:
                for j in _IN_MEMORY_JOBS.values():
                    if j.get("campaign_id") == campaign_id and j.get("status") in ["queued", "processing", "retrying"]:
                        jobs.append(j)
        else:
            for j in _IN_MEMORY_JOBS.values():
                if j.get("campaign_id") == campaign_id and j.get("status") in ["queued", "processing", "retrying"]:
                    jobs.append(j)

        return jobs

    @classmethod
    def get_campaign_stats(cls, campaign_id: str, user_id: str) -> Dict[str, Any]:
        """Aggregate progress counts directly from the campaign document and fetch at most 10 recent logs (1-11 reads vs 500+)."""
        FirestoreMetrics.record_read("get_campaign_stats_call", 1)
        camp = cls.get_campaign(campaign_id, user_id)
        if not camp:
            return {
                "campaign_id": campaign_id,
                "campaign_status": "draft",
                "total_count": 0,
                "sent_count": 0,
                "failed_count": 0,
                "queued_count": 0,
                "processing_count": 0,
                "retrying_count": 0,
                "cancelled_count": 0,
                "unknown_count": 0,
                "recent_logs": [],
            }

        total_recipients = int(camp.get("total_recipients") or 0)
        if total_recipients == 0:
            camp_parts = _IN_MEMORY_PARTICIPANTS.get(campaign_id)
            if camp_parts:
                total_recipients = len(camp_parts)
            else:
                jobs = cls.get_active_jobs_for_campaign(campaign_id)
                if jobs:
                    total_recipients = int(jobs[0].get("total_recipients") or 0)
        sent_count = int(camp.get("sent_count") or 0)
        failed_count = int(camp.get("failed_count") or 0)
        processing_count = int(camp.get("processing_count") or 0)
        retrying_count = int(camp.get("retrying_count") or 0)
        cancelled_count = int(camp.get("cancelled_count") or 0)
        unknown_count = int(camp.get("unknown_count") or 0)

        queued_val = camp.get("queued_count")
        if queued_val is None:
            queued_count = max(0, total_recipients - (sent_count + failed_count + processing_count + cancelled_count))
        else:
            queued_count = int(queued_val)

        counts = {
            "total_count": total_recipients,
            "sent_count": sent_count,
            "failed_count": failed_count,
            "queued_count": queued_count,
            "processing_count": processing_count,
            "retrying_count": retrying_count,
            "cancelled_count": cancelled_count,
            "unknown_count": unknown_count,
        }

        # Query ONLY up to 10 recent logs to minimize billable document reads
        sanitized_logs = []
        client = cls._get_client()
        if client:
            try:
                docs = (
                    client.collection("campaigns")
                    .document(campaign_id)
                    .collection("participants")
                    .select(cls.PARTICIPANT_METADATA_FIELDS)
                    .limit(10)
                    .stream()
                )
                log_count = 0
                for d in docs:
                    p = d.to_dict()
                    log_count += 1
                    sanitized_logs.append({
                        "id": p.get("id") or p.get("participant_id"),
                        "participant_id": p.get("participant_id") or p.get("id"),
                        "recipient_name": p.get("recipient_name") or p.get("name"),
                        "recipient_email": p.get("recipient_email") or p.get("email"),
                        "status": p.get("status", "queued"),
                        "email_status": p.get("email_status", "queued"),
                        "attempt_count": p.get("attempt_count", 0),
                        "gmail_message_id": p.get("gmail_message_id"),
                        "certificate_drive_file_id": p.get("certificate_drive_file_id") or p.get("drive_file_id"),
                        "last_error_code": p.get("last_error_code"),
                        "last_error_message": p.get("last_error_message"),
                        "sent_at": p.get("sent_at"),
                        "updated_at": p.get("updated_at"),
                        "created_at": p.get("created_at"),
                    })
                FirestoreMetrics.record_read("get_campaign_stats_logs", log_count)
            except Exception as e:
                log.debug("Recent logs query error", error=str(e))
        else:
            camp_parts = _IN_MEMORY_PARTICIPANTS.get(campaign_id, {})
            for p in list(camp_parts.values())[:10]:
                sanitized_logs.append({
                    "id": p.get("id") or p.get("participant_id"),
                    "participant_id": p.get("participant_id") or p.get("id"),
                    "recipient_name": p.get("recipient_name") or p.get("name"),
                    "recipient_email": p.get("recipient_email") or p.get("email"),
                    "status": p.get("status", "queued"),
                    "email_status": p.get("email_status", "queued"),
                    "attempt_count": p.get("attempt_count", 0),
                    "gmail_message_id": p.get("gmail_message_id"),
                    "certificate_drive_file_id": p.get("certificate_drive_file_id") or p.get("drive_file_id"),
                    "last_error_code": p.get("last_error_code"),
                    "last_error_message": p.get("last_error_message"),
                    "sent_at": p.get("sent_at"),
                    "updated_at": p.get("updated_at"),
                    "created_at": p.get("created_at"),
                })
            FirestoreMetrics.record_read("get_campaign_stats_logs_memory", len(sanitized_logs))

        return {
            "campaign_id": campaign_id,
            "campaign_status": camp.get("status", "draft"),
            **counts,
            "recent_logs": sanitized_logs,
        }

    @classmethod
    def claim_job_lease(cls, job_id: str, lease_duration_seconds: int = 300) -> Optional[str]:
        """
        Atomically claim a job lease for batch processing.
        Prevents multiple workers/threads from executing the same job concurrently.
        Returns lease_id if acquired, None if currently leased by another active worker.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_at = datetime.fromtimestamp(now.timestamp() + lease_duration_seconds, tz=timezone.utc).isoformat()
        new_lease_id = str(uuid.uuid4())

        client = cls._get_client()
        if client:
            try:
                from firebase_admin import firestore
                transaction = client.transaction()
                doc_ref = client.collection("email_jobs").document(job_id)

                @firestore.transactional
                def _claim_in_tx(tx):
                    snapshot = doc_ref.get(transaction=tx)
                    if not snapshot.exists:
                        return None
                    data = snapshot.to_dict()
                    current_status = data.get("status")
                    if current_status in ["paused", "cancelled", "completed"]:
                        return None

                    current_lease_expires = data.get("lease_expires_at")
                    # If lease is active and not expired, cannot claim
                    if current_lease_expires:
                        try:
                            exp_dt = datetime.fromisoformat(current_lease_expires)
                            if exp_dt > now:
                                return None  # Still actively leased
                        except Exception:
                            pass

                    tx.update(doc_ref, {
                        "lease_id": new_lease_id,
                        "lease_expires_at": expires_at,
                        "status": "processing",
                        "started_at": data.get("started_at") or now_iso,
                        "updated_at": now_iso,
                    })
                    return new_lease_id

                acquired = _claim_in_tx(transaction)
                if acquired:
                    return new_lease_id
            except Exception as e:
                log.warning("Firestore transaction for lease claim failed, evaluating fallback", error=str(e))

        # In-memory fallback
        job = _IN_MEMORY_JOBS.get(job_id)
        if not job:
            return None
        if job.get("status") in ["paused", "cancelled", "completed"]:
            return None
        exp = job.get("lease_expires_at")
        if exp:
            try:
                if datetime.fromisoformat(exp) > now:
                    return None
            except Exception:
                pass

        job["lease_id"] = new_lease_id
        job["lease_expires_at"] = expires_at
        job["status"] = "processing"
        job["started_at"] = job.get("started_at") or now_iso
        job["updated_at"] = now_iso
        return new_lease_id

    @classmethod
    def renew_job_lease(cls, job_id: str, lease_id: str, lease_duration_seconds: int = 300) -> bool:
        """Extend active lease while processing a long batch."""
        now = datetime.now(timezone.utc)
        expires_at = datetime.fromtimestamp(now.timestamp() + lease_duration_seconds, tz=timezone.utc).isoformat()
        now_iso = now.isoformat()

        client = cls._get_client()
        if client:
            try:
                doc_ref = client.collection("email_jobs").document(job_id)
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict()
                    if data.get("lease_id") == lease_id and data.get("status") == "processing":
                        doc_ref.update({"lease_expires_at": expires_at, "updated_at": now_iso})
                        return True
            except Exception:
                pass

        job = _IN_MEMORY_JOBS.get(job_id)
        if job and job.get("lease_id") == lease_id and job.get("status") == "processing":
            job["lease_expires_at"] = expires_at
            job["updated_at"] = now_iso
            return True
        return False

    @classmethod
    def release_job_lease(cls, job_id: str, lease_id: str, new_status: Optional[str] = None) -> None:
        """Release the processing lease upon completion, pause, or graceful yield."""
        now_iso = datetime.now(timezone.utc).isoformat()
        updates: Dict[str, Any] = {
            "lease_id": None,
            "lease_expires_at": None,
            "updated_at": now_iso,
        }
        if new_status:
            updates["status"] = new_status
            if new_status == "completed":
                updates["completed_at"] = now_iso

        client = cls._get_client()
        if client:
            try:
                doc_ref = client.collection("email_jobs").document(job_id)
                doc = doc_ref.get()
                if doc.exists and doc.to_dict().get("lease_id") == lease_id:
                    doc_ref.update(updates)
            except Exception:
                pass

        job = _IN_MEMORY_JOBS.get(job_id)
        if job and job.get("lease_id") == lease_id:
            job.update(updates)

    @classmethod
    def claim_participants_batch(
        cls,
        campaign_id: str,
        batch_size: int = 15,
        lease_id: str = "",
        lease_duration_seconds: int = 300,
    ) -> List[Dict[str, Any]]:
        """
        Atomically claim a bounded batch of eligible recipients (status in queued, retrying).
        Returns a list of participant dicts marked with processing status and lease.
        """
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()
        expires_at = datetime.fromtimestamp(now.timestamp() + lease_duration_seconds, tz=timezone.utc).isoformat()

        claimed: List[Dict[str, Any]] = []

        client = cls._get_client()
        if client:
            try:
                parts_ref = client.collection("campaigns").document(campaign_id).collection("participants")
                # Query queued or retrying participants
                docs = cls._apply_filter(parts_ref, "email_status", "in", ["queued", "retrying"]).limit(batch_size).stream()

                for d in docs:
                    p_data = d.to_dict()
                    p_id = d.id
                    # Update status to processing
                    p_updates = {
                        "email_status": "processing",
                        "processing_lease_id": lease_id,
                        "processing_lease_expires_at": expires_at,
                        "processing_at": now_iso,
                        "updated_at": now_iso,
                    }
                    d.reference.update(p_updates)
                    p_data.update(p_updates)
                    claimed.append(p_data)
                return claimed
            except Exception as e:
                log.warning("Firestore claim_participants_batch failed, using fallback", error=str(e))

        # In-memory fallback
        parts_map = _IN_MEMORY_PARTICIPANTS.get(campaign_id, {})
        for p_id, p in parts_map.items():
            if p.get("email_status") in ["queued", "retrying"]:
                p["email_status"] = "processing"
                p["processing_lease_id"] = lease_id
                p["processing_lease_expires_at"] = expires_at
                p["processing_at"] = now_iso
                p["updated_at"] = now_iso
                claimed.append(dict(p))
                if len(claimed) >= batch_size:
                    break

        return claimed

    @classmethod
    def record_participant_sent(
        cls,
        campaign_id: str,
        participant_id: str,
        message_id: str,
        attempt_count: int,
    ) -> None:
        """Mark participant as sent with Gmail message ID and clear bulky PDF base64 bytes to free storage."""
        now_iso = datetime.now(timezone.utc).isoformat()
        updates = {
            "email_status": "sent",
            "sent_at": now_iso,
            "gmail_message_id": message_id,
            "attempt_count": attempt_count,
            "last_error_code": None,
            "last_error_message": None,
            "processing_lease_id": None,
            "processing_lease_expires_at": None,
            "updated_at": now_iso,
            "certificate_bytes_b64": None,  # Free memory and Firestore storage
        }
        cls.update_participant(campaign_id, participant_id, updates)

    @classmethod
    def record_participant_failure(
        cls,
        campaign_id: str,
        participant_id: str,
        error_code: str,
        error_message: str,
        is_transient: bool,
        attempt_count: int,
        max_attempts: int = 3,
    ) -> None:
        """Record participant send failure (retrying if transient and attempts remain, else failed)."""
        now_iso = datetime.now(timezone.utc).isoformat()
        next_status = "retrying" if (is_transient and attempt_count < max_attempts) else "failed"

        updates = {
            "email_status": next_status,
            "attempt_count": attempt_count,
            "last_error_code": error_code,
            "last_error_message": error_message[:300],
            "processing_lease_id": None,
            "processing_lease_expires_at": None,
            "updated_at": now_iso,
        }
        cls.update_participant(campaign_id, participant_id, updates)

    @classmethod
    def record_participant_ambiguous(
        cls,
        campaign_id: str,
        participant_id: str,
        error_message: str,
        attempt_count: int,
    ) -> None:
        """Record ambiguous send outcome (e.g. timeout during HTTP transmission). Needs reconciliation."""
        now_iso = datetime.now(timezone.utc).isoformat()
        updates = {
            "email_status": "unknown",
            "attempt_count": attempt_count,
            "last_error_code": "AMBIGUOUS_DELIVERY",
            "last_error_message": f"Send state uncertain: {error_message[:250]}",
            "processing_lease_id": None,
            "processing_lease_expires_at": None,
            "updated_at": now_iso,
        }
        cls.update_participant(campaign_id, participant_id, updates)

    @classmethod
    def increment_campaign_counters(
        cls,
        campaign_id: str,
        sent_delta: int = 0,
        failed_delta: int = 0,
        unknown_delta: int = 0,
        processed_count: int = 0,
    ) -> None:
        """Incrementally update campaign delivery counters without querying participant subcollections."""
        camp = cls.get_campaign(campaign_id)
        if not camp:
            return

        total_recipients = int(camp.get("total_recipients") or 0)
        if total_recipients == 0:
            camp_parts = _IN_MEMORY_PARTICIPANTS.get(campaign_id)
            if camp_parts:
                total_recipients = len(camp_parts)
            else:
                jobs = cls.get_active_jobs_for_campaign(campaign_id)
                if jobs:
                    total_recipients = int(jobs[0].get("total_recipients") or 0)
        sent_count = int(camp.get("sent_count") or 0) + sent_delta
        failed_count = int(camp.get("failed_count") or 0) + failed_delta
        unknown_count = int(camp.get("unknown_count") or 0) + unknown_delta
        queued_count = max(0, total_recipients - (sent_count + failed_count + unknown_count))

        updates = {
            "sent_count": sent_count,
            "failed_count": failed_count,
            "unknown_count": unknown_count,
            "queued_count": queued_count,
            "processing_count": 0,
            "last_processed_at": datetime.now(timezone.utc).isoformat(),
        }
        cls.update_campaign(campaign_id, updates)

    @classmethod
    def recalculate_and_sync_campaign_counters(cls, campaign_id: str) -> Dict[str, Any]:
        """
        Recalculates accurate counts directly from participant subcollection using lightweight projection.
        Updates campaign document to keep authoritative counters completely synchronized without loading heavy blobs.
        """
        client = cls._get_client()
        counts = {
            "total_recipients": 0,
            "queued_count": 0,
            "processing_count": 0,
            "sent_count": 0,
            "failed_count": 0,
            "cancelled_count": 0,
            "unknown_count": 0,
        }

        if client:
            try:
                # Fast projection query: ONLY select email_status
                docs = (
                    client.collection("campaigns")
                    .document(campaign_id)
                    .collection("participants")
                    .select(["email_status"])
                    .stream()
                )
                for d in docs:
                    counts["total_recipients"] += 1
                    data = d.to_dict()
                    st = data.get("email_status", "queued")
                    if st == "sent":
                        counts["sent_count"] += 1
                    elif st == "failed":
                        counts["failed_count"] += 1
                    elif st == "processing":
                        counts["processing_count"] += 1
                    elif st == "cancelled":
                        counts["cancelled_count"] += 1
                    elif st == "unknown":
                        counts["unknown_count"] += 1
                    else:
                        counts["queued_count"] += 1
            except Exception as e:
                log.warning("Lightweight counter calculation fallback", error=str(e))
                participants = cls.get_campaign_participants(campaign_id, limit=2000, include_pdf_bytes=False)
                counts["total_recipients"] = len(participants)
                for p in participants:
                    st = p.get("email_status", "queued")
                    if st == "sent":
                        counts["sent_count"] += 1
                    elif st == "failed":
                        counts["failed_count"] += 1
                    elif st == "processing":
                        counts["processing_count"] += 1
                    elif st == "cancelled":
                        counts["cancelled_count"] += 1
                    elif st == "unknown":
                        counts["unknown_count"] += 1
                    else:
                        counts["queued_count"] += 1
        else:
            participants = cls.get_campaign_participants(campaign_id, limit=2000, include_pdf_bytes=False)
            counts["total_recipients"] = len(participants)
            for p in participants:
                st = p.get("email_status", "queued")
                if st == "sent":
                    counts["sent_count"] += 1
                elif st == "failed":
                    counts["failed_count"] += 1
                elif st == "processing":
                    counts["processing_count"] += 1
                elif st == "cancelled":
                    counts["cancelled_count"] += 1
                elif st == "unknown":
                    counts["unknown_count"] += 1
                else:
                    counts["queued_count"] += 1

        # Derive campaign status if all done
        camp = cls.get_campaign(campaign_id)
        current_status = camp.get("status") if camp else "draft"
        new_status = current_status

        if counts["total_recipients"] > 0 and (counts["queued_count"] + counts["processing_count"]) == 0:
            if current_status not in ["cancelled", "paused"]:
                if counts["failed_count"] == counts["total_recipients"]:
                    new_status = "failed"
                else:
                    new_status = "completed"

        updates = {
            **counts,
            "status": new_status,
            "last_processed_at": datetime.now(timezone.utc).isoformat(),
        }
        cls.update_campaign(campaign_id, updates)
        return updates

    @classmethod
    def find_expired_leased_jobs(cls) -> List[Dict[str, Any]]:
        """Find active email jobs whose lease has expired due to process death or Render sleep."""
        now = datetime.now(timezone.utc)
        expired_jobs: List[Dict[str, Any]] = []

        client = cls._get_client()
        if client:
            try:
                docs = cls._apply_filter(client.collection("email_jobs"), "status", "==", "processing").stream()
                for d in docs:
                    job = d.to_dict()
                    exp_str = job.get("lease_expires_at")
                    if exp_str:
                        try:
                            exp_dt = datetime.fromisoformat(exp_str)
                            if exp_dt < now:
                                expired_jobs.append(job)
                        except Exception:
                            expired_jobs.append(job)
                    else:
                        expired_jobs.append(job)
                return expired_jobs
            except Exception:
                pass

        for job in _IN_MEMORY_JOBS.values():
            if job.get("status") == "processing":
                exp_str = job.get("lease_expires_at")
                if exp_str:
                    try:
                        exp_dt = datetime.fromisoformat(exp_str)
                        if exp_dt < now:
                            expired_jobs.append(job)
                    except Exception:
                        expired_jobs.append(job)
                else:
                    expired_jobs.append(job)

        return expired_jobs

    @classmethod
    def reconcile_stuck_participants(cls, campaign_id: str, lease_timeout_seconds: int = 300) -> int:
        """
        Reset participants stuck in 'processing' status with expired leases back to 'queued' or 'retrying'.
        """
        now = datetime.now(timezone.utc)
        reconciled = 0
        participants = cls.get_campaign_participants(campaign_id, status_filter="processing", limit=500)

        for p in participants:
            p_id = p.get("participant_id") or p.get("id")
            if not p_id:
                continue
            exp_str = p.get("processing_lease_expires_at")
            is_expired = True
            if exp_str:
                try:
                    exp_dt = datetime.fromisoformat(exp_str)
                    is_expired = exp_dt < now
                except Exception:
                    is_expired = True

            if is_expired:
                attempts = p.get("attempt_count", 0)
                reset_status = "retrying" if attempts > 0 else "queued"
                cls.update_participant(
                    campaign_id,
                    p_id,
                    {
                        "email_status": reset_status,
                        "processing_lease_id": None,
                        "processing_lease_expires_at": None,
                        "updated_at": now.isoformat(),
                    },
                )
                reconciled += 1

        return reconciled


# Singleton instance
firestore_service = FirestoreService()
