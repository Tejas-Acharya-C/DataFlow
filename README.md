# DataFlow — Intelligent Data Reliability Platform

DataFlow is an engineering-grade data reliability platform for ingesting, validating, profiling, transforming, versioning, and managing datasets with strict deterministic quality controls, bounded retries, row-level quarantine persistence, and incremental watermark checkpointing.

Built as a **modular monolith** with FastAPI, SQLAlchemy 2.x, PostgreSQL/SQLite, Alembic, and React + TypeScript (Vite).

---

## 1. Key Platform Capabilities

- **Multi-Source Ingestion**:
  - **Streaming CSV**: Safe upload processing with size enforcement (50MB default limit), streaming SHA-256 content-addressable checksumming, path-traversal prevention, duplicate header checks, and automatic schema inference.
  - **External REST API**: Extraction from REST endpoints with SSRF prevention, configurable pagination (page/offset), rate limit handling (429 backoff), and bounded retries.
  - **Idempotent Ingestion**: Content-addressable SHA-256 deduplication on upload prevents duplicate version creation while preserving audit telemetry.
- **Incremental Watermarks & Checkpoints**:
  - Tracks extraction watermarks in `IngestionCheckpoint` records.
  - Checkpoints advance **only after** dataset persistence commits successfully in the database transaction, preventing skipped records upon partial failure.
- **Bounded Retries & Error Classification**:
  - Distinguishes **transient** errors (connection drops, lock timeouts, 429 rate limits, 502/503 upstream errors) from **permanent** errors (schema violations, syntax errors, 400/401/403/404).
  - Configurable exponential backoff with ceiling bounds and jitter; permanent errors fail immediately without burning retries.
- **Validation, Quarantine & Row-Level Rejection Persistence**:
  - Evaluates declarative data contracts against dataset versions.
  - Automatically partitions mixed-quality inputs into **clean** and **quarantine** CSV datasets.
  - Persists individual `ValidationRejection` records with row index, failing column, rejected value, and detailed error codes.
  - Dedicated endpoints for paginated rejection review and clean/quarantine file downloads.
- **Safe API Authentication**:
  - Optional API key authentication via `X-API-Key` header with constant-time comparison (`secrets.compare_digest`).
  - Fails safely (500) if auth is enabled without an configured key.
  - Health checks (`/api/v1/health`, `/live`, `/ready`) remain unconditionally accessible.
- **Statistical Profiling & Deterministic Quality Scoring**:
  - Deep column-level profiling (null ratios, distinct counts, distributions, string lengths).
  - 0–100 deterministic quality score with penalty breakdowns across completeness, uniqueness, consistency, and string hygiene.
- **Safe Transformations & Version Lineage**:
  - Injection-proof, parameterized transformations (`rename_columns`, `select_columns`, `drop_columns`, `remove_duplicates`, `fill_missing`, `cast_columns`, `filter_rows`, `sort_rows`, `trim_strings`, `convert_dates`) with dry-run preview before commit.
  - Row locking (`with_for_update()`) on PostgreSQL prevents conflicting version numbers under concurrency.
- **Audit Trails & Self-Healing Telemetry**:
  - Tracked `ProcessingJob` lifecycle (`pending`, `running`, `succeeded`, `failed`, `retried`, `interrupted`) with execution duration in milliseconds.
  - FastAPI lifespan auto-reconciles stale dangling jobs to `interrupted` upon server restart.
- **Modern Responsive Web Interface**:
  - Sleek dark-mode interface with live operational metrics, interactive dataset preview, guided transformation builder, and rejection download links.

---

## 2. Architecture & Data Flow

```text
┌───────────────────────┐       ┌───────────────────────┐
│ External REST API /   │       │   CSV File Uploads    │
│ Webhook Feeds         │       │   (Web UI / API)      │
└──────────┬────────────┘       └───────────┬───────────┘
           │                                │
           ▼                                ▼
┌────────────────────────────────────────────────────────┐
│             DataFlow Ingestion Layer                   │
│  - SSRF Verification & Protocol Validation             │
│  - Streaming SHA-256 Checksum Calculation              │
│  - Content Deduplication Check (Idempotency)           │
│  - In-Memory Sample Schema & Header Validation         │
└──────────────────────────┬─────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│              LocalStorageManager                       │
│  - Path-traversal proof storage root                   │
│  - Partitioned directory layout: datasets/{id}/{v}.csv │
└──────────────────────────┬─────────────────────────────┘
                           │
       ┌───────────────────┴───────────────────┐
       ▼                                       ▼
┌──────────────────────────────┐    ┌──────────────────────────────┐
│     Contract Validation      │    │    Statistical Profiling     │
│  - Evaluates ContractRules   │    │  - Column distributions      │
│  - Partitions Clean / Quaran │    │  - Uniqueness & null rates   │
│  - Stores ValidationRejection│    │  - Deterministic 0-100 Score │
└──────────────┬───────────────┘    └──────────────┬───────────────┘
               │                                   │
               ▼                                   ▼
┌────────────────────────────────────────────────────────┐
│           PostgreSQL / SQLite Database                 │
│  - Datasets & Immutable Versions (Row locked)          │
│  - DataContracts & ValidationRuns                      │
│  - ValidationRejections (Row-level quarantine details) │
│  - IngestionCheckpoints (Watermarks & Cursors)         │
│  - ProcessingJobs & Immutable AuditEvents              │
└────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

- **Backend**: Python 3.11, FastAPI, Pydantic v2, Pydantic Settings, SQLAlchemy 2.x, Alembic, psycopg 3, Pandas, HTTPX, Pytest, Ruff.
- **Frontend**: React 19, TypeScript, Vite, Lucide Icons, Vanilla CSS Design System.
- **Database & Storage**: PostgreSQL 16/17 (Docker/Production) or SQLite (Local unit testing), local hashed storage directory.
- **CI/CD**: GitHub Actions workflow running Ruff linting, Pytest test suite with live PostgreSQL service, and Vite frontend production build.

---

## 4. Setup & Running Locally

All commands below are executed from PowerShell in the project workspace:

### 4.1 Environment Setup
```powershell
# 1. Activate Virtual Environment
.\.venv\Scripts\Activate.ps1

# 2. Install backend dependencies in editable mode
pip install -e ".[dev]"

# 3. Configure environment file
Copy-Item .env.example .env
```

### 4.2 Start PostgreSQL & Run Migrations
```powershell
# Start local PostgreSQL container (mapped to host port 55432)
docker compose up -d

# Apply Alembic schema migrations
alembic upgrade head
```

### 4.3 Start Backend Dev Server
```powershell
uvicorn dataflow.main:app --host 127.0.0.1 --port 8000 --reload
```
- Interactive API Docs (Swagger): `http://127.0.0.1:8000/docs`
- Health Probe (Liveness): `http://127.0.0.1:8000/api/v1/health/live`
- Health Probe (Readiness): `http://127.0.0.1:8000/api/v1/health/ready`

### 4.4 Start Frontend Dev Server
```powershell
cd frontend
npm install
npm run dev
```
- Web Application: `http://localhost:5173`

---

## 5. Security & Authentication Setup

Authentication is disabled by default for zero-friction local development (`AUTH_ENABLED=False`). To secure your API:

In `.env`:
```env
AUTH_ENABLED=True
DATAFLOW_API_KEY=your-secure-random-token-here
```

When enabled:
- All mutative operations and dataset access require the header:
  `X-API-Key: your-secure-random-token-here`
- Verification uses constant-time comparison (`secrets.compare_digest`) to prevent timing attacks.
- If `AUTH_ENABLED=True` and `DATAFLOW_API_KEY` is not set, requests safely return `500 Internal Server Error` without leaking keys.
- Health checks (`/api/v1/health/live`, `/api/v1/health/ready`) remain unauthenticated so orchestration probes (Kubernetes/Docker) continue working.

---

## 6. Testing & CI Pipeline

The project maintains comprehensive regression and integration testing across unit, API, concurrency, and live database suites.

### Run All Automated Tests
```powershell
pytest -v
```

### Run Live PostgreSQL Integration Test Explicitly
```powershell
$env:REQUIRE_POSTGRES_TEST="1"
$env:DATAFLOW_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:55432/dataflow"
pytest tests/integration/test_postgres_live_integration.py -v
```

### Run Linter
```powershell
ruff check src tests
```

### Build Frontend
```powershell
cd frontend
npm run build
```

---

## 7. Performance Benchmarks

DataFlow features a reproducible performance benchmarking suite measuring streaming ingestion, column profiling, deterministic quality scoring, and contract validation with quarantine partitioning.

To run the benchmark locally:
```powershell
python scripts/benchmark.py
```

### Actual Benchmark Measurements (Windows 10 AMD64, Python 3.11, PostgreSQL)

| Dataset Size | File Size | Ingestion Time | Ingestion Throughput | Validation & Quarantine | Total Pipeline Time | Accepted Rows | Rejected Rows |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **10,000 rows** | 0.37 MB | 0.121s | **82,960 rows/s** (3.06 MB/s) | 0.288s (34,698 rows/s) | 0.542s | 9,500 | 500 |
| **100,000 rows** | 3.88 MB | 0.156s | **643,048 rows/s** (24.93 MB/s) | 2.093s (47,777 rows/s) | 2.930s | 95,000 | 5,000 |

Detailed breakdowns, methodology, and an explanation of why a dataset can achieve a **100.0 structural quality score while having rows rejected by business contracts** are documented in [docs/benchmarks.md](docs/benchmarks.md).

---

## 8. Reliability Guarantees & Known Limitations

### What DataFlow Guarantees:
1. **Idempotent Ingestion**: Repeated uploads of the exact same content will not create duplicate version records or duplicate storage artifacts when `deduplicate_identical=True`.
2. **Atomic Incremental Checkpoints**: An `IngestionCheckpoint` will only advance if the newly fetched batch and version commit successfully to the database. If extraction or validation crashes midway, the watermark remains at the last committed position.
3. **Partitioned Quarantine**: When validating mixed data, clean records and invalid records are partitioned into separate downloadable CSVs with individual row failure reasons preserved in `validation_rejections`.
4. **Transient Fault Recovery**: Network glitches and temporary database locks retry automatically using exponential backoff with jitter up to `MAX_RETRIES`. Permanent errors abort immediately.
5. **No Conflicting Versions**: On PostgreSQL, version allocations use `with_for_update()` row locks, ensuring strictly monotonic sequential versions.

### Intentionally Deferred Features:
1. **Distributed Celery/Kafka Workers**: DataFlow is architected as an agile modular monolith suitable for single-node deployment up to millions of records. Distributed worker clusters are deferred.
2. **Streaming Kafka/Pulsar Sources**: Current ingestion supports streaming CSV file uploads and REST APIs with incremental cursors. Real-time event log ingestion is outside current portfolio MVP scope.
