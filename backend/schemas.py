"""
TaskFlow Pro — Pydantic Schemas

Request/response models for all API endpoints.
Separated from ORM models for clean API boundaries.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import date, datetime


# ─── Task Schemas ──────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    status: str = Field(default="backlog", pattern="^(backlog|in_progress|review|done)$")
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: int = Field(default=1, ge=1, le=365)


class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(backlog|in_progress|review|done)$")
    column_order: Optional[int] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: Optional[int] = Field(None, ge=1, le=365)


class TaskResponse(BaseModel):
    id: str
    title: str
    description: str
    status: str
    column_order: int
    start_date: Optional[date]
    end_date: Optional[date]
    duration_days: int
    is_blocked: bool = False
    prerequisite_count: int = 0
    dependent_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TaskReorderRequest(BaseModel):
    task_id: str
    new_status: str = Field(..., pattern="^(backlog|in_progress|review|done)$")
    new_order: int = Field(..., ge=0)


class BulkReorderRequest(BaseModel):
    updates: list[TaskReorderRequest]


# ─── Dependency Schemas ────────────────────────────────────────

class DependencyCreate(BaseModel):
    source_task_id: str = Field(..., description="The prerequisite task ID")
    target_task_id: str = Field(..., description="The dependent task ID")


class DependencyResponse(BaseModel):
    id: str
    source_task_id: str
    target_task_id: str
    source_task_title: str = ""
    target_task_title: str = ""
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Graph Schemas ─────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    title: str
    description: str = ""
    status: str
    start_date: Optional[date]
    end_date: Optional[date]
    duration_days: int
    is_blocked: bool
    column_order: int = 0
    prerequisite_ids: list[str] = []
    dependent_ids: list[str] = []


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    is_critical: bool = False


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    critical_path: list[str]
    critical_path_duration: int = 0
    blocked_count: int = 0
    ready_count: int = 0


# ─── What-If Schemas ──────────────────────────────────────────

class WhatIfRequest(BaseModel):
    task_id: str
    new_duration_days: Optional[int] = Field(None, ge=1, le=365)
    new_end_date: Optional[date] = None


class ScheduleChange(BaseModel):
    task_id: str
    task_title: str
    old_start: Optional[date]
    old_end: Optional[date]
    new_start: Optional[date]
    new_end: Optional[date]
    shift_days: int = 0


class WhatIfResponse(BaseModel):
    affected_tasks: list[ScheduleChange]
    total_affected: int
    new_critical_path_duration: Optional[int] = None


# ─── AI Schemas ────────────────────────────────────────────────

class AISuggestion(BaseModel):
    source_task_id: str
    source_task_title: str
    target_task_id: str
    target_task_title: str
    confidence: int = Field(..., ge=0, le=100)
    direction: str  # "prerequisite" or "dependent"
    rationale: str


class AISuggestRequest(BaseModel):
    task_id: str


class AISuggestResponse(BaseModel):
    suggestions: list[AISuggestion]
    model_used: str = ""
    disclaimer: str = "AI suggestions are advisory only. All recommendations require human review and validation."


class RiskFactor(BaseModel):
    factor: str
    severity: str  # "low", "medium", "high"


class RiskItem(BaseModel):
    task_id: str
    task_title: str
    risk_score: int = Field(..., ge=0, le=100)
    factors: list[RiskFactor]
    on_critical_path: bool = False


class RiskAnalysisResponse(BaseModel):
    risk_items: list[RiskItem]
    high_risk_count: int = 0
    medium_risk_count: int = 0
    analysis_summary: str = ""


# ─── Event Log Schema ─────────────────────────────────────────

class EventLogResponse(BaseModel):
    id: int
    event_type: str
    payload: dict
    actor: str
    timestamp: datetime

    model_config = {"from_attributes": True}


# ─── Generic Response ─────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str
    success: bool = True
