"""
TaskFlow Pro — FastAPI Application Entry Point

Initializes the application, database, in-memory DAG engine,
and registers all API routers.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from database import init_db, SessionLocal
from models import Task, Dependency
from services.dag_engine import DAGEngine, TaskNode
from seed import seed_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Global DAG engine instance — the in-memory graph
dag_engine = DAGEngine()


def _sync_dag_from_db():
    """Load all tasks and dependencies from the database into the DAG engine."""
    db = SessionLocal()
    try:
        tasks = db.query(Task).all()
        deps = db.query(Dependency).all()

        task_records = [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status,
                "start_date": t.start_date,
                "end_date": t.end_date,
                "duration_days": t.duration_days,
                "description": t.description or "",
                "column_order": t.column_order,
            }
            for t in tasks
        ]
        dep_records = [
            {
                "source_task_id": d.source_task_id,
                "target_task_id": d.target_task_id,
            }
            for d in deps
        ]

        dag_engine.load_from_db_records(task_records, dep_records)

        logger.info(
            f"DAG engine loaded: {dag_engine.node_count} tasks, "
            f"{dag_engine.edge_count} dependencies"
        )

        # Compute and log critical path
        cp, cp_duration = dag_engine.compute_critical_path()
        if cp:
            cp_titles = [
                dag_engine.get_node(tid).title
                for tid in cp
                if dag_engine.get_node(tid)
            ]
            logger.info(
                f"Critical path ({cp_duration} days): {' → '.join(cp_titles)}"
            )

    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — init DB and load DAG on startup."""
    logger.info("=" * 60)
    logger.info(f"  {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"  Database: {settings.DATABASE_URL}")
    logger.info(f"  Gemini AI: {'enabled' if settings.gemini_available else 'disabled (no API key)'}")
    logger.info("=" * 60)

    # Initialize database tables
    init_db()

    # Seed sample data
    seed_database()

    # Load graph into memory
    _sync_dag_from_db()

    yield

    logger.info("TaskFlow Pro shutting down.")


# ─── Create FastAPI Application ───────────────────────────────

app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.DESCRIPTION,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# ─── CORS Middleware ──────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Register Routers ────────────────────────────────────────

from routers.tasks import router as tasks_router
from routers.dependencies import router as deps_router
from routers.graph import router as graph_router
from routers.ai import router as ai_router

app.include_router(tasks_router)
app.include_router(deps_router)
app.include_router(graph_router)
app.include_router(ai_router)


# ─── Health Check ─────────────────────────────────────────────

@app.get("/api/health", tags=["Health"])
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "dag_nodes": dag_engine.node_count,
        "dag_edges": dag_engine.edge_count,
        "gemini_available": settings.gemini_available,
    }


@app.get("/api/events", tags=["Events"])
def get_events(limit: int = 50):
    """Get recent event log entries."""
    from models import EventLog
    db = SessionLocal()
    try:
        events = db.query(EventLog).order_by(
            EventLog.timestamp.desc()
        ).limit(limit).all()
        return [
            {
                "id": e.id,
                "event_type": e.event_type,
                "payload": e.payload,
                "actor": e.actor,
                "timestamp": e.timestamp,
            }
            for e in events
        ]
    finally:
        db.close()


# ─── Run with Uvicorn ─────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True,
    )
