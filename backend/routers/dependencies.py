"""
TaskFlow Pro — Dependencies Router

Endpoints for managing dependency edges between tasks.
Every edge addition goes through cycle detection before being committed.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Task, Dependency, EventLog
from schemas import DependencyCreate, DependencyResponse, MessageResponse

router = APIRouter(prefix="/api/dependencies", tags=["Dependencies"])


def _get_dag_engine():
    from main import dag_engine
    return dag_engine


@router.get("", response_model=list[DependencyResponse])
def list_dependencies(db: Session = Depends(get_db)):
    """List all dependency edges with task titles."""
    deps = db.query(Dependency).all()
    result = []
    for dep in deps:
        source = db.query(Task).filter(Task.id == dep.source_task_id).first()
        target = db.query(Task).filter(Task.id == dep.target_task_id).first()
        result.append({
            "id": dep.id,
            "source_task_id": dep.source_task_id,
            "target_task_id": dep.target_task_id,
            "source_task_title": source.title if source else "",
            "target_task_title": target.title if target else "",
            "created_at": dep.created_at,
        })
    return result


@router.post("", response_model=DependencyResponse, status_code=201)
def create_dependency(data: DependencyCreate, db: Session = Depends(get_db)):
    """
    Add a dependency edge: source_task is a prerequisite of target_task.

    The DAG engine performs a DFS reachability check before allowing
    the edge. If adding this edge would create a cycle, the request
    is rejected with a 409 Conflict response.
    """
    dag = _get_dag_engine()

    # Validate tasks exist
    source = db.query(Task).filter(Task.id == data.source_task_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Source task not found")

    target = db.query(Task).filter(Task.id == data.target_task_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target task not found")

    if data.source_task_id == data.target_task_id:
        raise HTTPException(status_code=400, detail="A task cannot depend on itself")

    # Check for existing dependency
    existing = db.query(Dependency).filter(
        Dependency.source_task_id == data.source_task_id,
        Dependency.target_task_id == data.target_task_id,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Dependency already exists")

    # Cycle detection via DAG engine
    if dag.would_create_cycle(data.source_task_id, data.target_task_id):
        raise HTTPException(
            status_code=409,
            detail="Adding this dependency would create a cycle. "
                   "Dependencies must form a Directed Acyclic Graph (DAG)."
        )

    # Add to DAG engine
    success = dag.add_edge(data.source_task_id, data.target_task_id)
    if not success:
        raise HTTPException(status_code=409, detail="Failed to add dependency edge")

    # Persist to database
    dep = Dependency(
        source_task_id=data.source_task_id,
        target_task_id=data.target_task_id,
    )
    db.add(dep)

    # Log event
    db.add(EventLog(
        event_type="dependency_added",
        payload={
            "dependency_id": dep.id,
            "source_task_id": data.source_task_id,
            "source_task_title": source.title,
            "target_task_id": data.target_task_id,
            "target_task_title": target.title,
        },
    ))

    # Propagate schedule if source has an end_date
    if source.end_date:
        changes = dag.apply_propagation(data.source_task_id)
        for change in changes:
            dep_task = db.query(Task).filter(Task.id == change.task_id).first()
            if dep_task:
                dep_task.start_date = change.new_start
                dep_task.end_date = change.new_end

    db.commit()
    db.refresh(dep)

    return {
        "id": dep.id,
        "source_task_id": dep.source_task_id,
        "target_task_id": dep.target_task_id,
        "source_task_title": source.title,
        "target_task_title": target.title,
        "created_at": dep.created_at,
    }


@router.delete("/{dependency_id}", response_model=MessageResponse)
def delete_dependency(dependency_id: str, db: Session = Depends(get_db)):
    """Remove a dependency edge."""
    dag = _get_dag_engine()

    dep = db.query(Dependency).filter(Dependency.id == dependency_id).first()
    if not dep:
        raise HTTPException(status_code=404, detail="Dependency not found")

    source_id = dep.source_task_id
    target_id = dep.target_task_id

    # Remove from DAG engine
    dag.remove_edge(source_id, target_id)

    # Remove from database
    db.delete(dep)
    db.add(EventLog(
        event_type="dependency_removed",
        payload={
            "dependency_id": dependency_id,
            "source_task_id": source_id,
            "target_task_id": target_id,
        },
    ))
    db.commit()

    return MessageResponse(message="Dependency removed")


@router.delete(
    "/by-tasks/{source_id}/{target_id}",
    response_model=MessageResponse,
)
def delete_dependency_by_tasks(
    source_id: str, target_id: str, db: Session = Depends(get_db)
):
    """Remove a dependency edge by source and target task IDs."""
    dag = _get_dag_engine()

    dep = db.query(Dependency).filter(
        Dependency.source_task_id == source_id,
        Dependency.target_task_id == target_id,
    ).first()
    if not dep:
        raise HTTPException(status_code=404, detail="Dependency not found")

    dag.remove_edge(source_id, target_id)
    db.delete(dep)
    db.add(EventLog(
        event_type="dependency_removed",
        payload={
            "source_task_id": source_id,
            "target_task_id": target_id,
        },
    ))
    db.commit()

    return MessageResponse(message="Dependency removed")
