"""
TaskFlow Pro — Core DAG Engine

The heart of the application. Implements all directed acyclic graph algorithms:
- Cycle detection (DFS reachability)
- Schedule propagation without compounding (BFS, max incoming delay)
- Blocked/Ready state machine
- Critical path computation (DP over topological sort)
- What-If impact preview (operates on a deep copy)

This module is pure Python with zero database dependencies, making it
independently testable and the foundation for all graph operations.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


@dataclass
class TaskNode:
    """Lightweight in-memory representation of a task for graph operations."""
    id: str
    title: str
    status: str  # backlog, in_progress, review, done
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    duration_days: int = 1
    description: str = ""
    column_order: int = 0


@dataclass
class ScheduleDiff:
    """Represents a schedule change for a single task."""
    task_id: str
    task_title: str
    old_start: Optional[date]
    old_end: Optional[date]
    new_start: Optional[date]
    new_end: Optional[date]

    @property
    def shift_days(self) -> int:
        if self.old_start and self.new_start:
            return (self.new_start - self.old_start).days
        return 0


class DAGEngine:
    """
    Core Directed Acyclic Graph engine for task dependency management.

    Maintains an in-memory adjacency-list representation with both
    forward edges (prerequisite → dependent) and reverse edges
    (dependent → prerequisite) for O(1) neighbor lookup.

    All graph mutation operations include automatic cycle detection
    to guarantee the DAG invariant is never violated.
    """

    def __init__(self):
        # forward: source_id -> set of target_ids (prerequisite -> dependents)
        self._forward: dict[str, set[str]] = defaultdict(set)
        # reverse: target_id -> set of source_ids (dependent -> prerequisites)
        self._reverse: dict[str, set[str]] = defaultdict(set)
        # Task metadata indexed by ID
        self._nodes: dict[str, TaskNode] = {}

    # ─── Node Operations ──────────────────────────────────────

    def add_node(self, node: TaskNode) -> None:
        """Add a task node to the graph."""
        self._nodes[node.id] = node
        # Ensure adjacency entries exist
        if node.id not in self._forward:
            self._forward[node.id] = set()
        if node.id not in self._reverse:
            self._reverse[node.id] = set()

    def remove_node(self, node_id: str) -> None:
        """Remove a task and all its edges from the graph."""
        if node_id not in self._nodes:
            return

        # Remove all outgoing edges (this node as prerequisite)
        for dependent_id in list(self._forward.get(node_id, [])):
            self._reverse[dependent_id].discard(node_id)

        # Remove all incoming edges (this node as dependent)
        for prereq_id in list(self._reverse.get(node_id, [])):
            self._forward[prereq_id].discard(node_id)

        # Clean up
        self._forward.pop(node_id, None)
        self._reverse.pop(node_id, None)
        self._nodes.pop(node_id, None)

    def update_node(self, node_id: str, **kwargs) -> Optional[TaskNode]:
        """Update task node attributes."""
        node = self._nodes.get(node_id)
        if not node:
            return None
        for key, value in kwargs.items():
            if hasattr(node, key):
                setattr(node, key, value)
        return node

    def get_node(self, node_id: str) -> Optional[TaskNode]:
        """Get a task node by ID."""
        return self._nodes.get(node_id)

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return sum(len(targets) for targets in self._forward.values())

    # ─── Edge Operations ──────────────────────────────────────

    def would_create_cycle(self, source_id: str, target_id: str) -> bool:
        """
        Check if adding edge source→target would create a cycle.

        Uses DFS reachability: walks forward from target. If source
        is reachable from target, adding source→target would create
        a cycle. Self-loops are also rejected.

        Time complexity: O(V + E) worst case.
        """
        if source_id == target_id:
            return True

        if source_id not in self._nodes or target_id not in self._nodes:
            return False

        # DFS from target, checking if we can reach source
        visited: set[str] = set()
        stack = [target_id]

        while stack:
            current = stack.pop()
            if current == source_id:
                return True
            if current in visited:
                continue
            visited.add(current)
            # Follow forward edges from current
            for neighbor in self._forward.get(current, []):
                if neighbor not in visited:
                    stack.append(neighbor)

        return False

    def add_edge(self, source_id: str, target_id: str) -> bool:
        """
        Add a dependency edge: source is a prerequisite of target.

        Returns True if the edge was added successfully.
        Returns False if it would create a cycle (edge not added).
        """
        # Validate nodes exist
        if source_id not in self._nodes or target_id not in self._nodes:
            return False

        # Check for duplicate
        if target_id in self._forward.get(source_id, set()):
            return True  # Edge already exists

        # Cycle check
        if self.would_create_cycle(source_id, target_id):
            return False

        self._forward[source_id].add(target_id)
        self._reverse[target_id].add(source_id)
        return True

    def remove_edge(self, source_id: str, target_id: str) -> bool:
        """Remove a dependency edge. Returns True if it existed."""
        existed = target_id in self._forward.get(source_id, set())
        self._forward[source_id].discard(target_id)
        self._reverse[target_id].discard(source_id)
        return existed

    def has_edge(self, source_id: str, target_id: str) -> bool:
        """Check if an edge exists."""
        return target_id in self._forward.get(source_id, set())

    def get_prerequisites(self, task_id: str) -> set[str]:
        """Get all direct prerequisites of a task."""
        return set(self._reverse.get(task_id, set()))

    def get_dependents(self, task_id: str) -> set[str]:
        """Get all direct dependents of a task."""
        return set(self._forward.get(task_id, set()))

    # ─── Blocked / Ready State Machine ────────────────────────

    def is_blocked(self, task_id: str) -> bool:
        """
        A task is blocked if ANY of its prerequisites has not
        reached 'done' status.
        """
        for prereq_id in self._reverse.get(task_id, set()):
            prereq = self._nodes.get(prereq_id)
            if prereq and prereq.status != "done":
                return True
        return False

    def get_blocked_tasks(self) -> list[str]:
        """Return IDs of all tasks that are blocked by unfinished prerequisites."""
        return [tid for tid in self._nodes if self.is_blocked(tid)]

    def get_ready_tasks(self) -> list[str]:
        """Return IDs of tasks that are not done and have all prerequisites met."""
        return [
            tid for tid, node in self._nodes.items()
            if node.status != "done" and not self.is_blocked(tid)
        ]

    # ─── Topological Sort (Kahn's Algorithm) ──────────────────

    def topological_sort(self) -> list[str]:
        """
        Kahn's algorithm for topological ordering.

        Returns a list of task IDs in topological order.
        If the graph has a cycle (shouldn't happen due to cycle checks),
        the returned list will be shorter than the node count.
        """
        in_degree: dict[str, int] = {}
        for tid in self._nodes:
            in_degree[tid] = len(self._reverse.get(tid, set()))

        queue = deque(
            tid for tid, deg in in_degree.items() if deg == 0
        )
        result: list[str] = []

        while queue:
            node_id = queue.popleft()
            result.append(node_id)
            for dependent in self._forward.get(node_id, []):
                if dependent in in_degree:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

        return result

    # ─── Schedule Propagation Without Compounding ─────────────

    def propagate_schedule(self, changed_task_id: str) -> list[ScheduleDiff]:
        """
        BFS propagation from a changed task through all downstream dependents.

        For each downstream task, the new start date is computed as:
            max(end_date of all prerequisites) + 1 day

        This uses MAX (not SUM) to prevent double-counting when multiple
        dependency paths converge on the same task (the diamond problem).

        The visited-set ensures each node is processed exactly once.

        Time complexity: O(V + E) on the affected subgraph.
        """
        changes: list[ScheduleDiff] = []
        visited: set[str] = set()
        queue: deque[str] = deque()

        # Seed BFS with direct dependents of the changed task
        for dependent_id in self._forward.get(changed_task_id, []):
            queue.append(dependent_id)

        while queue:
            current_id = queue.popleft()
            if current_id in visited:
                continue
            visited.add(current_id)

            node = self._nodes.get(current_id)
            if not node:
                continue

            # Compute new start = max(end_date of all prerequisites) + 1 day
            max_prereq_end: Optional[date] = None
            all_prereqs_have_dates = True

            for prereq_id in self._reverse.get(current_id, set()):
                prereq = self._nodes.get(prereq_id)
                if prereq and prereq.end_date:
                    if max_prereq_end is None or prereq.end_date > max_prereq_end:
                        max_prereq_end = prereq.end_date
                else:
                    all_prereqs_have_dates = False

            if max_prereq_end is not None:
                new_start = max_prereq_end + timedelta(days=1)
                new_end = new_start + timedelta(days=max(node.duration_days - 1, 0))

                if new_start != node.start_date or new_end != node.end_date:
                    changes.append(ScheduleDiff(
                        task_id=current_id,
                        task_title=node.title,
                        old_start=node.start_date,
                        old_end=node.end_date,
                        new_start=new_start,
                        new_end=new_end,
                    ))
                    # Apply the change so downstream tasks see updated dates
                    node.start_date = new_start
                    node.end_date = new_end

            # Enqueue dependents for further propagation
            for dependent_id in self._forward.get(current_id, []):
                if dependent_id not in visited:
                    queue.append(dependent_id)

        return changes

    def apply_propagation(self, changed_task_id: str) -> list[ScheduleDiff]:
        """Propagate and commit schedule changes. Returns the list of changes made."""
        return self.propagate_schedule(changed_task_id)

    # ─── What-If Impact Preview ───────────────────────────────

    def what_if_preview(
        self,
        task_id: str,
        new_duration_days: Optional[int] = None,
        new_end_date: Optional[date] = None,
    ) -> list[ScheduleDiff]:
        """
        Preview the downstream impact of a schedule change WITHOUT
        modifying the actual graph.

        Creates a deep copy of the engine, applies the hypothetical
        change, runs propagation, and returns the projected diffs.
        """
        # Deep copy the engine
        engine_copy = DAGEngine()
        for tid, node in self._nodes.items():
            engine_copy.add_node(TaskNode(
                id=node.id,
                title=node.title,
                status=node.status,
                start_date=node.start_date,
                end_date=node.end_date,
                duration_days=node.duration_days,
                description=node.description,
                column_order=node.column_order,
            ))

        # Copy edges
        for source_id, targets in self._forward.items():
            for target_id in targets:
                engine_copy._forward[source_id].add(target_id)
                engine_copy._reverse[target_id].add(source_id)

        # Apply hypothetical change
        node = engine_copy._nodes.get(task_id)
        if node:
            if new_duration_days is not None:
                node.duration_days = new_duration_days
                if node.start_date:
                    node.end_date = node.start_date + timedelta(days=new_duration_days - 1)
            if new_end_date is not None:
                old_duration = node.duration_days
                node.end_date = new_end_date
                if node.start_date:
                    node.duration_days = (new_end_date - node.start_date).days + 1

        # Run propagation on the copy
        return engine_copy.propagate_schedule(task_id)

    # ─── Critical Path Computation ────────────────────────────

    def compute_critical_path(self) -> tuple[list[str], int]:
        """
        Compute the critical path using dynamic programming over
        the topological sort.

        The critical path is the longest-duration path through the DAG,
        representing the minimum possible project completion time.

        Returns:
            (path: list of task IDs, total_duration: int in days)
        """
        topo_order = self.topological_sort()

        if not topo_order:
            return [], 0

        # dp[node_id] = (longest path length ending here, predecessor on path)
        dp: dict[str, tuple[int, Optional[str]]] = {}

        for tid in topo_order:
            node = self._nodes.get(tid)
            duration = node.duration_days if node else 1

            prereqs = self._reverse.get(tid, set())
            if not prereqs:
                # Root node — path starts here
                dp[tid] = (duration, None)
            else:
                best_length = 0
                best_pred: Optional[str] = None
                for prereq_id in prereqs:
                    if prereq_id in dp:
                        length = dp[prereq_id][0]
                        if length > best_length:
                            best_length = length
                            best_pred = prereq_id
                dp[tid] = (best_length + duration, best_pred)

        if not dp:
            return [], 0

        # Find the terminal node with longest path
        end_node = max(dp, key=lambda x: dp[x][0])
        total_duration = dp[end_node][0]

        # Trace back from end to start
        path: list[str] = []
        current: Optional[str] = end_node
        while current is not None:
            path.append(current)
            current = dp[current][1]

        path.reverse()
        return path, total_duration

    # ─── Graph Data Export ────────────────────────────────────

    def get_graph_data(self) -> dict:
        """Export full graph structure for frontend visualization."""
        critical_path, critical_duration = self.compute_critical_path()
        critical_set = set(critical_path)

        # Build critical edge set
        critical_edges: set[tuple[str, str]] = set()
        for i in range(len(critical_path) - 1):
            critical_edges.add((critical_path[i], critical_path[i + 1]))

        nodes = []
        for tid, node in self._nodes.items():
            nodes.append({
                "id": tid,
                "title": node.title,
                "description": node.description,
                "status": node.status,
                "start_date": node.start_date.isoformat() if node.start_date else None,
                "end_date": node.end_date.isoformat() if node.end_date else None,
                "duration_days": node.duration_days,
                "is_blocked": self.is_blocked(tid),
                "column_order": node.column_order,
                "on_critical_path": tid in critical_set,
                "prerequisite_ids": list(self._reverse.get(tid, set())),
                "dependent_ids": list(self._forward.get(tid, set())),
            })

        edges = []
        for source_id, targets in self._forward.items():
            for target_id in targets:
                edge_id = f"{source_id}->{target_id}"
                edges.append({
                    "id": edge_id,
                    "source": source_id,
                    "target": target_id,
                    "is_critical": (source_id, target_id) in critical_edges,
                })

        blocked = self.get_blocked_tasks()
        ready = self.get_ready_tasks()

        return {
            "nodes": nodes,
            "edges": edges,
            "critical_path": critical_path,
            "critical_path_duration": critical_duration,
            "blocked_count": len(blocked),
            "ready_count": len(ready),
        }

    # ─── Bulk Load from Database ──────────────────────────────

    def load_from_db_records(
        self,
        tasks: list[dict],
        dependencies: list[dict],
    ) -> None:
        """
        Populate the in-memory graph from database records.
        Called on application startup and after significant mutations.
        """
        self._nodes.clear()
        self._forward.clear()
        self._reverse.clear()

        # Add all nodes first
        for task in tasks:
            self.add_node(TaskNode(
                id=task["id"],
                title=task["title"],
                status=task["status"],
                start_date=task.get("start_date"),
                end_date=task.get("end_date"),
                duration_days=task.get("duration_days", 1),
                description=task.get("description", ""),
                column_order=task.get("column_order", 0),
            ))

        # Add all edges (skip any that would create cycles — shouldn't happen
        # if data integrity is maintained, but defensive programming)
        for dep in dependencies:
            self.add_edge(dep["source_task_id"], dep["target_task_id"])
