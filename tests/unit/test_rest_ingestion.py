"""Unit tests for REST source ingestion, pagination, and incremental watermark checkpoints."""

import pytest

from dataflow.models.dataset import IngestionCheckpoint
from dataflow.schemas.source import RestSourceConfig
from dataflow.services.ingestion import IngestionService
from dataflow.services.rest_ingestion import RestIngestionService, validate_url_safety
from dataflow.services.retry import PermanentError


def test_ssrf_safety_validation_literal_ips_and_schemes():
    """Verify SSRF validation blocks dangerous loopback, private IPv4/IPv6, and non-http schemes."""
    # Unsupported schemes
    with pytest.raises(PermanentError, match="Unsupported URL scheme"):
        validate_url_safety("ftp://example.com/data.csv")

    with pytest.raises(PermanentError, match="Unsupported URL scheme"):
        validate_url_safety("file:///etc/passwd")

    with pytest.raises(PermanentError, match="Missing hostname"):
        validate_url_safety("http://")

    # Loopback IP and hostnames
    with pytest.raises(PermanentError, match="Access to loopback/metadata host"):
        validate_url_safety("http://127.0.0.1:8000/api")

    with pytest.raises(PermanentError, match="Access to loopback/metadata host"):
        validate_url_safety("http://localhost:5432/events")

    with pytest.raises(PermanentError, match="Access to loopback/metadata host"):
        validate_url_safety("http://metadata.google.internal/computeMetadata/v1/")

    # Private IPv4 ranges
    with pytest.raises(PermanentError, match="Access to private/unsafe IP"):
        validate_url_safety("http://10.0.0.1/data")

    with pytest.raises(PermanentError, match="Access to private/unsafe IP"):
        validate_url_safety("http://192.168.1.100:8080/data")

    with pytest.raises(PermanentError, match="Access to private/unsafe IP"):
        validate_url_safety("http://172.16.0.5/api")

    # Link-local / Cloud metadata IP (169.254.169.254)
    with pytest.raises(PermanentError, match="Access to private/unsafe IP"):
        validate_url_safety("http://169.254.169.254/latest/meta-data")

    # Carrier-grade NAT (100.64.0.0/10)
    with pytest.raises(PermanentError, match="Access to private/unsafe IP"):
        validate_url_safety("http://100.64.0.1/api")

    # IPv6 Loopback and link-local
    with pytest.raises(PermanentError, match="Access to loopback/metadata host|Access to private/unsafe IP"):
        validate_url_safety("http://[::1]:8080/metrics")

    with pytest.raises(PermanentError, match="Access to private/unsafe IP"):
        validate_url_safety("http://[fe80::1]/api")

    with pytest.raises(PermanentError, match="Access to private/unsafe IP"):
        validate_url_safety("http://[fc00::1]/api")

    # IPv4-mapped IPv6
    with pytest.raises(PermanentError, match="Access to private/unsafe IP"):
        validate_url_safety("http://[::ffff:127.0.0.1]/data")

    with pytest.raises(PermanentError, match="Access to private/unsafe IP"):
        validate_url_safety("http://[::ffff:10.0.0.1]/data")


def test_ssrf_safety_dns_resolution(monkeypatch):
    """Verify DNS resolution detects hostnames pointing to private or loopback IPs."""
    import socket

    # Simulate hostname resolving to a private IP (192.168.1.55)
    def mock_getaddrinfo_private(host, port, proto=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.168.1.55", port))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo_private)
    with pytest.raises(PermanentError, match="resolves to unsafe IP address"):
        validate_url_safety("https://internal.company.corp/api/data")

    # Simulate hostname resolving to loopback (127.0.0.1)
    def mock_getaddrinfo_loopback(host, port, proto=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo_loopback)
    with pytest.raises(PermanentError, match="resolves to unsafe IP address"):
        validate_url_safety("https://rebinding.attacker.com/leak")

    # Simulate unresolvable host (DNS failure)
    def mock_getaddrinfo_fail(host, port, proto=0):
        raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo_fail)
    with pytest.raises(PermanentError, match="Cannot resolve hostname"):
        validate_url_safety("https://nonexistent-domain-xyz123456.org/api")

    # Simulate legitimate public IP (93.184.216.34)
    def mock_getaddrinfo_public(host, port, proto=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    monkeypatch.setattr(socket, "getaddrinfo", mock_getaddrinfo_public)
    # Should succeed without raising
    validate_url_safety("https://example.com/api/data")


def test_ssrf_redirect_validation(storage, monkeypatch):
    """Verify that HTTP redirects to unsafe/private destinations are intercepted and rejected."""
    import httpx
    ingestion = IngestionService(storage=storage)
    service = RestIngestionService(ingestion_service=ingestion)

    # 1. Test redirect to private cloud metadata endpoint
    class MockRedirectToMetadataClient:
        def __init__(self, *args, **kwargs):
            pass

        def get(self, url, params=None, headers=None, follow_redirects=False):
            if "start" in url:
                # Return 302 redirecting to metadata service
                return httpx.Response(
                    status_code=302,
                    headers={"Location": "http://169.254.169.254/latest/meta-data"},
                    request=httpx.Request("GET", url),
                )
            raise AssertionError("Should not reach second request")

    mock_client = MockRedirectToMetadataClient()
    with pytest.raises(PermanentError, match="Access to private/unsafe IP address"):
        service._http_get_page(
            client=mock_client,
            url="https://legit-site.com/start",
            params={},
            headers={},
            allow_private_hosts=False,
        )

    # 2. Test redirect to legitimate destination works
    class MockValidRedirectClient:
        def get(self, url, params=None, headers=None, follow_redirects=False):
            if "start" in url:
                return httpx.Response(
                    status_code=301,
                    headers={"Location": "https://api.github.com/events"},
                    request=httpx.Request("GET", url),
                )
            elif "github.com" in url:
                return httpx.Response(
                    status_code=200,
                    json={"items": [{"id": 1}]},
                    request=httpx.Request("GET", url),
                )
            raise AssertionError(f"Unexpected url {url}")

    # Allow mock DNS resolution for api.github.com to a public IP
    import socket
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda h, p, proto=0: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("140.82.112.4", p))],
    )

    data = service._http_get_page(
        client=MockValidRedirectClient(),
        url="https://legit-site.com/start",
        params={},
        headers={},
        allow_private_hosts=False,
    )
    assert data == {"items": [{"id": 1}]}


def test_rest_ingestion_with_incremental_checkpoint(test_db_session, storage, monkeypatch):
    """Verify REST API extraction across pages with incremental watermark checkpointing."""
    ingestion = IngestionService(storage=storage)
    service = RestIngestionService(ingestion_service=ingestion)

    # Mock _http_get_page to return 2 pages of events
    def mock_http_get_page(client, url, params, headers, allow_private_hosts=False):
        page = params.get("page", 1)
        if page == 1:
            return {
                "results": [
                    {"id": 101, "event": "login", "timestamp": "2026-01-01T10:00:00Z"},
                    {"id": 102, "event": "click", "timestamp": "2026-01-01T10:05:00Z"},
                ]
            }
        elif page == 2:
            return {
                "results": [
                    {"id": 103, "event": "logout", "timestamp": "2026-01-01T10:15:00Z"},
                ]
            }
        return {"results": []}

    monkeypatch.setattr(service, "_http_get_page", mock_http_get_page)

    config = RestSourceConfig(
        source_identifier="events_api",
        url="https://api.external.com/events",
        pagination_type="page",
        page_size=2,
        max_pages=5,
        cursor_column="id",
        dataset_name="External Events",
    )

    # First run (allow_private_hosts=True to bypass public IP lookup in unit test)
    resp = service.ingest_from_rest(db=test_db_session, config=config, allow_private_hosts=True)

    assert resp.status == "succeeded"
    assert resp.records_ingested == 3
    assert resp.watermark_value == "103"
    assert resp.pages_fetched == 2

    # Check that IngestionCheckpoint was created in DB
    cp = test_db_session.query(IngestionCheckpoint).filter_by(
        source_identifier="events_api",
        dataset_id=resp.dataset_id,
    ).first()
    assert cp is not None
    assert cp.watermark_value == "103"
    assert cp.records_extracted == 3

    # Run second time: mock returns records up to 104
    def mock_second_run(client, url, params, headers, allow_private_hosts=False):
        return {
            "results": [
                {"id": 102, "event": "click", "timestamp": "2026-01-01T10:05:00Z"},
                {"id": 104, "event": "purchase", "timestamp": "2026-01-01T10:30:00Z"},
            ]
        }

    monkeypatch.setattr(service, "_http_get_page", mock_second_run)

    config_run2 = RestSourceConfig(
        source_identifier="events_api",
        url="https://api.external.com/events",
        cursor_column="id",
        dataset_id=resp.dataset_id,
    )

    resp2 = service.ingest_from_rest(db=test_db_session, config=config_run2, allow_private_hosts=True)

    # 102 was filtered out because it is <= previous watermark (103)
    assert resp2.records_ingested == 1
    assert resp2.watermark_value == "104"

    # Verify checkpoint advanced
    test_db_session.refresh(cp)
    assert cp.watermark_value == "104"
    assert cp.records_extracted == 4
