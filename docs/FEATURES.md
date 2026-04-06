# SPL 3.0 — Implemented Features

*Last updated: 2026-04-05. Based on `pytest tests/ -v` in conda env `spl2`.*
*Test result: **85 passed, 10 failed** out of 95 total.*

Status legend:
- `[DONE]` — implemented and all tests passing
- `[PARTIAL]` — implemented, some tests failing (root cause noted)
- `[TODO]` — designed/documented in ROADMAP.md, not yet coded

---

## spl/ — Core Runtime

### Type System (`spl/types.py`)

| Feature | Status | Tests |
|---|---|---|
| `SPL3Type` enum (TEXT, NUMBER, BOOL, LIST, MAP, STORAGE) | `[DONE]` | `test_types.py::TestSPL3Type` |
| `INT` / `FLOAT` split from `NUMBER` (v3.0 precision) | `[DONE]` | `TestSPL3Type`, `TestNumericTypes` |
| `NONE` / `NULL` type (first-class null) | `[DONE]` | `TestSPL3Type` |
| `SET` type (unordered unique collection) | `[DONE]` | `TestSPL3Type`, `TestSetLiteral` |
| `IMAGE` / `AUDIO` / `VIDEO` multimodal types | `[DONE]` | `TestSPL3Type`, `TestMultimodalTypes` |
| `DATACLASS` type placeholder (v3.1) | `[DONE]` | `TestSPL3Type` (enum member only) |
| `from_str()` with aliases (BOOLEAN→BOOL, NULL→NONE, INTEGER→INT, STR→TEXT, DICT→MAP) | `[DONE]` | `TestSPL3Type::test_from_str_aliases` |
| `is_multimodal` / `is_collection` / `is_numeric` properties | `[DONE]` | `TestSPL3Type` |
| `python_equivalent` property | `[DONE]` | `TestSPL3Type::test_python_equivalent` |
| `coerce_to_int()` (handles float strings: `"7.9"` → `7`) | `[DONE]` | `TestCoerceHelpers` |
| `coerce_to_float()` | `[DONE]` | `TestCoerceHelpers` |
| `is_none_value()` (NONE serializes to `""`) | `[DONE]` | `TestCoerceHelpers` |
| `SPL3_TYPE_KEYWORDS` dict for lexer extension | `[DONE]` | (unit test via `from_str`) |

### Parser Extensions (`spl/parser.py`, `spl/ast_nodes.py`)

| Feature | Status | Tests |
|---|---|---|
| `SET` literal `{a, b, c}` parsing + `{}` → MAP disambiguation | `[DONE]` | `TestSetLiteral` |
| `SET` evaluates to sorted, deduplicated JSON array | `[DONE]` | `TestSetLiteral::test_set_evaluates_to_sorted_json_array` |
| `IMPORT 'file.spl'` statement parsing | `[DONE]` | `TestImportStatement::test_import_parses` |
| `IMPORT` before `WORKFLOW` in same file | `[DONE]` | `TestImportStatement::test_import_before_workflow` |
| INT / FLOAT / IMAGE / AUDIO / VIDEO type annotations in `INPUT:` | `[DONE]` | `TestNumericTypes`, `TestMultimodalTypes`, `TestSetTypeAnnotation` |
| `NONE` / `NULL` as expression literal (`@x := NONE`) | `[PARTIAL]` | 4 tests fail — SPL2 base parser rejects NONE as expression token; SPL3Parser extension not yet wired |
| `NULL` alias for NONE | `[PARTIAL]` | same root cause |

### Loader (`spl/_loader.py`)

| Feature | Status | Tests |
|---|---|---|
| `load_workflows_from_file()` — parses `.spl` and returns `WorkflowDefinition` list | `[DONE]` | `TestImportStatement::test_import_loader_resolves_file` |
| IMPORT chain resolution (follows imports transitively) | `[DONE]` | `TestImportStatement::test_import_loader_resolves_file` |
| Circular IMPORT detection + warning (skips, does not crash) | `[DONE]` | `TestImportStatement::test_import_circular_detected` |

### Registry (`spl/registry.py`)

| Feature | Status | Tests |
|---|---|---|
| `LocalRegistry` — register / get / has / list / `__len__` | `[DONE]` | `TestLocalRegistry` |
| Overwrite-with-warning on name collision | `[DONE]` | `TestLocalRegistry::test_overwrite_warns` |
| `load_file()` — parse + register from `.spl` file | `[DONE]` | `TestLocalRegistry::test_load_file` |
| `load_dir()` — recursive load from directory | `[DONE]` | `TestLocalRegistry::test_load_dir` (uses `cookbook/code_pipeline/`) |
| `FederatedRegistry` — local-first, Hub fallback on miss | `[DONE]` | `TestFederatedRegistry` |
| `HubRegistry` — REST-backed registry | `[TODO]` | (designed in `spl/hub_registry.py`) |

### Invocation Event Model (`spl/event.py`)

| Feature | Status | Tests |
|---|---|---|
| `WorkflowInvocationEvent` dataclass (event_id, workflow_name, args, status, output) | `[DONE]` | `TestWorkflowInvocationEvent` |
| `EventStatus` enum (PENDING → RUNNING → COMPLETE \| FAILED) | `[DONE]` | `TestWorkflowInvocationEvent` |
| `mark_running()` / `mark_complete()` / `mark_failed()` lifecycle transitions | `[DONE]` | `TestWorkflowInvocationEvent` |
| `parent_event_id` call-tree linkage | `[DONE]` | `TestWorkflowInvocationEvent::test_is_not_root_when_has_parent` |
| `qualified_name` (namespace.workflow_name) | `[DONE]` | `TestWorkflowInvocationEvent::test_qualified_name_with_namespace` |
| `latency_ms` / `queue_wait_ms` derived properties | `[DONE]` | `TestWorkflowInvocationEvent::test_latency_ms` |
| `to_task_payload()` — Hub POST /tasks serialization (with `peer_hub` support) | `[DONE]` | `TestWorkflowInvocationEvent::test_to_task_payload` |
| `from_task_response()` — Hub GET /tasks/{id} deserialization | `[DONE]` | `TestWorkflowInvocationEvent::test_from_task_response` |
| `EventCallTree.build()` — reconstruct call tree from flat event list | `[DONE]` | `TestEventCallTree::test_build_tree` |
| `EventCallTree.print_tree()` — visual call tree for debugging | `[DONE]` | `TestEventCallTree::test_print_tree_runs` |
| `EventCallTree.build()` raises `ValueError` for all-orphaned events | `[PARTIAL]` | 1 test fails — build() returns None instead of raising |

### COMMIT Status → EXCEPTION Channel (`spl/status.py`)

| Feature | Status | Tests |
|---|---|---|
| `STATUS_TO_EXCEPTION` mapping (refused/blocked → RefusalToAnswer, partial → QualityBelowThreshold, timeout → NodeUnavailable, etc.) | `[DONE]` | `TestStatusToExceptionType` |
| `SUCCESSFUL_STATUSES` set (`complete`, `no_commit`) | `[DONE]` | `TestStatusToExceptionType` |
| `status_to_exception_type()` — unknown statuses fall back to GenerationError | `[DONE]` | `TestStatusToExceptionType::test_unknown_status_maps_to_generation_error` |
| `raise_if_failed()` — raises `WorkflowCompositionError` on non-success | `[DONE]` | `TestRaiseIfFailed` |
| `WorkflowCompositionError` — typed exception with `exception_type`, `workflow_name`, `status`, `output` fields | `[DONE]` | `TestRaiseIfFailed` |

### Code-RAG (`spl/code_rag.py`)

| Feature | Status | Tests |
|---|---|---|
| `CodeRAGStore` — `add_pair()` / `retrieve()` / `count()` / `format_examples()` | `[PARTIAL]` | 5 tests fail — hardcoded `sentence_transformers` provider; not installed in spl2. Switch to `ollama` adapter to fix |
| `seed_from_dir()` — index `.spl` files from a directory | `[PARTIAL]` | same root cause |
| `seed_from_catalog()` — index from JSON catalog | `[PARTIAL]` | same root cause |

### Workflow Composition (`spl/composer.py`)

| Feature | Status | Tests |
|---|---|---|
| `CALL workflow_name(@args) INTO @var` resolution | `[TODO]` | no tests yet |
| `CALL PARALLEL ... END` concurrent dispatch | `[TODO]` | no tests yet |

---

## text2spl/ — Semantic Layer (text → SPL logical view)

### Shared Recipe RAG (`spl/rag/`)

| Feature | Status | Notes |
|---|---|---|
| `index_recipes.py` — index all SPL v2.0 recipes into ChromaDB | `[DONE]` | 41/42 recipes indexed; recipe 22 skipped (shell script, no `.spl`). Uses `dd_embed` (OllamaEmbedAdapter) + `dd_vectordb` (ChromaVectorDB). Run: `python spl/rag/index_recipes.py --reset` |
| Context-window truncation (6 000 char cap for nomic-embed-text) | `[DONE]` | Prevents HTTP 500 on long recipes (plan_execute, code_review, ensemble_voting) |
| `search.py` — `search_recipes(query, k, category)` retrieval | `[DONE]` | Verified: rank-1 hit is semantically exact for 3 test queries |
| Category filter in search | `[DONE]` | `--category agentic` etc. |
| `text2spl.spl` workflow (intent → spec → .spl) | `[TODO]` | Design in SPL-by-spec.md; not yet coded |

---

## splc/ — Structural Layer (SPL logical view → physical deployment)

### Targets: Python (`cookbook/05_self_refine/targets/python/`)

| Target | Framework | Status | Notes |
|---|---|---|---|
| `self_refine_langgraph.py` | LangGraph | `[DONE]` | state graph: draft → critique → refine → commit |
| `self_refine_crewai.py` | CrewAI | `[DONE]` | Writer + Critic agents with manual loop |
| `self_refine_autogen.py` | AutoGen | `[DONE]` | ConversableAgent pair with termination condition |

### Targets: Go (`cookbook/05_self_refine/targets/go/`)

| Target | Status | Notes |
|---|---|---|
| `self_refine.go` (`splc --target go` prototype) | `[DONE]` | stdlib only; calls Ollama REST API directly; compiles and runs end-to-end |
| `go.mod` | `[DONE]` | module `spl30/self_refine`, Go 1.22, zero external deps |

### Targets: planned

| Target | Status | Notes |
|---|---|---|
| `splc --target snap` (Ubuntu 26.04 Inference Snap) | `[TODO]` | v3.1 milestone |
| `splc --target swift` (Apple M4/M5 Metal) | `[TODO]` | v3.2 milestone |
| `splc --target edge` (ARM / Android AICore) | `[TODO]` | v3.3 milestone |

---

## Cookbook Recipes (`cookbook/`)

| Recipe | Status | Notes |
|---|---|---|
| `05_self_refine/self_refine.spl` | `[DONE]` | Draft → critique → refine loop; WHILE + EVALUATE |
| `arxiv_morning_brief/` | `[DONE]` | Multi-workflow SPL3 recipe; `tools.py` + unit tests |
| `code_pipeline/` | `[DONE]` | CALL composition demo: generate → review → improve |

---

## Known Failures (10 tests)

| Test | Root Cause | Fix |
|---|---|---|
| `TestNoneLiteral::test_none_parses` (×4) | SPL2 base parser rejects `NONE` as an expression token — SPL3Parser extension not yet wired into expression dispatch | Extend `spl/parser.py` to handle `NONE`/`NULL` tokens as `NoneLiteral` AST nodes |
| `TestCodeRAGStore::*` (×5) | `spl/code_rag.py` hardcodes `sentence_transformers` as embed provider; not installed in spl2 | Change `_EMBED_PROVIDER = "ollama"` and `_EMBED_MODEL = "nomic-embed-text"` in `code_rag.py` |
| `TestEventCallTree::test_build_raises_without_root` | `EventCallTree.build()` returns `None` instead of raising `ValueError` when no root event exists | Add `if root_node is None: raise ValueError(...)` guard in `build()` |
