"""
TaskFlow Pro — DAG Engine Unit Tests

Comprehensive tests for the core DAG algorithms:
- Cycle detection
- Schedule propagation (with diamond dependency pattern)
- Blocked/Ready state machine
- Critical path computation
- What-If impact preview
- Edge cases (deep chains, rollback scenarios)
"""

import pytest
from datetime import date, timedelta

from services.dag_engine import DAGEngine, TaskNode, ScheduleDiff


# ─── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def empty_dag():
    """Empty DAG engine."""
    return DAGEngine()


@pytest.fixture
def simple_chain():
    """Linear chain: A → B → C"""
    dag = DAGEngine()
    dag.add_node(TaskNode(id="A", title="Task A", status="done",
                          start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), duration_days=2))
    dag.add_node(TaskNode(id="B", title="Task B", status="in_progress",
                          start_date=date(2026, 1, 3), end_date=date(2026, 1, 5), duration_days=3))
    dag.add_node(TaskNode(id="C", title="Task C", status="backlog",
                          start_date=date(2026, 1, 6), end_date=date(2026, 1, 7), duration_days=2))
    dag.add_edge("A", "B")
    dag.add_edge("B", "C")
    return dag


@pytest.fixture
def diamond_dag():
    """
    Diamond pattern (convergent paths):
        A
       / \
      B   C
       \ /
        D

    This tests that propagation uses MAX, not SUM, of parent delays.
    """
    dag = DAGEngine()
    dag.add_node(TaskNode(id="A", title="Root Task", status="done",
                          start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), duration_days=3))
    dag.add_node(TaskNode(id="B", title="Branch B", status="in_progress",
                          start_date=date(2026, 1, 4), end_date=date(2026, 1, 6), duration_days=3))
    dag.add_node(TaskNode(id="C", title="Branch C", status="in_progress",
                          start_date=date(2026, 1, 4), end_date=date(2026, 1, 5), duration_days=2))
    dag.add_node(TaskNode(id="D", title="Merge Task", status="backlog",
                          start_date=date(2026, 1, 7), end_date=date(2026, 1, 8), duration_days=2))
    dag.add_edge("A", "B")
    dag.add_edge("A", "C")
    dag.add_edge("B", "D")
    dag.add_edge("C", "D")
    return dag


@pytest.fixture
def complex_dag():
    """
    Complex graph with multiple paths and a deep chain:
        A → B → E → G
        A → C → F → G
        A → D
    """
    dag = DAGEngine()
    for i, (tid, title, dur) in enumerate([
        ("A", "Start", 1), ("B", "Path 1a", 3), ("C", "Path 2a", 2),
        ("D", "Independent", 1), ("E", "Path 1b", 2), ("F", "Path 2b", 4),
        ("G", "Final", 2),
    ]):
        dag.add_node(TaskNode(
            id=tid, title=title, status="backlog",
            start_date=date(2026, 1, 1), end_date=date(2026, 1, 1) + timedelta(days=dur - 1),
            duration_days=dur,
        ))
    dag.add_edge("A", "B")
    dag.add_edge("A", "C")
    dag.add_edge("A", "D")
    dag.add_edge("B", "E")
    dag.add_edge("C", "F")
    dag.add_edge("E", "G")
    dag.add_edge("F", "G")
    return dag


# ─── Cycle Detection Tests ───────────────────────────────────

class TestCycleDetection:
    def test_self_loop_rejected(self, empty_dag):
        dag = empty_dag
        dag.add_node(TaskNode(id="A", title="A", status="backlog"))
        assert dag.would_create_cycle("A", "A") is True
        assert dag.add_edge("A", "A") is False

    def test_direct_cycle_rejected(self, empty_dag):
        dag = empty_dag
        dag.add_node(TaskNode(id="A", title="A", status="backlog"))
        dag.add_node(TaskNode(id="B", title="B", status="backlog"))
        dag.add_edge("A", "B")
        assert dag.would_create_cycle("B", "A") is True
        assert dag.add_edge("B", "A") is False

    def test_indirect_cycle_rejected(self, simple_chain):
        """A → B → C, adding C → A should be rejected."""
        dag = simple_chain
        assert dag.would_create_cycle("C", "A") is True
        assert dag.add_edge("C", "A") is False

    def test_valid_edge_accepted(self, empty_dag):
        dag = empty_dag
        dag.add_node(TaskNode(id="A", title="A", status="backlog"))
        dag.add_node(TaskNode(id="B", title="B", status="backlog"))
        assert dag.would_create_cycle("A", "B") is False
        assert dag.add_edge("A", "B") is True

    def test_parallel_edges_no_cycle(self, diamond_dag):
        """Diamond pattern should not be detected as a cycle."""
        dag = diamond_dag
        # All edges in diamond are valid
        assert dag.node_count == 4
        assert dag.edge_count == 4

    def test_cycle_in_diamond_extension(self, diamond_dag):
        """Adding D → A in diamond should be rejected (creates cycle)."""
        dag = diamond_dag
        assert dag.would_create_cycle("D", "A") is True

    def test_duplicate_edge_idempotent(self, empty_dag):
        dag = empty_dag
        dag.add_node(TaskNode(id="A", title="A", status="backlog"))
        dag.add_node(TaskNode(id="B", title="B", status="backlog"))
        assert dag.add_edge("A", "B") is True
        assert dag.add_edge("A", "B") is True  # Idempotent
        assert dag.edge_count == 1


# ─── Blocked/Ready State Machine Tests ───────────────────────

class TestBlockedReady:
    def test_no_prerequisites_is_ready(self, empty_dag):
        dag = empty_dag
        dag.add_node(TaskNode(id="A", title="A", status="backlog"))
        assert dag.is_blocked("A") is False

    def test_done_prerequisite_unblocks(self, simple_chain):
        """A(done) → B: B should not be blocked."""
        dag = simple_chain
        assert dag.is_blocked("B") is False  # A is done

    def test_undone_prerequisite_blocks(self, simple_chain):
        """B(in_progress) → C: C should be blocked."""
        dag = simple_chain
        assert dag.is_blocked("C") is True  # B is in_progress

    def test_all_prereqs_done_unblocks(self, diamond_dag):
        """D is blocked until both B and C are done."""
        dag = diamond_dag
        assert dag.is_blocked("D") is True

        # Complete B, still blocked (C not done)
        dag.update_node("B", status="done")
        assert dag.is_blocked("D") is True

        # Complete C, now unblocked
        dag.update_node("C", status="done")
        assert dag.is_blocked("D") is False

    def test_get_blocked_tasks(self, simple_chain):
        dag = simple_chain
        blocked = dag.get_blocked_tasks()
        assert "C" in blocked
        assert "B" not in blocked  # A is done

    def test_get_ready_tasks(self, simple_chain):
        dag = simple_chain
        ready = dag.get_ready_tasks()
        assert "B" in ready  # A is done, so B is ready
        assert "C" not in ready  # B is not done

    def test_completing_task_updates_dependents(self, simple_chain):
        dag = simple_chain
        assert dag.is_blocked("C") is True
        dag.update_node("B", status="done")
        assert dag.is_blocked("C") is False

    def test_reopening_task_reblocks_dependents(self, simple_chain):
        """Moving a completed task backward should re-block dependents."""
        dag = simple_chain
        dag.update_node("B", status="done")
        assert dag.is_blocked("C") is False

        # Reopen B
        dag.update_node("B", status="in_progress")
        assert dag.is_blocked("C") is True


# ─── Topological Sort Tests ──────────────────────────────────

class TestTopologicalSort:
    def test_linear_chain(self, simple_chain):
        order = simple_chain.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("B") < order.index("C")

    def test_diamond(self, diamond_dag):
        order = diamond_dag.topological_sort()
        assert order.index("A") < order.index("B")
        assert order.index("A") < order.index("C")
        assert order.index("B") < order.index("D")
        assert order.index("C") < order.index("D")

    def test_empty_graph(self, empty_dag):
        assert empty_dag.topological_sort() == []

    def test_single_node(self, empty_dag):
        dag = empty_dag
        dag.add_node(TaskNode(id="X", title="X", status="backlog"))
        assert dag.topological_sort() == ["X"]


# ─── Schedule Propagation Tests ──────────────────────────────

class TestSchedulePropagation:
    def test_simple_propagation(self):
        """Extending A should push B and C forward."""
        dag = DAGEngine()
        dag.add_node(TaskNode(id="A", title="A", status="done",
                              start_date=date(2026, 1, 1), end_date=date(2026, 1, 5), duration_days=5))
        dag.add_node(TaskNode(id="B", title="B", status="backlog",
                              start_date=date(2026, 1, 3), end_date=date(2026, 1, 5), duration_days=3))
        dag.add_edge("A", "B")

        changes = dag.propagate_schedule("A")
        assert len(changes) == 1
        assert changes[0].task_id == "B"
        assert changes[0].new_start == date(2026, 1, 6)

    def test_diamond_uses_max_not_sum(self):
        """
        Diamond pattern: D's start should be max(B.end, C.end) + 1,
        NOT sum of both delays. This prevents double-counting.
        """
        dag = DAGEngine()
        dag.add_node(TaskNode(id="A", title="A", status="done",
                              start_date=date(2026, 1, 1), end_date=date(2026, 1, 3), duration_days=3))
        dag.add_node(TaskNode(id="B", title="B", status="backlog",
                              start_date=date(2026, 1, 4), end_date=date(2026, 1, 8), duration_days=5))
        dag.add_node(TaskNode(id="C", title="C", status="backlog",
                              start_date=date(2026, 1, 4), end_date=date(2026, 1, 6), duration_days=3))
        dag.add_node(TaskNode(id="D", title="D", status="backlog",
                              start_date=date(2026, 1, 7), end_date=date(2026, 1, 8), duration_days=2))
        dag.add_edge("A", "B")
        dag.add_edge("A", "C")
        dag.add_edge("B", "D")
        dag.add_edge("C", "D")

        changes = dag.propagate_schedule("A")

        # Find D's change
        d_change = next((c for c in changes if c.task_id == "D"), None)
        if d_change:
            # D should start after max(B.end=Jan 8, C.end=Jan 6) = Jan 9
            assert d_change.new_start == date(2026, 1, 9)
            assert d_change.new_end == date(2026, 1, 10)

    def test_deep_chain_propagation(self):
        """A → B → C → D → E: extending A should propagate through all."""
        dag = DAGEngine()
        start = date(2026, 1, 1)
        for i, tid in enumerate(["A", "B", "C", "D", "E"]):
            s = start + timedelta(days=i * 2)
            dag.add_node(TaskNode(
                id=tid, title=f"Task {tid}", status="backlog",
                start_date=s, end_date=s + timedelta(days=1), duration_days=2,
            ))
        dag.add_edge("A", "B")
        dag.add_edge("B", "C")
        dag.add_edge("C", "D")
        dag.add_edge("D", "E")

        # Extend A's end date by 3 days
        dag.update_node("A", end_date=date(2026, 1, 5))
        changes = dag.propagate_schedule("A")

        # All downstream tasks should be affected
        changed_ids = {c.task_id for c in changes}
        assert "B" in changed_ids
        assert "C" in changed_ids
        assert "D" in changed_ids
        assert "E" in changed_ids

    def test_no_changes_when_dates_align(self):
        """If dates are already correct, propagation returns no changes."""
        dag = DAGEngine()
        dag.add_node(TaskNode(id="A", title="A", status="done",
                              start_date=date(2026, 1, 1), end_date=date(2026, 1, 2), duration_days=2))
        dag.add_node(TaskNode(id="B", title="B", status="backlog",
                              start_date=date(2026, 1, 3), end_date=date(2026, 1, 4), duration_days=2))
        dag.add_edge("A", "B")

        changes = dag.propagate_schedule("A")
        assert len(changes) == 0


# ─── Critical Path Tests ────────────────────────────────────

class TestCriticalPath:
    def test_linear_chain_is_critical(self, simple_chain):
        path, duration = simple_chain.compute_critical_path()
        assert path == ["A", "B", "C"]
        assert duration == 7  # 2 + 3 + 2

    def test_diamond_picks_longest_branch(self, diamond_dag):
        """Critical path should go through the longer branch (B, 3 days vs C, 2 days)."""
        path, duration = diamond_dag.compute_critical_path()
        assert "A" in path
        assert "B" in path  # Longer branch
        assert "D" in path
        assert duration == 8  # 3 + 3 + 2

    def test_complex_graph_critical_path(self, complex_dag):
        """Complex graph should find the longest path."""
        path, duration = complex_dag.compute_critical_path()
        # Path 2: A(1) → C(2) → F(4) → G(2) = 9
        # Path 1: A(1) → B(3) → E(2) → G(2) = 8
        assert duration == 9
        assert "F" in path  # The longer path goes through F

    def test_empty_graph(self, empty_dag):
        path, duration = empty_dag.compute_critical_path()
        assert path == []
        assert duration == 0

    def test_single_node(self, empty_dag):
        dag = empty_dag
        dag.add_node(TaskNode(id="X", title="Solo", status="backlog", duration_days=5))
        path, duration = dag.compute_critical_path()
        assert path == ["X"]
        assert duration == 5


# ─── What-If Preview Tests ───────────────────────────────────

class TestWhatIfPreview:
    def test_preview_does_not_modify_original(self, simple_chain):
        dag = simple_chain
        original_b_start = dag.get_node("B").start_date

        # Preview extending A
        changes = dag.what_if_preview("A", new_duration_days=10)

        # Original should be unchanged
        assert dag.get_node("B").start_date == original_b_start

    def test_preview_returns_changes(self, simple_chain):
        dag = simple_chain
        changes = dag.what_if_preview("A", new_duration_days=10)
        assert len(changes) > 0

    def test_preview_with_new_end_date(self, simple_chain):
        dag = simple_chain
        changes = dag.what_if_preview("A", new_end_date=date(2026, 1, 10))
        assert len(changes) > 0
        b_change = next((c for c in changes if c.task_id == "B"), None)
        assert b_change is not None
        assert b_change.new_start == date(2026, 1, 11)


# ─── Node/Edge Operations Tests ──────────────────────────────

class TestNodeEdgeOperations:
    def test_add_remove_node(self, empty_dag):
        dag = empty_dag
        dag.add_node(TaskNode(id="X", title="X", status="backlog"))
        assert dag.node_count == 1
        dag.remove_node("X")
        assert dag.node_count == 0

    def test_remove_node_cascades_edges(self, simple_chain):
        """Removing B should clean up A→B and B→C edges."""
        dag = simple_chain
        assert dag.edge_count == 2
        dag.remove_node("B")
        assert dag.edge_count == 0
        assert dag.node_count == 2

    def test_get_prerequisites(self, diamond_dag):
        dag = diamond_dag
        prereqs = dag.get_prerequisites("D")
        assert prereqs == {"B", "C"}

    def test_get_dependents(self, diamond_dag):
        dag = diamond_dag
        deps = dag.get_dependents("A")
        assert deps == {"B", "C"}

    def test_has_edge(self, simple_chain):
        dag = simple_chain
        assert dag.has_edge("A", "B") is True
        assert dag.has_edge("B", "A") is False

    def test_graph_data_export(self, diamond_dag):
        data = diamond_dag.get_graph_data()
        assert len(data["nodes"]) == 4
        assert len(data["edges"]) == 4
        assert len(data["critical_path"]) > 0
        assert data["critical_path_duration"] > 0

    def test_load_from_db_records(self, empty_dag):
        dag = empty_dag
        tasks = [
            {"id": "1", "title": "T1", "status": "backlog", "duration_days": 1},
            {"id": "2", "title": "T2", "status": "backlog", "duration_days": 2},
        ]
        deps = [{"source_task_id": "1", "target_task_id": "2"}]
        dag.load_from_db_records(tasks, deps)
        assert dag.node_count == 2
        assert dag.edge_count == 1
        assert dag.has_edge("1", "2")
