import io
import ipaddress
import logging
import socket
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import httpx
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataflow.config import Settings, get_settings
from dataflow.models.dataset import Dataset, IngestionCheckpoint
from dataflow.schemas.source import RestIngestionResponse, RestSourceConfig
from dataflow.services.audit import AuditService
from dataflow.services.ingestion import IngestionService
from dataflow.services.retry import PermanentError, TransientError, execute_with_retry

logger = logging.getLogger(__name__)


def is_unsafe_ip(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> bool:
    """Return True if IP address is private, loopback, link-local, multicast, or reserved."""
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            return is_unsafe_ip(ip.ipv4_mapped)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        )

    if (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    ):
        return True

    # Carrier-grade NAT (100.64.0.0/10) and Current network (0.0.0.0/8)
    if isinstance(ip, ipaddress.IPv4Address):
        if ip in ipaddress.IPv4Network("100.64.0.0/10"):
            return True
        if ip in ipaddress.IPv4Network("0.0.0.0/8"):
            return True

    return False


def validate_url_safety(url_str: str, allow_private_ip: bool = False) -> None:
    """Validate URL format and prevent unauthorized SSRF destinations, including DNS pre-resolution."""
    try:
        parsed = urllib.parse.urlparse(url_str)
    except Exception as exc:
        raise PermanentError(f"Malformed URL: {exc}") from exc

    if parsed.scheme not in ("http", "https"):
        raise PermanentError(f"Unsupported URL scheme '{parsed.scheme}'. Only http and https are allowed.")

    hostname = parsed.hostname
    if not hostname:
        raise PermanentError(f"Invalid URL '{url_str}': Missing hostname.")

    if allow_private_ip:
        return

    # 1. Check literal hostname strings
    lower_host = hostname.lower().strip("[]")
    if lower_host in ("localhost", "0.0.0.0", "127.0.0.1", "::1", "metadata.google.internal"):
        raise PermanentError(f"Access to loopback/metadata host '{hostname}' is forbidden.")

    # 2. Check if hostname is a literal IP address
    try:
        ip = ipaddress.ip_address(lower_host)
        if is_unsafe_ip(ip):
            raise PermanentError(f"Access to private/unsafe IP address '{hostname}' is forbidden.")
        return
    except ValueError:
        pass  # Hostname is a domain name, proceed to DNS resolution

    # 3. DNS Resolution check to prevent DNS rebinding to private/loopback addresses
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        addr_info = socket.getaddrinfo(hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as err:
        raise PermanentError(f"Cannot resolve hostname '{hostname}': {err}") from err
    except Exception as err:
        raise PermanentError(f"DNS resolution failed for '{hostname}': {err}") from err

    for _, _, _, _, sockaddr in addr_info:
        raw_ip = sockaddr[0]
        try:
            resolved_ip = ipaddress.ip_address(raw_ip)
            if is_unsafe_ip(resolved_ip):
                raise PermanentError(
                    f"Hostname '{hostname}' resolves to unsafe IP address '{resolved_ip}'. Access is forbidden."
                )
        except ValueError:
            raise PermanentError(f"Invalid resolved IP '{raw_ip}' for host '{hostname}'.")


class RestIngestionService:
    """Orchestrates HTTP extraction, pagination, canonical mapping, and checkpointing."""

    MAX_REDIRECTS = 5

    def __init__(
        self,
        ingestion_service: IngestionService,
        audit_service: Optional[AuditService] = None,
        settings: Optional[Settings] = None,
    ):
        self.ingestion = ingestion_service
        self.audit = audit_service or AuditService()
        self.settings = settings or get_settings()

    def ingest_from_rest(
        self,
        db: Session,
        config: RestSourceConfig,
        allow_private_hosts: bool = False,
    ) -> RestIngestionResponse:
        """Execute REST extraction, canonical conversion, and atomic checkpoint commit."""
        validate_url_safety(config.url, allow_private_ip=allow_private_hosts)

        # Initialize audit job
        job = self.audit.create_job(
            db=db,
            job_type="rest_ingestion",
            dataset_id=config.dataset_id,
        )

        try:
            # 1. Row-lock Dataset if targeting an existing dataset to prevent concurrent ingestion interleaving
            if config.dataset_id:
                ds_stmt = select(Dataset).where(Dataset.id == config.dataset_id)
                if db.bind and db.bind.dialect.name == "postgresql":
                    ds_stmt = ds_stmt.with_for_update()
                dataset_obj = db.scalar(ds_stmt)
                if not dataset_obj or dataset_obj.is_deleted:
                    raise PermanentError(f"Dataset with ID {config.dataset_id} not found.")

            # 2. Resolve existing checkpoint with row-lock if present
            checkpoint: Optional[IngestionCheckpoint] = None
            if config.dataset_id:
                cp_stmt = select(IngestionCheckpoint).where(
                    IngestionCheckpoint.source_identifier == config.source_identifier,
                    IngestionCheckpoint.dataset_id == config.dataset_id,
                )
                if db.bind and db.bind.dialect.name == "postgresql":
                    cp_stmt = cp_stmt.with_for_update()
                checkpoint = db.scalar(cp_stmt)

            # 3. Extract records across pages with bounded retries and SSRF-safe redirect validation
            records, pages_fetched = self._fetch_all_records(
                config=config,
                existing_watermark=checkpoint.watermark_value if checkpoint else None,
                allow_private_hosts=allow_private_hosts,
            )

            # 4. Handle incremental filtering if cursor is present
            new_watermark = None
            if config.cursor_column and records:
                if checkpoint and checkpoint.watermark_value:
                    records = [
                        r for r in records
                        if str(r.get(config.cursor_column, "")) > checkpoint.watermark_value
                    ]

                if records:
                    cursor_vals = [
                        str(r.get(config.cursor_column, ""))
                        for r in records
                        if r.get(config.cursor_column) is not None
                    ]
                    if cursor_vals:
                        new_watermark = max(cursor_vals)

            if not records:
                # No new records to ingest
                self.audit.complete_job(
                    db=db,
                    job=job,
                    status="succeeded",
                    metrics={"records_extracted": 0, "pages_fetched": pages_fetched},
                )
                db.commit()
                return RestIngestionResponse(
                    job_id=job.id,
                    dataset_id=config.dataset_id or "none",
                    version_id="none",
                    records_ingested=0,
                    watermark_value=checkpoint.watermark_value if checkpoint else None,
                    pages_fetched=pages_fetched,
                    status="succeeded",
                )

            # 5. Canonicalize to DataFrame and CSV buffer
            df = pd.DataFrame(records)
            csv_buf = io.BytesIO()
            df.to_csv(csv_buf, index=False, encoding="utf-8")
            csv_bytes = csv_buf.getvalue()
            filename = f"{config.source_identifier}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.csv"

            # 6. Persist via IngestionService (creates or updates dataset & version)
            d_name = config.dataset_name or f"REST: {config.source_identifier}"
            dataset, version = self.ingestion.ingest_csv(
                db=db,
                file_obj=io.BytesIO(csv_bytes),
                filename=filename,
                dataset_name=d_name,
                dataset_id=config.dataset_id,
                description=f"Ingested from {config.url}",
            )
            target_dataset_id = dataset.id

            # 7. Advance or create IngestionCheckpoint atomically in the same transaction
            final_watermark = new_watermark or (checkpoint.watermark_value if checkpoint else "0")
            if config.cursor_column:
                # Re-query checkpoint with lock in case it was created concurrently
                recheck_stmt = select(IngestionCheckpoint).where(
                    IngestionCheckpoint.source_identifier == config.source_identifier,
                    IngestionCheckpoint.dataset_id == target_dataset_id,
                )
                if db.bind and db.bind.dialect.name == "postgresql":
                    recheck_stmt = recheck_stmt.with_for_update()
                current_checkpoint = db.scalar(recheck_stmt)

                if current_checkpoint:
                    current_checkpoint.watermark_value = final_watermark
                    current_checkpoint.records_extracted += len(records)
                    current_checkpoint.last_run_at = datetime.now(timezone.utc)
                else:
                    new_checkpoint = IngestionCheckpoint(
                        source_identifier=config.source_identifier,
                        dataset_id=target_dataset_id,
                        cursor_column=config.cursor_column,
                        watermark_value=final_watermark,
                        records_extracted=len(records),
                        last_run_at=datetime.now(timezone.utc),
                    )
                    db.add(new_checkpoint)

            db.commit()

            # 8. Complete job record
            self.audit.complete_job(
                db=db,
                job=job,
                status="succeeded",
                metrics={
                    "records_extracted": len(records),
                    "pages_fetched": pages_fetched,
                    "watermark": final_watermark,
                },
            )

            return RestIngestionResponse(
                job_id=job.id,
                dataset_id=target_dataset_id,
                version_id=version.id,
                records_ingested=len(records),
                watermark_value=final_watermark if config.cursor_column else None,
                pages_fetched=pages_fetched,
                status="succeeded",
            )

        except Exception as exc:
            db.rollback()
            self.audit.complete_job(
                db=db,
                job=job,
                status="failed",
                error_message=str(exc),
            )
            raise

    def _fetch_all_records(
        self,
        config: RestSourceConfig,
        existing_watermark: Optional[str] = None,
        allow_private_hosts: bool = False,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Fetch records with pagination, retry handling, and SSRF-safe redirect validation."""
        all_records: List[Dict[str, Any]] = []
        page = 1
        offset = 0
        pages_fetched = 0

        timeout = httpx.Timeout(
            connect=5.0,
            read=self.settings.DEFAULT_TIMEOUT_SECONDS,
            write=10.0,
            pool=5.0,
        )

        with httpx.Client(timeout=timeout, follow_redirects=False) as client:
            while pages_fetched < config.max_pages:
                current_params = dict(config.params)

                # Inject incremental watermark if requested
                if config.cursor_param and existing_watermark:
                    current_params[config.cursor_param] = existing_watermark

                # Inject pagination params
                if config.pagination_type == "page":
                    current_params[config.page_param] = page
                    current_params[config.limit_param] = config.page_size
                elif config.pagination_type == "offset":
                    current_params[config.page_param] = offset
                    current_params[config.limit_param] = config.page_size

                # Bounded retry wrapped HTTP request
                page_data = execute_with_retry(
                    operation=lambda p=current_params: self._http_get_page(
                        client=client,
                        url=config.url,
                        params=p,
                        headers=config.headers,
                        allow_private_hosts=allow_private_hosts,
                    ),
                    max_attempts=self.settings.MAX_RETRIES,
                    backoff_factor=self.settings.RETRY_BACKOFF_FACTOR,
                    max_backoff=self.settings.RETRY_MAX_BACKOFF_SECONDS,
                    jitter=False,  # deterministic in tests
                )

                records = self._extract_records_from_response(page_data, config.records_json_path)
                pages_fetched += 1

                if not records:
                    break

                all_records.extend(records)

                # If single page or returned fewer than requested page_size, end pagination
                if not config.pagination_type or len(records) < config.page_size:
                    break

                page += 1
                offset += len(records)

        return all_records, pages_fetched

    def _http_get_page(
        self,
        client: httpx.Client,
        url: str,
        params: Dict[str, Any],
        headers: Dict[str, str],
        allow_private_hosts: bool = False,
    ) -> Any:
        """Execute HTTP request with strict redirect validation to prevent SSRF bypass."""
        current_url = url
        current_params = params

        for _ in range(self.MAX_REDIRECTS):
            try:
                resp = client.get(
                    current_url,
                    params=current_params,
                    headers=headers,
                    follow_redirects=False,
                )
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as err:
                raise TransientError(f"Network transient error reaching {current_url}: {err}") from err
            except Exception as err:
                raise PermanentError(f"HTTP client request failure: {err}") from err

            # Intercept redirects to validate target destination URL before fetching
            if resp.is_redirect:
                location = resp.headers.get("Location")
                if not location:
                    raise PermanentError(f"Redirect response from {current_url} missing Location header")

                next_url = urllib.parse.urljoin(str(resp.url), location)
                # CRITICAL: Validate redirect destination against SSRF policy
                validate_url_safety(next_url, allow_private_ip=allow_private_hosts)

                current_url = next_url
                current_params = {}  # Parameters are already encoded into the redirect target URL
                continue

            if resp.status_code == 429:
                raise TransientError(f"HTTP 429 Rate limited by upstream {current_url}")
            elif resp.status_code in (500, 502, 503, 504):
                raise TransientError(f"HTTP {resp.status_code} Upstream service unavailable: {resp.text[:200]}")
            elif resp.status_code >= 400:
                raise PermanentError(f"HTTP {resp.status_code} Client error from upstream: {resp.text[:200]}")

            try:
                return resp.json()
            except Exception as exc:
                raise PermanentError(f"Failed to parse upstream JSON response: {exc}") from exc

        raise PermanentError(f"Too many redirects (exceeded limit of {self.MAX_REDIRECTS})")

    def _extract_records_from_response(
        self,
        data: Any,
        records_json_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Extract list of records from structured JSON."""
        if records_json_path:
            parts = records_json_path.split(".")
            curr = data
            for part in parts:
                if isinstance(curr, dict) and part in curr:
                    curr = curr[part]
                else:
                    return []
            if isinstance(curr, list):
                return [r for r in curr if isinstance(r, dict)]
            elif isinstance(curr, dict):
                return [curr]
            return []

        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]

        if isinstance(data, dict):
            for common_key in ("results", "data", "items", "records", "features"):
                if common_key in data and isinstance(data[common_key], list):
                    return [r for r in data[common_key] if isinstance(r, dict)]
            return [data]

        return []
