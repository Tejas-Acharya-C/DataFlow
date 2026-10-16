"""API integration tests for authentication enforcement, health bypass, and misconfiguration handling."""

from fastapi.testclient import TestClient

from dataflow.config import Settings, get_settings
from dataflow.main import app


def test_auth_enforcement_on_protected_endpoints():
    """Verify endpoints reject unauthenticated requests when AUTH_ENABLED=True."""
    custom_settings = Settings(
        AUTH_ENABLED=True,
        DATAFLOW_API_KEY="super-secret-key-123",
    )
    app.dependency_overrides[get_settings] = lambda: custom_settings

    try:
        client = TestClient(app)

        # 1. Missing API key -> 401 Unauthorized
        resp_missing = client.get("/api/v1/datasets")
        assert resp_missing.status_code == 401
        assert "Missing API key" in resp_missing.json()["detail"]

        # 2. Invalid API key -> 401 Unauthorized
        resp_invalid = client.get("/api/v1/datasets", headers={"X-API-Key": "wrong-key"})
        assert resp_invalid.status_code == 401
        assert "Invalid API key" in resp_invalid.json()["detail"]

        # 3. Valid API key -> 200 OK
        resp_valid = client.get("/api/v1/datasets", headers={"X-API-Key": "super-secret-key-123"})
        assert resp_valid.status_code == 200

        # 4. Health endpoint remains accessible without credentials
        resp_health = client.get("/api/v1/health")
        assert resp_health.status_code == 200

        resp_readiness = client.get("/api/v1/health/readiness")
        assert resp_readiness.status_code == 200

    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_auth_misconfigured_safe_failure():
    """Verify server returns 500 when AUTH_ENABLED=True but no DATAFLOW_API_KEY is configured."""
    custom_settings = Settings(
        AUTH_ENABLED=True,
        DATAFLOW_API_KEY=None,
    )
    app.dependency_overrides[get_settings] = lambda: custom_settings

    try:
        client = TestClient(app)
        resp = client.get("/api/v1/datasets", headers={"X-API-Key": "any-key"})
        assert resp.status_code == 500
        assert "misconfigured" in resp.json()["detail"]
    finally:
        app.dependency_overrides.pop(get_settings, None)


def test_auth_disabled_by_default():
    """Verify development default (AUTH_ENABLED=False) allows requests without API key."""
    custom_settings = Settings(AUTH_ENABLED=False)
    app.dependency_overrides[get_settings] = lambda: custom_settings

    try:
        client = TestClient(app)
        resp = client.get("/api/v1/datasets")
        assert resp.status_code == 200
    finally:
        app.dependency_overrides.pop(get_settings, None)
