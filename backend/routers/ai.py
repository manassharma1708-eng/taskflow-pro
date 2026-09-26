"""
TaskFlow Pro — AI Router

Endpoints for Gemini-powered dependency suggestions and risk analysis.
All AI features are advisory only — no direct graph mutations.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import Task
from schemas import (
    AISuggestRequest, AISuggestResponse, AISuggestion,
    RiskAnalysisResponse, RiskItem, RiskFactor,
)
from services.gemini_service import suggest_dependencies, analyze_risk
from config import settings

router = APIRouter(prefix="/api/ai", tags=["AI"])


def _get_dag_engine():
    from main import dag_engine
    return dag_engine


@router.post("/suggest-dependencies", response_model=AISuggestResponse)
async def get_dependency_suggestions(
    data: AISuggestRequest,
    db: Session = Depends(get_db),
):
    """
    Get AI-powered dependency suggestions for a task.

    Sends the task info + existing task summaries to Gemini,
    which returns structured suggestions with confidence scores.

    Follows human-in-the-loop principle: suggestions are displayed
    in a side panel for the user to Accept or Reject individually.
    """
    task = db.query(Task).filter(Task.id == data.task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if not settings.gemini_available:
        return AISuggestResponse(
            suggestions=[],
            model_used="none",
            disclaimer="AI features require a Gemini API key. Set GEMINI_API_KEY in your .env file.",
        )

    # Get all other tasks as context
    all_tasks = db.query(Task).filter(Task.id != data.task_id).all()
    existing = [
        {
            "id": t.id,
            "title": t.title,
            "description": t.description or "",
            "status": t.status,
        }
        for t in all_tasks
    ]

    raw_suggestions = await suggest_dependencies(
        new_task_title=task.title,
        new_task_description=task.description or "",
        existing_tasks=existing,
    )

    suggestions = []
    for s in raw_suggestions:
        direction = s.get("direction", "prerequisite")
        if direction == "prerequisite":
            source_id = s["existing_task_id"]
            target_id = data.task_id
            source_title = s["existing_task_title"]
            target_title = task.title
        else:
            source_id = data.task_id
            target_id = s["existing_task_id"]
            source_title = task.title
            target_title = s["existing_task_title"]

        suggestions.append(AISuggestion(
            source_task_id=source_id,
            source_task_title=source_title,
            target_task_id=target_id,
            target_task_title=target_title,
            confidence=s["confidence"],
            direction=direction,
            rationale=s.get("rationale", ""),
        ))

    return AISuggestResponse(
        suggestions=suggestions,
        model_used=settings.GEMINI_MODEL,
    )


@router.get("/risk-analysis", response_model=RiskAnalysisResponse)
def get_risk_analysis():
    """
    Analyze the DAG structure to identify risk indicators.

    Risk factors are computed deterministically from graph topology:
    - Critical path membership
    - High fan-in (many prerequisites)
    - High fan-out (many dependents)
    - Missing schedule dates
    - Short/vague task titles

    The core dependency engine remains fully deterministic.
    """
    dag = _get_dag_engine()
    graph_data = dag.get_graph_data()

    risk_items_raw = analyze_risk(
        nodes=graph_data["nodes"],
        edges=graph_data["edges"],
        critical_path=graph_data["critical_path"],
    )

    risk_items = []
    for item in risk_items_raw:
        risk_items.append(RiskItem(
            task_id=item["task_id"],
            task_title=item["task_title"],
            risk_score=item["risk_score"],
            factors=[
                RiskFactor(factor=f["factor"], severity=f["severity"])
                for f in item["factors"]
            ],
            on_critical_path=item.get("on_critical_path", False),
        ))

    high_risk = sum(1 for r in risk_items if r.risk_score >= 60)
    medium_risk = sum(1 for r in risk_items if 30 <= r.risk_score < 60)

    summary = f"{len(risk_items)} tasks analyzed. "
    if high_risk > 0:
        summary += f"{high_risk} high-risk tasks identified. "
    if medium_risk > 0:
        summary += f"{medium_risk} medium-risk tasks. "
    summary += "Focus on tasks with high fan-in on the critical path."

    return RiskAnalysisResponse(
        risk_items=risk_items,
        high_risk_count=high_risk,
        medium_risk_count=medium_risk,
        analysis_summary=summary,
    )
