'use client';

import { useState } from 'react';
import { useAppStore } from '@/stores/taskStore';
import type { TaskUpdate, TaskStatus } from '@/types';

export default function SidePanel() {
  const {
    selectedTaskId,
    tasks,
    graphData,
    aiSuggestions,
    whatIfResult,
    sidePanelContent,
    closeSidePanel,
    updateTask,
    deleteTask,
    addDependency,
    removeDependency,
    runWhatIf,
    clearWhatIf,
    riskItems,
  } = useAppStore();

  const task = tasks.find((t) => t.id === selectedTaskId);
  const risk = riskItems.find((r) => r.task_id === selectedTaskId);

  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<TaskUpdate>({});
  const [whatIfDuration, setWhatIfDuration] = useState(task?.duration_days || 1);
  const [depTargetId, setDepTargetId] = useState('');

  if (!task) return null;

  const handleEdit = () => {
    setEditForm({
      title: task.title,
      description: task.description,
      status: task.status,
      duration_days: task.duration_days,
      start_date: task.start_date,
      end_date: task.end_date,
    });
    setIsEditing(true);
  };

  const handleSave = async () => {
    await updateTask(task.id, editForm);
    setIsEditing(false);
  };

  // Get task's dependencies from graph data
  const prereqs = graphData?.nodes.filter(
    (n) => graphData.edges.some((e) => e.source === n.id && e.target === task.id)
  ) || [];

  const dependents = graphData?.nodes.filter(
    (n) => graphData.edges.some((e) => e.source === task.id && e.target === n.id)
  ) || [];

  const otherTasks = tasks.filter((t) => t.id !== task.id);

  const formatDate = (d: string | null) => {
    if (!d) return '—';
    return new Date(d).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="side-panel">
      <div className="side-panel-header">
        <h3 style={{ fontSize: 'var(--text-lg)', fontWeight: 700 }}>
          {sidePanelContent === 'ai-suggestions' ? '✨ AI Suggestions' :
           sidePanelContent === 'what-if' ? '🔮 What-If Preview' :
           'Task Details'}
        </h3>
        <button className="modal-close" onClick={closeSidePanel}>✕</button>
      </div>

      <div className="side-panel-body">
        {/* ─── Task Detail View ─────────────────────────────── */}
        {sidePanelContent === 'task-detail' && (
          <>
            {!isEditing ? (
              <>
                <h2 style={{ fontSize: 'var(--text-xl)', fontWeight: 700, marginBottom: 'var(--space-2)' }}>
                  {task.title}
                </h2>

                <div className="task-card-badges" style={{ marginBottom: 'var(--space-4)' }}>
                  <span className="badge" style={{
                    background: `var(--status-${task.status}-bg)`,
                    color: `var(--status-${task.status})`,
                    border: `1px solid var(--status-${task.status})`,
                  }}>
                    {task.status.replace('_', ' ')}
                  </span>
                  {task.is_blocked && <span className="badge badge-blocked">🔒 Blocked</span>}
                  {risk && risk.risk_score >= 60 && <span className="badge badge-risk-high">⚠ Risk: {risk.risk_score}</span>}
                  {risk && risk.on_critical_path && <span className="badge badge-critical">🔥 Critical Path</span>}
                </div>

                {task.description && (
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 'var(--space-5)' }}>
                    {task.description}
                  </p>
                )}

                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 'var(--space-3)', marginBottom: 'var(--space-5)' }}>
                  <div style={{ background: 'var(--bg-glass)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginBottom: 2 }}>Duration</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontWeight: 600 }}>{task.duration_days} day{task.duration_days > 1 ? 's' : ''}</div>
                  </div>
                  <div style={{ background: 'var(--bg-glass)', padding: 'var(--space-3)', borderRadius: 'var(--radius-md)' }}>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)', marginBottom: 2 }}>Dates</div>
                    <div style={{ fontSize: 'var(--text-xs)', fontFamily: 'var(--font-mono)' }}>
                      {formatDate(task.start_date)} → {formatDate(task.end_date)}
                    </div>
                  </div>
                </div>

                {/* Dependencies Section */}
                <div style={{ marginBottom: 'var(--space-5)' }}>
                  <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--space-3)' }}>
                    Prerequisites ({prereqs.length})
                  </h4>
                  {prereqs.length === 0 ? (
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>No prerequisites</p>
                  ) : (
                    prereqs.map((p) => (
                      <div key={p.id} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: 'var(--space-2) var(--space-3)', background: 'var(--bg-glass)',
                        borderRadius: 'var(--radius-sm)', marginBottom: 'var(--space-2)',
                        fontSize: 'var(--text-sm)',
                      }}>
                        <span>{p.title}</span>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => removeDependency(p.id, task.id)}
                          title="Remove dependency"
                        >✕</button>
                      </div>
                    ))
                  )}
                </div>

                <div style={{ marginBottom: 'var(--space-5)' }}>
                  <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--space-3)' }}>
                    Dependents ({dependents.length})
                  </h4>
                  {dependents.length === 0 ? (
                    <p style={{ fontSize: 'var(--text-xs)', color: 'var(--text-tertiary)' }}>No dependents</p>
                  ) : (
                    dependents.map((d) => (
                      <div key={d.id} style={{
                        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                        padding: 'var(--space-2) var(--space-3)', background: 'var(--bg-glass)',
                        borderRadius: 'var(--radius-sm)', marginBottom: 'var(--space-2)',
                        fontSize: 'var(--text-sm)',
                      }}>
                        <span>{d.title}</span>
                        <button
                          className="btn btn-ghost btn-sm"
                          onClick={() => removeDependency(task.id, d.id)}
                          title="Remove dependency"
                        >✕</button>
                      </div>
                    ))
                  )}
                </div>

                {/* Add dependency */}
                <div style={{ marginBottom: 'var(--space-5)' }}>
                  <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--space-3)' }}>
                    Add Prerequisite
                  </h4>
                  <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <select
                      className="form-select"
                      value={depTargetId}
                      onChange={(e) => setDepTargetId(e.target.value)}
                      style={{ flex: 1 }}
                    >
                      <option value="">Select a task...</option>
                      {otherTasks.map((t) => (
                        <option key={t.id} value={t.id}>{t.title}</option>
                      ))}
                    </select>
                    <button
                      className="btn btn-secondary"
                      disabled={!depTargetId}
                      onClick={() => {
                        if (depTargetId) {
                          addDependency(depTargetId, task.id);
                          setDepTargetId('');
                        }
                      }}
                    >Add</button>
                  </div>
                </div>

                {/* Risk factors */}
                {risk && risk.factors.length > 0 && (
                  <div style={{ marginBottom: 'var(--space-5)' }}>
                    <h4 style={{ fontSize: 'var(--text-sm)', fontWeight: 600, marginBottom: 'var(--space-3)' }}>
                      ⚠ Risk Factors
                    </h4>
                    {risk.factors.map((f, i) => (
                      <div key={i} style={{
                        fontSize: 'var(--text-xs)', color: 'var(--text-secondary)',
                        padding: 'var(--space-2)', background: 'var(--bg-glass)',
                        borderRadius: 'var(--radius-sm)', marginBottom: 'var(--space-1)',
                        borderLeft: `2px solid var(--risk-${f.severity})`,
                        paddingLeft: 'var(--space-3)',
                      }}>
                        {f.factor}
                      </div>
                    ))}
                  </div>
                )}
              </>
            ) : (
              /* Edit mode */
              <>
                <div className="form-group">
                  <label className="form-label">Title</label>
                  <input
                    className="form-input"
                    value={editForm.title || ''}
                    onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  />
                </div>
                <div className="form-group">
                  <label className="form-label">Description</label>
                  <textarea
                    className="form-textarea"
                    value={editForm.description || ''}
                    onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                    rows={3}
                  />
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Status</label>
                    <select
                      className="form-select"
                      value={editForm.status || ''}
                      onChange={(e) => setEditForm({ ...editForm, status: e.target.value as TaskStatus })}
                    >
                      <option value="backlog">Backlog</option>
                      <option value="in_progress">In Progress</option>
                      <option value="review">Review</option>
                      <option value="done">Done</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Duration</label>
                    <input
                      className="form-input"
                      type="number"
                      min={1}
                      value={editForm.duration_days || 1}
                      onChange={(e) => setEditForm({ ...editForm, duration_days: parseInt(e.target.value) || 1 })}
                    />
                  </div>
                </div>
                <div className="form-row">
                  <div className="form-group">
                    <label className="form-label">Start Date</label>
                    <input
                      className="form-input"
                      type="date"
                      value={editForm.start_date || ''}
                      onChange={(e) => setEditForm({ ...editForm, start_date: e.target.value || null })}
                    />
                  </div>
                  <div className="form-group">
                    <label className="form-label">End Date</label>
                    <input
                      className="form-input"
                      type="date"
                      value={editForm.end_date || ''}
                      onChange={(e) => setEditForm({ ...editForm, end_date: e.target.value || null })}
                    />
                  </div>
                </div>
              </>
            )}
          </>
        )}

        {/* ─── AI Suggestions View ─────────────────────────── */}
        {sidePanelContent === 'ai-suggestions' && (
          <>
            <div className="ai-disclaimer">
              🤖 AI suggestions are advisory only — human review required
            </div>

            {aiSuggestions.length === 0 ? (
              <div className="loading-overlay">
                <div className="spinner" />
                <p style={{ fontSize: 'var(--text-sm)' }}>Analyzing dependencies...</p>
              </div>
            ) : (
              aiSuggestions.map((s, i) => (
                <div key={i} className="ai-suggestion-card">
                  <div className="ai-suggestion-header">
                    <div className="ai-suggestion-arrow">
                      <span>{s.source_task_title}</span>
                      <span style={{ color: 'var(--accent-primary)' }}>→</span>
                      <span>{s.target_task_title}</span>
                    </div>
                    <span className={`ai-confidence ${s.confidence >= 70 ? 'high' : s.confidence >= 40 ? 'medium' : 'low'}`}>
                      {s.confidence}%
                    </span>
                  </div>
                  <div className="ai-suggestion-rationale">{s.rationale}</div>
                  <div className="ai-suggestion-actions">
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => addDependency(s.source_task_id, s.target_task_id)}
                    >
                      ✓ Accept
                    </button>
                    <button className="btn btn-ghost btn-sm">
                      ✕ Reject
                    </button>
                  </div>
                </div>
              ))
            )}
          </>
        )}

        {/* ─── What-If Preview View ────────────────────────── */}
        {sidePanelContent === 'what-if' && (
          <>
            {!whatIfResult ? (
              <div style={{ marginBottom: 'var(--space-4)' }}>
                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', marginBottom: 'var(--space-4)' }}>
                  Preview the impact of changing <strong>{task.title}</strong>&apos;s duration without committing changes.
                </p>
                <div className="form-group">
                  <label className="form-label">New Duration (days)</label>
                  <input
                    className="form-input"
                    type="number"
                    min={1}
                    value={whatIfDuration}
                    onChange={(e) => setWhatIfDuration(parseInt(e.target.value) || 1)}
                  />
                </div>
                <button
                  className="btn btn-primary"
                  onClick={() => runWhatIf(task.id, whatIfDuration)}
                >
                  🔮 Run What-If Preview
                </button>
              </div>
            ) : (
              <div className="what-if-panel">
                <div className="what-if-title">
                  🔮 Impact Preview — {whatIfResult.total_affected} task{whatIfResult.total_affected !== 1 ? 's' : ''} affected
                </div>

                {whatIfResult.affected_tasks.length === 0 ? (
                  <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)' }}>
                    No downstream tasks would be affected by this change.
                  </p>
                ) : (
                  whatIfResult.affected_tasks.map((change) => (
                    <div key={change.task_id} className="what-if-change">
                      <span className="what-if-task-name">{change.task_title}</span>
                      <span className="what-if-shift positive">
                        +{change.shift_days}d
                      </span>
                    </div>
                  ))
                )}

                <div style={{ marginTop: 'var(--space-4)', display: 'flex', gap: 'var(--space-3)' }}>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => {
                      updateTask(task.id, { duration_days: whatIfDuration });
                      clearWhatIf();
                      closeSidePanel();
                    }}
                  >
                    ✓ Apply Changes
                  </button>
                  <button className="btn btn-secondary btn-sm" onClick={clearWhatIf}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>

      {/* ─── Footer Actions ──────────────────────────────── */}
      {sidePanelContent === 'task-detail' && (
        <div className="side-panel-footer">
          {isEditing ? (
            <>
              <button className="btn btn-secondary" onClick={() => setIsEditing(false)}>Cancel</button>
              <button className="btn btn-primary" onClick={handleSave}>Save Changes</button>
            </>
          ) : (
            <>
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => {
                  setWhatIfDuration(task.duration_days);
                  clearWhatIf();
                  useAppStore.getState().openSidePanel('what-if');
                }}
              >
                🔮 What-If
              </button>
              <button className="btn btn-danger btn-sm" onClick={() => deleteTask(task.id)}>
                Delete
              </button>
              <button className="btn btn-primary" onClick={handleEdit}>
                Edit Task
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
