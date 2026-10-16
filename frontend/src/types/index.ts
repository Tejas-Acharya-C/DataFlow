/**
 * TypeScript types for DataFlow API contracts.
 */

export interface SchemaField {
  name: string;
  type: string;
  nullable: boolean;
}

export interface DatasetVersion {
  id: string;
  dataset_id: string;
  version_number: number;
  storage_path: string;
  original_filename: string;
  file_size_bytes: number;
  checksum: string;
  row_count: number;
  column_count: number;
  schema_json: SchemaField[];
  parent_version_id?: string | null;
  creation_reason: string;
  transformation_details?: Record<string, any> | null;
  created_at: string;
}

export interface Dataset {
  id: string;
  name: string;
  description?: string | null;
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
  latest_version?: DatasetVersion | null;
  version_count: number;
}

export interface DatasetDetail extends Dataset {
  versions: DatasetVersion[];
}

export interface DatasetPreview {
  dataset_id: string;
  version_id: string;
  version_number: number;
  columns: string[];
  rows: Record<string, any>[];
  total_preview_rows: number;
  total_rows: number;
}

export interface VersionCompareResult {
  version_a_number: number;
  version_b_number: number;
  row_count_delta: number;
  column_count_delta: number;
  columns_added: string[];
  columns_removed: string[];
  columns_retained: string[];
  schema_changes: Array<{
    column: string;
    change: string;
    old_type?: string;
    new_type?: string;
    type?: string;
  }>;
}

export interface ContractRules {
  required_columns?: string[];
  column_types?: Record<string, string>;
  nullable_columns?: Record<string, boolean>;
  unique_columns?: string[];
  allowed_values?: Record<string, any[]>;
  numeric_ranges?: Record<string, { min?: number; max?: number }>;
  string_lengths?: Record<string, { min_len?: number; max_len?: number }>;
  date_formats?: Record<string, string>;
  min_rows?: number;
  max_rows?: number;
  disallow_schema_drift?: boolean;
}

export interface DataContract {
  id: string;
  name: string;
  description?: string | null;
  version: number;
  rules_json: ContractRules;
  created_at: string;
  updated_at: string;
}

export interface ValidationCheck {
  name: string;
  category: string;
  status: 'passed' | 'failed' | 'warning';
  severity: 'error' | 'warning';
  message: string;
  affected_column?: string | null;
  failed_count: number;
  failure_rate: number;
  sample_failures: any[];
  recommendation?: string | null;
}

export interface ValidationRun {
  id: string;
  dataset_id: string;
  version_id: string;
  contract_id: string;
  status: 'passed' | 'failed' | 'warning';
  passed_count: number;
  failed_count: number;
  results_json: {
    contract_name?: string;
    overall_status: string;
    passed_count: number;
    failed_count: number;
    checks: ValidationCheck[];
  };
  executed_at: string;
}

export interface ColumnProfile {
  name: string;
  detected_type: string;
  total_count: number;
  null_count: number;
  null_percentage: number;
  distinct_count: number;
  uniqueness_percentage: number;
  is_constant: boolean;
  numeric_min?: number | null;
  numeric_max?: number | null;
  numeric_mean?: number | null;
  numeric_median?: number | null;
  numeric_std?: number | null;
  string_min_length?: number | null;
  string_max_length?: number | null;
  string_avg_length?: number | null;
  top_values: Array<{ value: string; count: number; percentage: number }>;
  min_date?: string | null;
  max_date?: string | null;
}

export interface ProfilingResult {
  id: string;
  dataset_id: string;
  version_id: string;
  summary_json: {
    row_count: number;
    column_count: number;
    total_cells: number;
    total_missing_cells: number;
    missing_cells_percentage: number;
    duplicate_rows_count: number;
    duplicate_rows_percentage: number;
  };
  columns_json: Record<string, ColumnProfile>;
  created_at: string;
}

export interface QualityCheckItem {
  name: string;
  category: string;
  status: 'passed' | 'failed' | 'warning';
  score_impact: number;
  message: string;
  affected_column?: string | null;
  failure_rate: number;
  recommendation?: string | null;
}

export interface QualityResult {
  id: string;
  dataset_id: string;
  version_id: string;
  score: number;
  status: 'excellent' | 'good' | 'fair' | 'poor';
  summary: string;
  checks_json: {
    checks: QualityCheckItem[];
  };
  recommendations_json: string[];
  created_at: string;
}

export interface ProcessingJob {
  id: string;
  job_type: string;
  dataset_id?: string | null;
  version_id?: string | null;
  status: 'pending' | 'running' | 'succeeded' | 'failed';
  progress: number;
  error_message?: string | null;
  metadata_json?: Record<string, any> | null;
  created_at: string;
  finished_at?: string | null;
}

export interface AuditEvent {
  id: string;
  event_type: string;
  entity_type: string;
  entity_id: string;
  dataset_id?: string | null;
  version_id?: string | null;
  outcome: string;
  details_json?: Record<string, any> | null;
  created_at: string;
}

export interface SystemHealth {
  status: string;
  database: string;
  storage: string;
  version: string;
  environment: string;
}
