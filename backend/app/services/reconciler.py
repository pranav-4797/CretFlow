"""
Restart Recovery and Job Reconciliation Service for CertFlow.
Handles automatic recovery after service restarts or Render Web Service spin-down on free tier.

Responsibilities:
1. Scan for jobs left in 'processing' whose leases expired during process shutdown or idle sleep.
2. Reconcile participants stuck in 'processing' beyond lease timeout back to 'retrying' or 'queued'.
3. Idempotently recalculate and sync accurate campaign counters from persistent Firestore records.
4. Auto-resume eligible unfinished jobs safely when service wakes up.
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

import structlog

from app.services.firestore_service import firestore_service

log = structlog.get_logger(__name__)


class RestartReconciler:
    """Reconciles interrupted email jobs and stuck participants on startup or activity wakeup."""

    @classmethod
    async def reconcile_all_on_startup(cls) -> Dict[str, Any]:
        """
        Executes safe, idempotent recovery on application startup.
        Identifies orphaned leases from previous runs or Render container restarts.
        """
        log.info("Starting CertFlow job reconciliation on application startup")
        recovered_jobs = 0
        reconciled_participants = 0
        campaigns_checked = set()

        try:
            # 1. Find expired leased jobs
            expired_jobs = firestore_service.find_expired_leased_jobs()
            log.info("Found expired leased jobs for reconciliation", count=len(expired_jobs))

            for job in expired_jobs:
                job_id = job.get("job_id")
                campaign_id = job.get("campaign_id")
                if not job_id or not campaign_id:
                    continue

                campaigns_checked.add(campaign_id)

                # Reset job lease and mark retrying or queued
                now_iso = datetime.now(timezone.utc).isoformat()
                firestore_service.update_email_job(
                    job_id,
                    {
                        "status": "queued",
                        "lease_id": None,
                        "lease_expires_at": None,
                        "updated_at": now_iso,
                    },
                )
                recovered_jobs += 1

                # Reconcile participants stuck in processing for this campaign
                stuck = firestore_service.reconcile_stuck_participants(campaign_id)
                reconciled_participants += stuck

                # Recalculate campaign progress counters
                firestore_service.recalculate_and_sync_campaign_counters(campaign_id)

            log.info(
                "Startup reconciliation completed successfully",
                recovered_jobs=recovered_jobs,
                reconciled_participants=reconciled_participants,
                campaigns_affected=len(campaigns_checked),
            )

            return {
                "recovered_jobs": recovered_jobs,
                "reconciled_participants": reconciled_participants,
                "campaigns_checked": list(campaigns_checked),
            }

        except Exception as e:
            log.error("Error during startup job reconciliation (continuing boot)", error=str(e))
            return {
                "recovered_jobs": recovered_jobs,
                "reconciled_participants": reconciled_participants,
                "error": str(e),
            }

    @classmethod
    async def reconcile_campaign_on_activity(cls, campaign_id: str) -> None:
        """
        Reconcile a specific campaign when requested by the organizer dashboard.
        Guarantees that if a campaign was interrupted by Render sleep, any stuck recipients
        are reset back to queued/retrying so progress can resume.
        """
        try:
            stuck = firestore_service.reconcile_stuck_participants(campaign_id)
            if stuck > 0:
                log.info("Activity check reset stuck participants", campaign_id=campaign_id, count=stuck)
            firestore_service.recalculate_and_sync_campaign_counters(campaign_id)
        except Exception as e:
            log.warning("Campaign activity reconciliation skipped", campaign_id=campaign_id, error=str(e))


# Singleton instance
reconciler = RestartReconciler()
