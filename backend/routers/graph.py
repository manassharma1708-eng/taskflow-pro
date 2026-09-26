"""
TaskFlow Pro — Graph & What-If Router

Endpoints for graph visualization data, what-if impact preview,
and schedule propagation.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database import get_db
from schemas import GraphResponse, WhatIfRequest, WhatIfResponse, ScheduleChange

router = APIRouter(prefix="/api/graph", tags=["Graph"])


def _get_dag_engine():
    from main import dag_engine
    return dag_engine


@router.get("", response_model=GraphResponse)
def get_graph():
    """
    Get full graph structure for frontend visualization.

    Returns all nodes with computed properties (blocked status,
    critical path membership), all edges, and the critical path.
    """
    dag = _get_dag_engine()
    data = dag.get_graph_data()
    return GraphResponse(**data)


@router.post("/what-if", response_model=WhatIfResponse)
def what_if_preview(data: WhatIfRequest):
    """
    Preview the downstream impact of a hypothetical schedule change
    WITHOUT modifying the actual graph.

    Operates on a deep copy of the DAG engine, applies the change,
    runs propagation, and returns the projected date shifts.

    This is the "What-If Impact Preview" described in the synopsis.
    """
    dag = _get_dag_engine()

    changes = dag.what_if_preview(
        task_id=data.task_id,
        new_duration_days=data.new_duration_days,
        new_end_date=data.new_end_date,
    )

    affected = [
        ScheduleChange(
            task_id=c.task_id,
            task_title=c.task_title,
            old_start=c.old_start,
            old_end=c.old_end,
            new_start=c.new_start,
            new_end=c.new_end,
            shift_days=c.shift_days,
        )
        for c in changes
    ]

    # Compute new critical path duration on the copy
    new_cp_duration = None
    if changes:
        # Re-run critical path on a fresh what-if
        from services.dag_engine import DAGEngine, TaskNode
        engine_copy = DAGEngine()
        for tid, node in dag._nodes.items():
            engine_copy.add_node(TaskNode(
                id=node.id, title=node.title, status=node.status,
                start_date=node.start_date, end_date=node.end_date,
                duration_days=node.duration_days,
            ))
        for src, tgts in dag._forward.items():
            for tgt in tgts:
                engine_copy._forward[src].add(tgt)
                engine_copy._reverse[tgt].add(src)

        node = engine_copy._nodes.get(data.task_id)
        if node and data.new_duration_days:
            node.duration_days = data.new_duration_days
        _, new_cp_duration = engine_copy.compute_critical_path()

    return WhatIfResponse(
        affected_tasks=affected,
        total_affected=len(affected),
        new_critical_path_duration=new_cp_duration,
    )
