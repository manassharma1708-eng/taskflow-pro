"""
TaskFlow Pro — Seed Data

Populates the database with 10 realistic engineering tasks and
dependencies that demonstrate the DAG engine's capabilities:
- Diamond dependency pattern (convergent paths)
- Sequential chains
- Parallel independent branches
- Blocked/ready states
- Critical path

Project scenario: Building a REST API microservice
"""

from datetime import date, timedelta
from sqlalchemy.orm import Session

from models import Task, Dependency, EventLog
from database import engine, Base, SessionLocal


# ─── Task definitions ─────────────────────────────────────────

SEED_TASKS = [
    {
        "id": "task-001",
        "title": "Design Database Schema",
        "description": "Define PostgreSQL tables, relationships, indexes, and constraints for the user and order management system. Include ERD diagram.",
        "status": "done",
        "column_order": 0,
        "start_date": date(2026, 9, 26),
        "end_date": date(2026, 9, 27),
        "duration_days": 2,
    },
    {
        "id": "task-002",
        "title": "Set Up Project Scaffold",
        "description": "Initialize FastAPI project with folder structure, linting (ruff), formatting (black), and CI pipeline. Include Docker setup.",
        "status": "done",
        "column_order": 1,
        "start_date": date(2026, 9, 26),
        "end_date": date(2026, 9, 26),
        "duration_days": 1,
    },
    {
        "id": "task-003",
        "title": "Implement User Authentication",
        "description": "Build JWT-based auth with login, register, refresh token, and password reset endpoints. Include rate limiting.",
        "status": "in_progress",
        "column_order": 0,
        "start_date": date(2026, 9, 28),
        "end_date": date(2026, 9, 30),
        "duration_days": 3,
    },
    {
        "id": "task-004",
        "title": "Build CRUD API for Orders",
        "description": "Create, read, update, delete endpoints for the orders resource with pagination, filtering, and sorting support.",
        "status": "in_progress",
        "column_order": 1,
        "start_date": date(2026, 9, 28),
        "end_date": date(2026, 9, 30),
        "duration_days": 3,
    },
    {
        "id": "task-005",
        "title": "Write Integration Tests",
        "description": "End-to-end API tests covering auth flows, order CRUD, edge cases, and error handling. Target 80% coverage.",
        "status": "backlog",
        "column_order": 0,
        "start_date": date(2026, 10, 1),
        "end_date": date(2026, 10, 3),
        "duration_days": 3,
    },
    {
        "id": "task-006",
        "title": "Implement Payment Gateway",
        "description": "Integrate Stripe payment processing with webhook handlers for payment success, failure, and refund events.",
        "status": "backlog",
        "column_order": 1,
        "start_date": date(2026, 10, 1),
        "end_date": date(2026, 10, 3),
        "duration_days": 3,
    },
    {
        "id": "task-007",
        "title": "Build Notification Service",
        "description": "Email and in-app notification system for order status updates, payment confirmations, and system alerts.",
        "status": "backlog",
        "column_order": 2,
        "start_date": date(2026, 10, 4),
        "end_date": date(2026, 10, 5),
        "duration_days": 2,
    },
    {
        "id": "task-008",
        "title": "Performance Optimization",
        "description": "Database query optimization, Redis caching layer, connection pooling, and API response time benchmarking.",
        "status": "backlog",
        "column_order": 3,
        "start_date": date(2026, 10, 4),
        "end_date": date(2026, 10, 6),
        "duration_days": 3,
    },
    {
        "id": "task-009",
        "title": "Security Audit & Hardening",
        "description": "OWASP top 10 review, SQL injection testing, XSS prevention, CORS configuration, and dependency vulnerability scan.",
        "status": "backlog",
        "column_order": 4,
        "start_date": date(2026, 10, 6),
        "end_date": date(2026, 10, 8),
        "duration_days": 3,
    },
    {
        "id": "task-010",
        "title": "Deploy to Production",
        "description": "Kubernetes deployment with health checks, auto-scaling, monitoring (Prometheus + Grafana), and rollback strategy.",
        "status": "backlog",
        "column_order": 5,
        "start_date": date(2026, 10, 9),
        "end_date": date(2026, 10, 10),
        "duration_days": 2,
    },
]

# ─── Dependency definitions (source is prerequisite of target) ─

SEED_DEPENDENCIES = [
    # Schema must be done before API work
    {"id": "dep-001", "source_task_id": "task-001", "target_task_id": "task-003"},  # Schema -> Auth
    {"id": "dep-002", "source_task_id": "task-001", "target_task_id": "task-004"},  # Schema -> Orders

    # Scaffold must be done before any coding
    {"id": "dep-003", "source_task_id": "task-002", "target_task_id": "task-003"},  # Scaffold -> Auth
    {"id": "dep-004", "source_task_id": "task-002", "target_task_id": "task-004"},  # Scaffold -> Orders

    # Diamond pattern: Auth and Orders both needed before Tests
    {"id": "dep-005", "source_task_id": "task-003", "target_task_id": "task-005"},  # Auth -> Tests
    {"id": "dep-006", "source_task_id": "task-004", "target_task_id": "task-005"},  # Orders -> Tests

    # Orders needed before Payment
    {"id": "dep-007", "source_task_id": "task-004", "target_task_id": "task-006"},  # Orders -> Payment

    # Payment and Auth both needed before Notifications
    {"id": "dep-008", "source_task_id": "task-006", "target_task_id": "task-007"},  # Payment -> Notifications
    {"id": "dep-009", "source_task_id": "task-003", "target_task_id": "task-007"},  # Auth -> Notifications

    # Tests and Payment needed before Performance
    {"id": "dep-010", "source_task_id": "task-005", "target_task_id": "task-008"},  # Tests -> Performance
    {"id": "dep-011", "source_task_id": "task-006", "target_task_id": "task-008"},  # Payment -> Performance

    # Performance and Notifications needed before Security Audit
    {"id": "dep-012", "source_task_id": "task-008", "target_task_id": "task-009"},  # Performance -> Security
    {"id": "dep-013", "source_task_id": "task-007", "target_task_id": "task-009"},  # Notifications -> Security

    # Security must pass before Production Deploy
    {"id": "dep-014", "source_task_id": "task-009", "target_task_id": "task-010"},  # Security -> Deploy
]


def seed_database():
    """Populate database with sample data. Idempotent — skips if data exists."""
    db = SessionLocal()
    try:
        # Check if data already exists
        existing = db.query(Task).count()
        if existing > 0:
            print(f"Database already has {existing} tasks. Skipping seed.")
            return

        # Create tables
        Base.metadata.create_all(bind=engine)

        # Insert tasks
        for task_data in SEED_TASKS:
            task = Task(**task_data)
            db.add(task)

        db.flush()

        # Insert dependencies
        for dep_data in SEED_DEPENDENCIES:
            dep = Dependency(**dep_data)
            db.add(dep)

        # Insert seed event
        db.add(EventLog(
            event_type="database_seeded",
            payload={"task_count": len(SEED_TASKS), "dependency_count": len(SEED_DEPENDENCIES)},
            actor="system",
        ))

        db.commit()
        print(f"[OK] Seeded {len(SEED_TASKS)} tasks and {len(SEED_DEPENDENCIES)} dependencies")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_database()
