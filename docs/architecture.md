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
- Synchronous and background operations emit structured `ProcessingJob` records tracking execution state (`pending`, `running`, `succeeded`, `failed`) and progress.
- Immutable `AuditEvent` log records all user mutations, uploads, transformations, contract runs, downloads, and failures with timestamps, entity IDs, and diagnostic details.
