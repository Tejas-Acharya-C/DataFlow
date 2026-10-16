import React, { useEffect, useState } from 'react';
import {
  History,
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  RefreshCw,
  Search,
} from 'lucide-react';
import { api } from '../api/client';
import { ProcessingJob, AuditEvent } from '../types';

export const AuditJobsPage: React.FC = () => {
  const [jobs, setJobs] = useState<ProcessingJob[]>([]);
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([]);
  const [activeSubTab, setActiveSubTab] = useState<'jobs' | 'audit'>('jobs');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadTelemetry();
  }, []);

  const loadTelemetry = async () => {
    setLoading(true);
    try {
      const [jData, aData] = await Promise.all([
        api.getJobs(),
        api.getAuditEvents(0, 100),
      ]);
      setJobs(jData.items);
      setAuditEvents(aData.items);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Processing Jobs & Audit Trails</h1>
          <p className="page-subtitle">
            Inspect background and synchronous job execution and query the immutable compliance audit log.
          </p>
        </div>
        <button className="btn btn-secondary" onClick={loadTelemetry} disabled={loading}>
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
          <span>Refresh Telemetry</span>
        </button>
      </div>

      {/* Sub Tabs */}
      <div
        style={{
          display: 'flex',
          gap: '0.5rem',
          borderBottom: '1px solid var(--border-color)',
          marginBottom: '1.5rem',
        }}
      >
        <button
          className={`nav-item ${activeSubTab === 'jobs' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('jobs')}
        >
          <Activity size={16} /> Processing Jobs ({jobs.length})
        </button>
        <button
          className={`nav-item ${activeSubTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveSubTab('audit')}
        >
          <History size={16} /> Audit Event Log ({auditEvents.length})
        </button>
      </div>

      {/* Sub Tab 1: Processing Jobs */}
      {activeSubTab === 'jobs' && (
        <div className="card">
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Job ID</th>
                  <th>Operation Type</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Error / Metadata</th>
                  <th>Started At</th>
                  <th>Completed At</th>
                </tr>
              </thead>
              <tbody>
                {jobs.length === 0 ? (
                  <tr>
                    <td colSpan={7} style={{ textAlign: 'center', padding: '2rem' }}>
                      No processing jobs recorded.
                    </td>
                  </tr>
                ) : (
                  jobs.map((job) => (
                    <tr key={job.id}>
                      <td className="font-mono" style={{ fontSize: '0.78rem' }}>
                        {job.id.substring(0, 8)}...
                      </td>
                      <td style={{ fontWeight: 600 }}>{job.job_type}</td>
                      <td>
                        <span
                          className={`badge ${
                            job.status === 'succeeded'
                              ? 'badge-success'
                              : job.status === 'running'
                              ? 'badge-info'
                              : job.status === 'failed'
                              ? 'badge-danger'
                              : 'badge-warning'
                          }`}
                        >
                          {job.status}
                        </span>
                      </td>
                      <td>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <div
                            style={{
                              flex: 1,
                              height: '6px',
                              background: 'var(--bg-tertiary)',
                              borderRadius: '3px',
                              overflow: 'hidden',
                              minWidth: '60px',
                            }}
                          >
                            <div
                              style={{
                                width: `${job.progress}%`,
                                height: '100%',
                                background:
                                  job.status === 'failed' ? 'var(--accent-rose)' : 'var(--accent-emerald)',
                              }}
                            />
                          </div>
                          <span style={{ fontSize: '0.75rem' }} className="font-mono">
                            {job.progress}%
                          </span>
                        </div>
                      </td>
                      <td style={{ fontSize: '0.82rem', color: job.error_message ? 'var(--accent-rose)' : 'var(--text-muted)' }}>
                        {job.error_message || (job.metadata_json ? JSON.stringify(job.metadata_json) : '-')}
                      </td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {new Date(job.created_at).toLocaleTimeString()}
                      </td>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {job.finished_at ? new Date(job.finished_at).toLocaleTimeString() : '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Sub Tab 2: Audit Logs */}
      {activeSubTab === 'audit' && (
        <div className="card">
          <div className="table-container">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Timestamp</th>
                  <th>Event Type</th>
                  <th>Entity</th>
                  <th>Entity ID</th>
                  <th>Outcome</th>
                  <th>Details Payload</th>
                </tr>
              </thead>
              <tbody>
                {auditEvents.length === 0 ? (
                  <tr>
                    <td colSpan={6} style={{ textAlign: 'center', padding: '2rem' }}>
                      No audit events recorded.
                    </td>
                  </tr>
                ) : (
                  auditEvents.map((evt) => (
                    <tr key={evt.id}>
                      <td style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {new Date(evt.created_at).toLocaleString()}
                      </td>
                      <td style={{ fontWeight: 600 }}>{evt.event_type}</td>
                      <td>
                        <span className="badge badge-purple">{evt.entity_type}</span>
                      </td>
                      <td className="font-mono" style={{ fontSize: '0.78rem' }}>
                        {evt.entity_id.substring(0, 10)}...
                      </td>
                      <td>
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
                      </td>
                      <td className="font-mono" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
                        {evt.details_json ? JSON.stringify(evt.details_json) : '-'}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
