# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Package Identity

- Package name: `spl` (PyPI), but the source lives in `spl3/` — **not** `spl/`
- CLI entry point: `spl3` (maps to `spl3.cli:main`)
- Depends on `spl-llm >= 2.0.0` (SPL 2.0 runtime — lexer, parser, base executor, adapters). Import from `spl.xxx` for SPL 2.0 symbols; import from `spl3.xxx` for SPL 3.0 additions.

## Install & Setup

```bash
conda activate spl3          # Python 3.11 environment
pip install spl-llm>=2.0.0                     # SPL 2.0 base runtime
pip install -e ~/projects/digital-duck/SPL30   # this repo
```

## Common Commands

```bash
# Run a workflow
spl3 run cookbook/05_self_refine/self_refine.spl \
    --adapter ollama \
    --param writer_model="gemma3" \
    --param critic_model="gemma3"

# Run with prompt logging
spl3 run <file.spl> --adapter ollama --log-prompts <dir>

# Run against a Momagrid Hub
spl3 --hub http://localhost:8080 run <file.spl>

# Register workflows on Hub
spl3 --hub http://localhost:8080 register cookbook/05_self_refine/

# Pipeline-level tests (requires .test.yaml alongside .spl)
spl3 test cookbook/05_self_refine/self_refine.spl --adapter ollama

# Unit tests
pytest
pytest tests/test_registry.py          # single file
pytest -k test_status_mapping          # single test

# Code-RAG index
spl3 code-rag seed cookbook/ --catalog cookbook/cookbook_catalog.json
spl3 code-rag query "judge-retry loop"
```

## Architecture

### SPL 3.0 extends SPL 2.0 — never replaces it

```
spl3/
  cli.py          — entry point; builds registry + executor + composer, then runs
  _loader.py      — parses .spl files; returns WorkflowDefinition list; handles IMPORT recursively
  parser.py       — SPL3Parser extends SPL 2.0 parser with new AST nodes
  ast_nodes.py    — SPL 3.0 AST additions: ImportStatement, NoneLiteral, SetLiteral, CallParallelStatement
  executor.py     — SPL3Executor(SPL2Executor): adds type coercion, CALL dispatch, CALL PARALLEL
  registry.py     — LocalRegistry, FederatedRegistry: name → WorkflowDefinition map
  hub_registry.py — REST-backed registry (Hub's POST /tasks endpoint)
  composer.py     — WorkflowComposer: executes sub-workflow CALL, maps OUTPUT back to caller
  event.py        — WorkflowInvocationEvent: runtime identity (event_id/UUID, parent_event_id, status)
  status.py       — COMMIT status → SPL exception type mapping (e.g. "refused" → RefusalToAnswer)
  types.py        — SPL3Type coercion helpers (INT, FLOAT)
  code_rag.py     — CodeRAGStore: indexes .spl cookbook recipes as (description, source) pairs
  peer.py         — Hub-to-Hub peering
```

### Execution flow for `spl3 run`

1. `cli.py` parses `--param` flags, builds `LocalRegistry` by loading all `.spl` files in the same directory as the target file, attaches `HubRegistry` if `--hub` given.
2. `_loader.py` tokenizes (SPL 2.0 `Lexer`) → parses (`SPL3Parser`) → returns `WorkflowDefinition` list; resolves `IMPORT` recursively.
3. `SPL3Executor` is created with the adapter; a `WorkflowComposer(registry, executor)` is attached as `executor.composer`.
4. `executor.execute_workflow(stmt, params)` runs the top-level workflow. On `CALL workflow_name(...)`, `_exec_call` checks the composer's registry first; if found, delegates to `WorkflowComposer.call()` (sub-workflow), otherwise falls through to SPL 2.0 tool/LLM handling.
5. `CALL PARALLEL` dispatches via `composer.call_parallel()` → `asyncio.gather`.
6. Non-`complete` COMMIT status raises `WorkflowCompositionError` (from `status.py`) in the calling scope.

### Registry resolution order

`FederatedRegistry.get(name)` → local first → Hub peers on miss. This mirrors OS shared-library lookup.

### Workflow definition vs. invocation

`WorkflowDefinition` is static (parsed AST). `WorkflowInvocationEvent` is the runtime instance (UUID `event_id`, lifecycle, Hub serialization). Two concurrent `CALL review_code(...)` produce two independent events with isolated variable scopes.

## Cookbook structure

Each cookbook recipe is a numbered directory under `cookbook/`:

```
cookbook/05_self_refine/
  self_refine.spl          — orchestrator + critique_workflow (sub-workflow CALL demo)
  self_refine.test.yaml    — pipeline-level test cases
  targets/python/langgraph/  — LangGraph port of same pattern
  benchmark-langgraph.sh   — runs gemma3, gemma4:e2b, gemma4:e4b sequentially
```

The self-refine recipe is the **primary integration test** for sub-workflow CALL composition — it was the first recipe in SPL30 to use `CALL critique_workflow(...) INTO @feedback`.

## Key conventions

- **Extension, not replacement:** `SPL3Executor` must stay backward compatible with SPL 2.0. New statement handling goes in overridden methods (`_eval_expression`, `execute_workflow`, `_exec_call`) and always calls `super()` as the fallback.
- **`Executor` alias:** `executor.py` exports `Executor = SPL3Executor` so `cli.py` can `from spl3.executor import Executor` without caring about the class name.
- **COMMIT status is the exception channel:** OUTPUT carries the value; non-`complete` status raises `WorkflowCompositionError`. Add new status strings to `STATUS_TO_EXCEPTION` in `status.py`.
- **New cookbook recipes** need both a `.spl` file and a `.test.yaml` alongside it.
- **`asyncio_mode = "auto"`** is set in `pyproject.toml` — async test functions work without `@pytest.mark.asyncio`.
