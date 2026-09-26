"""
TaskFlow Pro — SQLAlchemy ORM Models

Three primary tables:
- tasks: Project tasks with status, dates, and ordering
- dependencies: Directed edges between tasks (source is prerequisite of target)
- event_log: Append-only audit trail for all mutations
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, Integer, Date, DateTime,
    JSON, ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship

from database import Base


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Task(Base):
    """A project task displayed on the Kanban board and DAG graph."""
    __tablename__ = "tasks"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    title = Column(String(255), nullable=False)
    description = Column(Text, default="")
    status = Column(String(20), default="backlog", nullable=False)
    column_order = Column(Integer, default=0)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    duration_days = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships — a task can be a source (prerequisite) or target (dependent)
    dependencies_as_source = relationship(
        "Dependency",
        foreign_keys="Dependency.source_task_id",
        back_populates="source_task",
        cascade="all, delete-orphan",
    )
    dependencies_as_target = relationship(
        "Dependency",
        foreign_keys="Dependency.target_task_id",
        back_populates="target_task",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Task(id={self.id[:8]}, title='{self.title}', status='{self.status}')>"


class Dependency(Base):
    """A directed edge: source_task is a prerequisite of target_task."""
    __tablename__ = "dependencies"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    source_task_id = Column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_task_id = Column(
        String(36),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "source_task_id", "target_task_id",
            name="uq_dependency_pair"
        ),
    )

    source_task = relationship(
        "Task",
        foreign_keys=[source_task_id],
        back_populates="dependencies_as_source",
    )
    target_task = relationship(
        "Task",
        foreign_keys=[target_task_id],
        back_populates="dependencies_as_target",
    )

    def __repr__(self) -> str:
        return f"<Dependency({self.source_task_id[:8]} -> {self.target_task_id[:8]})>"


class EventLog(Base):
    """Append-only audit trail capturing every mutation for undo support."""
    __tablename__ = "event_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(50), nullable=False)
    payload = Column(JSON, nullable=False)
    actor = Column(String(100), default="user")
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<EventLog(id={self.id}, type='{self.event_type}')>"
