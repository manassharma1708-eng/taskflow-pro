'use client';

import { useState } from 'react';
import { useAppStore } from '@/stores/taskStore';
import type { TaskCreate } from '@/types';

export default function CreateTaskModal() {
  const { createTask, closeCreateModal } = useAppStore();

  const [form, setForm] = useState<TaskCreate>({
    title: '',
    description: '',
    status: 'backlog',
    start_date: null,
    end_date: null,
    duration_days: 1,
  });

  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.title.trim()) return;

    setIsSubmitting(true);
    await createTask({
      ...form,
      start_date: form.start_date || null,
      end_date: form.end_date || null,
    });
    setIsSubmitting(false);
  };

  return (
    <div className="modal-overlay" onClick={closeCreateModal}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2 className="modal-title">Create New Task</h2>
          <button className="modal-close" onClick={closeCreateModal} id="btn-close-modal">
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label className="form-label">Title *</label>
            <input
              className="form-input"
              type="text"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="e.g., Implement User Authentication"
              autoFocus
              required
              id="input-task-title"
            />
          </div>

          <div className="form-group">
            <label className="form-label">Description</label>
            <textarea
              className="form-textarea"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="Describe the task scope, requirements, and acceptance criteria..."
              rows={3}
              id="input-task-description"
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Status</label>
              <select
                className="form-select"
                value={form.status}
                onChange={(e) => setForm({ ...form, status: e.target.value as TaskCreate['status'] })}
                id="select-task-status"
              >
                <option value="backlog">Backlog</option>
                <option value="in_progress">In Progress</option>
                <option value="review">Review</option>
                <option value="done">Done</option>
              </select>
            </div>

            <div className="form-group">
              <label className="form-label">Duration (days)</label>
              <input
                className="form-input"
                type="number"
                min={1}
                max={365}
                value={form.duration_days}
                onChange={(e) => setForm({ ...form, duration_days: parseInt(e.target.value) || 1 })}
                id="input-task-duration"
              />
            </div>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label className="form-label">Start Date</label>
              <input
                className="form-input"
                type="date"
                value={form.start_date || ''}
                onChange={(e) => setForm({ ...form, start_date: e.target.value || null })}
                id="input-task-start-date"
              />
            </div>

            <div className="form-group">
              <label className="form-label">End Date</label>
              <input
                className="form-input"
                type="date"
                value={form.end_date || ''}
                onChange={(e) => setForm({ ...form, end_date: e.target.value || null })}
                id="input-task-end-date"
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: 'var(--space-3)', justifyContent: 'flex-end', marginTop: 'var(--space-6)' }}>
            <button type="button" className="btn btn-secondary" onClick={closeCreateModal}>
              Cancel
            </button>
            <button
              type="submit"
              className="btn btn-primary btn-lg"
              disabled={!form.title.trim() || isSubmitting}
              id="btn-submit-task"
            >
              {isSubmitting ? (
                <><span className="spinner" /> Creating...</>
              ) : (
                'Create Task'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
