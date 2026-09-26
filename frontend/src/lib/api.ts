/**
 * TaskFlow Pro — API Client
 *
 * Centralized HTTP client for all backend API calls.
 * Uses fetch with consistent error handling.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;

  const config: RequestInit = {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  };

  const response = await fetch(url, config);

  if (!response.ok) {
    const error = await response.json().catch(() => ({
      detail: `HTTP ${response.status}: ${response.statusText}`,
    }));
    throw new Error(error.detail || 'Request failed');
  }

  return response.json();
}

// ─── Task Endpoints ──────────────────────────────────────────

import type {
  Task,
  TaskCreate,
  TaskUpdate,
  Dependency,
  DependencyCreate,
  GraphData,
  WhatIfResponse,
  AISuggestResponse,
  RiskAnalysisResponse,
  HealthCheck,
} from '@/types';

export const api = {
  // Health
  health: () => request<HealthCheck>('/api/health'),

  // Tasks
  getTasks: (status?: string) => {
    const params = status ? `?status=${status}` : '';
    return request<Task[]>(`/api/tasks${params}`);
  },

  getTask: (id: string) => request<Task>(`/api/tasks/${id}`),

  createTask: (data: TaskCreate) =>
    request<Task>('/api/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  updateTask: (id: string, data: TaskUpdate) =>
    request<Task>(`/api/tasks/${id}`, {
      method: 'PATCH',
      body: JSON.stringify(data),
    }),

  deleteTask: (id: string) =>
    request<{ message: string }>(`/api/tasks/${id}`, {
      method: 'DELETE',
    }),

  reorderTasks: (updates: { task_id: string; new_status: string; new_order: number }[]) =>
    request<{ message: string }>('/api/tasks/reorder', {
      method: 'POST',
      body: JSON.stringify({ updates }),
    }),

  // Dependencies
  getDependencies: () => request<Dependency[]>('/api/dependencies'),

  createDependency: (data: DependencyCreate) =>
    request<Dependency>('/api/dependencies', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  deleteDependency: (id: string) =>
    request<{ message: string }>(`/api/dependencies/${id}`, {
      method: 'DELETE',
    }),

  deleteDependencyByTasks: (sourceId: string, targetId: string) =>
    request<{ message: string }>(`/api/dependencies/by-tasks/${sourceId}/${targetId}`, {
      method: 'DELETE',
    }),

  // Graph
  getGraph: () => request<GraphData>('/api/graph'),

  whatIf: (taskId: string, newDurationDays?: number, newEndDate?: string) =>
    request<WhatIfResponse>('/api/graph/what-if', {
      method: 'POST',
      body: JSON.stringify({
        task_id: taskId,
        new_duration_days: newDurationDays,
        new_end_date: newEndDate,
      }),
    }),

  // AI
  suggestDependencies: (taskId: string) =>
    request<AISuggestResponse>('/api/ai/suggest-dependencies', {
      method: 'POST',
      body: JSON.stringify({ task_id: taskId }),
    }),

  getRiskAnalysis: () => request<RiskAnalysisResponse>('/api/ai/risk-analysis'),

  // Events
  getEvents: (limit = 50) =>
    request<Array<{ id: number; event_type: string; payload: Record<string, unknown>; actor: string; timestamp: string }>>(
      `/api/events?limit=${limit}`
    ),
};
