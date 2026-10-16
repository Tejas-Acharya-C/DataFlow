# DataFlow Architecture Specification

## 1. Executive Summary

DataFlow is a high-reliability data platform designed to ingest, validate, profile, transform, version, and store datasets with deterministic reliability guarantees. Built as a maintainable **modular monolith**, it prioritizes simplicity, safety, and strict reproducibility without introducing unneeded infrastructure complexity such as distributed task queues, microservices, or complex external dependencies.

---

## 2. System Architecture

```text
               +----------------------------------+
               |     React + TypeScript (Vite)     |
               |      Modern Responsive UI        |
               +-----------------+----------------+
                                 | (HTTP / REST API)
                                 v
               +----------------------------------+
               |         FastAPI Gateway          |
               |       (/api/v1 Endpoints)        |
               +-----------------+----------------+
                                 |
         +-----------------------+-----------------------+
         |                       |                       |
         v                       v                       v
+-----------------+     +-----------------+     +-----------------+
| Ingestion &     |     | Contracts &     |     | Transform &     |
| Profiling       |     | Quality Engine  |     | Lineage Engine  |
+--------+--------+     +--------+--------+     +--------+--------+
         |                       |                       |
         +-----------------------+-----------------------+
                                 |
         +-----------------------+-----------------------+
         |                                               |
         v                                               v
+-------------------------------+             +--------------------+
| PostgreSQL / SQLite Database  |             | Local File Storage |
| SQLAlchemy 2.x + Alembic      |             | (SHA-256 Hashed    |
| (Metadata, Lineage, Audit)    |             | CSV Artifacts)     |
+-------------------------------+             +--------------------+
```

---

## 3. Core Modules and Responsibilities

### 3.1 CSV Ingestion and Storage Layer (`dataflow.storage.local`, `dataflow.services.ingestion`)
- **Safety**: Upload limits are strictly enforced (`MAX_UPLOAD_SIZE_BYTES`). Path traversal attacks (`../`) are detected and rejected.
- **Integrity**: Streaming SHA-256 checksums are calculated on the fly without unbounded memory consumption.
- **Validation**: Rejects empty files, non-CSV files, malformed syntax, and duplicate column headers.
- **Persistence**: File contents are saved to `./dataflow_storage/datasets/{dataset_id}/{version_id}.csv`.

### 3.2 Data Contracts and Validation (`dataflow.services.validation`)
- Reusable, declarative specifications defining:
  - Required column sets
  - Expected column types (`int`, `float`, `string`, `boolean`, `datetime`)
  - Nullability constraints
  - Uniqueness constraints
  - Allowed categorical values
  - Numeric minimum / maximum ranges
  - String length bounds
  - Dataset-level row count boundaries (`min_rows`, `max_rows`)
  - Schema drift detection (flags unexpected extra columns)
- Structured results return overall status (`passed`, `failed`, `warning`), failed counts, bounded sample failures (max 10 rows), and actionable remediation guidance.

### 3.3 Statistical Profiling & Quality Scoring (`dataflow.services.profiling`, `dataflow.services.quality`)
- **Profiling**: Row counts, column counts, duplicate row metrics, overall missingness, column-level detected types, distinct values, null counts, numeric min/max/mean/median/std, string lengths, common categorical distributions, and constant column detection.
- **Deterministic Quality Scoring (0 - 100)**:
  - **Completeness (35 pts)**: Deductions based on missing cells ratio.
  - **Uniqueness (25 pts)**: Deductions based on duplicate row ratio.
  - **Consistency & Empty Columns (20 pts)**: Penalties for empty columns and unexpected constant columns.
  - **String Hygiene (20 pts)**: Penalties for leading/trailing whitespaces and unnormalized text.
  - **Rating Tiers**: `excellent` (>=90), `good` (>=75), `fair` (>=50), `poor` (<50).

### 3.4 Safe Transformations & Immutable Versioning (`dataflow.services.transformation`, `dataflow.services.lineage`)
- Operations supported:
  - `rename_columns`, `select_columns`, `drop_columns`
  - `remove_duplicates`
  - `fill_missing` (constant, mean, median, mode, forward fill)
  - `cast_columns` (`int`, `float`, `str`, `bool`, `datetime`)
  - `filter_rows` (`eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `is_not_null`, `contains`)
  - `sort_rows`
  - `trim_strings`
  - `convert_dates`
- **Security**: Strictly no `eval`, shell execution, or arbitrary SQL.
- **Immutability**: Source versions are NEVER modified in place. Transformations generate a new `DatasetVersion` (`version_number` incremented, `parent_version_id` linked, SHA-256 computed, audit logged).
- **Lineage Diff**: Compares version A and version B with row/column deltas, added/removed columns, and schema type alterations.

### 3.5 Processing Telemetry and Audit Trails (`dataflow.services.audit`)
- Synchronous and background operations emit structured `ProcessingJob` records tracking execution state (`pending`, `running`, `succeeded`, `failed`, `retried`, `interrupted`) with progress and millisecond-accurate duration telemetry.
- Self-healing startup: `reconcile_stale_jobs()` identifies dangling running jobs upon application restart and marks them `interrupted` with `process_crash` classification.
- Immutable `AuditEvent` log records all user mutations, uploads, transformations, contract runs, downloads, and failures with timestamps, entity IDs, and diagnostic details.

### 3.6 Idempotent Ingestion Architecture (`dataflow.services.ingestion`)
- Streaming SHA-256 computation uniquely fingerprints the binary content of uploads.
- When `deduplicate_identical=True` (default), uploads matching the existing latest checksum return the existing `DatasetVersion` without creating duplicate storage artifacts or redundant version rows.
- Concurrency protection: on PostgreSQL, version assignment acquires an exclusive row lock (`with_for_update()`) on the parent `Dataset`, preventing duplicate version number allocation during simultaneous uploads.

### 3.7 Bounded Retries & Error Classification (`dataflow.services.retry`)
- Unified error classifier (`classify_exception`) partitions exceptions into:
  - **Transient Errors**: Network timeouts, connection resets, database lock conflicts, HTTP 429 rate limits, and 502/503/504 upstream outages.
  - **Permanent Errors**: Syntax errors, schema mismatches, contract violations, missing files, and HTTP 400/401/403/404/422 responses.
- `execute_with_retry()` applies exponential backoff ($factor \times 2^{attempt-1}$) bounded by `RETRY_MAX_BACKOFF_SECONDS` with optional uniform jitter.
- Permanent errors fail immediately without exhausting retries.

### 3.8 Validation Quarantine & Rejection Persistence (`dataflow.services.validation`)
- When a data contract runs on a version, rows failing any rule are flagged and extracted into a dedicated **quarantine CSV** dataset.
- Conforming rows are written to a **clean CSV** dataset.
- Row-level diagnostics are persisted in `validation_rejections`:
  - `row_number` (source row position)
  - `failure_reasons` (array of failing column names, rule types, and error descriptions)
  - `raw_data` (JSON snapshot of the invalid record for audit diagnosis)
- Clean and quarantine files are downloadable via dedicated API endpoints.

### 3.9 REST API Ingestion & Incremental Watermarks (`dataflow.services.rest_ingestion`)
- **SSRF Safe**: Validates URL protocols (only `http`/`https`) and denies private/loopback host access unless explicitly overridden.
- **Pagination**: Supports both page-based and offset-based pagination bounded by `max_pages`.
- **Atomic Checkpoints**:
  - `IngestionCheckpoint` persists `(source_identifier, dataset_id, cursor_column, watermark_value, records_extracted)`.
  - Watermark advancement is committed within the exact same database transaction as the dataset version creation.
  - Interrupted or failed runs abort the transaction, guaranteeing that the watermark is never advanced past uncommitted data.

### 3.10 Proportionate API Authentication (`dataflow.api.deps`)
- Optional static API key authentication via `X-API-Key` header.
- Verification uses `secrets.compare_digest` for constant-time comparison.
- Fails closed with `HTTP 500` if `AUTH_ENABLED=True` and server secret is missing.
- Health checks (`/api/v1/health`, `/live`, `/ready`) remain public for orchestration probes.
