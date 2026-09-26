# TaskFlow Pro

**Dependency-Aware Kanban Board with DAG Engine & AI-Powered Insights**

A graph-first project management tool that replaces traditional isolated Kanban cards with an intelligent dependency graph. The DAG (Directed Acyclic Graph) is the authoritative source of truth — the Kanban board is a synchronized projection.

![TaskFlow Pro](https://img.shields.io/badge/status-active-brightgreen) ![Python](https://img.shields.io/badge/python-3.12+-blue) ![Next.js](https://img.shields.io/badge/next.js-15-black) ![FastAPI](https://img.shields.io/badge/fastapi-0.115+-teal)

---

## ✨ Key Features

- **Kanban Board** — Drag-and-drop task cards across Backlog, In Progress, Review, and Done columns
- **Interactive DAG Visualization** — See your project's dependency graph with auto-layout, critical path highlighting, and animated flow edges
- **Cycle Detection** — DFS reachability check prevents circular dependencies before they're created
- **Schedule Propagation** — BFS propagation uses MAX (not SUM) of converging parent delays to prevent double-counting (diamond dependency pattern)
- **What-If Impact Preview** — Preview downstream schedule impacts before committing changes
- **Blocked/Ready State Machine** — Tasks automatically show blocked/ready status based on prerequisite completion
- **Critical Path Analysis** — Dynamic programming over topological sort identifies the longest path through your project
- **AI Dependency Suggestions** — Google Gemini analyzes tasks and suggests likely dependencies with confidence scores
- **Risk Heatmap** — Deterministic risk analysis based on fan-in, fan-out, critical path membership, and schedule gaps
- **Event Log** — Append-only audit trail for all mutations

---

## 🚀 Quick Start (2 commands)

### Prerequisites
- **Python 3.12+** 
- **Node.js 18+**

### 1. Backend

```bash
cd backend
python -m venv venv
# Windows
.\venv\Scripts\activate
# macOS/Linux
source venv/bin/activate

pip install -r requirements.txt
python main.py
```

The backend starts at **http://localhost:8000** with:
- Auto-created SQLite database (zero configuration)
- 10 sample tasks with 14 dependencies pre-seeded
- Interactive API docs at **http://localhost:8000/docs**

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000** — you're ready!

---

## 🐳 Docker Setup (PostgreSQL)

For production-like setup with PostgreSQL:

```bash
# Copy environment template
cp .env.example .env
# (Optional) Add your Gemini API key to .env

docker-compose up --build
```

---

## 🏗 Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Frontend (Next.js + TypeScript)                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Kanban Board │  │  DAG Graph   │  │  Side Panel  │  │
│  │  (dnd-kit)   │  │  (React Flow)│  │  (AI/What-If)│  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         └──────────────────┴─────────────────┘          │
│                     Zustand Store                        │
└─────────────────────────┬───────────────────────────────┘
                          │ REST API
┌─────────────────────────┴───────────────────────────────┐
│  Backend (FastAPI + Python)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │  Task CRUD   │  │  Graph API   │  │  AI Service  │  │
│  │  Router      │  │  What-If     │  │  (Gemini)    │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
│         └──────────────────┴─────────────────┘          │
│                   DAG Engine (Pure Python)                │
│         Cycle Detection │ Propagation │ Critical Path    │
└─────────────────────────┬───────────────────────────────┘
                          │
┌─────────────────────────┴───────────────────────────────┐
│  Storage: SQLite (default) / PostgreSQL (Docker)         │
│  Tables: tasks │ dependencies │ event_log               │
└─────────────────────────────────────────────────────────┘
```

---

## 🧪 Running Tests

```bash
cd backend
# Activate virtual environment first
pytest tests/ -v
```

Tests cover:
- Cycle detection (self-loops, direct, indirect, diamond patterns)
- Schedule propagation (simple, diamond MAX-not-SUM, deep chains)
- Blocked/Ready state machine (including reopen scenarios)
- Critical path computation (linear, diamond, complex graphs)
- What-If preview (immutability guarantee)

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check with DAG stats |
| GET | `/api/tasks` | List all tasks |
| POST | `/api/tasks` | Create a task |
| PATCH | `/api/tasks/{id}` | Update a task (triggers propagation) |
| DELETE | `/api/tasks/{id}` | Delete a task |
| POST | `/api/tasks/reorder` | Bulk reorder after drag-drop |
| GET | `/api/dependencies` | List all dependency edges |
| POST | `/api/dependencies` | Add dependency (with cycle check) |
| DELETE | `/api/dependencies/{id}` | Remove dependency |
| GET | `/api/graph` | Full graph data for visualization |
| POST | `/api/graph/what-if` | What-If impact preview |
| POST | `/api/ai/suggest-dependencies` | AI dependency suggestions |
| GET | `/api/ai/risk-analysis` | Risk heatmap analysis |
| GET | `/api/events` | Recent event log |

Full interactive docs: **http://localhost:8000/docs**

---

## 🔧 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./taskflow.db` | Database connection string |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |
| `GEMINI_API_KEY` | *(empty)* | Google Gemini API key (optional) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |
| `API_HOST` | `0.0.0.0` | Backend host |
| `API_PORT` | `8000` | Backend port |

---

## 🛡 Security

- **SQL Injection**: All queries use SQLAlchemy parameterized queries
- **AI Privacy**: Only task titles and descriptions sent to Gemini — never internal IDs or user metadata
- **CORS**: Restricted to configured frontend origin
- **No Committed Secrets**: API keys loaded from environment variables only

---

## 📦 Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 15, TypeScript | App framework |
| Kanban | dnd-kit | Drag-and-drop |
| Graph Viz | React Flow, dagre | DAG visualization & layout |
| State | Zustand | Global state management |
| Styling | Vanilla CSS | Custom dark glassmorphism theme |
| Backend | FastAPI | REST API |
| DAG Engine | Pure Python | Core algorithms |
| Database | SQLite / PostgreSQL | Persistence |
| AI | Google Gemini | Dependency suggestions |
| DevOps | Docker Compose | One-command deployment |

---

## 🤖 AI Tool Declaration

This project was developed collaboratively, combining human expertise and decision-making with Claude’s assistance in code generation and architecture design.

---

## 📄 License

Built for the Contata Hackathon 2026.
