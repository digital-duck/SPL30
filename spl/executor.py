"""SPL 3.0 Executor — extends SPL 2.0 executor with new type system support.

New capabilities over SPL 2.0:
  - NoneLiteral (NONE / NULL)  →  evaluates to '' (empty string, consistent
                                  with undefined variables in the string store)
  - SetLiteral                 →  serializes as sorted, deduplicated JSON array
  - INT / INTEGER param type   →  INPUT params coerced via int(float(x))
  - FLOAT param type           →  INPUT params coerced via float(x)
  - IMAGE / AUDIO / VIDEO      →  passed through as-is (file path or data URI);
                                  multimodal encoding is the adapter's job
  - CallParallelStatement      →  dispatches branches via WorkflowComposer

SPL 2.0 backward compatibility is fully preserved.
"""

from __future__ import annotations

import json
import logging

_log = logging.getLogger("spl.executor")

from spl.executor import Executor as SPL2Executor

from spl.ast_nodes import NoneLiteral, SetLiteral, CallParallelStatement
from spl.types import coerce_to_int, coerce_to_float


# Types that receive numeric coercion in workflow INPUT init
_INT_TYPES   = {"INT", "INTEGER"}
_FLOAT_TYPES = {"FLOAT"}


class SPL3Executor(SPL2Executor):
    """SPL 3.0 executor, extending SPL 2.0 with the extended type system."""

    # ------------------------------------------------------------------ #
    # Expression evaluation                                                #
    # ------------------------------------------------------------------ #

    def _eval_expression(self, expr, state) -> str:
        """Evaluate an expression to a string value.

        Handles SPL 3.0 additions before delegating to SPL 2.0:
          NoneLiteral  →  '' (empty string; same as undefined variable)
          SetLiteral   →  sorted, deduplicated JSON array string
        """
        # NONE / NULL literal → empty string
        if isinstance(expr, NoneLiteral):
            return ""

        # SET literal → sorted, deduplicated JSON array
        if isinstance(expr, SetLiteral):
            elements = [self._eval_expression(e, state) for e in expr.elements]
            unique_sorted = sorted(set(elements))
            return json.dumps(unique_sorted)

        return super()._eval_expression(expr, state)

    # ------------------------------------------------------------------ #
    # Workflow execution — typed INPUT param coercion                     #
    # ------------------------------------------------------------------ #

    async def execute_workflow(self, stmt, params=None):
        """Execute a WORKFLOW statement with SPL 3.0 type coercion.

        Before delegating to the SPL 2.0 executor, coerces incoming params
        for INT- and FLOAT-typed INPUT parameters:

          INT / INTEGER  →  int(float(value))   (handles '42', '42.0', etc.)
          FLOAT          →  float(value)

        IMAGE, AUDIO, VIDEO params are passed through as-is (file paths or
        data URIs); encoding is handled by the LLM adapter at inference time.

        All other types use SPL 2.0's existing behavior (str conversion).
        """
        if params and stmt.inputs:
            params = dict(params)  # don't mutate caller's dict
            for inp in stmt.inputs:
                ptype = (inp.param_type or "").upper()
                if inp.name not in params:
                    continue
                if ptype in _INT_TYPES:
                    try:
                        params[inp.name] = str(coerce_to_int(str(params[inp.name])))
                    except ValueError as e:
                        _log.warning("INT coercion failed for %s: %s", inp.name, e)
                elif ptype in _FLOAT_TYPES:
                    try:
                        params[inp.name] = str(coerce_to_float(str(params[inp.name])))
                    except ValueError as e:
                        _log.warning("FLOAT coercion failed for %s: %s", inp.name, e)
                # IMAGE / AUDIO / VIDEO: pass through unchanged (file path / data URI)

        return await super().execute_workflow(stmt, params=params)

    # ------------------------------------------------------------------ #
    # CALL PARALLEL execution                                              #
    # ------------------------------------------------------------------ #

    async def _execute_call_parallel(self, stmt: CallParallelStatement, state) -> None:
        """Execute a CALL PARALLEL statement using WorkflowComposer.

        Requires a WorkflowComposer to be attached as self.composer before
        execution.  Attach it after constructing the executor:

            executor = SPL3Executor(adapter=adapter)
            executor.composer = WorkflowComposer(registry, executor)

        If no composer is set, logs a warning and skips the parallel branches.
        """
        composer = getattr(self, "composer", None)

        if composer is None:
            _log.warning(
                "CALL PARALLEL: no WorkflowComposer attached; "
                "set executor.composer = WorkflowComposer(registry, executor). "
                "Skipping %d branch(es).",
                len(stmt.branches),
            )
            return

        # Build (name, args_dict, into_var) tuples for all branches.
        # Arguments are positional; we resolve names from the target workflow's
        # INPUT param list if available, otherwise use arg0, arg1, ...
        calls = []
        for branch in stmt.branches:
            try:
                defn = composer.registry.get(branch.workflow_name)
                param_names = [inp.name for inp in defn.ast_node.inputs]
            except Exception:
                param_names = []

            args: dict[str, str] = {}
            for i, arg_expr in enumerate(branch.arguments):
                key = param_names[i] if i < len(param_names) else f"arg{i}"
                args[key] = self._eval_expression(arg_expr, state)

            calls.append((branch.workflow_name, args, branch.target_var))

        results = await composer.call_parallel(calls)

        for sub_result in results:
            state.set_var(sub_result.output_var, sub_result.output_value)
            state.total_llm_calls += sub_result.total_llm_calls
            state.total_latency_ms += sub_result.latency_ms

    # ------------------------------------------------------------------ #
    # CALL statement — registry-aware override                             #
    # ------------------------------------------------------------------ #

    async def _exec_call(self, stmt, state) -> None:
        """Execute CALL procedure(args) INTO @var.

        Extends SPL 2.0 _exec_call with workflow registry lookup:

        1. If a WorkflowComposer is attached and the procedure name is found
           in the registry, delegate to the composer (sub-workflow CALL).
        2. Otherwise fall through to SPL 2.0 tool / builtin / LLM handling.
        """
        composer = getattr(self, "composer", None)
        if composer is not None:
            from spl.registry import RegistryError
            try:
                defn = composer.registry.get(stmt.procedure_name)
            except RegistryError:
                defn = None

            if defn is not None:
                # Resolve positional arguments by matching INPUT param names
                try:
                    param_names = [inp.name for inp in defn.ast_node.inputs]
                except (AttributeError, TypeError):
                    param_names = []

                args: dict[str, str] = {}
                for i, arg_expr in enumerate(stmt.arguments):
                    key = param_names[i] if i < len(param_names) else f"arg{i}"
                    args[key] = self._eval_expression(arg_expr, state)

                into_var = stmt.target_variable or ""
                sub_result = await composer.call(stmt.procedure_name, args, into_var)

                if into_var:
                    state.set_var(into_var, sub_result.output_value)
                state.total_llm_calls += sub_result.total_llm_calls
                state.total_latency_ms += sub_result.latency_ms
                return

        # Fall through to SPL 2.0 tool / builtin / procedure / LLM handling
        await super()._exec_call(stmt, state)
