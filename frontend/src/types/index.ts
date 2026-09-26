/* TypeScript interfaces matching the backend Pydantic schemas */

export type TaskStatus = 'backlog' | 'in_progress' | 'review' | 'done';

export interface Task {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  column_order: number;
  start_date: string | null;
  end_date: string | null;
  duration_days: number;
  is_blocked: boolean;
  prerequisite_count: number;
  dependent_count: number;
  created_at: string;
  updated_at: string;
}

export interface TaskCreate {
  title: string;
  description?: string;
  status?: TaskStatus;
  start_date?: string | null;
  end_date?: string | null;
  duration_days?: number;
}

export interface TaskUpdate {
  title?: string;
  description?: string;
  status?: TaskStatus;
  column_order?: number;
  start_date?: string | null;
  end_date?: string | null;
  duration_days?: number;
}

export interface Dependency {
  id: string;
  source_task_id: string;
  target_task_id: string;
  source_task_title: string;
  target_task_title: string;
  created_at: string;
}

export interface DependencyCreate {
  source_task_id: string;
  target_task_id: string;
}

export interface GraphNode {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  start_date: string | null;
  end_date: string | null;
  duration_days: number;
  is_blocked: boolean;
  column_order: number;
  on_critical_path?: boolean;
  prerequisite_ids: string[];
  dependent_ids: string[];
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  is_critical: boolean;
}

export interface GraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
  critical_path: string[];
  critical_path_duration: number;
  blocked_count: number;
  ready_count: number;
}

export interface ScheduleChange {
  task_id: string;
  task_title: string;
  old_start: string | null;
  old_end: string | null;
  new_start: string | null;
  new_end: string | null;
  shift_days: number;
}

export interface WhatIfResponse {
  affected_tasks: ScheduleChange[];
  total_affected: number;
  new_critical_path_duration: number | null;
}

export interface AISuggestion {
  source_task_id: string;
  source_task_title: string;
  target_task_id: string;
  target_task_title: string;
  confidence: number;
  direction: string;
  rationale: string;
}

export interface AISuggestResponse {
  suggestions: AISuggestion[];
  model_used: string;
  disclaimer: string;
}

export interface RiskFactor {
  factor: string;
  severity: 'low' | 'medium' | 'high';
}

export interface RiskItem {
  task_id: string;
  task_title: string;
  risk_score: number;
  factors: RiskFactor[];
  on_critical_path: boolean;
}

export interface RiskAnalysisResponse {
  risk_items: RiskItem[];
  high_risk_count: number;
  medium_risk_count: number;
  analysis_summary: string;
}

export interface HealthCheck {
  status: string;
  version: string;
  dag_nodes: number;
  dag_edges: number;
  gemini_available: boolean;
}

export type ViewMode = 'kanban' | 'dag' | 'split';

export type ToastType = 'success' | 'error' | 'warning' | 'info';

export interface Toast {
  id: string;
  type: ToastType;
  message: string;
}

// Column configuration for Kanban
export const COLUMNS: { id: TaskStatus; title: string; color: string }[] = [
  { id: 'backlog', title: 'Backlog', color: 'var(--status-backlog)' },
  { id: 'in_progress', title: 'In Progress', color: 'var(--status-in-progress)' },
  { id: 'review', title: 'Review', color: 'var(--status-review)' },
  { id: 'done', title: 'Done', color: 'var(--status-done)' },
];
