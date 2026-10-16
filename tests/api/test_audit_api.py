"""API tests for jobs and audit logs."""

def test_jobs_and_audit_endpoints(client):
    # Retrieve audit list
    res_audit = client.get("/api/v1/audit")
    assert res_audit.status_code == 200
    assert "items" in res_audit.json()
    assert "total" in res_audit.json()

    # Retrieve jobs list
    res_jobs = client.get("/api/v1/jobs")
    assert res_jobs.status_code == 200
    assert "items" in res_jobs.json()
    assert "total" in res_jobs.json()
