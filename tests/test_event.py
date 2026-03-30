"""Tests for WorkflowInvocationEvent and EventCallTree.

Run: pytest tests/test_event.py -v
"""
import time
import pytest

from spl3.event import (
    WorkflowInvocationEvent,
    EventCallTree,
    EventStatus,
)


class TestWorkflowInvocationEvent:

    def test_unique_event_ids(self):
        e1 = WorkflowInvocationEvent(workflow_name="review_code")
        e2 = WorkflowInvocationEvent(workflow_name="review_code")
        assert e1.event_id != e2.event_id

    def test_same_workflow_name_different_instances(self):
        """Two concurrent callers of the same workflow are independent events."""
        e1 = WorkflowInvocationEvent(workflow_name="review_code", args={"code": "def foo(): ..."})
        e2 = WorkflowInvocationEvent(workflow_name="review_code", args={"code": "def bar(): ..."})
        assert e1.event_id != e2.event_id
        assert e1.args != e2.args
        assert e1.workflow_name == e2.workflow_name  # same definition

    def test_default_status_is_pending(self):
        e = WorkflowInvocationEvent(workflow_name="generate_code")
        assert e.status == EventStatus.PENDING

    def test_is_root_when_no_parent(self):
        e = WorkflowInvocationEvent(workflow_name="code_pipeline")
        assert e.is_root is True

    def test_is_not_root_when_has_parent(self):
        parent = WorkflowInvocationEvent(workflow_name="code_pipeline")
        child = WorkflowInvocationEvent(
            workflow_name="review_code",
            parent_event_id=parent.event_id,
        )
        assert child.is_root is False
        assert child.parent_event_id == parent.event_id

    def test_mark_running(self):
        e = WorkflowInvocationEvent(workflow_name="review_code")
        e.mark_running(node_id="duck")
        assert e.status == EventStatus.RUNNING
        assert e.started_at is not None
        assert e.node_id == "duck"

    def test_mark_complete(self):
        e = WorkflowInvocationEvent(workflow_name="review_code")
        e.mark_complete(output="LGTM", commit_status="complete")
        assert e.status == EventStatus.COMPLETE
        assert e.output == "LGTM"
        assert e.commit_status == "complete"
        assert e.completed_at is not None

    def test_mark_failed(self):
        e = WorkflowInvocationEvent(workflow_name="review_code")
        e.mark_failed(error="Timeout", commit_status="timeout")
        assert e.status == EventStatus.FAILED
        assert e.error == "Timeout"

    def test_latency_ms(self):
        e = WorkflowInvocationEvent(workflow_name="review_code")
        e.submitted_at = time.time() - 1.5   # 1.5 seconds ago
        e.mark_complete(output="ok")
        assert e.latency_ms is not None
        assert e.latency_ms >= 1400  # at least 1.4 seconds

    def test_qualified_name_no_namespace(self):
        e = WorkflowInvocationEvent(workflow_name="review_code")
        assert e.qualified_name == "review_code"

    def test_qualified_name_with_namespace(self):
        e = WorkflowInvocationEvent(workflow_name="review_code", namespace="python")
        assert e.qualified_name == "python.review_code"

    def test_to_task_payload(self):
        e = WorkflowInvocationEvent(
            workflow_name="review_code",
            args={"code": "x = 1"},
            requester_id="user-42",
            parent_event_id="abc-001",
        )
        payload = e.to_task_payload()
        assert payload["type"] == "workflow"
        assert payload["workflow"] == "review_code"
        assert payload["args"] == {"code": "x = 1"}
        assert payload["event_id"] == e.event_id
        assert payload["parent_event_id"] == "abc-001"
        assert payload["requester_id"] == "user-42"
        assert "peer_hub" not in payload

    def test_to_task_payload_with_peer_hub(self):
        e = WorkflowInvocationEvent(workflow_name="review_code")
        payload = e.to_task_payload(peer_hub="https://oracle-hub.momagrid.org")
        assert payload["peer_hub"] == "https://oracle-hub.momagrid.org"

    def test_from_task_response(self):
        data = {
            "task_id":      "abc-003",
            "event_id":     "abc-003",
            "workflow":     "review_code",
            "status":       "complete",
            "result":       "LGTM",
            "commit_status": "complete",
            "node_id":      "duck",
            "requester_id": "user-42",
        }
        e = WorkflowInvocationEvent.from_task_response(data)
        assert e.event_id == "abc-003"
        assert e.workflow_name == "review_code"
        assert e.status == EventStatus.COMPLETE
        assert e.output == "LGTM"
        assert e.node_id == "duck"

    def test_repr(self):
        e = WorkflowInvocationEvent(workflow_name="review_code")
        r = repr(e)
        assert "review_code" in r
        assert "pending" in r


class TestEventCallTree:

    def _make_pipeline_events(self):
        root = WorkflowInvocationEvent(workflow_name="code_pipeline")
        root.mark_complete("final_code")

        gen = WorkflowInvocationEvent(
            workflow_name="generate_code", parent_event_id=root.event_id)
        gen.mark_complete("def foo(): ...")

        review = WorkflowInvocationEvent(
            workflow_name="review_code", parent_event_id=root.event_id)
        review.mark_complete("LGTM")

        improve = WorkflowInvocationEvent(
            workflow_name="improve_code", parent_event_id=root.event_id)
        improve.mark_complete("def foo(): pass")

        return [root, gen, review, improve]

    def test_build_tree(self):
        events = self._make_pipeline_events()
        tree = EventCallTree.build(events)
        assert tree.root.workflow_name == "code_pipeline"
        assert len(tree.children) == 3

    def test_child_names(self):
        events = self._make_pipeline_events()
        tree = EventCallTree.build(events)
        child_names = {c.root.workflow_name for c in tree.children}
        assert child_names == {"generate_code", "review_code", "improve_code"}

    def test_build_raises_without_root(self):
        # All events have a parent that doesn't exist in the list
        orphan = WorkflowInvocationEvent(
            workflow_name="orphan", parent_event_id="nonexistent-id")
        with pytest.raises(ValueError, match="No root event"):
            EventCallTree.build([orphan])

    def test_print_tree_runs(self, capsys):
        events = self._make_pipeline_events()
        tree = EventCallTree.build(events)
        tree.print_tree()
        captured = capsys.readouterr()
        assert "code_pipeline" in captured.out
        assert "generate_code" in captured.out
