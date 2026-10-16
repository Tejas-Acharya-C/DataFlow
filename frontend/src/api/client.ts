/**
 * Centralized API client for DataFlow platform.
 */

import {
  Dataset,
  DatasetDetail,
  DatasetPreview,
  DatasetVersion,
  VersionCompareResult,
  DataContract,
  ValidationRun,
  ProfilingResult,
  QualityResult,
  ProcessingJob,
  AuditEvent,
  SystemHealth,
} from '../types';

const API_BASE = '/api/v1';

let currentApiKey: string | null =
  typeof window !== 'undefined' ? localStorage.getItem('dataflow_api_key') : null;

export function setApiKey(key: string | null): void {
  currentApiKey = key;
  if (typeof window !== 'undefined') {
    if (key) {
      localStorage.setItem('dataflow_api_key', key);
    } else {
      localStorage.removeItem('dataflow_api_key');
    }
  }
}

export function getApiKey(): string | null {
  return currentApiKey;
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers: Record<string, string> = {
    Accept: 'application/json',
    ...((options.headers as Record<string, string>) || {}),
  };

  if (currentApiKey) {
    headers['X-API-Key'] = currentApiKey;
  }

  const response = await fetch(url, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errorJson = await response.json();
      errorDetail = errorJson.detail || errorDetail;
    } catch {
      // ignore json parse error
    }
    throw new Error(errorDetail);
  }

  return response.json();
}

export const api = {
  // Health
  getHealth: (): Promise<SystemHealth> => request<SystemHealth>('/health/ready'),

  // Datasets
  getDatasets: (skip = 0, limit = 50, search?: string): Promise<{ items: Dataset[]; total: number }> => {
    const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (search) params.append('search', search);
    return request<{ items: Dataset[]; total: number }>(`/datasets?${params.toString()}`);
  },

  getDataset: (id: string): Promise<DatasetDetail> => request<DatasetDetail>(`/datasets/${id}`),

  uploadDataset: async (
    file: File,
    name?: string,
    description?: string,
    datasetId?: string
  ): Promise<DatasetDetail> => {
    const formData = new FormData();
    formData.append('file', file);
    if (name) formData.append('name', name);
    if (description) formData.append('description', description);
    if (datasetId) formData.append('dataset_id', datasetId);

    const response = await fetch(`${API_BASE}/datasets/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || 'Failed to upload CSV dataset');
    }

    return response.json();
  },

  previewDataset: (datasetId: string, versionId?: string, maxRows = 50): Promise<DatasetPreview> => {
    const params = new URLSearchParams({ max_rows: String(maxRows) });
    if (versionId) params.append('version_id', versionId);
    return request<DatasetPreview>(`/datasets/${datasetId}/preview?${params.toString()}`);
  },

  deleteDataset: (id: string): Promise<{ message: string; id: string }> =>
    request<{ message: string; id: string }>(`/datasets/${id}`, { method: 'DELETE' }),

  getDownloadUrl: (datasetId: string, versionId?: string) => {
    return versionId
      ? `${API_BASE}/versions/${versionId}/download`
      : `${API_BASE}/datasets/${datasetId}/download`;
  },

  // Versions
  getVersions: (datasetId: string): Promise<DatasetVersion[]> =>
    request<DatasetVersion[]>(`/versions/dataset/${datasetId}`),

  compareVersions: (versionAId: string, versionBId: string): Promise<VersionCompareResult> =>
    request<VersionCompareResult>('/versions/compare', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version_a_id: versionAId, version_b_id: versionBId }),
    }),

  // Contracts
  getContracts: (): Promise<DataContract[]> => request<DataContract[]>('/contracts'),

  createContract: (data: { name: string; description?: string; rules: any }): Promise<DataContract> =>
    request<DataContract>('/contracts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  updateContract: (id: string, data: { description?: string; rules?: any }): Promise<DataContract> =>
    request<DataContract>(`/contracts/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    }),

  deleteContract: (id: string): Promise<{ message: string }> =>
    request<{ message: string }>(`/contracts/${id}`, { method: 'DELETE' }),

  validateContract: (contractId: string, versionId: string): Promise<ValidationRun> =>
    request<ValidationRun>(`/contracts/${contractId}/validate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ version_id: versionId }),
    }),

  getValidations: (params: { datasetId?: string; versionId?: string; contractId?: string }): Promise<ValidationRun[]> => {
    const qs = new URLSearchParams();
    if (params.datasetId) qs.append('dataset_id', params.datasetId);
    if (params.versionId) qs.append('version_id', params.versionId);
    if (params.contractId) qs.append('contract_id', params.contractId);
    return request<ValidationRun[]>(`/validations?${qs.toString()}`);
  },

  // Profiling
  getProfiling: (versionId: string): Promise<ProfilingResult> =>
    request<ProfilingResult>(`/profiling/${versionId}`),

  runProfiling: (versionId: string): Promise<ProfilingResult> =>
    request<ProfilingResult>(`/profiling/${versionId}`, { method: 'POST' }),

  // Quality
  getQuality: (versionId: string): Promise<QualityResult> =>
    request<QualityResult>(`/quality/${versionId}`),

  evaluateQuality: (versionId: string): Promise<QualityResult> =>
    request<QualityResult>(`/quality/${versionId}`, { method: 'POST' }),

  // Transformations
  previewTransformation: (payload: { dataset_id: string; version_id: string; operations: any[] }) =>
    request<any>('/transformations/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  applyTransformation: (payload: {
    dataset_id: string;
    version_id: string;
    operations: any[];
    reason?: string;
  }) =>
    request<any>('/transformations/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),

  // Jobs & Audit
  getJobs: (status?: string): Promise<{ items: ProcessingJob[]; total: number }> => {
    const qs = status ? `?status=${status}` : '';
    return request<{ items: ProcessingJob[]; total: number }>(`/jobs${qs}`);
  },

  getAuditEvents: (skip = 0, limit = 50, datasetId?: string): Promise<{ items: AuditEvent[]; total: number }> => {
    const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (datasetId) params.append('dataset_id', datasetId);
    return request<{ items: AuditEvent[]; total: number }>(`/audit?${params.toString()}`);
  },

  // Validation Rejections & Quarantine
  getValidationRejections: (
    validationId: string,
    skip = 0,
    limit = 50,
    errorCode?: string
  ): Promise<{ items: any[]; total: number }> => {
    const params = new URLSearchParams({ skip: String(skip), limit: String(limit) });
    if (errorCode) params.append('error_code', errorCode);
    return request<{ items: any[]; total: number }>(`/contracts/validations/${validationId}/rejections?${params.toString()}`);
  },

  getQuarantineDownloadUrl: (validationId: string): string =>
    `${API_BASE}/contracts/validations/${validationId}/quarantine/download`,

  getCleanDownloadUrl: (validationId: string): string =>
    `${API_BASE}/contracts/validations/${validationId}/clean/download`,

  // Sources & Checkpoints
  ingestRestSource: (config: any): Promise<any> =>
    request<any>('/sources/rest/ingest', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config),
    }),

  getCheckpoints: (datasetId?: string): Promise<any[]> => {
    const qs = datasetId ? `?dataset_id=${datasetId}` : '';
    return request<any[]>(`/sources/checkpoints${qs}`);
  },
};
