# DataFlow Pipeline Performance Benchmark

## Environment Specifications
- **OS**: Windows 10 (AMD64)
- **Python Version**: 3.11.9
- **Storage Engine**: LocalStorageManager (Streaming SHA-256 chunked I/O)
- **Database Engine**: PostgreSQL / SQLAlchemy
- **Benchmark Date**: 2026-10-16 12:50:41 UTC

## Benchmark Results Summary

| Dataset Size (Rows) | File Size | Ingestion Time | Ingestion Throughput | Validation & Quarantine | Total Pipeline Time | Accepted Rows | Rejected Rows | Quality Score |
|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| 10,000 | 0.37 MB | 0.121s | 82,960 rows/s (3.06 MB/s) | 0.288s (34,698 rows/s) | 0.542s | 9,500 | 500 | 100.0 |
| 100,000 | 3.88 MB | 0.156s | 643,048 rows/s (24.93 MB/s) | 2.093s (47,777 rows/s) | 2.93s | 95,000 | 5,000 | 100.0 |

## Stage Breakdown

| Dataset Size | Ingestion | Profiling | Quality Evaluation | Validation & Quarantine |
|:---:|:---:|:---:|:---:|:---:|
| 10,000 rows | 0.121s | 0.077s | 0.056s | 0.288s |
| 100,000 rows | 0.156s | 0.363s | 0.318s | 2.093s |

## Methodology & Guarantees
1. **Scope of Timings**: Ingestion timings measure end-to-end streaming file write, real-time SHA-256 checksumming, header validation, schema inference, and database transactional commit.
2. **Correctness Coupled with Speed**: Validation timings measure full contract rule checking, row-level error identification, quarantine CSV file creation, clean CSV file creation, and individual `ValidationRejection` database row persistence.
3. **Zero Secrets / Synthetic Data**: Generated data is completely synthetic containing simulated user identifiers, emails, ages, and statuses with a controlled 5% error rate.
4. **Reproducibility**: Run `python scripts/benchmark.py` to regenerate measurements.

## Understanding Quality Score (100.0) vs. Business-Rule Rejections (5% Rejection)

A vital architectural distinction in DataFlow is the operational separation between **unsupervised structural profiling quality scores** and **declarative business-rule contract validation**:

### 1. Structural Profiling Quality Score (`QualityService`)
- **Evaluation Target**: The syntactic and statistical health of the physical dataset artifact.
- **Core Dimensions**:
  - **Completeness**: Ratio of non-null cells across columns (detecting unparsed fields or truncated rows).
  - **Uniqueness**: Distinctness of primary keys and absence of duplicate row anomalies.
  - **Type Conformance**: Whether data types parse without physical corruption (e.g., numeric columns parse as valid floats/integers, dates parse without syntax errors).
  - **String Hygiene**: Checks for null-byte injections, trailing whitespace, or empty strings masquerading as data.
- **Why the Benchmark Dataset Scores 100.0**: In the benchmark, all 100,000 cells adhere to their expected physical representations (`id` is an integer, `email` is a valid string, `age` is an integer, `status` is a string). There are no corrupt characters, missing bytes, or unparseable fields. From a purely structural and statistical perspective, the file is 100% healthy.

### 2. Declarative Business-Rule Validation (`ValidationService`)
- **Evaluation Target**: Domain-specific organizational business rules declared inside a `DataContract`.
- **Contract Rules Evaluated**:
  - `age BETWEEN 18 AND 120`: Domain policy requiring users to be of legal age.
  - `status IN ('active', 'pending')`: Domain lifecycle state whitelist.
  - `email REGEX r'^[\w\.-]+@[\w\.-]+\.\w+$'`: Corporate email format verification.
- **Why 5,000 Rows (5%) Are Rejected**: The benchmark's synthetic data generator injects a controlled 5% error rate where rows contain underage values (e.g., `age: 15`) or unapproved lifecycle states (e.g., `status: 'banned'`).
- **Architectural Synergy**:
  - A row with `age: 15` is **structurally valid** (it is a valid integer `15`, perfectly non-null, and correctly encoded). It therefore receives a **100.0 structural quality score**.
  - However, because it violates the declared business contract rule (`age >= 18`), `ValidationService` deterministically intercepts it, routes it to the **quarantine CSV artifact**, and logs a persistent `ValidationRejection` with the rejection reason.

Structural profiling verifies that data is **syntactically intact and parsable**; declarative validation guarantees that data is **semantically compliant with business contracts**.