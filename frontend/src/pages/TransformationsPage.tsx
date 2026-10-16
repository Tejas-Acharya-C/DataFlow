import React, { useEffect, useState } from 'react';
import {
  Layers,
  Plus,
  Play,
  Save,
  Trash2,
  Eye,
  CheckCircle2,
  ArrowRight,
} from 'lucide-react';
import { api } from '../api/client';
import { Dataset, DatasetVersion } from '../types';

interface TransformationsPageProps {
  initialDatasetId?: string;
  initialVersionId?: string;
  onNavigateToDataset: (id: string) => void;
}

export const TransformationsPage: React.FC<TransformationsPageProps> = ({
  initialDatasetId,
  initialVersionId,
  onNavigateToDataset,
}) => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(initialDatasetId || '');
  const [versions, setVersions] = useState<DatasetVersion[]>([]);
  const [selectedVersionId, setSelectedVersionId] = useState(initialVersionId || '');

  // Operations list
  const [operations, setOperations] = useState<any[]>([]);
  const [opType, setOpType] = useState('rename_columns');

  // Operation specific builder states
  const [renameOld, setRenameOld] = useState('');
  const [renameNew, setRenameNew] = useState('');
  const [dropCol, setDropCol] = useState('');
  const [fillCol, setFillCol] = useState('');
  const [fillVal, setFillVal] = useState('');
  const [fillStrategy, setFillStrategy] = useState('constant');
  const [castCol, setCastCol] = useState('');
  const [castType, setCastType] = useState('int');
  const [filterCol, setFilterCol] = useState('');
  const [filterOp, setFilterOp] = useState('eq');
  const [filterVal, setFilterVal] = useState('');
  const [sortCol, setSortCol] = useState('');
  const [sortAsc, setSortAsc] = useState(true);
  const [trimCol, setTrimCol] = useState('');

  // Results
  const [previewResult, setPreviewResult] = useState<any | null>(null);
  const [applyResult, setApplyResult] = useState<any | null>(null);
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
      if (!selectedDatasetId && data.items.length > 0) {
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
      if (vList.length > 0 && !selectedVersionId) {
        setSelectedVersionId(vList[0].id);
      }
    } catch (err) {
      console.error(err);
    }
  };

  const addOperation = () => {
    let newOp: any = null;

    if (opType === 'rename_columns') {
      if (!renameOld || !renameNew) return alert('Specify both old and new column names');
      newOp = { op: 'rename_columns', mapping: { [renameOld]: renameNew } };
      setRenameOld('');
      setRenameNew('');
    } else if (opType === 'drop_columns') {
      if (!dropCol) return alert('Specify column to drop');
      newOp = { op: 'drop_columns', columns: [dropCol] };
      setDropCol('');
    } else if (opType === 'remove_duplicates') {
      newOp = { op: 'remove_duplicates' };
    } else if (opType === 'fill_missing') {
      if (!fillCol) return alert('Specify column');
      newOp = { op: 'fill_missing', columns: [fillCol], strategy: fillStrategy, value: fillVal };
      setFillCol('');
      setFillVal('');
    } else if (opType === 'cast_columns') {
      if (!castCol) return alert('Specify column');
      newOp = { op: 'cast_columns', conversions: { [castCol]: castType } };
      setCastCol('');
    } else if (opType === 'filter_rows') {
      if (!filterCol) return alert('Specify column');
      newOp = { op: 'filter_rows', column: filterCol, operator: filterOp, value: filterVal };
      setFilterCol('');
      setFilterVal('');
    } else if (opType === 'sort_rows') {
      if (!sortCol) return alert('Specify column');
      newOp = { op: 'sort_rows', by: [sortCol], ascending: [sortAsc] };
      setSortCol('');
    } else if (opType === 'trim_strings') {
      newOp = { op: 'trim_strings', columns: trimCol ? [trimCol] : null };
      setTrimCol('');
    }

    if (newOp) {
      setOperations([...operations, newOp]);
      setPreviewResult(null);
    }
  };

  const removeOp = (index: number) => {
    setOperations(operations.filter((_, i) => i !== index));
    setPreviewResult(null);
  };

  const handlePreview = async () => {
    if (!selectedDatasetId || !selectedVersionId || operations.length === 0) {
      alert('Select dataset version and add at least one operation.');
      return;
    }

    setLoading(true);
    try {
      const res = await api.previewTransformation({
        dataset_id: selectedDatasetId,
        version_id: selectedVersionId,
        operations,
      });
      setPreviewResult(res);
    } catch (err: any) {
      alert(err.message || 'Transformation preview failed');
    } finally {
      setLoading(false);
    }
  };

  const handleApply = async () => {
    if (!selectedDatasetId || !selectedVersionId || operations.length === 0) return;

    if (!confirm('This will create an immutable new dataset version. Proceed?')) return;

    setLoading(true);
    try {
      const res = await api.applyTransformation({
        dataset_id: selectedDatasetId,
        version_id: selectedVersionId,
        operations,
        reason: `Transformation pipeline (${operations.length} operations)`,
      });
      setApplyResult(res);
      loadVersions(selectedDatasetId);
    } catch (err: any) {
      alert(err.message || 'Failed to apply transformation');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h1 className="page-title">Safe Data Transformations</h1>
          <p className="page-subtitle">
            Construct reproducible cleaning and transformation pipelines that create immutable versions.
          </p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '380px 1fr', gap: '1.5rem' }}>
        {/* Pipeline Builder Sidebar */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* Target Version Selector */}
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.85rem' }}>
              Target Dataset & Version
            </h3>
            <div style={{ marginBottom: '0.75rem' }}>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Dataset
              </label>
              <select
                value={selectedDatasetId}
                onChange={(e) => {
                  setSelectedDatasetId(e.target.value);
                  setSelectedVersionId('');
                }}
                className="input-control"
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Source Version
              </label>
              <select
                value={selectedVersionId}
                onChange={(e) => setSelectedVersionId(e.target.value)}
                className="input-control"
              >
                {versions.map((v) => (
                  <option key={v.id} value={v.id}>
                    v{v.version_number} — {v.original_filename} ({v.row_count} rows)
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Add Operation Card */}
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.85rem' }}>
              Add Operation
            </h3>

            <div style={{ marginBottom: '1rem' }}>
              <select
                value={opType}
                onChange={(e) => setOpType(e.target.value)}
                className="input-control"
              >
                <option value="rename_columns">Rename Column</option>
                <option value="drop_columns">Drop Column</option>
                <option value="remove_duplicates">Remove Duplicate Rows</option>
                <option value="fill_missing">Fill Missing Values</option>
                <option value="cast_columns">Cast Column Type</option>
                <option value="filter_rows">Filter Rows</option>
                <option value="sort_rows">Sort Rows</option>
                <option value="trim_strings">Trim Strings & Hygiene</option>
              </select>
            </div>

            {/* Dynamic Inputs per Op */}
            {opType === 'rename_columns' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Old column name"
                  value={renameOld}
                  onChange={(e) => setRenameOld(e.target.value)}
                  className="input-control"
                />
                <input
                  type="text"
                  placeholder="New column name"
                  value={renameNew}
                  onChange={(e) => setRenameNew(e.target.value)}
                  className="input-control"
                />
              </div>
            )}

            {opType === 'drop_columns' && (
              <div style={{ marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Column to drop"
                  value={dropCol}
                  onChange={(e) => setDropCol(e.target.value)}
                  className="input-control"
                />
              </div>
            )}

            {opType === 'fill_missing' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Column name"
                  value={fillCol}
                  onChange={(e) => setFillCol(e.target.value)}
                  className="input-control"
                />
                <select
                  value={fillStrategy}
                  onChange={(e) => setFillStrategy(e.target.value)}
                  className="input-control"
                >
                  <option value="constant">Constant Value</option>
                  <option value="mean">Mean (numeric)</option>
                  <option value="median">Median (numeric)</option>
                  <option value="forward_fill">Forward Fill</option>
                </select>
                {fillStrategy === 'constant' && (
                  <input
                    type="text"
                    placeholder="Replacement value"
                    value={fillVal}
                    onChange={(e) => setFillVal(e.target.value)}
                    className="input-control"
                  />
                )}
              </div>
            )}

            {opType === 'cast_columns' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Column name"
                  value={castCol}
                  onChange={(e) => setCastCol(e.target.value)}
                  className="input-control"
                />
                <select
                  value={castType}
                  onChange={(e) => setCastType(e.target.value)}
                  className="input-control"
                >
                  <option value="int">Integer (int)</option>
                  <option value="float">Float (decimal)</option>
                  <option value="str">String (text)</option>
                  <option value="bool">Boolean</option>
                  <option value="datetime">Datetime</option>
                </select>
              </div>
            )}

            {opType === 'filter_rows' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Column name"
                  value={filterCol}
                  onChange={(e) => setFilterCol(e.target.value)}
                  className="input-control"
                />
                <select
                  value={filterOp}
                  onChange={(e) => setFilterOp(e.target.value)}
                  className="input-control"
                >
                  <option value="eq">Equal (==)</option>
                  <option value="neq">Not Equal (!=)</option>
                  <option value="gt">Greater Than (&gt;)</option>
                  <option value="gte">Greater or Equal (&gt;=)</option>
                  <option value="lt">Less Than (&lt;)</option>
                  <option value="lte">Less or Equal (&lt;=)</option>
                  <option value="is_not_null">Is Not Null</option>
                  <option value="contains">Contains Substring</option>
                </select>
                {filterOp !== 'is_not_null' && (
                  <input
                    type="text"
                    placeholder="Comparison value"
                    value={filterVal}
                    onChange={(e) => setFilterVal(e.target.value)}
                    className="input-control"
                  />
                )}
              </div>
            )}

            {opType === 'sort_rows' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Column name to sort by"
                  value={sortCol}
                  onChange={(e) => setSortCol(e.target.value)}
                  className="input-control"
                />
                <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem' }}>
                  <input
                    type="checkbox"
                    checked={sortAsc}
                    onChange={(e) => setSortAsc(e.target.checked)}
                  />
                  Sort Ascending
                </label>
              </div>
            )}

            {opType === 'trim_strings' && (
              <div style={{ marginBottom: '1rem' }}>
                <input
                  type="text"
                  placeholder="Optional column (blank for all)"
                  value={trimCol}
                  onChange={(e) => setTrimCol(e.target.value)}
                  className="input-control"
                />
              </div>
            )}

            <button className="btn btn-secondary btn-sm" style={{ width: '100%' }} onClick={addOperation}>
              <Plus size={14} /> Add Step
            </button>
          </div>

          {/* Configured Steps List */}
          <div className="card">
            <h3 style={{ fontSize: '0.95rem', fontWeight: 600, marginBottom: '0.85rem' }}>
              Pipeline Operations ({operations.length})
            </h3>

            {operations.length === 0 ? (
              <p style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                No steps added yet. Add an operation above.
              </p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                {operations.map((op, idx) => (
                  <div
                    key={idx}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '0.6rem 0.85rem',
                      background: 'var(--bg-tertiary)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: '0.82rem',
                    }}
                  >
                    <div>
                      <span className="badge badge-purple" style={{ marginRight: '0.5rem' }}>
                        {idx + 1}
                      </span>
                      <span style={{ fontWeight: 600 }}>{op.op}</span>
                    </div>
                    <button
                      onClick={() => removeOp(idx)}
                      style={{ background: 'transparent', border: 'none', color: 'var(--text-muted)', cursor: 'pointer' }}
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                ))}

                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem' }}>
                  <button
                    className="btn btn-secondary btn-sm"
                    style={{ flex: 1 }}
                    onClick={handlePreview}
                    disabled={loading}
                  >
                    <Eye size={14} /> Preview
                  </button>
                  <button
                    className="btn btn-primary btn-sm"
                    style={{ flex: 1 }}
                    onClick={handleApply}
                    disabled={loading}
                  >
                    <Save size={14} /> Apply Version
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Execution & Preview Output */}
        <div>
          {applyResult && (
            <div
              className="card"
              style={{
                marginBottom: '1.5rem',
                border: '1px solid rgba(16, 185, 129, 0.4)',
                background: 'rgba(16, 185, 129, 0.05)',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.5rem' }}>
                <CheckCircle2 size={20} color="var(--accent-emerald)" />
                <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--accent-emerald)' }}>
                  Immutable Version Created Successfully!
                </h3>
              </div>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.75rem' }}>
                Created <strong>v{applyResult.version_number}</strong> with {applyResult.row_count} rows and {applyResult.column_count} columns.
              </p>
              <button
                className="btn btn-primary btn-sm"
                onClick={() => onNavigateToDataset(selectedDatasetId)}
              >
                Inspect New Version in Dataset View <ArrowRight size={14} />
              </button>
            </div>
          )}

          {previewResult ? (
            <div className="card">
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '1.25rem',
                }}
              >
                <div>
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>Transformation Preview</h3>
                  <p style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>
                    Original: {previewResult.original_row_count} rows, {previewResult.original_column_count} cols →
                    Transformed: <strong>{previewResult.new_row_count} rows, {previewResult.new_column_count} cols</strong>
                  </p>
                </div>
                <span className="badge badge-success">Preview Clean</span>
              </div>

              <div className="table-container">
                <table className="data-table">
                  <thead>
                    <tr>
                      {previewResult.columns.map((c: string) => (
                        <th key={c}>{c}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {previewResult.preview_rows.map((row: any, idx: number) => (
                      <tr key={idx}>
                        {previewResult.columns.map((col: string) => (
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
            </div>
          ) : (
            <div className="card empty-state" style={{ minHeight: '300px', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              <Layers size={40} className="empty-icon" />
              <h3 style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>Preview Workspace</h3>
              <p>Configure transformation operations on the left and click "Preview" to inspect the resulting sample table before committing.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
