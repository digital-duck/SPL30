"""WorkflowInvocationEvent: the runtime unit of execution in SPL 3.0.

Key design principle: separate definition from invocation.

  Definition  — static, shared, named (the .spl WORKFLOW block)
  Invocation  — dynamic, isolated, identified by event_id (UUID)

Two concurrent callers of 'review_code' produce two independent events
with completely isolated variable scopes. The name collision question
(design-time) is irrelevant at runtime because identity is event_id,
not workflow name.

OS analogy:
  workflow definition  ≈  program binary  (shared, static)
  WorkflowInvocationEvent  ≈  process      (isolated, has PID)
  event_id             ≈  PID
  parent_event_id      ≈  parent PID      (fork() lineage)
  EventStatus          ≈  process state   (R/S/Z)
  Hub event log        ≈  /proc table     (kernel process table)

Hub protocol extension (POST /tasks):
  {
    "type":            "workflow",
    "workflow":        "review_code",
    "args":            {"code": "..."},
    "event_id":        "abc-003",       <- client-generated (idempotency key)
    "parent_event_id": "abc-001",       <- call tree linkage
    "requester_id":    "user-42",       <- attribution / Moma Points debit
    ...existing SPL 2.0 fields...
  }

The Hub's SQLite store (already in momahub.go) becomes the event log:
one row per invocation, queryable by workflow / requester / status / time.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EventStatus(str, Enum):
    PENDING  = "pending"   # submitted, not yet dispatched
    RUNNING  = "running"   # dispatched to a node, executing
    COMPLETE = "complete"  # COMMIT reached, output available
    FAILED   = "failed"    # exception not caught, or non-complete COMMIT status


@dataclass
class WorkflowInvocationEvent:
    """A single runtime invocation of a WORKFLOW definition.

    One event is created per CALL statement at runtime.
    Concurrent invocations of the same workflow produce independent events
    with non-overlapping scopes — no shared state, no name collision risk.

    Fields
    ------
    event_id        Globally unique identifier (UUID4). Used as the Hub
                    task_id and as the idempotency key: re-submitting an
                    already-complete event_id returns the cached output.

    workflow_name   Name of the WORKFLOW definition in the registry.

    namespace       Registry namespace (from IMPORT AS alias). Empty string
                    means local/unqualified scope.

    args            INPUT parameter bindings for this invocation.
                    {param_name: resolved_value} after caller variable
                    substitution.

    requester_id    Identity of the invoking party: a user session ID,
                    a parent workflow's event_id, or an external API key.
                    Used for Moma Points attribution and audit trails.

    parent_event_id event_id of the calling workflow, if this invocation
                    was triggered by a CALL statement inside another
                    workflow. None for top-level invocations (spl run).
                    Chains form a call tree rooted at the top-level event.

    submitted_at    Unix timestamp when the event was created (CALL executed).

    started_at      Unix timestamp when the Hub dispatched to a GPU node.

    completed_at    Unix timestamp when COMMIT or FAILED state was reached.

    status          Current lifecycle state (EventStatus enum).

    output          The workflow's OUTPUT value after COMMIT. None until
                    status == COMPLETE.

    commit_status   The status string from COMMIT ... WITH status = '...'.
                    'complete' for normal completion; other values cause
                    WorkflowCompositionError in the parent event's scope.

    node_id         ID of the GPU node that executed this event (set by Hub
                    on dispatch). Useful for debugging thermal throttle issues.

    error           Exception message if status == FAILED.
    """

    workflow_name:   str
    args:            dict[str, str]        = field(default_factory=dict)
    namespace:       str                   = ""
    requester_id:    str                   = ""
    parent_event_id: Optional[str]         = None
    event_id:        str                   = field(default_factory=lambda: str(uuid.uuid4()))
    submitted_at:    float                 = field(default_factory=time.time)
    started_at:      Optional[float]       = None
    completed_at:    Optional[float]       = None
    status:          EventStatus           = EventStatus.PENDING
    output:          Optional[str]         = None
    commit_status:   str                   = "pending"
    node_id:         Optional[str]         = None
    error:           Optional[str]         = None

    # ------------------------------------------------------------------ #
    # Lifecycle transitions                                                #
    # ------------------------------------------------------------------ #

    def mark_running(self, node_id: str) -> None:
        self.status = EventStatus.RUNNING
        self.started_at = time.time()
        self.node_id = node_id

    def mark_complete(self, output: str, commit_status: str = "complete") -> None:
        self.status = EventStatus.COMPLETE
        self.completed_at = time.time()
        self.output = output
        self.commit_status = commit_status

    def mark_failed(self, error: str, commit_status: str = "error") -> None:
        self.status = EventStatus.FAILED
        self.completed_at = time.time()
        self.error = error
        self.commit_status = commit_status

    # ------------------------------------------------------------------ #
    # Derived properties                                                   #
    # ------------------------------------------------------------------ #

    @property
    def qualified_name(self) -> str:
        """namespace.workflow_name or just workflow_name if no namespace."""
        return f"{self.namespace}.{self.workflow_name}" if self.namespace else self.workflow_name

    @property
    def is_root(self) -> bool:
        """True if this is a top-level invocation (no parent)."""
        return self.parent_event_id is None

    @property
    def latency_ms(self) -> Optional[float]:
        if self.submitted_at and self.completed_at:
            return (self.completed_at - self.submitted_at) * 1000
        return None

    @property
    def queue_wait_ms(self) -> Optional[float]:
        """Time between submission and dispatch to a node."""
        if self.submitted_at and self.started_at:
            return (self.started_at - self.submitted_at) * 1000
        return None

    # ------------------------------------------------------------------ #
    # Hub protocol serialization                                           #
    # ------------------------------------------------------------------ #

    def to_task_payload(self, peer_hub: Optional[str] = None) -> dict:
        """Serialize to Hub POST /tasks request body.

        Extends the SPL 2.0 task payload with event fields.
        Backward compatible: SPL 2.0 nodes ignore unknown fields.
        """
        payload: dict = {
            "type":            "workflow",       # NEW in SPL 3.0
            "workflow":        self.workflow_name,
            "namespace":       self.namespace,
            "args":            self.args,
            "event_id":        self.event_id,    # idempotency key
            "parent_event_id": self.parent_event_id,
            "requester_id":    self.requester_id,
        }
        if peer_hub:
            payload["peer_hub"] = peer_hub       # Hub-to-Hub routing
        return payload

    @classmethod
    def from_task_response(cls, data: dict) -> "WorkflowInvocationEvent":
        """Reconstruct an event from a Hub GET /tasks/{id} response."""
        event = cls(
            workflow_name=data.get("workflow", ""),
            args=data.get("args", {}),
            namespace=data.get("namespace", ""),
            requester_id=data.get("requester_id", ""),
            parent_event_id=data.get("parent_event_id"),
            event_id=data.get("event_id", data.get("task_id", str(uuid.uuid4()))),
        )
        status_str = data.get("status", "pending")
        event.status = EventStatus(status_str) if status_str in EventStatus._value2member_map_ else EventStatus.PENDING
        event.output = data.get("result")
        event.commit_status = data.get("commit_status", status_str)
        event.node_id = data.get("node_id")
        event.error = data.get("error")
        return event

    def __repr__(self) -> str:
        parent = f" parent={self.parent_event_id[:8]}" if self.parent_event_id else ""
        return (
            f"WorkflowInvocationEvent("
            f"id={self.event_id[:8]} "
            f"workflow={self.qualified_name} "
            f"status={self.status.value}"
            f"{parent})"
        )


@dataclass
class EventCallTree:
    """A tree of WorkflowInvocationEvents rooted at a top-level invocation.

    Built by the Hub from its event log for observability:
      GET /events?root=abc-001  →  full call tree

    Useful for:
      - Distributed tracing (parent → child chains)
      - Cost attribution (sum LLM calls across tree)
      - Debugging (which sub-workflow caused the failure?)
    """
    root: WorkflowInvocationEvent
    children: list["EventCallTree"] = field(default_factory=list)

    @classmethod
    def build(cls, events: list[WorkflowInvocationEvent]) -> "EventCallTree":
        """Build a call tree from a flat list of events."""
        by_id = {e.event_id: cls(root=e) for e in events}
        root_node = None
        for node in by_id.values():
            pid = node.root.parent_event_id
            if pid and pid in by_id:
                by_id[pid].children.append(node)
            else:
                root_node = node
        if root_node is None:
            raise ValueError("No root event found (event with no parent_event_id)")
        return root_node

    def total_llm_calls(self) -> int:
        """Recursively count LLM calls across the full tree (for cost attribution)."""
        # Placeholder — real impl would sum from WorkflowResult.total_llm_calls
        return 1 + sum(c.total_llm_calls() for c in self.children)

    def print_tree(self, indent: int = 0) -> None:
        prefix = "  " * indent
        status = self.root.status.value
        latency = f"{self.root.latency_ms:.0f}ms" if self.root.latency_ms else "..."
        print(f"{prefix}[{self.root.event_id[:8]}] {self.root.qualified_name}  {status}  {latency}")
        for child in self.children:
            child.print_tree(indent + 1)
