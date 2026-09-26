'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/stores/taskStore';
import Header from '@/components/Header';
import KanbanBoard from '@/components/KanbanBoard';
import DagView from '@/components/DagView';
import CreateTaskModal from '@/components/CreateTaskModal';
import SidePanel from '@/components/SidePanel';
import ToastContainer from '@/components/ToastContainer';

export default function Home() {
  const {
    viewMode,
    isCreateModalOpen,
    isSidePanelOpen,
    isLoading,
    fetchTasks,
    fetchGraph,
    fetchRiskAnalysis,
  } = useAppStore();

  useEffect(() => {
    fetchTasks();
    fetchGraph();
    fetchRiskAnalysis();
  }, [fetchTasks, fetchGraph, fetchRiskAnalysis]);

  return (
    <div className="app-layout">
      <Header />

      <div className="app-main">
        <div className="app-content">
          {isLoading ? (
            <div className="loading-overlay">
              <div className="spinner spinner-lg" />
              <p>Loading TaskFlow Pro...</p>
            </div>
          ) : (
            <>
              {viewMode === 'kanban' && <KanbanBoard />}
              {viewMode === 'dag' && <DagView />}
              {viewMode === 'split' && (
                <div style={{ display: 'flex', gap: 'var(--space-4)', height: '100%' }}>
                  <div style={{ flex: 1, overflow: 'auto' }}>
                    <KanbanBoard />
                  </div>
                  <div style={{ flex: 1 }}>
                    <DagView />
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {isSidePanelOpen && <SidePanel />}
      </div>

      {isCreateModalOpen && <CreateTaskModal />}
      <ToastContainer />
    </div>
  );
}
