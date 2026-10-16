import React, { useEffect, useState } from 'react';
import {
  FileCode2,
  Plus,
  Play,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Trash2,
  X,
} from 'lucide-react';
import { api } from '../api/client';
import { DataContract, Dataset, ValidationRun } from '../types';

export const ContractsPage: React.FC = () => {
  const [contracts, setContracts] = useState<DataContract[]>([]);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedContract, setSelectedContract] = useState<DataContract | null>(null);
  const [validationRun, setValidationRun] = useState<ValidationRun | null>(null);
  const [selectedDatasetId, setSelectedDatasetId] = useState('');
  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [validating, setValidating] = useState(false);

  // New contract form fields
  const [newName, setNewName] = useState('');
  const [newDesc, setNewDesc] = useState('');
  const [requiredCols, setRequiredCols] = useState('');
  const [uniqueCols, setUniqueCols] = useState('');
  const [nonNullableCols, setNonNullableCols] = useState('');
  const [allowedValuesJson, setAllowedValuesJson] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [cList, dList] = await Promise.all([
        api.getContracts(),
        api.getDatasets(0, 50),
      ]);
      setContracts(cList);
      setDatasets(dList.items);
      if (cList.length > 0 && !selectedContract) {
        setSelectedContract(cList[0]);
      }
      if (dList.items.length > 0 && !selectedDatasetId) {
        setSelectedDatasetId(dList.items[0].id);
      }
    } catch (err) {
      console.error('Failed to load contracts data:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateContract = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let allowedValues = {};
      if (allowedValuesJson.trim()) {
        try {
          allowedValues = JSON.parse(allowedValuesJson);
        } catch {
          alert('Allowed values must be valid JSON: {"column_name": ["val1", "val2"]}');
          return;
        }
      }

      const nullableCols: Record<string, boolean> = {};
      nonNullableCols
        .split(',')
        .map((c) => c.trim())
        .filter(Boolean)
        .forEach((c) => {
          nullableCols[c] = false;
        });

      const rules = {
        required_columns: requiredCols.split(',').map((c) => c.trim()).filter(Boolean),
        unique_columns: uniqueCols.split(',').map((c) => c.trim()).filter(Boolean),
        nullable_columns: nullableCols,
        allowed_values: allowedValues,
      };

      const created = await api.createContract({
        name: newName,
        description: newDesc,
        rules,
      });

      setIsCreateOpen(false);
      setNewName('');
      setNewDesc('');
      setRequiredCols('');
      setUniqueCols('');
      setNonNullableCols('');
      setAllowedValuesJson('');
      loadData();
      setSelectedContract(created);
    } catch (err: any) {
      alert(err.message || 'Failed to create contract');
    }
  };

  const handleRunValidation = async () => {
    if (!selectedContract || !selectedDatasetId) return;

    // Get latest version of chosen dataset
    const ds = datasets.find((d) => d.id === selectedDatasetId);
    if (!ds || !ds.latest_version) {
      alert('Selected dataset has no versions to validate.');
      return;
    }

    setValidating(true);
    setValidationRun(null);
    try {
      const run = await api.validateContract(selectedContract.id, ds.latest_version.id);
      setValidationRun(run);
    } catch (err: any) {
      alert(err.message || 'Validation execution failed');
    } finally {
      setValidating(false);
    }
  };

  const handleDeleteContract = async (id: string, name: string) => {
    if (confirm(`Delete contract '${name}'?`)) {
      try {
        await api.deleteContract(id);
        setSelectedContract(null);
        loadData();
      } catch (err: any) {
        alert(err.message || 'Failed to delete contract');
      }
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Data Contracts & Quality SLAs</h1>
          <p className="page-subtitle">
            Define declarative validation rules to prevent schema drift and quality degradation.
          </p>
        </div>
        <button className="btn btn-primary" onClick={() => setIsCreateOpen(true)}>
          <Plus size={16} />
          <span>New Data Contract</span>
        </button>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.5rem' }}>
        {/* Contracts Sidebar */}
        <div className="card" style={{ height: 'fit-content' }}>
          <h2 style={{ fontSize: '1rem', fontWeight: 600, marginBottom: '1rem' }}>
            Registered Contracts ({contracts.length})
          </h2>

          {contracts.length === 0 ? (
            <div className="empty-state" style={{ padding: '1rem 0' }}>
              <p>No contracts defined yet.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {contracts.map((c) => (
                <div
                  key={c.id}
                  onClick={() => {
                    setSelectedContract(c);
                    setValidationRun(null);
                  }}
                  style={{
                    padding: '0.75rem 1rem',
                    borderRadius: 'var(--radius-sm)',
                    border: `1px solid ${
                      selectedContract?.id === c.id ? 'var(--accent-indigo)' : 'var(--border-color)'
                    }`,
                    background:
                      selectedContract?.id === c.id ? 'rgba(99, 102, 241, 0.1)' : 'var(--bg-tertiary)',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '0.88rem' }}>{c.name}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      v{c.version} · {c.rules_json?.required_columns?.length || 0} req. cols
                    </div>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteContract(c.id, c.name);
                    }}
                    style={{
                      background: 'transparent',
                      border: 'none',
                      color: 'var(--text-muted)',
                      cursor: 'pointer',
                    }}
                    title="Delete"
                  >
                    <Trash2 size={14} />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Contract Inspection & Validation Pane */}
        <div>
          {selectedContract ? (
            <>
              {/* Contract Rules Card */}
              <div className="card" style={{ marginBottom: '1.5rem' }}>
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    marginBottom: '1rem',
                  }}
                >
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                      <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>
                        {selectedContract.name}
                      </h2>
                      <span className="badge badge-purple">v{selectedContract.version}</span>
                    </div>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                      {selectedContract.description || 'No description provided.'}
                    </p>
                  </div>
                </div>

                {/* Preformatted rules */}
                <div
                  style={{
                    background: 'var(--bg-primary)',
                    padding: '1rem',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-color)',
                    marginBottom: '1.5rem',
                  }}
                >
                  <pre
                    className="font-mono"
                    style={{ fontSize: '0.82rem', color: '#cbd5e1', whiteSpace: 'pre-wrap' }}
                  >
                    {JSON.stringify(selectedContract.rules_json, null, 2)}
                  </pre>
                </div>

                {/* Validation Trigger Controls */}
                <div
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '1rem',
                    flexWrap: 'wrap',
                    padding: '1rem',
                    background: 'var(--bg-tertiary)',
                    borderRadius: 'var(--radius-md)',
                  }}
                >
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', fontWeight: 500 }}>
                    Apply Contract To Dataset:
                  </label>
                  <select
                    value={selectedDatasetId}
                    onChange={(e) => setSelectedDatasetId(e.target.value)}
                    className="input-control"
                    style={{ width: 'auto', minWidth: '220px' }}
                  >
                    {datasets.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.name} (v{d.latest_version?.version_number || 1})
                      </option>
                    ))}
                  </select>

                  <button
                    className="btn btn-primary btn-sm"
                    onClick={handleRunValidation}
                    disabled={validating || datasets.length === 0}
                  >
                    <Play size={14} />
                    <span>{validating ? 'Evaluating...' : 'Run Validation'}</span>
                  </button>
                </div>
              </div>

              {/* Validation Results Card */}
              {validationRun && (
                <div className="card">
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '1rem',
                    }}
                  >
                    <h3 style={{ fontSize: '1.05rem', fontWeight: 600 }}>Validation Run Outcome</h3>
                    <span
                      className={`badge ${
                        validationRun.status === 'passed' ? 'badge-success' : 'badge-danger'
                      }`}
                    >
                      {validationRun.status.toUpperCase()}
                    </span>
                  </div>

                  <div style={{ display: 'flex', gap: '1.5rem', marginBottom: '1.25rem' }}>
                    <div>
                      <span className="metric-label">Passed Checks</span>
                      <div style={{ fontSize: '1.3rem', fontWeight: 700, color: 'var(--accent-emerald)' }}>
                        {validationRun.passed_count}
                      </div>
                    </div>
                    <div>
                      <span className="metric-label">Failed Checks</span>
                      <div
                        style={{
                          fontSize: '1.3rem',
                          fontWeight: 700,
                          color: validationRun.failed_count > 0 ? 'var(--accent-rose)' : 'var(--text-primary)',
                        }}
                      >
                        {validationRun.failed_count}
                      </div>
                    </div>
                  </div>

                  {/* Checks Table */}
                  <div className="table-container">
                    <table className="data-table">
                      <thead>
                        <tr>
                          <th>Check Rule</th>
                          <th>Category</th>
                          <th>Status</th>
                          <th>Message & Remediation</th>
                        </tr>
                      </thead>
                      <tbody>
                        {validationRun.results_json.checks.map((chk, idx) => (
                          <tr key={idx}>
                            <td style={{ fontWeight: 600 }}>{chk.name}</td>
                            <td>
                              <span className="badge badge-info">{chk.category}</span>
                            </td>
                            <td>
                              <span
                                className={`badge ${
                                  chk.status === 'passed' ? 'badge-success' : 'badge-danger'
                                }`}
                              >
                                {chk.status}
                              </span>
                            </td>
                            <td>
                              <div style={{ fontSize: '0.85rem' }}>{chk.message}</div>
                              {chk.recommendation && (
                                <div style={{ fontSize: '0.78rem', color: 'var(--accent-amber)', marginTop: '0.2rem' }}>
                                  💡 {chk.recommendation}
                                </div>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="card empty-state">Select or create a data contract to view rules.</div>
          )}
        </div>
      </div>

      {/* Modal: Create Contract */}
      {isCreateOpen && (
        <div className="modal-overlay" onClick={() => setIsCreateOpen(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2 style={{ fontSize: '1.2rem', fontWeight: 600 }}>Define Data Contract</h2>
              <button
                onClick={() => setIsCreateOpen(false)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}
              >
                <X size={20} />
              </button>
            </div>

            <form onSubmit={handleCreateContract}>
              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                  Contract Name
                </label>
                <input
                  type="text"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  placeholder="e.g. Orders Ingestion SLA"
                  className="input-control"
                  required
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                  Description
                </label>
                <input
                  type="text"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  placeholder="Business context and compliance purpose"
                  className="input-control"
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                  Required Columns (comma-separated)
                </label>
                <input
                  type="text"
                  value={requiredCols}
                  onChange={(e) => setRequiredCols(e.target.value)}
                  placeholder="e.g. order_id, customer_id, amount"
                  className="input-control"
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                  Unique Columns (comma-separated)
                </label>
                <input
                  type="text"
                  value={uniqueCols}
                  onChange={(e) => setUniqueCols(e.target.value)}
                  placeholder="e.g. order_id, email"
                  className="input-control"
                />
              </div>

              <div style={{ marginBottom: '1rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                  Non-Nullable Columns (comma-separated)
                </label>
                <input
                  type="text"
                  value={nonNullableCols}
                  onChange={(e) => setNonNullableCols(e.target.value)}
                  placeholder="e.g. order_id, amount"
                  className="input-control"
                />
              </div>

              <div style={{ marginBottom: '1.5rem' }}>
                <label style={{ display: 'block', fontSize: '0.85rem', marginBottom: '0.3rem' }}>
                  Allowed Values JSON (Optional)
                </label>
                <textarea
                  value={allowedValuesJson}
                  onChange={(e) => setAllowedValuesJson(e.target.value)}
                  placeholder='e.g. {"status": ["PENDING", "COMPLETED", "CANCELLED"]}'
                  className="input-control font-mono"
                  rows={2}
                />
              </div>

              <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.75rem' }}>
                <button type="button" onClick={() => setIsCreateOpen(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary">
                  Save Contract
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
