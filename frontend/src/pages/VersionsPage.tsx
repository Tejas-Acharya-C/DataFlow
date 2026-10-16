import React, { useEffect, useState } from 'react';
import {
  GitBranch,
  ArrowRight,
  Download,
  CheckCircle2,
  AlertCircle,
  Plus,
  Minus,
} from 'lucide-react';
import { api } from '../api/client';
import { Dataset, DatasetVersion, VersionCompareResult } from '../types';

export const VersionsPage: React.FC = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [versions, setVersions] = useState<DatasetVersion[]>([]);
  const [versionAId, setVersionAId] = useState('');
  const [versionBId, setVersionBId] = useState('');
  const [compareResult, setCompareResult] = useState<VersionCompareResult | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadDatasets();
  }, []);

  useEffect(() => {
    if (selectedDatasetId) {
      loadVersions(selectedDatasetId);
    }
  }, [selectedDatasetId]);

  const loadDatasets = async () => {
    try {
      const data = await api.getDatasets(0, 50);
      setDatasets(data.items);
      if (data.items.length > 0) {
        setSelectedDatasetId(data.items[0].id);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const loadVersions = async (dsId: string) => {
    try {
      const vList = await api.getVersions(dsId);
      setVersions(vList);
      setCompareResult(null);
      if (vList.length >= 2) {
        setVersionAId(vList[1].id);
        setVersionBId(vList[0].id);
      } else if (vList.length === 1) {
        setVersionAId(vList[0].id);
        setVersionBId(vList[0].id);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const handleCompare = async () => {
    if (!versionAId || !versionBId) return;
    setLoading(true);
    try {
      const res = await api.compareVersions(versionAId, versionBId);
      setCompareResult(res);
    } catch (err: any) {
      alert(err.message || 'Comparison failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Version History & Diff Engine</h1>
          <p className="page-subtitle">
            Inspect immutable artifact versions, detect schema drift, and compare lineage deltas.
          </p>
        </div>
      </div>

      {/* Dataset Selector */}
      <div className="card" style={{ marginBottom: '1.5rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
          <label style={{ fontSize: '0.88rem', fontWeight: 600 }}>Select Dataset:</label>
          <select
            value={selectedDatasetId}
            onChange={(e) => setSelectedDatasetId(e.target.value)}
            className="input-control"
            style={{ width: 'auto', minWidth: '260px' }}
          >
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} ({d.version_count} versions)
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Two Column Layout: Version Lineage Table & Version Comparator */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '1.5rem' }}>
        {/* Version Compare Tool */}
        <div className="card">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
            Compare Two Versions
          </h2>

          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              flexWrap: 'wrap',
              marginBottom: '1.5rem',
              padding: '1rem',
              background: 'var(--bg-tertiary)',
              borderRadius: 'var(--radius-md)',
            }}
          >
            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
                Base Version (A)
              </label>
              <select
                value={versionAId}
                onChange={(e) => setVersionAId(e.target.value)}
                className="input-control"
                style={{ width: 'auto' }}
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} ({v.row_count} rows)
                  </option>
                ))}
              </select>
            </div>

            <ArrowRight size={20} color="var(--text-muted)" style={{ marginTop: '1rem' }} />

            <div>
              <label style={{ display: 'block', fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.3rem' }}>
                Target Version (B)
              </label>
              <select
                value={versionBId}
                onChange={(e) => setVersionBId(e.target.value)}
                className="input-control"
                style={{ width: 'auto' }}
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} ({v.row_count} rows)
                  </option>
                ))}
              </select>
            </div>

            <button
              className="btn btn-primary btn-sm"
              style={{ marginTop: '1rem' }}
              onClick={handleCompare}
              disabled={loading || versions.length < 2}
            >
              <GitBranch size={14} /> Compare Versions
            </button>
          </div>

          {compareResult && (
            <div>
              {/* Deltas Metric Strip */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ background: 'var(--bg-tertiary)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
                  <span className="metric-label">Row Count Delta</span>
                  <div
                    style={{
                      fontSize: '1.4rem',
                      fontWeight: 700,
                      color:
                        compareResult.row_count_delta > 0
                          ? 'var(--accent-emerald)'
                          : compareResult.row_count_delta < 0
                          ? 'var(--accent-rose)'
                          : 'var(--text-primary)',
                    }}
                  >
                    {compareResult.row_count_delta > 0 ? `+${compareResult.row_count_delta}` : compareResult.row_count_delta}
                  </div>
                </div>

                <div style={{ background: 'var(--bg-tertiary)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
                  <span className="metric-label">Columns Added</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                    +{compareResult.columns_added.length}
                  </div>
                </div>

                <div style={{ background: 'var(--bg-tertiary)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
                  <span className="metric-label">Columns Removed</span>
                  <div style={{ fontSize: '1.4rem', fontWeight: 700, color: 'var(--accent-rose)' }}>
                    -{compareResult.columns_removed.length}
                  </div>
                </div>
              </div>

              {/* Added / Removed Column Lists */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem', marginBottom: '1.5rem' }}>
                <div style={{ background: 'var(--bg-tertiary)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
                  <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-emerald)', marginBottom: '0.5rem' }}>
                    + Added Columns
                  </h4>
                  {compareResult.columns_added.length === 0 ? (
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>None</span>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                      {compareResult.columns_added.map((c) => (
                        <span key={c} className="badge badge-success">
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                </div>

                <div style={{ background: 'var(--bg-tertiary)', padding: '1rem', borderRadius: 'var(--radius-sm)' }}>
                  <h4 style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--accent-rose)', marginBottom: '0.5rem' }}>
                    - Removed Columns
                  </h4>
                  {compareResult.columns_removed.length === 0 ? (
                    <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>None</span>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                      {compareResult.columns_removed.map((c) => (
                        <span key={c} className="badge badge-danger">
                          {c}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Detailed Schema Modification Table */}
              {compareResult.schema_changes.length > 0 && (
                <div>
                  <h4 style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: '0.6rem' }}>
                    Schema Drift & Type Changes
                  </h4>
                  <div className="table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Column</th>
                          <th>Change Type</th>
                          <th>Details</th>
                        </tr>
                      </thead>
                      <tbody>
                        {compareResult.schema_changes.map((sc, idx) => (
                          <tr key={idx}>
                            <td style={{ fontWeight: 600 }}>{sc.column}</td>
                            <td>
                              <span className="badge badge-warning">{sc.change}</span>
                            </td>
                            <td className="font-mono" style={{ fontSize: '0.82rem' }}>
                              {sc.old_type ? `${sc.old_type} → ${sc.new_type}` : sc.type || '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* All Versions Table */}
        <div className="card">
          <h2 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '1rem' }}>
            Version Artifacts Repository
          </h2>
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Version</th>
                  <th>Filename</th>
                  <th>Row Count</th>
                  <th>Column Count</th>
                  <th>Storage Size</th>
                  <th>SHA-256 Checksum</th>
                  <th>Creation Reason</th>
                  <th>Created At</th>
                  <th style={{ textAlign: 'right' }}>Download</th>
                </tr>
              </thead>
              <tbody>
                {versions.map((v) => (
                  <tr key={v.id}>
                    <td>
                      <span className="badge badge-purple">v{v.version_number}</span>
                    </td>
                    <td>{v.original_filename}</td>
                    <td className="font-mono">{v.row_count.toLocaleString()}</td>
                    <td className="font-mono">{v.column_count}</td>
                    <td className="font-mono">{(v.file_size_bytes / 1024).toFixed(1)} KB</td>
                    <td className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {v.checksum.substring(0, 12)}...
                    </td>
                    <td style={{ fontSize: '0.85rem' }}>{v.creation_reason}</td>
                    <td style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                      {new Date(v.created_at).toLocaleString()}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <a
                        href={api.getDownloadUrl(selectedDatasetId, v.id)}
                        download
                        className="btn btn-secondary btn-sm"
                      >
                        <Download size={13} />
                      </a>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};
