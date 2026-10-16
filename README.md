# DataFlow — Data Reliability Platform

DataFlow is an engineering-grade data reliability platform for safely ingesting, validating, profiling, transforming, versioning, and managing CSV datasets with strict deterministic quality controls.

Built as a **modular monolith** with FastAPI, SQLAlchemy 2.x, PostgreSQL/SQLite, Alembic, and React + TypeScript (Vite).

---

## 1. Key Features

- **CSV Ingestion & Storage**: Safe upload processing with size enforcement (50MB default limit), streaming SHA-256 checksum calculation, path-traversal prevention, header verification, and automatic schema inference.
- **Declarative Data Contracts**: Reusable schema contracts enforcing required columns, expected types, nullability, uniqueness, allowed categorical sets, numeric ranges, and schema drift prevention.
- **Statistical Profiling**: Automated dataset and column-level metrics including null ratios, distinct counts, uniqueness percentages, numeric min/max/mean/median/std, string lengths, top categorical frequencies, and constant-column detection.
- **Deterministic Quality Scoring (0–100)**: Transparent, reproducible quality evaluation with check breakdowns, penalty scoring across completeness, uniqueness, consistency, and string hygiene, accompanied by actionable remediation recommendations.
- **Safe Transformations**: Constrained, injection-proof dataframe transformations (`rename_columns`, `select_columns`, `drop_columns`, `remove_duplicates`, `fill_missing`, `cast_columns`, `filter_rows`, `sort_rows`, `trim_strings`, `convert_dates`) with preview support before commit.
- **Immutable Dataset Versions & Lineage**: Every transformation produces a new version without mutating existing artifacts, maintaining parent version linkages, cryptographic checksums, and version comparison diffs.
- **Audit Trails & Execution Telemetry**: Transparent `ProcessingJob` tracking and compliance `AuditEvent` logging for uploads, validations, transformations, downloads, and failures.
- **Modern Responsive Web Interface**: Sleek dark-mode interface with live operational metrics, interactive dataset preview, guided transformation builder, and audit inspectors.

---

## 2. Technology Stack

- **Backend**: Python 3.11, FastAPI, Pydantic v2, Pydantic Settings, SQLAlchemy 2.x, Alembic, psycopg 3, Pandas, Pytest, HTTPX, Ruff.
- **Frontend**: React 19, TypeScript, Vite, Lucide Icons, Vanilla CSS Design System.
- **Database & Storage**: PostgreSQL 16/17 (production/Docker) or SQLite (offline/local development & unit testing), local hashed storage directory.
- **CI/CD**: GitHub Actions workflow running Ruff linting, Pytest test suite, and Vite frontend production build.

---

## 3. Project Structure

```text
DataFlow/
├── src/
│   └── dataflow/
│       ├── main.py                  # FastAPI application entrypoint & lifespan
│       ├── config.py                # Pydantic Settings centralized configuration
│       ├── api/
│       │   ├── router.py            # Master /api/v1 router aggregation
│       │   ├── deps.py              # Dependency injection providers
│       │   └── endpoints/           # Modular route controllers
│       ├── db/
│       │   ├── base.py              # SQLAlchemy 2.0 DeclarativeBase
│       │   └── session.py           # Engine & Session factory
│       ├── models/                  # SQLAlchemy 2.0 database models
│       ├── schemas/                 # Pydantic request & response validation schemas
│       ├── services/                # Core business logic services
│       └── storage/                 # Local filesystem storage manager with safety checks
├── frontend/                        # React + TypeScript Vite web application
├── migrations/                      # Alembic migration scripts
├── tests/                           # Pytest unit, api, and integration test suite
├── docs/                            # Architecture and design documentation
├── .github/workflows/               # GitHub Actions CI workflow
├── pyproject.toml                   # Project packaging & dependencies
├── alembic.ini                      # Alembic migration configuration
├── docker-compose.yml               # Containerized PostgreSQL service
├── .env.example                     # Environment template with sensible defaults
└── README.md
```

---

## 4. Windows Development Setup & PowerShell Commands

All commands below are run from PowerShell in the workspace root: `E:\Python\Python projects\DataFlow`.

### 4.1 Activate Python Virtual Environment
```powershell
.\.venv\Scripts\Activate.ps1
```

### 4.2 Install Backend Dependencies
```powershell
.\.venv\Scripts\pip.exe install -e ".[dev]"
```

### 4.3 Install Frontend Dependencies
```powershell
Set-Location frontend
npm install
Set-Location ..
```

### 4.4 Configure Environment Variables
Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

For local testing or offline development, SQLite is automatically supported by setting:
```env
DATAFLOW_DATABASE_URL=sqlite:///./dataflow.db
```
For PostgreSQL (e.g. running locally or via Docker):
```env
DATAFLOW_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/dataflow
```

### 4.5 Run Database Migrations
```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

### 4.6 Start PostgreSQL via Docker Compose (Optional)
```powershell
docker compose up -d
```
*(PostgreSQL will be exposed on port `55432` to avoid conflicting with existing port `5432` services).*

### 4.7 Start the Backend Dev Server
```powershell
.\.venv\Scripts\uvicorn.exe dataflow.main:app --host 127.0.0.1 --port 8000 --reload
```
- API Documentation (Swagger): `http://127.0.0.1:8000/docs`
- Health Live Probe: `http://127.0.0.1:8000/api/v1/health/live`
- Health Ready Probe: `http://127.0.0.1:8000/api/v1/health/ready`

### 4.8 Start the Frontend Dev Server
In a separate terminal:
```powershell
Set-Location frontend
npm run dev
```
- Web Application: `http://localhost:5173`

### 4.9 Run Backend Automated Tests
```powershell
.\.venv\Scripts\pytest.exe -v
```

### 4.10 Run Lint Checks
```powershell
.\.venv\Scripts\ruff.exe check src tests
```

### 4.11 Build Frontend Production Bundle
```powershell
Set-Location frontend
npm run build
Set-Location ..
```

---

## 5. Security & Data Integrity

1. **Path Traversal Protection**: All storage artifact access paths are verified using strict path resolution against `DATAFLOW_STORAGE_ROOT`. Attempts to escape the directory via `../` raise `PathTraversalError`.
2. **Safe Transformations**: All dataframe manipulation uses explicit, parameterized operations. Arbitrary code evaluation (`eval`), shell commands, and raw string SQL are strictly disallowed.
3. **Immutability Guarantee**: Existing CSV versions are never modified in place. Any transformation operation generates a new version with its own SHA-256 hash, lineage tracking, and audit event.
4. **Data Privacy**: Audit events record metadata, operation counts, and IDs; full dataset contents or sensitive credentials are never written to audit logs.
