import React, { useEffect, useState } from 'react';
import {
  ArrowLeft,
  Database,
  Download,
  Upload,
  Play,
  Award,
  Layers,
  FileCode2,
  Table as TableIcon,
  BarChart2,
  CheckCircle2,
  AlertTriangle,
  History,
} from 'lucide-react';
import { api } from '../api/client';
import {
  DatasetDetail,
  DatasetVersion,
  DatasetPreview,
  ProfilingResult,
  QualityResult,
} from '../types';

interface DatasetDetailPageProps {
  datasetId: string;
  onBack: () => void;
  onNavigateToTransform: (datasetId: string, versionId: string) => void;
  onNavigateToContracts: () => void;
  onOpenUploadVersion: (datasetId: string) => void;
}

export const DatasetDetailPage: React.FC<DatasetDetailPageProps> = ({
  datasetId,
  onBack,
  onNavigateToTransform,
  onNavigateToContracts,
  onOpenUploadVersion,
}) => {
  const [dataset, setDataset] = useState<DatasetDetail | null>(null);
  const [selectedVersionId, setSelectedVersionId] = useState<string>('');
  const [preview, setPreview] = useState<DatasetPreview | null>(null);
  const [profiling, setProfiling] = useState<ProfilingResult | null>(null);
  const [quality, setQuality] = useState<QualityResult | null>(null);
  const [activeTab, setActiveTab] = useState<'preview' | 'schema' | 'quality' | 'versions'>('preview');
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);

  useEffect(() => {
    loadDataset();
  }, [datasetId]);

  useEffect(() => {
    if (selectedVersionId) {
      loadVersionData(selectedVersionId);
    }
  }, [selectedVersionId]);

  const loadDataset = async () => {
    setLoading(true);
    try {
      const data = await api.getDataset(datasetId);
      setDataset(data);
      if (data.versions.length > 0) {
        setSelectedVersionId(data.versions[0].id);
      }
    } catch (err) {
      console.error('Failed to load dataset:', err);
    } finally {
      setLoading(false);
    }
  };

  const loadVersionData = async (versionId: string) => {
    try {
      const [prevData, profData, qualData] = await Promise.all([
        api.previewDataset(datasetId, versionId, 30),
        api.getProfiling(versionId).catch(() => null),
        api.getQuality(versionId).catch(() => null),
      ]);
      setPreview(prevData);
      setProfiling(profData);
      setQuality(qualData);
    } catch (err) {
      console.error('Failed to load version details:', err);
    }
  };

  const handleRunProfiling = async () => {
    if (!selectedVersionId) return;
    setActionLoading(true);
    try {
      const res = await api.runProfiling(selectedVersionId);
      setProfiling(res);
      setActiveTab('quality');
    } catch (err: any) {
      alert(err.message || 'Profiling failed');
    } finally {
      setActionLoading(false);
    }
  };

  const handleEvaluateQuality = async () => {
    if (!selectedVersionId) return;
    setActionLoading(true);
    try {
      const res = await api.evaluateQuality(selectedVersionId);
      setQuality(res);
      setActiveTab('quality');
    } catch (err: any) {
      alert(err.message || 'Quality evaluation failed');
    } finally {
      setActionLoading(false);
    }
  };

  if (loading || !dataset) {
    return <div className="card empty-state">Loading dataset details...</div>;
  }

  const selectedVersion = dataset.versions.find((v) => v.id === selectedVersionId) || dataset.versions[0];

  return (
    <div>
      {/* Back button & Action Header */}
      <div style={{ marginBottom: '1.25rem' }}>
        <button
          onClick={onBack}
          className="btn btn-secondary btn-sm"
          style={{ marginBottom: '1rem' }}
        >
          <ArrowLeft size={14} /> Back to Datasets
        </button>

        <div className="page-header" style={{ marginBottom: '1rem' }}>
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
              <h1 className="page-title">{dataset.name}</h1>
              <span className="badge badge-purple">
                v{selectedVersion?.version_number || 1}
              </span>
            </div>
            <p className="page-subtitle">
              {dataset.description || 'No description provided.'}
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => onOpenUploadVersion(dataset.id)}
            >
              <Upload size={14} /> Upload New Version
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleRunProfiling}
              disabled={actionLoading}
            >
              <BarChart2 size={14} /> Profile Data
            </button>
            <button
              className="btn btn-secondary btn-sm"
              onClick={handleEvaluateQuality}
              disabled={actionLoading}
            >
              <Award size={14} /> Evaluate Quality
            </button>
            <button
              className="btn btn-primary btn-sm"
              onClick={() => onNavigateToTransform(dataset.id, selectedVersion.id)}
            >
              <Layers size={14} /> Transform
            </button>
            <a
              href={api.getDownloadUrl(dataset.id, selectedVersion?.id)}
              download
              className="btn btn-secondary btn-sm"
            >
              <Download size={14} /> Download CSV
            </a>
          </div>
        </div>

        {/* Version Switcher Bar */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'var(--bg-secondary)',
            padding: '0.75rem 1.25rem',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-color)',
            marginBottom: '1.5rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
              Selected Version:
            </span>
            <select
              value={selectedVersionId}
              onChange={(e) => setSelectedVersionId(e.target.value)}
              className="input-control"
              style={{ width: 'auto', padding: '0.35rem 0.75rem' }}
            >
              {dataset.versions.map((v) => (
                <option key={v.id} value={v.id}>
                  v{v.version_number} — {v.original_filename} ({v.row_count} rows)
                </option>
              ))}
            </select>
          </div>

          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }} className="font-mono">
            Checksum: {selectedVersion?.checksum || '-'}
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          borderBottom: '1px solid var(--border-color)',
          marginBottom: '1.5rem',
        }}
      >
        <button
          className={`nav-item ${activeTab === 'preview' ? 'active' : ''}`}
          onClick={() => setActiveTab('preview')}
        >
          <TableIcon size={16} /> Data Preview ({selectedVersion?.row_count} rows)
        </button>
        <button
          className={`nav-item ${activeTab === 'schema' ? 'active' : ''}`}
          onClick={() => setActiveTab('schema')}
        >
          <Database size={16} /> Schema & Contract ({selectedVersion?.column_count} columns)
        </button>
        <button
          className={`nav-item ${activeTab === 'quality' ? 'active' : ''}`}
          onClick={() => setActiveTab('quality')}
        >
          <Award size={16} /> Quality & Profiling
        </button>
        <button
          className={`nav-item ${activeTab === 'versions' ? 'active' : ''}`}
          onClick={() => setActiveTab('versions')}
        >
          <History size={16} /> Version Lineage ({dataset.versions.length})
        </button>
      </div>

      {/* Tab 1: Data Preview */}
      {activeTab === 'preview' && (
        <div className="card">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1rem',
            }}
          >
            <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>Bounded Sample Rows</h3>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
              Showing {preview?.rows.length || 0} of {selectedVersion?.row_count.toLocaleString()} rows
            </span>
          </div>

          {preview && preview.rows.length > 0 ? (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    {preview.columns.map((c) => (
                      <th key={c}>{c}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {preview.rows.map((row, idx) => (
                    <tr key={idx}>
                      {preview.columns.map((col) => (
                        <td key={col} className="font-mono" style={{ fontSize: '0.82rem' }}>
                          {row[col] !== null && row[col] !== undefined ? String(row[col]) : (
                            <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>null</span>
                          )}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="empty-state">No preview records available.</div>
          )}
        </div>
      )}

      {/* Tab 2: Schema */}
      {activeTab === 'schema' && (
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>
            Inferred Column Schema
          </h3>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Column Name</th>
                  <th>Inferred Type</th>
                  <th>Nullable</th>
                </tr>
              </thead>
              <tbody>
                {selectedVersion?.schema_json.map((field) => (
                  <tr key={field.name}>
                    <td style={{ fontWeight: 600 }}>{field.name}</td>
                    <td>
                      <span className="badge badge-info">{field.type}</span>
                    </td>
                    <td>
                      {field.nullable ? (
                        <span className="badge badge-warning">Nullable</span>
                      ) : (
                        <span className="badge badge-success">Required</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Tab 3: Quality & Profiling */}
      {activeTab === 'quality' && (
        <div>
          {/* Quality Summary Score Card */}
          <div className="card" style={{ marginBottom: '1.5rem' }}>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                flexWrap: 'wrap',
                gap: '1rem',
              }}
            >
              <div>
                <span className="metric-label">Deterministic Quality Score</span>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.75rem', marginTop: '0.25rem' }}>
                  <span
                    style={{
                      fontSize: '2.5rem',
                      fontWeight: 800,
                      color:
                        quality && quality.score >= 90
                          ? 'var(--accent-emerald)'
                          : quality && quality.score >= 70
                          ? 'var(--accent-amber)'
                          : 'var(--accent-rose)',
                    }}
                  >
                    {quality ? quality.score : '--'}
                  </span>
                  <span style={{ color: 'var(--text-muted)' }}>/ 100</span>
                  {quality && (
                    <span
                      className={`badge ${
                        quality.status === 'excellent'
                          ? 'badge-success'
                          : quality.status === 'good'
                          ? 'badge-info'
                          : 'badge-warning'
                      }`}
                    >
                      {quality.status.toUpperCase()}
                    </span>
                  )}
                </div>
                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                  {quality?.summary || 'Run quality evaluation to compute score.'}
                </p>
              </div>

              <div style={{ display: 'flex', gap: '0.6rem' }}>
                <button
                  className="btn btn-secondary btn-sm"
                  onClick={handleEvaluateQuality}
                  disabled={actionLoading}
                >
                  <Award size={14} /> Re-evaluate Quality
                </button>
              </div>
            </div>

            {/* Quality Checks Breakdown */}
            {quality && quality.checks_json.checks && (
              <div style={{ marginTop: '1.5rem', borderTop: '1px solid var(--border-color)', paddingTop: '1.25rem' }}>
                <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.75rem' }}>
                  Quality Checks Detail
                </h4>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                  {quality.checks_json.checks.map((chk, idx) => (
                    <div
                      key={idx}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.65rem 1rem',
                        background: 'var(--bg-tertiary)',
                        borderRadius: 'var(--radius-sm)',
                        fontSize: '0.85rem',
                      }}
                    >
                      <div>
                        <span style={{ fontWeight: 600 }}>{chk.name}: </span>
                        <span style={{ color: 'var(--text-secondary)' }}>{chk.message}</span>
                      </div>
                      <span
                        className={`badge ${
                          chk.status === 'passed'
                            ? 'badge-success'
                            : chk.status === 'warning'
                            ? 'badge-warning'
                            : 'badge-danger'
                        }`}
                      >
                        {chk.status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Statistical Profiling Card */}
          <div className="card">
            <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>
              Column-Level Statistical Profiling
            </h3>
            {profiling ? (
              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Column</th>
                      <th>Type</th>
                      <th>Nulls (%)</th>
                      <th>Distinct</th>
                      <th>Min / Max</th>
                      <th>Mean / Median</th>
                      <th>Constant?</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.values(profiling.columns_json).map((c) => (
                      <tr key={c.name}>
                        <td style={{ fontWeight: 600 }}>{c.name}</td>
                        <td>
                          <span className="badge badge-info">{c.detected_type}</span>
                        </td>
                        <td className="font-mono">
                          {c.null_count} ({c.null_percentage}%)
                        </td>
                        <td className="font-mono">{c.distinct_count}</td>
                        <td className="font-mono">
                          {c.numeric_min !== null ? `${c.numeric_min} .. ${c.numeric_max}` : '-'}
                        </td>
                        <td className="font-mono">
                          {c.numeric_mean !== null ? `${c.numeric_mean} / ${c.numeric_median}` : '-'}
                        </td>
                        <td>
                          {c.is_constant ? (
                            <span className="badge badge-warning">Constant</span>
                          ) : (
                            <span className="badge badge-success">Dynamic</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="empty-state">
                <BarChart2 size={32} className="empty-icon" />
                <p>No profiling metrics computed yet.</p>
                <button
                  className="btn btn-primary btn-sm"
                  style={{ marginTop: '0.75rem' }}
                  onClick={handleRunProfiling}
                >
                  Run Statistical Profiling
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Tab 4: Version Lineage */}
      {activeTab === 'versions' && (
        <div className="card">
          <h3 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>
            Immutable Version Lineage
          </h3>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Created Reason</th>
                  <th>Rows</th>
                  <th>Cols</th>
                  <th>Checksum</th>
                  <th>Created At</th>
                  <th style={{ textAlign: 'right' }}>Download</th>
                </tr>
              </thead>
              <tbody>
                {dataset.versions.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <span className="badge badge-purple">v{v.version_number}</span>
                    </td>
                    <td>{v.creation_reason}</td>
                    <td className="font-mono">{v.row_count.toLocaleString()}</td>
                    <td className="font-mono">{v.column_count}</td>
                    <td className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {v.checksum.substring(0, 12)}...
                    </td>
                    <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      {new Date(v.created_at).toLocaleString()}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <a
                        href={api.getDownloadUrl(dataset.id, v.id)}
                        download
                        className="btn btn-secondary btn-sm"
                      >
                        <Download size={14} />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
