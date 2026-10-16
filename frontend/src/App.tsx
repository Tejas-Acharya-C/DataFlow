import React, { useEffect, useState } from 'react';
import { Navbar } from './components/Navbar';
import { UploadModal } from './components/UploadModal';
import { DashboardPage } from './pages/DashboardPage';
import { DatasetsPage } from './pages/DatasetsPage';
import { DatasetDetailPage } from './pages/DatasetDetailPage';
import { ContractsPage } from './pages/ContractsPage';
import { TransformationsPage } from './pages/TransformationsPage';
import { VersionsPage } from './pages/VersionsPage';
import { AuditJobsPage } from './pages/AuditJobsPage';
import { api } from './api/client';
import { SystemHealth } from './types';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<string>('dashboard');
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [transformDatasetId, setTransformDatasetId] = useState<string | undefined>();
  const [transformVersionId, setTransformVersionId] = useState<string | undefined>();
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [isUploadOpen, setIsUploadOpen] = useState(false);
  const [uploadTargetDatasetId, setUploadTargetDatasetId] = useState<string | undefined>();

  useEffect(() => {
    checkHealth();
    const interval = setInterval(checkHealth, 30000);
    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    try {
      const h = await api.getHealth();
      setHealth(h);
    } catch {
      setHealth({
        status: 'disconnected',
        database: 'unreachable',
        storage: 'unknown',
        version: '0.1.0',
        environment: 'offline',
      });
    }
  };

  const handleNavigate = (tab: string, datasetId?: string) => {
    if (datasetId) {
      setSelectedDatasetId(datasetId);
      setActiveTab('dataset-detail');
    } else {
      setActiveTab(tab);
    }
  };

  const handleSelectDataset = (id: string) => {
    setSelectedDatasetId(id);
    setActiveTab('dataset-detail');
  };

  const handleNavigateToTransform = (dsId: string, vId: string) => {
    setTransformDatasetId(dsId);
    setTransformVersionId(vId);
    setActiveTab('transformations');
  };

  const handleOpenUploadNew = () => {
    setUploadTargetDatasetId(undefined);
    setIsUploadOpen(true);
  };

  const handleOpenUploadVersion = (datasetId: string) => {
    setUploadTargetDatasetId(datasetId);
    setIsUploadOpen(true);
  };

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab === 'dataset-detail' ? 'datasets' : activeTab}
        setActiveTab={(tab) => {
          setSelectedDatasetId(null);
          setActiveTab(tab);
        }}
        health={health}
        onOpenUpload={handleOpenUploadNew}
      />

      <main className="main-content">
        {activeTab === 'dashboard' && (
          <DashboardPage
            onNavigate={handleNavigate}
            onOpenUpload={handleOpenUploadNew}
          />
        )}

        {activeTab === 'datasets' && (
          <DatasetsPage
            onSelectDataset={handleSelectDataset}
            onOpenUpload={handleOpenUploadNew}
          />
        )}

        {activeTab === 'dataset-detail' && selectedDatasetId && (
          <DatasetDetailPage
            datasetId={selectedDatasetId}
            onBack={() => {
              setSelectedDatasetId(null);
              setActiveTab('datasets');
            }}
            onNavigateToTransform={handleNavigateToTransform}
            onNavigateToContracts={() => setActiveTab('contracts')}
            onOpenUploadVersion={handleOpenUploadVersion}
          />
        )}

        {activeTab === 'contracts' && <ContractsPage />}

        {activeTab === 'transformations' && (
          <TransformationsPage
            initialDatasetId={transformDatasetId}
            initialVersionId={transformVersionId}
            onNavigateToDataset={handleSelectDataset}
          />
        )}

        {activeTab === 'versions' && <VersionsPage />}

        {activeTab === 'audit' && <AuditJobsPage />}
      </main>

      <UploadModal
        isOpen={isUploadOpen}
        existingDatasetId={uploadTargetDatasetId}
        onClose={() => setIsUploadOpen(false)}
        onSuccess={() => {
          checkHealth();
          if (activeTab === 'dataset-detail' && selectedDatasetId) {
            // refresh detail
            setSelectedDatasetId(selectedDatasetId);
          }
        }}
      />
    </div>
  );
};

export default App;
