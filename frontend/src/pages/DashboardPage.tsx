import React, { useEffect, useState } from 'react';
import {
  Database,
  CheckCircle2,
  XCircle,
  Award,
  Clock,
  ArrowRight,
  TrendingUp,
} from 'lucide-react';
import { api } from '../api/client';
import { Dataset, ProcessingJob, AuditEvent, SystemHealth } from '../types';

interface DashboardPageProps {
  onNavigate: (tab: string, datasetId?: string) => void;
  onOpenUpload: () => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  onNavigate,
  onOpenUpload,
}) => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    setLoading(true);
    try {
      const [dsData, jobData, auditData, healthData] = await Promise.all([
        api.getDatasets(0, 5),
        api.getJobs(),
        api.getAuditEvents(0, 6),
        api.getHealth().catch(() => null),
      ]);
      setDatasets(dsData.items);
      setJobs(jobData.items);
      setAuditEvents(auditData.items);
      setHealth(healthData);
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
    } finally {
      setLoading(false);
    }
  };

  const succeededJobs = jobs.filter((j) => j.status === 'succeeded').length;
  const failedJobs = jobs.filter((j) => j.status === 'failed').length;

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Platform Overview</h1>
          <p className="page-subtitle">
            Reliability metrics, recent dataset versions, and real-time execution telemetry.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '0.75rem' }}>
          <button className="btn btn-secondary" onClick={loadDashboardData}>
            Refresh
          </button>
          <button className="btn btn-primary" onClick={onOpenUpload}>
            Ingest Dataset
          </button>
        </div>
      </div>

      {/* Metric Cards Grid */}
      <div className="grid-cols-4">
        <div className="metric-card">
          <div>
            <div className="metric-label">Managed Datasets</div>
            <div className="metric-value">{datasets.length}</div>
            <div className="metric-desc">Active logical datasets</div>
          </div>
          <div className="metric-icon-wrap">
            <Database size={22} />
          </div>
        </div>

        <div className="metric-card">
          <div>
            <div className="metric-label">Successful Operations</div>
            <div className="metric-value" style={{ color: 'var(--accent-emerald)' }}>
              {succeededJobs}
            </div>
            <div className="metric-desc">Ingestions & transformations</div>
          </div>
          <div
            className="metric-icon-wrap"
            style={{ background: 'rgba(16, 185, 129, 0.1)', color: 'var(--accent-emerald)' }}
          >
            <CheckCircle2 size={22} />
          </div>
        </div>

        <div className="metric-card">
          <div>
            <div className="metric-label">Failed Operations</div>
            <div
              className="metric-value"
              style={{ color: failedJobs > 0 ? 'var(--accent-rose)' : 'var(--text-primary)' }}
            >
              {failedJobs}
            </div>
            <div className="metric-desc">Requires inspection & fix</div>
          </div>
          <div
            className="metric-icon-wrap"
            style={{ background: 'rgba(239, 68, 68, 0.1)', color: 'var(--accent-rose)' }}
          >
            <XCircle size={22} />
          </div>
        </div>

        <div className="metric-card">
          <div>
            <div className="metric-label">Engine Health</div>
            <div className="metric-value" style={{ fontSize: '1.4rem' }}>
              {health?.status === 'ready' ? 'Operational' : 'Degraded'}
            </div>
            <div className="metric-desc">
              DB: {health?.database || 'offline'} · Storage: {health?.storage || 'offline'}
            </div>
          </div>
          <div
            className="metric-icon-wrap"
            style={{ background: 'rgba(6, 182, 212, 0.1)', color: 'var(--accent-cyan)' }}
          >
            <Award size={22} />
          </div>
        </div>
      </div>

      {/* 2-Column Split: Recent Datasets & Audit Activity */}
      <div className="grid-cols-2">
        {/* Recent Datasets Card */}
        <div className="card">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1.25rem',
            }}
          >
            <h2 style={{ fontSize: '1.15rem', fontWeight: 600 }}>Recent Datasets</h2>
            <button
              onClick={() => onNavigate('datasets')}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--accent-indigo)',
                fontSize: '0.85rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
              }}
            >
              View all <ArrowRight size={14} />
            </button>
          </div>

          {datasets.length === 0 ? (
            <div className="empty-state">
              <Database size={32} className="empty-icon" />
              <p>No datasets uploaded yet.</p>
              <button
                className="btn btn-primary btn-sm"
                style={{ marginTop: '0.75rem' }}
                onClick={onOpenUpload}
              >
                Upload your first CSV
              </button>
            </div>
          ) : (
            <div className="table-container">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Versions</th>
                    <th>Rows</th>
                    <th>Last Updated</th>
                  </tr>
                </thead>
                <tbody>
                  {datasets.map((d) => (
                    <tr
                      key={d.id}
                      style={{ cursor: 'pointer' }}
                      onClick={() => onNavigate('datasets', d.id)}
                    >
                      <td style={{ fontWeight: 500 }}>
                        <div style={{ color: 'var(--text-primary)' }}>{d.name}</div>
                        {d.description && (
                          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                            {d.description}
                          </div>
                        )}
                      </td>
                      <td>
                        <span className="badge badge-purple">
                          v{d.latest_version?.version_number || 1}
                        </span>
                      </td>
                      <td className="font-mono">
                        {d.latest_version?.row_count.toLocaleString() || 0}
                      </td>
                      <td style={{ color: 'var(--text-secondary)', fontSize: '0.8rem' }}>
                        {new Date(d.updated_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Real-time Audit Telemetry */}
        <div className="card">
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              marginBottom: '1.25rem',
            }}
          >
            <h2 style={{ fontSize: '1.15rem', fontWeight: 600 }}>Recent Audit Telemetry</h2>
            <button
              onClick={() => onNavigate('audit')}
              style={{
                background: 'transparent',
                border: 'none',
                color: 'var(--accent-indigo)',
                fontSize: '0.85rem',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '0.3rem',
              }}
            >
              View audit log <ArrowRight size={14} />
            </button>
          </div>

          {auditEvents.length === 0 ? (
            <div className="empty-state">
              <Clock size={32} className="empty-icon" />
              <p>No audit events recorded yet.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
              {auditEvents.map((evt) => (
                <div
                  key={evt.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '0.75rem 1rem',
                    background: 'var(--bg-tertiary)',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--border-color)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 500, fontSize: '0.88rem' }}>
                      {evt.event_type}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      Entity: {evt.entity_type} · {new Date(evt.created_at).toLocaleTimeString()}
                    </div>
                  </div>
                  <span
                    className={`badge ${
                      evt.outcome === 'success' || evt.outcome === 'passed'
                        ? 'badge-success'
                        : evt.outcome === 'warning'
                        ? 'badge-warning'
                        : 'badge-danger'
                    }`}
                  >
                    {evt.outcome}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
