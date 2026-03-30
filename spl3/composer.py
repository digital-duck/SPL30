"""WorkflowComposer: extends SPL 2.0 executor with workflow-to-workflow CALL.

When the SPL 3.0 executor encounters:

    CALL generate_code(@spec) INTO @code

it resolves 'generate_code' via the WorkflowRegistry, executes it as a
sub-workflow with scoped variable binding, maps the OUTPUT back to the
caller's @code, and raises a WorkflowCompositionError if the sub-workflow
commits with a non-complete status.

In OS terms:
  - CALL = system call (push frame onto Hub workflow stack)
  - Sub-workflow execution = child process
  - OUTPUT binding = return value via Hub register
  - COMMIT status = exit code (non-zero → exception in caller)

CALL PARALLEL dispatches multiple sub-workflows concurrently via
asyncio.gather — the Hub routes them to different nodes, same mechanism
as existing multi-node task dispatch.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass

from spl3.status import raise_if_failed

_log = logging.getLogger("spl3.composer")


@dataclass
class SubWorkflowResult:
    """Result of a single sub-workflow CALL."""
    workflow_name: str
    output_var: str          # caller's INTO @var name
    output_value: str        # value to bind
    status: str
    latency_ms: float
    total_llm_calls: int


class WorkflowComposer:
    """Executes CALL workflow_name(@args) INTO @var statements.

    Instantiated by the SPL 3.0 executor and called whenever a
    CallStatement targets a registered WORKFLOW (not just an @spl_tool).

    The composer is stateless — it receives the caller's variable state,
    creates an isolated scope for the sub-workflow, executes it, and
    returns the OUTPUT binding back to the caller.
    """

    def __init__(self, registry, executor) -> None:
        """
        registry: spl3.registry.LocalRegistry | FederatedRegistry
        executor: spl.executor.Executor (SPL 2.0 executor instance)
        """
        self.registry = registry
        self.executor = executor

    async def call(
        self,
        workflow_name: str,
        args: dict[str, str],
        into_var: str,
    ) -> SubWorkflowResult:
        """Execute a named workflow and return its OUTPUT binding.

        args:     caller's resolved argument values {param_name: value}
        into_var: name of the caller's variable to bind the OUTPUT into

        Raises WorkflowCompositionError if sub-workflow status is non-complete.
        """
        defn = self.registry.get(workflow_name)
        stmt = defn.ast_node

        _log.info("CALL %s(%s) INTO @%s", workflow_name, list(args), into_var)
        start = time.perf_counter()

        result = await self.executor.execute_workflow(stmt, params=args)

        latency = (time.perf_counter() - start) * 1000
        _log.info(
            "CALL %s completed: status=%s in %.0fms (%d LLM calls)",
            workflow_name, result.status, latency, result.total_llm_calls,
        )

        # Status → exception mapping: non-complete raises in caller scope.
        raise_if_failed(result.status, workflow_name, result.committed_value)

        # Extract OUTPUT: prefer committed_value, fall back to first output var.
        output_value = result.committed_value or ""
        if not output_value and stmt.outputs:
            first_out = stmt.outputs[0].name
            output_value = result.output.get(first_out, "")

        return SubWorkflowResult(
            workflow_name=workflow_name,
            output_var=into_var,
            output_value=output_value,
            status=result.status,
            latency_ms=latency,
            total_llm_calls=result.total_llm_calls,
        )

    async def call_parallel(
        self,
        calls: list[tuple[str, dict[str, str], str]],
    ) -> list[SubWorkflowResult]:
        """Execute multiple sub-workflows concurrently (CALL PARALLEL).

        calls: list of (workflow_name, args, into_var) tuples

        All sub-workflows run concurrently via asyncio.gather.
        The Hub routes each to an available node — same as existing
        multi-node task dispatch, no new infrastructure.

        If any sub-workflow fails, all results are still collected;
        the first failure raises after all have completed.
        """
        tasks = [
            self.call(name, args, into_var)
            for name, args, into_var in calls
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Re-raise first exception after collecting all results.
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            raise errors[0]

        return [r for r in results if isinstance(r, SubWorkflowResult)]
