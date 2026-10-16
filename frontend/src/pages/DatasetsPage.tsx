import React, { useEffect, useState } from 'react';
import {
  Database,
  Search,
  Upload,
  Eye,
  Trash2,
  FileSpreadsheet,
  Download,
  Layers,
} from 'lucide-react';
import { api } from '../api/client';
import { Dataset } from '../types';

interface DatasetsPageProps {
  onSelectDataset: (id: string) => void;
  onOpenUpload: () => void;
}

export const DatasetsPage: React.FC<DatasetsPageProps> = ({
  onSelectDataset,
  onOpenUpload,
}) => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDatasets();
  }, [search]);

  const loadDatasets = async () => {
    setLoading(true);
    try {
      const data = await api.getDatasets(0, 50, search || undefined);
      setDatasets(data.items);
    } catch (err) {
      console.error('Failed to load datasets:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent, id: string, name: string) => {
    e.stopPropagation();
    if (confirm(`Are you sure you want to archive dataset '${name}'?`)) {
      try {
        await api.deleteDataset(id);
        loadDatasets();
      } catch (err: any) {
        alert(err.message || 'Failed to archive dataset');
      }
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Dataset Management</h1>
          <p className="page-subtitle">
            Ingest, inspect schemas, and manage versioned datasets safely.
          </p>
        </div>
        <button className="btn btn-primary" onClick={onOpenUpload}>
          <Upload size={16} />
          <span>Upload New CSV</span>
        </button>
      </div>

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '1rem',
          marginBottom: '1.5rem',
        }}
      >
        <div style={{ position: 'relative', flex: 1, maxWidth: '400px' }}>
          <Search
            size={18}
            style={{
              position: 'absolute',
              left: '12px',
              top: '50%',
              transform: 'translateY(-50%)',
              color: 'var(--text-muted)',
            }}
          />
          <input
            type="text"
            placeholder="Search datasets by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="input-control"
            style={{ paddingLeft: '2.4rem' }}
          />
        </div>
      </div>

      {loading ? (
        <div className="card empty-state">Loading datasets...</div>
      ) : datasets.length === 0 ? (
        <div className="card empty-state">
          <Database size={40} className="empty-icon" />
          <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>No datasets found</h3>
          <p>Upload a CSV file to get started with validation and profiling.</p>
          <button className="btn btn-primary" style={{ marginTop: '1rem' }} onClick={onOpenUpload}>
            <Upload size={16} />
            <span>Upload CSV</span>
          </button>
        </div>
      ) : (
        <div className="table-container">
          <table className="data-table">
            <thead>
              <tr>
                <th>Dataset Name</th>
                <th>Version</th>
                <th>Rows</th>
                <th>Columns</th>
                <th>Storage Size</th>
                <th>Checksum</th>
                <th>Last Ingested</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {datasets.map((d) => {
                const latest = d.latest_version;
                const sizeKb = latest ? (latest.file_size_bytes / 1024).toFixed(1) : '0';
                return (
                  <tr
                    key={d.id}
                    style={{ cursor: 'pointer' }}
                    onClick={() => onSelectDataset(d.id)}
                  >
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                        {d.name}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                        {latest?.original_filename || 'No files'}
                      </div>
                    </td>
                    <td>
                      <span className="badge badge-purple">
                        v{latest?.version_number || 1}
                      </span>
                    </td>
                    <td className="font-mono">
                      {latest?.row_count.toLocaleString() || 0}
                    </td>
                    <td className="font-mono">{latest?.column_count || 0}</td>
                    <td className="font-mono">{sizeKb} KB</td>
                    <td className="font-mono" style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      {latest?.checksum ? `${latest.checksum.substring(0, 10)}...` : '-'}
                    </td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '0.82rem' }}>
                      {new Date(d.updated_at).toLocaleDateString()}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <div
                        style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '0.5rem',
                        }}
                      >
                        <button
                          className="btn btn-secondary btn-sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectDataset(d.id);
                          }}
                          title="View Details"
                        >
                          <Eye size={14} />
                        </button>
                        <a
                          href={api.getDownloadUrl(d.id)}
                          download
                          className="btn btn-secondary btn-sm"
                          onClick={(e) => e.stopPropagation()}
                          title="Download CSV"
                        >
                          <Download size={14} />
                        </a>
                        <button
                          className="btn btn-danger btn-sm"
                          onClick={(e) => handleDelete(e, d.id, d.name)}
                          title="Archive"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
