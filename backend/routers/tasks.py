"""
TaskFlow Pro — Task CRUD Router

Endpoints for creating, reading, updating, and deleting tasks.
All mutations sync with the in-memory DAG engine and log events.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Task, Dependency, EventLog
from schemas import (
    TaskCreate, TaskUpdate, TaskResponse,
    TaskReorderRequest, BulkReorderRequest, MessageResponse,
)

router = APIRouter(prefix="/api/tasks", tags=["Tasks"])


def _get_dag_engine():
    """Import here to avoid circular imports."""
    from main import dag_engine
    return dag_engine


def _enrich_task_response(task: Task, dag) -> dict:
    """Add computed fields (is_blocked, dependency counts) to task response."""
    return {
        "id": task.id,
        "title": task.title,
        "description": task.description or "",
        "status": task.status,
        "column_order": task.column_order,
        "start_date": task.start_date,
        "end_date": task.end_date,
        "duration_days": task.duration_days,
        "is_blocked": dag.is_blocked(task.id),
        "prerequisite_count": len(dag.get_prerequisites(task.id)),
        "dependent_count": len(dag.get_dependents(task.id)),
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


@router.get("", response_model=list[TaskResponse])
def list_tasks(
    status: Optional[str] = Query(None, pattern="^(backlog|in_progress|review|done)$"),
    db: Session = Depends(get_db),
):
    """List all tasks, optionally filtered by status."""
    dag = _get_dag_engine()
    query = db.query(Task)
    if status:
        query = query.filter(Task.status == status)
    query = query.order_by(Task.column_order, Task.created_at)
    tasks = query.all()
    return [_enrich_task_response(t, dag) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(task_id: str, db: Session = Depends(get_db)):
    """Get a single task by ID."""
    dag = _get_dag_engine()
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return _enrich_task_response(task, dag)


@router.post("", response_model=TaskResponse, status_code=201)
def create_task(data: TaskCreate, db: Session = Depends(get_db)):
    """Create a new task."""
    dag = _get_dag_engine()

    # Auto-calculate end_date if start_date and duration provided
    task_data = data.model_dump()
    if task_data.get("start_date") and not task_data.get("end_date"):
        from datetime import timedelta
        task_data["end_date"] = task_data["start_date"] + timedelta(
            days=task_data.get("duration_days", 1) - 1
        )

    # Get the max column_order for the status column
    max_order = db.query(Task.column_order).filter(
        Task.status == task_data["status"]
    ).order_by(Task.column_order.desc()).first()
    task_data["column_order"] = (max_order[0] + 1) if max_order else 0

    task = Task(**task_data)
    db.add(task)

    # Log event
    db.add(EventLog(
        event_type="task_created",
        payload={"task_id": task.id, "title": task.title},
    ))
    db.commit()
    db.refresh(task)

    # Sync with DAG engine
    from services.dag_engine import TaskNode
    dag.add_node(TaskNode(
        id=task.id,
        title=task.title,
        status=task.status,
        start_date=task.start_date,
        end_date=task.end_date,
        duration_days=task.duration_days,
        description=task.description or "",
        column_order=task.column_order,
    ))

    return _enrich_task_response(task, dag)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(task_id: str, data: TaskUpdate, db: Session = Depends(get_db)):
    """Update a task. Triggers schedule propagation if dates change."""
    dag = _get_dag_engine()

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    update_data = data.model_dump(exclude_unset=True)
    old_status = task.status
    dates_changed = False

    for key, value in update_data.items():
        if key in ("start_date", "end_date", "duration_days"):
            dates_changed = True
        setattr(task, key, value)

    # Auto-calculate end_date if duration changed
    if "duration_days" in update_data and task.start_date:
        from datetime import timedelta
        task.end_date = task.start_date + timedelta(days=task.duration_days - 1)
        dates_changed = True

    task.updated_at = datetime.utcnow()

    # Log event
    db.add(EventLog(
        event_type="task_updated",
        payload={
            "task_id": task_id,
            "changes": update_data,
            "old_status": old_status,
        },
    ))
    db.commit()
    db.refresh(task)

    # Sync with DAG engine
    dag.update_node(
        task_id,
        title=task.title,
        status=task.status,
        start_date=task.start_date,
        end_date=task.end_date,
        duration_days=task.duration_days,
        description=task.description or "",
        column_order=task.column_order,
    )

    # Propagate schedule if dates changed
    if dates_changed:
        changes = dag.apply_propagation(task_id)
        # Persist propagated changes to database
        for change in changes:
            dep_task = db.query(Task).filter(Task.id == change.task_id).first()
            if dep_task:
                dep_task.start_date = change.new_start
                dep_task.end_date = change.new_end
                dep_task.updated_at = datetime.utcnow()
        if changes:
            db.add(EventLog(
                event_type="schedule_propagated",
                payload={
                    "trigger_task_id": task_id,
                    "affected_count": len(changes),
                    "changes": [
                        {
                            "task_id": c.task_id,
                            "old_start": c.old_start.isoformat() if c.old_start else None,
                            "new_start": c.new_start.isoformat() if c.new_start else None,
                        }
                        for c in changes
                    ],
                },
            ))
            db.commit()

    # Re-evaluate blocked status for dependents if status changed
    if "status" in update_data and update_data["status"] == "done":
        # Moving a completed task backward triggers re-evaluation
        pass  # Blocked status is computed dynamically by the DAG engine

    return _enrich_task_response(task, dag)


@router.delete("/{task_id}", response_model=MessageResponse)
def delete_task(task_id: str, db: Session = Depends(get_db)):
    """Delete a task and all its dependency edges."""
    dag = _get_dag_engine()

    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    title = task.title
    db.delete(task)
    db.add(EventLog(
        event_type="task_deleted",
        payload={"task_id": task_id, "title": title},
    ))
    db.commit()

    # Remove from DAG engine
    dag.remove_node(task_id)

    return MessageResponse(message=f"Task '{title}' deleted")


@router.post("/reorder", response_model=MessageResponse)
def reorder_tasks(data: BulkReorderRequest, db: Session = Depends(get_db)):
    """Bulk update task positions after drag-and-drop."""
    dag = _get_dag_engine()

    for update in data.updates:
        task = db.query(Task).filter(Task.id == update.task_id).first()
        if task:
            old_status = task.status
            task.status = update.new_status
            task.column_order = update.new_order
            task.updated_at = datetime.utcnow()

            # Sync with DAG
            dag.update_node(
                task.id,
                status=update.new_status,
                column_order=update.new_order,
            )

            if old_status != update.new_status:
                db.add(EventLog(
                    event_type="status_changed",
                    payload={
                        "task_id": task.id,
                        "old_status": old_status,
                        "new_status": update.new_status,
                    },
                ))

    db.commit()
    return MessageResponse(message=f"Reordered {len(data.updates)} tasks")
