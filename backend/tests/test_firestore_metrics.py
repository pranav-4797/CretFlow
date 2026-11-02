import pytest
from app.services.firestore_service import firestore_service, FirestoreMetrics


def test_firestore_metrics_recording():
    FirestoreMetrics.reset()
    FirestoreMetrics.record_read("test_op", 5)
    FirestoreMetrics.record_read("test_op", 2)
    FirestoreMetrics.record_read("another_op", 1)

    summary = FirestoreMetrics.get_summary()
    assert summary.get("test_op") == 7
    assert summary.get("another_op") == 1


def test_get_user_analytics_does_not_scan_participants():
    FirestoreMetrics.reset()
    user_id = "test-analytics-user"
    # Create test campaign with metadata
    c = firestore_service.create_campaign({
        "campaign_id": "analytics_camp_1",
        "campaign_name": "Analytics Camp",
        "owner_uid": user_id,
        "total_recipients": 150,
        "sent_count": 50,
    })

    analytics = firestore_service.get_user_analytics(user_id)
    assert analytics["total_campaigns"] >= 1
    assert analytics["total_participants"] >= 150
    assert analytics["emails_sent"] >= 50

    summary = FirestoreMetrics.get_summary()
    # Should not have performed full participant subcollection scans
    assert summary.get("get_user_analytics_subcollection_scan", 0) == 0


def test_get_campaign_stats_uses_campaign_metadata_and_limits_logs():
    FirestoreMetrics.reset()
    user_id = "stats-user-123"
    camp_id = "stats_camp_99"

    firestore_service.create_campaign({
        "campaign_id": camp_id,
        "campaign_name": "Stats Campaign",
        "owner_uid": user_id,
        "total_recipients": 200,
        "sent_count": 80,
        "queued_count": 110,
        "failed_count": 10,
        "status": "processing",
    })

    # Add 25 in-memory participants to test subcollection limiting
    for i in range(25):
        firestore_service.save_participant(camp_id, {
            "participant_id": f"part_{i}",
            "recipient_name": f"Recipient {i}",
            "recipient_email": f"p{i}@example.com",
            "email_status": "sent" if i < 10 else "queued",
        })

    stats = firestore_service.get_campaign_stats(camp_id, user_id)
    assert stats["total_count"] == 200
    assert stats["sent_count"] == 80
    assert stats["failed_count"] == 10
    # Must never return more than 10 logs to avoid heavy network/read overhead
    assert len(stats["recent_logs"]) <= 10


def test_campaign_caching_and_invalidation():
    FirestoreMetrics.reset()
    user_id = "cache-user-456"
    camp_id = "cache_camp_1"

    firestore_service.create_campaign({
        "campaign_id": camp_id,
        "campaign_name": "Initial Name",
        "owner_uid": user_id,
    })

    # First get
    c1 = firestore_service.get_campaign(camp_id, user_id)
    assert c1["campaign_name"] == "Initial Name"

    # Second get should hit cache
    c2 = firestore_service.get_campaign(camp_id, user_id)
    assert c2["campaign_name"] == "Initial Name"

    # Invalidate via update
    firestore_service.update_campaign(camp_id, {"campaign_name": "Updated Name"})
    c3 = firestore_service.get_campaign(camp_id, user_id)
    assert c3["campaign_name"] == "Updated Name"
