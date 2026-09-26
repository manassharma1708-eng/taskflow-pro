# TaskFlow Pro — Design Document

## Architecture, Data Model & Known Limitations

---

## 1. System Architecture

TaskFlow Pro uses a **"Graph-First, Board-Second"** architecture. The DAG (Directed Acyclic Graph) is the authoritative source of truth; the Kanban board is a synchronized projection of the graph state.

### Three-Tier Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     PRESENTATION LAYER                           │
│  Next.js 15 + TypeScript                                         │
│  ┌────────────┐  ┌──────────────┐  ┌───────────┐  ┌──────────┐ │
│  │ Kanban View │  │  DAG Graph   │  │ Side Panel│  │  Modals  │ │
│  │ (dnd-kit)  │  │ (React Flow) │  │ (AI/What- │  │ (Create/ │ │
│  │            │  │  + dagre     │  │  If/Risk)  │  │  Edit)   │ │
│  └─────┬──────┘  └──────┬───────┘  └─────┬─────┘  └────┬─────┘ │
│        └────────────────┬┘               └──────────────┘       │
│                    Zustand Store (Global State)                   │
│                         │ fetch()                                │
└─────────────────────────┼────────────────────────────────────────┘
                          │ REST API (JSON)
┌─────────────────────────┼────────────────────────────────────────┐
│                     APPLICATION LAYER                             │
│  FastAPI (Python)                                                 │
│  ┌──────────┐  ┌──────────────┐  ┌──────────┐  ┌─────────────┐ │
│  │ Tasks    │  │ Dependencies │  │ Graph /  │  │ AI Router   │ │
│  │ Router   │  │ Router       │  │ What-If  │  │ (Gemini)    │ │
│  └─────┬────┘  └──────┬───────┘  └────┬─────┘  └──────┬──────┘ │
│        └───────────────┴───────────────┘               │        │
│                    DAG Engine (Pure Python)             │        │
│         ┌──────────────────────────────────┐    ┌──────┴──────┐ │
│         │ In-Memory Adjacency Lists        │    │ Gemini API  │ │
│         │ (forward + reverse edges)        │    │ Integration │ │
│         │ O(1) neighbor lookup             │    └─────────────┘ │
│         └──────────────┬───────────────────┘                    │
└─────────────────────────┼────────────────────────────────────────┘
                          │ SQLAlchemy ORM
┌─────────────────────────┼────────────────────────────────────────┐
│                     DATA LAYER                                    │
│  SQLite (default) / PostgreSQL (Docker)                           │
│  ┌────────┐  ┌──────────────┐  ┌───────────┐                    │
│  │ tasks  │  │ dependencies │  │ event_log │                    │
│  └────────┘  └──────────────┘  └───────────┘                    │
└──────────────────────────────────────────────────────────────────┘
```

### Key Design Decisions

1. **In-Memory DAG Engine**: All graph algorithms operate on an in-memory adjacency-list representation for O(V+E) performance. The in-memory graph is synchronized with the database via write-through on every mutation.

2. **SQLite as Default**: Zero-configuration startup for evaluators. No Docker, no PostgreSQL install — just `pip install` and `python main.py`. PostgreSQL is available via Docker Compose for production.

3. **Human-in-the-Loop AI**: The Gemini integration is strictly advisory. AI suggestions are displayed in a side panel for the user to Accept or Reject individually. The AI layer has no direct write access to the graph. The app works fully without a Gemini API key.

4. **Next.js API Proxy**: The frontend proxies `/api/*` requests to the FastAPI backend via Next.js rewrites, eliminating CORS issues in development.

---

## 2. Data Model

### Entity-Relationship Diagram

```
┌──────────────────────┐       ┌──────────────────────────┐
│       tasks           │       │      dependencies         │
├──────────────────────┤       ├──────────────────────────┤
│ id          (PK, UUID)│◄──┐  │ id        (PK, UUID)     │
│ title       (VARCHAR) │   ├──│ source_task_id (FK)       │
│ description (TEXT)    │   └──│ target_task_id (FK)       │
│ status      (VARCHAR) │      │ created_at (DATETIME)     │
│ column_order (INT)    │      ├──────────────────────────┤
│ start_date  (DATE)    │      │ UNIQUE(source, target)   │
│ end_date    (DATE)    │      └──────────────────────────┘
│ duration_days (INT)   │
│ created_at  (DATETIME)│      ┌──────────────────────────┐
│ updated_at  (DATETIME)│      │       event_log           │
└──────────────────────┘      ├──────────────────────────┤
                               │ id        (PK, AUTO INT) │
                               │ event_type (VARCHAR)     │
                               │ payload    (JSON)        │
                               │ actor      (VARCHAR)     │
                               │ timestamp  (DATETIME)    │
                               └──────────────────────────┘
```

### Table Details

**tasks**: Each row represents a project task displayed on both the Kanban board and DAG graph.
- `status` is one of: `backlog`, `in_progress`, `review`, `done`
- `column_order` determines vertical position within a Kanban column
- `start_date` and `end_date` define the schedule window
- `duration_days` is the planned work duration (minimum 1)
- Dates auto-propagate: changing `duration_days` recalculates `end_date` from `start_date`

**dependencies**: Each row is a directed edge in the DAG. `source_task_id` is the prerequisite; `target_task_id` is the dependent.
- UNIQUE constraint on `(source_task_id, target_task_id)` prevents duplicate edges
- ON DELETE CASCADE removes edges when a task is deleted
- Every edge addition goes through cycle detection before being committed

**event_log**: Append-only audit trail capturing every mutation for debugging and potential undo.
- `event_type` examples: `task_created`, `task_updated`, `status_changed`, `dependency_added`, `schedule_propagated`
- `payload` is a JSON blob with event-specific details
- Never deleted or updated — true append-only

### In-Memory Graph Representation

```python
# Forward edges: prerequisite -> set of dependents
_forward: dict[str, set[str]] = defaultdict(set)

# Reverse edges: dependent -> set of prerequisites  
_reverse: dict[str, set[str]] = defaultdict(set)

# Task metadata
_nodes: dict[str, TaskNode] = {}
```

Both forward and reverse adjacency lists are maintained for O(1) neighbor lookup in either direction. The graph is rebuilt from the database on application startup and kept in sync via write-through on every mutation.

---

## 3. Core Algorithms

### Cycle Detection
- **Algorithm**: DFS reachability check from target toward source
- **Complexity**: O(V + E) worst case
- **When**: Before every `add_edge` operation
- **Behavior**: If source is reachable from target via existing edges, adding source→target would create a cycle. The edge is rejected and the graph remains unchanged.

### Schedule Propagation Without Compounding
- **Algorithm**: BFS from the changed node with a visited-set
- **Key insight**: When paths converge (diamond pattern), the engine takes the MAX incoming delay across all parents, not the SUM. This prevents double-counting.
- **Complexity**: O(V + E) on the affected subgraph
- **When**: Automatically triggered when a task's dates or duration change, or when a new dependency is added

### Blocked/Ready State Machine
- **Blocked**: A task is blocked if ANY prerequisite has not reached `done` status
- **Ready**: A task is ready if it is NOT done AND all prerequisites are `done`
- **Computed dynamically**: Not stored in the database; evaluated on every query from the in-memory graph

### Critical Path
- **Algorithm**: Dynamic programming over Kahn's topological sort
- **Output**: The longest-duration path through the DAG, representing minimum project completion time
- **Complexity**: O(V + E)
- **Visualization**: Critical path nodes and edges are highlighted with orange color and animated flow

### What-If Impact Preview
- **Approach**: Deep-copy the entire in-memory graph, apply the hypothetical change, run propagation on the copy, return the diff
- **Immutability guarantee**: The original graph is never modified during preview
- **Output**: List of affected tasks with old/new dates and shift in days

---

## 4. AI / LLM Integration

### Dependency Suggestion Engine
- **Model**: Google Gemini (configurable via `GEMINI_MODEL` env var)
- **Prompt design**: Structured prompt with numbered existing task list for context grounding
- **Temperature**: 0.2 for deterministic responses
- **Output format**: Structured JSON with task reference, confidence score (0-100), direction, and rationale
- **Grounding**: Only references real existing tasks; validated against database
- **Filtering**: Suggestions below 40% confidence are discarded
- **Graceful degradation**: Returns empty suggestions if API key is missing or API is unreachable

### Risk Analysis
- **Approach**: Deterministic (no LLM needed) — computed from graph topology
- **Factors**: fan-in count, fan-out count, critical path membership, schedule gaps, description quality
- **Output**: Risk score (0-100) per task with severity-tagged factors
- **Core engine remains fully deterministic**: AI layer has no write access

---

## 5. Known Limitations

1. **Single-User System**: No authentication or multi-user support. Designed for single-team use with up to 30 concurrent users accessing the same project.

2. **Synchronous What-If**: The What-If preview computes propagation synchronously on the server. For graphs exceeding 500 tasks with deep dependency chains, this may add noticeable latency. A future iteration would offload this to a background worker.

3. **DAG Visualization Scalability**: The dagre auto-layout stays readable up to approximately 100 tasks. Beyond that, the graph becomes dense and would benefit from hierarchical clustering and zoom-to-subgraph features (not implemented in this sprint).

4. **AI Suggestion Quality**: Depends on descriptive task titles. Vague labels like "Fix bug" yield low-confidence suggestions. Confidence scoring helps surface this, but cannot fully compensate.

5. **Optimistic Concurrency**: The system uses optimistic concurrency with set writes. For larger teams (>30), CRDP-based conflict resolution would be needed.

6. **Duration Granularity**: Task durations are estimated in whole days for simplicity. Sub-day granularity (hours) is not supported.

7. **No Undo UI**: The event log captures all mutations for potential undo, but the undo UI is not implemented in this sprint. The data foundation exists for future implementation.

8. **SQLite Limitations**: WAL mode is enabled for better concurrent read performance, but SQLite is not recommended for production deployments with high write throughput. PostgreSQL via Docker Compose is available for production use.

---

## 6. Technology Justification

| Technology | Why Chosen |
|------------|-----------|
| **FastAPI** | Async-capable, auto-generated OpenAPI docs, Pydantic validation, mature ecosystem |
| **SQLAlchemy 2.0** | Industry-standard ORM, supports SQLite and PostgreSQL transparently |
| **SQLite** | Zero-configuration for evaluators, no external dependencies |
| **Next.js 15** | Server-side rendering, API route proxying, TypeScript-first, mature ecosystem |
| **React Flow** | Best-in-class graph visualization library with built-in pan/zoom/minimap |
| **dagre** | Well-tested directed graph layout algorithm (Sugiyama-style) |
| **dnd-kit** | Modern drag-and-drop with accessibility, sortable lists, and collision detection |
| **Zustand** | Minimal boilerplate state management, works with React 18+ |
| **Google Gemini** | Structured output support, competitive pricing, Python SDK |
| **Docker Compose** | One-command full-stack deployment for PostgreSQL setup |

All chosen technologies are mature, well-documented, and minimize the risk of unexpected blockers within the sprint window.

---

## 7. Testing Strategy

### Unit Tests (38 tests, all passing)
- **Cycle Detection**: Self-loops, direct cycles, indirect cycles, diamond extensions, duplicate edges
- **Blocked/Ready**: No prerequisites, done prerequisites, undone prerequisites, partial completion, reopen scenarios
- **Topological Sort**: Linear chains, diamond patterns, empty graphs, single nodes
- **Schedule Propagation**: Simple chains, diamond MAX-not-SUM, deep chains, no-change scenarios
- **Critical Path**: Linear, diamond (picks longest branch), complex multi-path graphs
- **What-If Preview**: Immutability guarantee, returns correct changes, works with end dates
- **Node/Edge Operations**: Add/remove with cascade, prerequisites/dependents, graph export, bulk load

### API Integration Tests
- Health check endpoint validation
- Task CRUD with dependency enforcement
- Cycle rejection with 409 response

---

## 8. Security Considerations

- **SQL Injection Prevention**: All queries use SQLAlchemy's parameterized query builder
- **AI Data Privacy**: Only task titles and descriptions are sent to Gemini — never internal UUIDs, user metadata, or sensitive data
- **No Committed Secrets**: API keys loaded exclusively from environment variables; `.env` is in `.gitignore`
- **CORS**: Restricted to configured frontend origin only
- **API Rate Limiting**: Configurable via environment variables (not enforced in development)
