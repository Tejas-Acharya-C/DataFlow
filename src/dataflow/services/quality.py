"""Data quality evaluation service with deterministic scoring."""

from typing import List, Optional

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from dataflow.models.dataset import DatasetVersion
from dataflow.models.profiling import QualityResult
from dataflow.schemas.quality import QualityCheckItem
from dataflow.services.audit import complete_job, create_job, log_audit
from dataflow.storage.local import LocalStorageManager


class QualityService:
    """Evaluates multi-dimensional data quality and calculates deterministic score."""

    def __init__(self, storage: Optional[LocalStorageManager] = None):
        self.storage = storage or LocalStorageManager()

    def evaluate_version(self, db: Session, version: DatasetVersion) -> QualityResult:
        """Calculate deterministic 0-100 data quality score with check breakdown."""
        job = create_job(
            db,
            job_type="quality_evaluation",
            dataset_id=version.dataset_id,
            version_id=version.id,
        )

        try:
            df = self.storage.load_dataframe(version.storage_path)
            row_count = len(df)
            col_count = len(df.columns)
            total_cells = row_count * col_count

            checks: List[QualityCheckItem] = []
            recommendations: List[str] = []

            # Starting score 100
            score = 100.0

            # --- Dimension 1: Completeness (Weight 35) ---
            missing_cells = int(df.isna().sum().sum())
            missing_rate = (missing_cells / total_cells) if total_cells > 0 else 0.0
            completeness_deduction = round(min(35.0, missing_rate * 70.0), 2)  # up to 35 pts
            score -= completeness_deduction

            if missing_cells > 0:
                checks.append(
                    QualityCheckItem(
                        name="completeness",
                        category="completeness",
                        status="warning" if missing_rate < 0.1 else "failed",
                        score_impact=completeness_deduction,
                        message=f"{missing_cells} missing cells detected ({round(missing_rate * 100, 2)}% of dataset).",
                        failure_rate=round(missing_rate, 4),
                        recommendation="Use fill_missing or drop rows to handle missing data.",
                    )
                )
                recommendations.append(f"Resolve {missing_cells} missing values using fill_missing transformation.")
            else:
                checks.append(
                    QualityCheckItem(
                        name="completeness",
                        category="completeness",
                        status="passed",
                        score_impact=0.0,
                        message="Zero missing values detected across all columns.",
                    )
                )

            # --- Dimension 2: Uniqueness (Weight 25) ---
            dup_rows = int(df.duplicated().sum())
            dup_rate = (dup_rows / row_count) if row_count > 0 else 0.0
            uniqueness_deduction = round(min(25.0, dup_rate * 50.0), 2)
            score -= uniqueness_deduction

            if dup_rows > 0:
                checks.append(
                    QualityCheckItem(
                        name="duplicate_rows",
                        category="uniqueness",
                        status="warning" if dup_rate < 0.05 else "failed",
                        score_impact=uniqueness_deduction,
                        message=f"{dup_rows} duplicate rows detected ({round(dup_rate * 100, 2)}% of dataset).",
                        failure_rate=round(dup_rate, 4),
                        recommendation="Apply remove_duplicates transformation to eliminate redundant records.",
                    )
                )
                recommendations.append(f"Remove {dup_rows} duplicate rows using remove_duplicates transformation.")
            else:
                checks.append(
                    QualityCheckItem(
                        name="duplicate_rows",
                        category="uniqueness",
                        status="passed",
                        score_impact=0.0,
                        message="No duplicate rows found in dataset.",
                    )
                )

            # --- Dimension 3: Column consistency & empty columns (Weight 20) ---
            empty_cols = [c for c in df.columns if df[c].isna().all()]
            constant_cols = [c for c in df.columns if df[c].nunique(dropna=True) <= 1 and c not in empty_cols]

            col_deduction = 0.0
            if empty_cols:
                deduct = min(10.0, len(empty_cols) * 5.0)
                col_deduction += deduct
                checks.append(
                    QualityCheckItem(
                        name="empty_columns",
                        category="consistency",
                        status="failed",
                        score_impact=deduct,
                        message=f"Empty columns detected: {empty_cols}",
                        recommendation="Drop fully empty columns using drop_columns.",
                    )
                )
                recommendations.append(f"Drop completely empty columns: {', '.join(empty_cols)}.")

            if constant_cols:
                deduct = min(10.0, len(constant_cols) * 2.5)
                col_deduction += deduct
                checks.append(
                    QualityCheckItem(
                        name="constant_columns",
                        category="consistency",
                        status="warning",
                        score_impact=deduct,
                        message=f"Columns with single constant value: {constant_cols}",
                        recommendation="Review constant columns to verify if they carry meaningful variance.",
                    )
                )

            score -= col_deduction

            # --- Dimension 4: String hygiene & whitespaces (Weight 20) ---
            string_cols = [c for c in df.columns if pd.api.types.is_string_dtype(df[c]) or df[c].dtype == object]
            whitespace_issues = 0
            for sc in string_cols:
                non_null = df[sc].dropna().astype(str)
                untrimmed = (non_null != non_null.str.strip()).sum()
                if untrimmed > 0:
                    whitespace_issues += untrimmed

            if whitespace_issues > 0:
                ws_deduction = min(20.0, round((whitespace_issues / max(1, row_count)) * 10.0, 2))
                score -= ws_deduction
                checks.append(
                    QualityCheckItem(
                        name="string_whitespace_hygiene",
                        category="validity",
                        status="warning",
                        score_impact=ws_deduction,
                        message=f"{whitespace_issues} values have leading/trailing whitespaces.",
                        recommendation="Use trim_strings transformation to clean leading/trailing whitespace.",
                    )
                )
                recommendations.append("Apply trim_strings transformation to clean text formatting.")
            else:
                checks.append(
                    QualityCheckItem(
                        name="string_whitespace_hygiene",
                        category="validity",
                        status="passed",
                        score_impact=0.0,
                        message="All text fields are trimmed and normalized.",
                    )
                )

            # Clamp score 0.0 to 100.0
            final_score = round(max(0.0, min(100.0, score)), 1)

            if final_score >= 90.0:
                status = "excellent"
                summary = "Dataset has high reliability with minimal or no quality anomalies."
            elif final_score >= 75.0:
                status = "good"
                summary = "Dataset is in good shape with minor non-critical quality findings."
            elif final_score >= 50.0:
                status = "fair"
                summary = "Dataset requires moderate cleaning and transformation before downstream use."
            else:
                status = "poor"
                summary = "Dataset has severe data quality issues (high missingness, duplicates, or empty fields)."

            # Persist quality result
            existing = db.scalar(
                select(QualityResult).where(QualityResult.version_id == version.id)
            )
            if existing:
                existing.score = final_score
                existing.status = status
                existing.summary = summary
                existing.checks_json = {"checks": [c.model_dump() for c in checks]}
                existing.recommendations_json = recommendations
                quality_record = existing
            else:
                quality_record = QualityResult(
                    dataset_id=version.dataset_id,
                    version_id=version.id,
                    score=final_score,
                    status=status,
                    summary=summary,
                    checks_json={"checks": [c.model_dump() for c in checks]},
                    recommendations_json=recommendations,
                )
                db.add(quality_record)

            db.commit()
            db.refresh(quality_record)

            log_audit(
                db,
                event_type="quality.evaluated",
                entity_type="version",
                entity_id=version.id,
                dataset_id=version.dataset_id,
                version_id=version.id,
                details={"score": final_score, "status": status},
            )

            complete_job(db, job, status="succeeded")
            return quality_record

        except Exception as exc:
            db.rollback()
            complete_job(db, job, status="failed", error_message=str(exc))
            log_audit(
                db,
                event_type="quality.failed",
                entity_type="version",
                entity_id=version.id,
                outcome="failure",
                dataset_id=version.dataset_id,
                version_id=version.id,
                details={"error": str(exc)},
            )
            raise
