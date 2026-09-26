/**
 * TaskFlow Pro — Global State Store (Zustand)
 *
 * Single source of truth for tasks, graph data, and UI state.
 * Handles API calls and optimistic updates.
 */

import { create } from 'zustand';
import { api } from '@/lib/api';
import type {
  Task,
  TaskCreate,
  TaskUpdate,
  GraphData,
  RiskItem,
  AISuggestion,
  Toast,
  ViewMode,
  TaskStatus,
  WhatIfResponse,
  ScheduleChange,
} from '@/types';

interface AppState {
  // Data
  tasks: Task[];
  graphData: GraphData | null;
  riskItems: RiskItem[];
  aiSuggestions: AISuggestion[];

  // UI State
  viewMode: ViewMode;
  selectedTaskId: string | null;
  isCreateModalOpen: boolean;
  isSidePanelOpen: boolean;
  sidePanelContent: 'task-detail' | 'ai-suggestions' | 'what-if' | null;
  toasts: Toast[];
  isLoading: boolean;
  whatIfResult: WhatIfResponse | null;

  // Actions
  setViewMode: (mode: ViewMode) => void;
  setSelectedTaskId: (id: string | null) => void;
  openCreateModal: () => void;
  closeCreateModal: () => void;
  openSidePanel: (content: 'task-detail' | 'ai-suggestions' | 'what-if') => void;
  closeSidePanel: () => void;
  addToast: (type: Toast['type'], message: string) => void;
  removeToast: (id: string) => void;

  // API Actions
  fetchTasks: () => Promise<void>;
  fetchGraph: () => Promise<void>;
  createTask: (data: TaskCreate) => Promise<void>;
  updateTask: (id: string, data: TaskUpdate) => Promise<void>;
  deleteTask: (id: string) => Promise<void>;
  moveTask: (taskId: string, newStatus: TaskStatus, newOrder: number) => Promise<void>;
  addDependency: (sourceId: string, targetId: string) => Promise<void>;
  removeDependency: (sourceId: string, targetId: string) => Promise<void>;
  fetchRiskAnalysis: () => Promise<void>;
  fetchAISuggestions: (taskId: string) => Promise<void>;
  runWhatIf: (taskId: string, newDuration?: number) => Promise<void>;
  clearWhatIf: () => void;
}

let toastCounter = 0;

export const useAppStore = create<AppState>((set, get) => ({
  // Initial State
  tasks: [],
  graphData: null,
  riskItems: [],
  aiSuggestions: [],
  viewMode: 'kanban',
  selectedTaskId: null,
  isCreateModalOpen: false,
  isSidePanelOpen: false,
  sidePanelContent: null,
  toasts: [],
  isLoading: true,
  whatIfResult: null,

  // UI Actions
  setViewMode: (mode) => set({ viewMode: mode }),

  setSelectedTaskId: (id) => set({ selectedTaskId: id }),

  openCreateModal: () => set({ isCreateModalOpen: true }),

  closeCreateModal: () => set({ isCreateModalOpen: false }),

  openSidePanel: (content) =>
    set({ isSidePanelOpen: true, sidePanelContent: content }),

  closeSidePanel: () =>
    set({ isSidePanelOpen: false, sidePanelContent: null, whatIfResult: null }),

  addToast: (type, message) => {
    const id = `toast-${++toastCounter}`;
    set((state) => ({
      toasts: [...state.toasts, { id, type, message }],
    }));
    // Auto-remove after 4 seconds
    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }));
    }, 4000);
  },

  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),

  // API Actions
  fetchTasks: async () => {
    try {
      const tasks = await api.getTasks();
      set({ tasks, isLoading: false });
    } catch (error) {
      set({ isLoading: false });
      get().addToast('error', `Failed to load tasks: ${error}`);
    }
  },

  fetchGraph: async () => {
    try {
      const graphData = await api.getGraph();
      set({ graphData });
    } catch (error) {
      get().addToast('error', `Failed to load graph: ${error}`);
    }
  },

  createTask: async (data) => {
    try {
      const task = await api.createTask(data);
      set((state) => ({ tasks: [...state.tasks, task] }));
      get().addToast('success', `Task "${task.title}" created`);
      get().closeCreateModal();
      get().fetchGraph();
    } catch (error) {
      get().addToast('error', `Failed to create task: ${error}`);
    }
  },

  updateTask: async (id, data) => {
    try {
      const updated = await api.updateTask(id, data);
      set((state) => ({
        tasks: state.tasks.map((t) => (t.id === id ? updated : t)),
      }));
      get().addToast('success', `Task updated`);
      // Refresh to get propagated changes
      get().fetchTasks();
      get().fetchGraph();
    } catch (error) {
      get().addToast('error', `Failed to update task: ${error}`);
    }
  },

  deleteTask: async (id) => {
    try {
      const task = get().tasks.find((t) => t.id === id);
      await api.deleteTask(id);
      set((state) => ({
        tasks: state.tasks.filter((t) => t.id !== id),
        selectedTaskId: state.selectedTaskId === id ? null : state.selectedTaskId,
      }));
      get().addToast('success', `Task "${task?.title}" deleted`);
      get().closeSidePanel();
      get().fetchGraph();
    } catch (error) {
      get().addToast('error', `Failed to delete task: ${error}`);
    }
  },

  moveTask: async (taskId, newStatus, newOrder) => {
    // Optimistic update
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === taskId ? { ...t, status: newStatus, column_order: newOrder } : t
      ),
    }));

    try {
      await api.reorderTasks([
        { task_id: taskId, new_status: newStatus, new_order: newOrder },
      ]);
      // Refresh to get updated blocked status
      get().fetchTasks();
      get().fetchGraph();
    } catch (error) {
      // Revert on error
      get().fetchTasks();
      get().addToast('error', `Failed to move task: ${error}`);
    }
  },

  addDependency: async (sourceId, targetId) => {
    try {
      await api.createDependency({
        source_task_id: sourceId,
        target_task_id: targetId,
      });
      get().addToast('success', 'Dependency added');
      get().fetchTasks();
      get().fetchGraph();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : String(error);
      if (message.includes('cycle')) {
        get().addToast('error', '🔄 Cannot add — this would create a cycle!');
      } else {
        get().addToast('error', `Failed to add dependency: ${message}`);
      }
    }
  },

  removeDependency: async (sourceId, targetId) => {
    try {
      await api.deleteDependencyByTasks(sourceId, targetId);
      get().addToast('success', 'Dependency removed');
      get().fetchTasks();
      get().fetchGraph();
    } catch (error) {
      get().addToast('error', `Failed to remove dependency: ${error}`);
    }
  },

  fetchRiskAnalysis: async () => {
    try {
      const result = await api.getRiskAnalysis();
      set({ riskItems: result.risk_items });
    } catch (error) {
      get().addToast('error', `Risk analysis failed: ${error}`);
    }
  },

  fetchAISuggestions: async (taskId) => {
    try {
      set({ aiSuggestions: [] });
      get().openSidePanel('ai-suggestions');
      const result = await api.suggestDependencies(taskId);
      set({ aiSuggestions: result.suggestions });
      if (result.suggestions.length === 0) {
        get().addToast('info', 'No dependency suggestions found');
      }
    } catch (error) {
      get().addToast('error', `AI suggestions failed: ${error}`);
    }
  },

  runWhatIf: async (taskId, newDuration) => {
    try {
      const result = await api.whatIf(taskId, newDuration);
      set({ whatIfResult: result });
      get().openSidePanel('what-if');
    } catch (error) {
      get().addToast('error', `What-If preview failed: ${error}`);
    }
  },

  clearWhatIf: () => set({ whatIfResult: null }),
}));
