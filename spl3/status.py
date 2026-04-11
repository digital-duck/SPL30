"""COMMIT status → EXCEPTION mapping for workflow composition.

In SPL 3.0, OUTPUT is the data channel and COMMIT status is the
exception channel. When a sub-workflow is invoked via:

    CALL generate_code(@spec) INTO @code

the caller receives @code (the OUTPUT value) on success.
If the sub-workflow COMMITs with a non-'complete' status, the calling
executor raises a typed SPLWorkflowError so the caller can handle it
via EXCEPTION WHEN:

    CALL generate_code(@spec) INTO @code
    EXCEPTION WHEN RefusalToAnswer THEN
        COMMIT 'Cannot process.' WITH status = 'blocked'
    END

This design keeps OUTPUT clean (single typed value) and reuses the
existing EXCEPTION hierarchy as the error/status channel — no new
primitives needed.
"""

from __future__ import annotations

# Maps COMMIT status strings to SPL exception type names.
# These align with the exception taxonomy in SPL 2.0 (Appendix D).
STATUS_TO_EXCEPTION: dict[str, str] = {
    "refused":    "RefusalToAnswer",
    "blocked":    "RefusalToAnswer",
    "partial":    "QualityBelowThreshold",
    "timeout":    "NodeUnavailable",
    "error":      "GenerationError",
    "overloaded": "ModelOverloaded",
    "budget":     "BudgetExceeded",
}

# Statuses that are considered successful — no exception raised.
SUCCESSFUL_STATUSES = {"complete", "no_commit"}


def status_to_exception_type(status: str) -> str | None:
    """Return the SPL exception type name for a given COMMIT status.

    Returns None if the status is considered successful (no exception raised).
    Returns 'GenerationError' as a fallback for unknown non-complete statuses.
    """
    if status in SUCCESSFUL_STATUSES:
        return None
    return STATUS_TO_EXCEPTION.get(status, "GenerationError")


def raise_if_failed(status: str, workflow_name: str, output: str | None) -> None:
    """Raise a workflow composition error if status is non-successful.

    Called by WorkflowComposer after a sub-workflow completes.
    The raised exception is caught by the caller's EXCEPTION WHEN handler.
    """
    exc_type = status_to_exception_type(status)
    if exc_type is None:
        return
    raise WorkflowCompositionError(
        exception_type=exc_type,
        workflow_name=workflow_name,
        status=status,
        output=output,
    )


class WorkflowCompositionError(Exception):
    """Raised when a sub-workflow completes with a non-successful COMMIT status.

    Caught by the calling workflow's EXCEPTION WHEN handler.
    The exception_type field aligns with SPL 2.0's exception taxonomy,
    allowing existing EXCEPTION WHEN handlers to catch composition failures
    without any syntax changes.
    """

    def __init__(
        self,
        exception_type: str,
        workflow_name: str,
        status: str,
        output: str | None = None,
    ) -> None:
        self.exception_type = exception_type
        self.workflow_name = workflow_name
        self.status = status
        self.output = output
        super().__init__(
            f"Workflow '{workflow_name}' committed with status='{status}' "
            f"(raises {exception_type})"
        )
