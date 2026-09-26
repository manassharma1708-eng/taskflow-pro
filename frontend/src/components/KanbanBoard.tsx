'use client';

import { useAppStore } from '@/stores/taskStore';
import { COLUMNS, type TaskStatus } from '@/types';
import TaskCard from './TaskCard';
import {
  DndContext,
  DragOverlay,
  closestCorners,
  PointerSensor,
  useSensor,
  useSensors,
  type DragStartEvent,
  type DragEndEvent,
  type DragOverEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { useDroppable } from '@dnd-kit/core';
import { useState } from 'react';

function DroppableColumn({
  id,
  title,
  color,
  count,
  children,
}: {
  id: string;
  title: string;
  color: string;
  count: number;
  children: React.ReactNode;
}) {
  const { isOver, setNodeRef } = useDroppable({ id });

  return (
    <div
      ref={setNodeRef}
      className={`kanban-column ${isOver ? 'drag-over' : ''}`}
      id={`column-${id}`}
    >
      <div className="kanban-column-header">
        <div className="kanban-column-title">
          <span className="kanban-column-dot" style={{ backgroundColor: color }} />
          {title}
        </div>
        <span className="kanban-column-count">{count}</span>
      </div>
      <div className="kanban-column-cards">
        {children}
      </div>
    </div>
  );
}

export default function KanbanBoard() {
  const { tasks, moveTask, riskItems } = useAppStore();
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: { distance: 5 },
    })
  );

  const getTasksByColumn = (status: TaskStatus) =>
    tasks
      .filter((t) => t.status === status)
      .sort((a, b) => a.column_order - b.column_order);

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveId(null);

    if (!over) return;

    const taskId = active.id as string;
    const overId = over.id as string;

    // Determine the target column
    let targetColumn: TaskStatus | null = null;

    // Check if dropped on a column directly
    const column = COLUMNS.find((c) => c.id === overId);
    if (column) {
      targetColumn = column.id;
    } else {
      // Dropped on another task card — find which column it belongs to
      const overTask = tasks.find((t) => t.id === overId);
      if (overTask) {
        targetColumn = overTask.status;
      }
    }

    if (targetColumn) {
      const columnTasks = getTasksByColumn(targetColumn);
      const newOrder = columnTasks.length;
      moveTask(taskId, targetColumn, newOrder);
    }
  };

  const handleDragOver = (_event: DragOverEvent) => {
    // Could add visual indicators here
  };

  const activeTask = activeId ? tasks.find((t) => t.id === activeId) : null;

  // Build risk map for quick lookup
  const riskMap = new Map(riskItems.map((r) => [r.task_id, r]));

  return (
    <>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCorners}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
        onDragOver={handleDragOver}
      >
        <div className="kanban-board">
          {COLUMNS.map((column) => {
            const columnTasks = getTasksByColumn(column.id);
            return (
              <DroppableColumn
                key={column.id}
                id={column.id}
                title={column.title}
                color={column.color}
                count={columnTasks.length}
              >
                <SortableContext
                  items={columnTasks.map((t) => t.id)}
                  strategy={verticalListSortingStrategy}
                >
                  {columnTasks.length === 0 ? (
                    <div className="kanban-column-empty">
                      Drop tasks here
                    </div>
                  ) : (
                    columnTasks.map((task) => (
                      <TaskCard
                        key={task.id}
                        task={task}
                        risk={riskMap.get(task.id)}
                        isDragging={activeId === task.id}
                      />
                    ))
                  )}
                </SortableContext>
              </DroppableColumn>
            );
          })}
        </div>

        <DragOverlay>
          {activeTask ? (
            <TaskCard
              task={activeTask}
              risk={riskMap.get(activeTask.id)}
              isDragging={false}
              isOverlay
            />
          ) : null}
        </DragOverlay>
      </DndContext>
    </>
  );
}
