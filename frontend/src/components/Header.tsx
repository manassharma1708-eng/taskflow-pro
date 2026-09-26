'use client';

import { useAppStore } from '@/stores/taskStore';
import type { ViewMode } from '@/types';

export default function Header() {
  const { viewMode, setViewMode, graphData, openCreateModal } = useAppStore();

  const navItems: { id: ViewMode; label: string; icon: string }[] = [
    { id: 'kanban', label: 'Board', icon: '▦' },
    { id: 'dag', label: 'Graph', icon: '◈' },
    { id: 'split', label: 'Split', icon: '⊞' },
  ];

  return (
    <header className="header">
      <div className="header-logo">
        <div className="header-logo-icon">TF</div>
        <span className="header-logo-text">TaskFlow Pro</span>
        <span className="header-logo-badge">DAG-Powered</span>
      </div>

      <nav className="header-nav">
        {navItems.map((item) => (
          <button
            key={item.id}
            className={`header-nav-btn ${viewMode === item.id ? 'active' : ''}`}
            onClick={() => setViewMode(item.id)}
            id={`nav-${item.id}`}
          >
            <span>{item.icon}</span>
            {item.label}
          </button>
        ))}
      </nav>

      <div className="header-actions">
        {graphData && (
          <div className="view-stats">
            <span className="view-stat">
              <span className="view-stat-value" style={{ color: 'var(--state-blocked)' }}>
                {graphData.blocked_count}
              </span>
              blocked
            </span>
            <span className="view-stat">
              <span className="view-stat-value" style={{ color: 'var(--state-ready)' }}>
                {graphData.ready_count}
              </span>
              ready
            </span>
            <span className="view-stat">
              <span className="view-stat-value" style={{ color: 'var(--critical-color)' }}>
                {graphData.critical_path_duration}d
              </span>
              critical path
            </span>
          </div>
        )}
        <button className="btn btn-primary" onClick={openCreateModal} id="btn-create-task">
          + New Task
        </button>
      </div>
    </header>
  );
}
