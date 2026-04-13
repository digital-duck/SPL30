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
import re

_log = logging.getLogger("spl.executor")

from spl.executor import Executor as SPL2Executor

from spl.ast_nodes import Condition
from spl3.ast_nodes import NoneLiteral, SetLiteral, CallParallelStatement, UnaryOp, CompoundCondition
from spl3.types import coerce_to_int, coerce_to_float


# Types that receive numeric coercion in workflow INPUT init
_INT_TYPES   = {"INT", "INTEGER"}
_FLOAT_TYPES = {"FLOAT"}


def _builtin_clean_code(text: str) -> str:
    """Remove common LLM output artifacts from generated code.

    Currently handles:
      - Markdown fences  (```python ... ``` or ``` ... ```)
      - Leading / trailing blank lines

    Future candidates: shebang lines, stray prose commentary,
    indentation normalisation, BOM stripping.
    """
    text = text.strip()
    # Remove opening fence line: ```python, ```go, ``` etc.
    text = re.sub(r'^```[^\n]*\n', '', text)
    # Remove closing fence line: trailing ```
    text = re.sub(r'\n```\s*$', '', text)
    return text.strip()


class SPL3Executor(SPL2Executor):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Register SPL 3.0 built-ins
        self.functions._builtins["clean_code"] = lambda text: _builtin_clean_code(str(text))
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
        # NOT <expr> — boolean negation
        if isinstance(expr, UnaryOp) and expr.operator == 'NOT':
            val = self._eval_expression(expr.operand, state)
            # Falsy values: '', '0', 'false', 'FALSE', 'False', 'none', 'null'
            falsy = val.strip().lower() in ('', '0', 'false', 'none', 'null')
            return 'true' if falsy else 'false'

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
    # WHILE condition evaluation                                            #
    # ------------------------------------------------------------------ #

    def _eval_while_cond(self, cond, state) -> bool:
        """Recursively evaluate a WHILE condition to bool.

        Handles SPL 3.0 additions:
          UnaryOp(NOT)      — boolean negation
          CompoundCondition — AND / OR of two sub-conditions
          Condition         — numeric comparison (delegated)
        Falls through to truthy string check for plain expressions.
        """
        if isinstance(cond, CompoundCondition):
            left_val  = self._eval_while_cond(cond.left,  state)
            right_val = self._eval_while_cond(cond.right, state)
            if cond.operator == 'AND':
                return left_val and right_val
            else:  # OR
                return left_val or right_val

        if isinstance(cond, UnaryOp) and cond.operator == 'NOT':
            return not self._eval_while_cond(cond.operand, state)

        if isinstance(cond, Condition):
            try:
                left_val  = float(self._eval_expression(cond.left,  state))
                right_val = float(self._eval_expression(cond.right, state))
                return self._compare(left_val, cond.operator, right_val)
            except (ValueError, TypeError):
                return False

        # Plain expression — truthy string check
        val = self._eval_expression(cond, state)
        return bool(val and val != '0' and val.lower() not in ('false', 'none', 'null'))

    async def _exec_while(self, stmt, state):
        """Override to use _eval_while_cond for SPL 3.0 compound conditions."""
        from spl.ast_nodes import SemanticCondition
        # Only intercept CompoundCondition and UnaryOp; delegate the rest to SPL 2.0
        if isinstance(stmt.condition, (CompoundCondition, UnaryOp)):
            iteration = 0
            max_iter  = stmt.max_iterations or self.DEFAULT_MAX_ITERATIONS
            while iteration < max_iter:
                if state.committed:
                    return
                if not self._eval_while_cond(stmt.condition, state):
                    break
                await self._execute_body(stmt.body, state)
                iteration += 1
            if iteration >= max_iter:
                from spl.exceptions import MaxIterationsReached
                raise MaxIterationsReached(
                    f"WHILE loop exceeded {max_iter} iterations"
                )
            return
        # SPL 2.0 handles Condition and SemanticCondition
        await super()._exec_while(stmt, state)


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
            from spl3.registry import RegistryError
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

Executor = SPL3Executor  # convenience alias for cli.py imports
