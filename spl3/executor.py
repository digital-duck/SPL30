"""SPL 3.0 Executor — extends SPL 2.0 executor with new type system support.

New capabilities over SPL 2.0:
  - NoneLiteral (NONE / NULL)  →  evaluates to '' (empty string, consistent
                                  with undefined variables in the string store)
  - SetLiteral                 →  serializes as sorted, deduplicated JSON array
  - INT / INTEGER param type   →  INPUT params coerced via int(float(x))
  - FLOAT param type           →  INPUT params coerced via float(x)
  - IMAGE / AUDIO / VIDEO      →  when a GENERATE function has an IMAGE-typed
                                  param, the executor encodes the file/URL via
                                  spl3.codecs.encode_image() and calls
                                  adapter.generate_multimodal() instead of
                                  adapter.generate().  Workflow INPUT params of
                                  these types are still passed through as-is.
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
      - Prose preamble before the first fence (e.g. "Here is the code:\n```python\n...")
      - Leading / trailing blank lines

    Future candidates: shebang lines, stray prose commentary,
    indentation normalisation, BOM stripping.
    """
    text = text.strip()
    # If there is a fenced code block anywhere, extract just its content.
    # This handles prose preamble that precedes the fence.
    m = re.search(r'```[^\n]*\n(.*?)```', text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # Fallback: no fences found — strip any stray fence markers and return.
    text = re.sub(r'```[^\n]*\n?', '', text)
    text = re.sub(r'\n?```', '', text)
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
    # GENERATE — multimodal dispatch for IMAGE/AUDIO/VIDEO-typed params   #
    # ------------------------------------------------------------------ #

    _MULTIMODAL_TYPES = {"IMAGE", "AUDIO", "VIDEO"}

    async def _exec_generate_into(self, stmt, state):
        """Override to dispatch to generate_multimodal() when a GENERATE
        function has one or more IMAGE-, AUDIO-, or VIDEO-typed parameters.

        Strategy:
          1. Inspect the first GENERATE segment's function definition.
          2. If no multimodal params are found, delegate entirely to the SPL 2.0
             implementation (zero overhead for all text-only workflows).
          3. If multimodal params are present, encode each arg via the matching
             codec (encode_image / encode_audio), build a content array
             [TextPart, ...MediaParts], and call adapter.generate_multimodal().
        """
        first_gen = stmt.generate_clause
        if first_gen is None:
            return await super()._exec_generate_into(stmt, state)

        func_def = self.functions.get(first_gen.function_name)
        if not func_def:
            return await super()._exec_generate_into(stmt, state)

        mm_param_names = {
            p.name for p in func_def.parameters
            if (getattr(p, "param_type", None) or "").upper() in self._MULTIMODAL_TYPES
        }
        if not mm_param_names:
            return await super()._exec_generate_into(stmt, state)

        # ── Multimodal path ───────────────────────────────────────────────
        from spl3.codecs.image_codec import encode_image
        from spl3.codecs.audio_codec import encode_audio

        current_gen = first_gen
        last_content: str = ""
        segment_count = 0

        while current_gen is not None:
            segment_count += 1

            args_text = []
            for arg in current_gen.arguments:
                args_text.append(self._eval_expression(arg, state))

            if segment_count > 1 and not args_text:
                args_text = [last_content]

            # Resolve function def for this segment (may differ from first)
            seg_func_def = self.functions.get(current_gen.function_name)
            if seg_func_def:
                seg_mm_params = {
                    p.name: (getattr(p, "param_type", None) or "").upper()
                    for p in seg_func_def.parameters
                    if (getattr(p, "param_type", None) or "").upper() in self._MULTIMODAL_TYPES
                }
                prompt = seg_func_def.body
                media_parts = []
                for param, arg_val in zip(seg_func_def.parameters, args_text):
                    ptype = seg_mm_params.get(param.name)
                    if ptype == "IMAGE":
                        try:
                            media_parts.append(encode_image(arg_val))
                        except Exception as exc:
                            _log.warning("IMAGE encode failed for %s=%r: %s",
                                         param.name, arg_val, exc)
                    elif ptype == "AUDIO":
                        try:
                            media_parts.append(encode_audio(arg_val))
                        except Exception as exc:
                            _log.warning("AUDIO encode failed for %s=%r: %s",
                                         param.name, arg_val, exc)
                    else:
                        prompt = prompt.replace("{" + param.name + "}", arg_val)
            else:
                prompt = f"Task: {current_gen.function_name}\n\n"
                for i, arg_val in enumerate(args_text):
                    prompt += f"Input {i+1}:\n{arg_val}\n\n"
                media_parts = []

            if self.default_model:
                model = self.default_model
            elif "model" in state.current_overrides:
                model = state.current_overrides["model"]
            else:
                model = current_gen.model or ""
                if model.startswith("@"):
                    model = state.get_var(model[1:])

            budget = current_gen.output_budget
            if isinstance(budget, str) and budget.startswith("@"):
                budget = int(state.get_var(budget[1:]))
            max_tokens = int(budget) if budget else self.default_max_tokens

            temp = current_gen.temperature or 0.7
            if "temperature" in state.current_overrides:
                try:
                    temp = float(state.current_overrides["temperature"])
                except ValueError:
                    pass

            self._log_prompt(current_gen.function_name, model, prompt, max_tokens, temp)
            self._check_budget(state)

            if media_parts and hasattr(self.adapter, "generate_multimodal"):
                content = [{"type": "text", "text": prompt}] + media_parts
                gen_result = await self.adapter.generate_multimodal(
                    content,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temp,
                )
            else:
                gen_result = await self.adapter.generate(
                    prompt=prompt,
                    model=model,
                    max_tokens=max_tokens,
                    temperature=temp,
                )

            state.record_llm_call(gen_result)
            last_content = gen_result.content

            _log.info("GENERATE segment %d (%s) -> %d tokens, %.0fms",
                      segment_count, current_gen.function_name,
                      gen_result.output_tokens, gen_result.latency_ms)

            current_gen = current_gen.next_segment

        if stmt.target_variable and stmt.target_variable not in ("NONE", "_"):
            state.set_var(stmt.target_variable, last_content)
            _log.info("GENERATE chain done -> @%s (%d chars total)",
                      stmt.target_variable, len(last_content))
        else:
            _log.info("GENERATE chain done -> [DISCARDED] (%d chars)", len(last_content))

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
