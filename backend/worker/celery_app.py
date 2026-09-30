"""
CertFlow Worker — Celery Application

Handles background tasks:
- Certificate generation
- Bulk email sending
- Retry logic
- Report generation

Phase 1: Skeleton only.
Phase 10: Full implementation with Celery + Upstash Redis.
"""

from celery import Celery
from app.core.config import settings

# Create Celery application
celery_app = Celery(
    "certflow_worker",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "worker.tasks.certificates",
        "worker.tasks.emails",
    ],
)

# Configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_acks_late=True,          # Don't ack until task completes
    task_reject_on_worker_lost=True,  # Re-queue if worker crashes
    task_track_started=True,
    task_default_queue="default",
    task_queues={
        "default": {},
        "certificates": {},
        "emails": {},
    },
    task_routes={
        "worker.tasks.certificates.*": {"queue": "certificates"},
        "worker.tasks.emails.*": {"queue": "emails"},
    },
    # Retry policy
    task_max_retries=3,
    task_default_retry_delay=60,  # 1 minute between retries
)


if __name__ == "__main__":
    celery_app.start()
