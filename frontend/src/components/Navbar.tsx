import React from 'react';
import {
  Database,
  BarChart3,
  FileCode2,
  GitBranch,
  History,
  Activity,
  Layers,
  Upload,
} from 'lucide-react';
import { SystemHealth } from '../types';

interface NavbarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
  health: SystemHealth | null;
  onOpenUpload: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  setActiveTab,
  health,
  onOpenUpload,
}) => {
  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: BarChart3 },
    { id: 'datasets', label: 'Datasets', icon: Database },
    { id: 'contracts', label: 'Data Contracts', icon: FileCode2 },
    { id: 'transformations', label: 'Transformations', icon: Layers },
    { id: 'versions', label: 'Version History', icon: GitBranch },
    { id: 'audit', label: 'Jobs & Audit', icon: History },
  ];

  return (
    <header className="navbar">
      <div className="brand-section">
        <div className="brand-logo">
          <Activity size={22} />
        </div>
        <div>
          <span className="brand-title">DataFlow</span>
        </div>
      </div>

      <nav className="nav-links">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`nav-item ${isActive ? 'active' : ''}`}
            >
              <Icon size={16} />
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      <div style={{ display: 'flex', alignItems: 'center', gap: '0.85rem' }}>
        <div
          className={`badge ${
            health?.status === 'ready' ? 'badge-success' : 'badge-warning'
          }`}
          title={`Database: ${health?.database || 'checking'}, Storage: ${health?.storage || 'checking'}`}
        >
          <span
            style={{
              width: '6px',
              height: '6px',
              borderRadius: '50%',
              backgroundColor: health?.status === 'ready' ? '#10B981' : '#F59E0B',
              display: 'inline-block',
            }}
          />
          {health?.status === 'ready' ? 'System Ready' : 'Connecting...'}
        </div>

        <button className="btn btn-primary btn-sm" onClick={onOpenUpload}>
          <Upload size={14} />
          <span>Upload CSV</span>
        </button>
      </div>
    </header>
  );
};
