'use client';

import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { useAppStore } from '@/stores/taskStore';
import type { Task, RiskItem } from '@/types';

interface TaskCardProps {
  task: Task;
  risk?: RiskItem;
  isDragging: boolean;
  isOverlay?: boolean;
}

export default function TaskCard({ task, risk, isDragging, isOverlay }: TaskCardProps) {
  const { setSelectedTaskId, openSidePanel, fetchAISuggestions } = useAppStore();

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id: task.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.4 : 1,
  };

  const handleClick = () => {
    setSelectedTaskId(task.id);
    openSidePanel('task-detail');
  };

  const handleAISuggest = (e: React.MouseEvent) => {
    e.stopPropagation();
    setSelectedTaskId(task.id);
    fetchAISuggestions(task.id);
  };

  const statusClass = task.is_blocked ? 'blocked' : task.status === 'done' ? '' : 'ready';
  const totalDeps = task.prerequisite_count + task.dependent_count;

  const formatDate = (d: string | null) => {
    if (!d) return null;
    const date = new Date(d);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  };

  return (
    <div
      ref={isOverlay ? undefined : setNodeRef}
      style={isOverlay ? {} : style}
      {...(isOverlay ? {} : attributes)}
      {...(isOverlay ? {} : listeners)}
      className={`task-card ${statusClass} ${isDragging ? 'dragging' : ''}`}
      onClick={handleClick}
      id={`task-card-${task.id}`}
    >
      <div className="task-card-title">{task.title}</div>

      {task.description && (
        <div className="task-card-description">{task.description}</div>
      )}

      <div className="task-card-meta">
        <div className="task-card-badges">
          {task.is_blocked && (
            <span className="badge badge-blocked">🔒 Blocked</span>
          )}
          {!task.is_blocked && task.status !== 'done' && task.prerequisite_count > 0 && (
            <span className="badge badge-ready">✓ Ready</span>
          )}
          {totalDeps > 0 && (
            <span className="badge badge-deps">
              ⬡ {totalDeps} dep{totalDeps > 1 ? 's' : ''}
            </span>
          )}
          <span className="badge badge-duration">
            {task.duration_days}d
          </span>
          {risk && risk.risk_score >= 60 && (
            <span className="badge badge-risk-high">⚠ High Risk</span>
          )}
          {risk && risk.risk_score >= 30 && risk.risk_score < 60 && (
            <span className="badge badge-risk-medium">⚡ At Risk</span>
          )}
        </div>

        {(task.start_date || task.end_date) && (
          <div className="task-card-dates">
            {formatDate(task.start_date)}
            {task.start_date && task.end_date && ' → '}
            {formatDate(task.end_date)}
          </div>
        )}
      </div>

      {/* Quick action: AI suggestion button */}
      <button
        className="btn btn-ghost btn-sm"
        onClick={handleAISuggest}
        style={{
          position: 'absolute',
          top: '8px',
          right: '8px',
          opacity: 0,
          transition: 'opacity var(--transition-fast)',
          fontSize: '14px',
        }}
        onMouseEnter={(e) => { (e.target as HTMLElement).style.opacity = '1'; }}
        onMouseLeave={(e) => { (e.target as HTMLElement).style.opacity = '0'; }}
        title="Get AI suggestions"
      >
        ✨
      </button>
    </div>
  );
}
