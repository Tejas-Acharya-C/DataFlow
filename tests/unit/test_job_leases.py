"""Unit tests for worker job heartbeat leases and stale-job reconciliation."""

from datetime import datetime, timedelta, timezone

from dataflow.services.audit import (
    create_job,
    is_job_lease_expired,
    reconcile_stale_jobs,
    touch_job_heartbeat,
)


def test_active_job_lease_preserved_during_reconciliation(test_db_session):
    """Verify that a job actively held by another worker is NOT marked interrupted on startup."""
    # Create active job on worker-beta with 120s lease
    job = create_job(
        db=test_db_session,
        job_type="ingestion",
        lease_seconds=120,
        worker_id="worker-beta",
    )
    assert job.status == "running"
    assert is_job_lease_expired(job) is False

    # Simulate startup reconciliation running from another process
    reconciled = reconcile_stale_jobs(db=test_db_session, stale_threshold_seconds=60)

    # Active job must be preserved
    assert reconciled == 0
    test_db_session.refresh(job)
    assert job.status == "running"
    assert job.metadata_json["worker_id"] == "worker-beta"


def test_stale_expired_job_reconciled_to_interrupted(test_db_session):
    """Verify that a crashed job whose lease expired is safely marked interrupted."""
    now = datetime.now(timezone.utc)
    expired_time = now - timedelta(seconds=120)

    # Create job with expired heartbeat metadata
    job = create_job(
        db=test_db_session,
        job_type="transformation",
        worker_id="crashed-worker",
    )
    job.metadata_json = {
        "worker_id": "crashed-worker",
        "heartbeat_at": (expired_time - timedelta(seconds=60)).isoformat(),
        "lease_expires_at": expired_time.isoformat(),
        "lease_seconds": 60,
    }
    test_db_session.add(job)
    test_db_session.commit()

    assert is_job_lease_expired(job, now=now) is True

    # Run reconciliation
    reconciled = reconcile_stale_jobs(db=test_db_session, stale_threshold_seconds=60)
    assert reconciled == 1

    test_db_session.refresh(job)
    assert job.status == "interrupted"
    assert job.error_category == "process_crash"
    assert "lease expired" in job.error_message


def test_touch_heartbeat_extends_lease(test_db_session):
    """Verify that touch_job_heartbeat extends the worker lease into the future."""
    job = create_job(
        db=test_db_session,
        job_type="validation",
        lease_seconds=30,
        worker_id="worker-gamma",
    )
    initial_expiry = job.metadata_json["lease_expires_at"]

    # Touch heartbeat with longer lease
    touch_job_heartbeat(db=test_db_session, job=job, lease_seconds=300)

    test_db_session.refresh(job)
    new_expiry = job.metadata_json["lease_expires_at"]
    assert new_expiry > initial_expiry
    assert is_job_lease_expired(job) is False
