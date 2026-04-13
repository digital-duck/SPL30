# SPL — Implemented Features

*Last updated: 2026-04-13.*
*SPL30 is the canonical source of truth for SPL language design and runtime features.*

Status legend:
- `[DONE]` — implemented and tested
- `[PARTIAL]` — implemented, some gaps or known issues noted
- `[TODO]` — designed, not yet coded (see ROADMAP.md)

---

## Language Versions

| Version | Runtime | CLI | Repo |
|---------|---------|-----|------|
| SPL 1.0 | Python | `spl` | `SPL/` |
| SPL 2.0 | Python | `spl3` (base layer) | `SPL20/` |
| SPL 3.0 | Python | `spl3` | `SPL30/` |
| SPL (Go port) | Go | `spl-go` | `SPL.go/` |
| SPL (TypeScript port) | TypeScript / Node.js / Browser | `spl-ts` | `SPL.ts/` |

SPL30 is the reference implementation. All other runtimes are ports validated
against SPL30 via **NDD closure** (`spl3 run --adapter echo` as oracle, `diff` as judge).

---

## SPL Language Constructs

### SPL 1.0 — Prompt-Query Layer

| Construct | Description | Status |
|-----------|-------------|--------|
| `PROMPT name WITH BUDGET n TOKENS` | Named prompt definition with token budget | `[DONE]` |
| `SELECT expr AS alias LIMIT n TOKENS` | Select clause with per-item token limits | `[DONE]` |
| `FROM source AS alias` | Data source binding | `[DONE]` |
| `WHERE cond AND/OR cond` | Deterministic filter conditions | `[DONE]` |
| `ORDER BY expr ASC/DESC` | Result ordering | `[DONE]` |
| `GENERATE fn(args) WITH OUTPUT BUDGET n TOKENS` | LLM generation clause | `[DONE]` |
| `USING MODEL 'name'` | Per-prompt model selection | `[DONE]` |
| `STORE RESULT IN memory.key` | Result persistence | `[DONE]` |
| `CACHE FOR n minutes/hours` | Prompt result caching | `[DONE]` |
| `VERSION n` | Prompt versioning | `[DONE]` |
| `ON GRID [url]` | Route execution to Momagrid node | `[DONE]` |
| `WITH VRAM n` | Minimum VRAM constraint for node selection | `[DONE]` |
| `WITH ... AS (...)` CTEs | Common Table Expressions (composable sub-prompts) | `[DONE]` |
| `CREATE FUNCTION name(params) RETURN TEXT AS $$ ... $$` | Named prompt templates | `[DONE]` |
| `EXPLAIN PROMPT name` | Prompt introspection | `[DONE]` |
| `EXECUTE PROMPT name WITH PARAMS (...)` | Dynamic prompt invocation | `[DONE]` |
| `rag.query(text, top_k=n)` | RAG retrieval in SELECT | `[DONE]` |
| `memory.get('key')` | Memory read in SELECT | `[DONE]` |
| `system_role('desc')` | System role injection | `[DONE]` |
| `context.field` | Context field reference | `[DONE]` |

### SPL 2.0 — Workflow / Procedural Layer

| Construct | Description | Status |
|-----------|-------------|--------|
| `WORKFLOW name INPUT: ... OUTPUT: ... DO ... END` | Named workflow definition | `[DONE]` |
| `PROCEDURE name(params) RETURNS type DO ... END` | Named procedure (function-style) | `[DONE]` |
| `@var := expr` | Variable assignment | `[DONE]` |
| `SET @var = expr` | Alternative assignment syntax | `[DONE]` |
| `GENERATE fn(args) ... INTO @var` | LLM generation into variable | `[DONE]` |
| `SELECT ... FROM ... INTO @var` | Query result into variable | `[DONE]` |
| `CALL name(args) INTO @var` | Sub-workflow / procedure call | `[DONE]` |
| `EVALUATE @var WHEN ... THEN ... ELSE ... END` | Semantic branching | `[DONE]` |
| `WHEN contains('token')` | Token presence condition | `[DONE]` |
| `WHEN contains('a') OR contains('b')` | Multi-token OR condition | `[DONE]` |
| `WHEN startswith('prefix')` | Prefix condition | `[DONE]` |
| `WHEN = value / > / < / >= / <=` | Comparison conditions | `[DONE]` |
| `WHILE cond DO ... END` | Conditional loop | `[DONE]` |
| `WHILE NOT @var DO` | Negation loop condition | `[DONE]` |
| `WHILE @a < @b AND NOT @done DO` | Compound loop condition (AND/OR) | `[DONE]` |
| `WHILE @item IN @items DO` | Collection iteration | `[DONE]` |
| `RETURN expr [WITH status = '...']` | Commit workflow output with optional status | `[DONE]` |
| `COMMIT expr [WITH status = '...']` | Alias for RETURN (deprecated) | `[DONE]` |
| `RAISE ExceptionType 'message'` | Raise SPL exception | `[DONE]` |
| `EXCEPTION WHEN Type THEN ... END` | Exception handler | `[DONE]` |
| `WHEN OTHERS THEN` | Catch-all exception handler | `[DONE]` |
| `DO ... EXCEPTION ... END` | Inline exception scope | `[DONE]` |
| `RETRY [WITH ...] [LIMIT n]` | Retry on failure | `[DONE]` |
| `LOGGING expr LEVEL INFO/DEBUG/WARN/ERROR` | Structured logging | `[DONE]` |
| `LOGGING expr TO 'file'` | Log to file destination | `[DONE]` |
| `f'text {@var} text'` | F-string interpolation | `[DONE]` |
| `@a + @b` / `@a - @b` / `@a || @b` | Arithmetic and string concat operators | `[DONE]` |
| `[a, b, c]` list literals | List literal expression | `[DONE]` |
| `{'key': value}` map literals | Map literal expression | `[DONE]` |
| `DEFAULT value` on INPUT params | Input parameter defaults | `[DONE]` |
| `SECURITY: CLASSIFICATION: level` | Security metadata block | `[DONE]` |
| `ACCOUNTING: key: value` | Accounting metadata block | `[DONE]` |
| `LABELS: {'key': 'value'}` | Label metadata block | `[DONE]` |

### SPL 3.0 — Composition / Distribution Layer

| Construct | Description | Status |
|-----------|-------------|--------|
| `IMPORT 'file.spl'` | Multi-file workflow composition | `[DONE]` |
| `IMPORT 'file'` | Extension-optional import | `[DONE]` |
| `CALL PARALLEL ... END` | Concurrent sub-workflow dispatch | `[DONE]` |
| `INTO NONE` | Discard call result explicitly | `[DONE]` |
| `{a, b, c}` SET literals | Unordered unique collection | `[DONE]` |
| `NONE` / `NULL` literals | First-class null value | `[PARTIAL]` — SPL2 base parser gap |
| `IMAGE` / `AUDIO` / `VIDEO` param types | Multi-modal INPUT type annotations | `[DONE]` |
| `STORAGE(backend, path)` param type | Persistent storage binding | `[DONE]` |

---

## Exception Types

| Exception | Raised when |
|-----------|-------------|
| `RefusalToAnswer` | Model refuses to answer |
| `HallucinationDetected` | LLM judge flags hallucination |
| `ModelUnavailable` | Adapter cannot reach model |
| `MaxIterationsReached` | WHILE loop exceeds limit |
| `QualityBelowThreshold` | Quality judge score too low |
| `WorkflowCompositionError` | CALL returns non-complete status |
| `ToolFailed` | CALL tool raises Python exception |

---

## Type System

| Type | Description | Status |
|------|-------------|--------|
| `TEXT` | String (default) | `[DONE]` |
| `INT` / `INTEGER` | Integer with coercion from float strings | `[DONE]` |
| `FLOAT` | Floating point | `[DONE]` |
| `BOOL` | Boolean (`TRUE`/`FALSE`) | `[DONE]` |
| `LIST` | JSON array | `[DONE]` |
| `MAP` | JSON object | `[DONE]` |
| `SET` | Sorted deduplicated JSON array | `[DONE]` |
| `NONE` / `NULL` | First-class null | `[PARTIAL]` |
| `IMAGE` / `AUDIO` / `VIDEO` | Multi-modal media | `[DONE]` |
| `STORAGE` | Persistent key-value store binding | `[DONE]` |

---

## Adapters

### Python (SPL30)

| Adapter | Backend | Status |
|---------|---------|--------|
| `ollama` | Ollama REST API (local) | `[DONE]` |
| `echo` | Returns prompt unchanged (NDD closure testing) | `[DONE]` |
| `anthropic` / `claude_cli` | Anthropic API | `[DONE]` |
| `openai` | OpenAI API | `[DONE]` |
| `openrouter` | OpenRouter | `[DONE]` |
| `deepseek` | DeepSeek API | `[DONE]` |
| `qwen` | Qwen API | `[DONE]` |
| `liquid` (LiquidAdapter) | LFM2-8B/24B + LFM-2.5 via Ollama or OpenRouter | `[DONE]` |
| `snap` (SnapAdapter) | Ubuntu AI Snap | `[TODO]` — awaits Ubuntu 26.04 GA |
| Multi-modal base (`MultiModalMixin`) | Image / Audio / Video content parts | `[DONE]` |

### Go (SPL.go)

| Adapter | Status |
|---------|--------|
| `ollama` | `[DONE]` |
| `echo` | `[DONE]` |
| `anthropic` | `[DONE]` |
| `openai` | `[DONE]` |
| `openrouter` | `[DONE]` |
| `deepseek` | `[DONE]` |
| `qwen` | `[DONE]` |
| `momagrid` | `[DONE]` |
| `claude_cli` | `[DONE]` |

### TypeScript (SPL.ts)

| Adapter | Status | Notes |
|---------|--------|-------|
| `echo` | `[DONE]` | NDD closure oracle |
| `ollama` | `[DONE]` | fetch-based; browser-compatible with `OLLAMA_ORIGINS=*` |
| `openai` | `[DONE]` | fetch-based; works with OpenAI, Groq, Together, Mistral |

---

## Multi-Runtime Support

| Runtime | CLI | Browser | Node.js | Status |
|---------|-----|---------|---------|--------|
| Python (SPL30) | `spl3` | No | No | `[DONE]` |
| Go (SPL.go) | `spl-go` | No | No | `[DONE]` |
| TypeScript (SPL.ts) | `spl-ts` | Yes | Yes | `[DONE]` |

SPL.ts architecture constraint: core (lexer/parser/executor/stdlib) uses zero
Node.js-specific APIs — only Web APIs (`fetch`, `console`, `Map`, `Promise`).
`node:fs` is isolated to `cli.ts` only.

---

## Standard Library (Builtins)

48 pure functions, available in all runtimes:

| Category | Functions |
|----------|-----------|
| Type conversion | `to_int`, `to_float`, `to_text`, `to_bool` |
| String | `upper`, `lower`, `trim`, `length`, `reverse`, `substr`, `replace`, `concat`, `split_part` |
| Pattern | `like`, `startswith`, `endswith`, `contains`, `regexp_match` |
| Numeric | `abs_val`, `round_val`, `ceil_val`, `floor_val`, `mod_val`, `power_val`, `sqrt_val`, `sign_val`, `clamp` |
| JSON | `json_get`, `json_set`, `json_keys`, `json_length`, `json_pretty` |
| Date/time | `now_iso`, `date_format_val`, `date_diff_days` |
| Hashing | `md5_hash`, `sha256_hash` |
| List | `list_get`, `list_length`, `list_join`, `list_contains`, `trim_turns` |
| Null/coalesce | `isnull`, `nvl`, `isblank`, `coalesce`, `nullif`, `iif` |
| Aggregates | `word_count`, `char_count`, `line_count` |

---

## Workflow Registry

| Feature | Python | Go | TypeScript | Status |
|---------|--------|----|------------|--------|
| `LocalRegistry` / `Registry` | ✓ | ✓ | ✓ | `[DONE]` |
| `load_dir()` / `loadFile()` | ✓ | ✓ | ✓ | `[DONE]` |
| Circular IMPORT detection | ✓ | ✓ | ✓ | `[DONE]` |
| `FederatedRegistry` (local + Hub fallback) | ✓ | — | `[TODO]` | `[PARTIAL]` |
| `HubRegistry` (REST-backed) | ✓ | ✓ | `[TODO]` | `[PARTIAL]` |
| Duplicate load silent skip (same file) | ✓ | ✓ | ✓ | `[DONE]` |

---

## Momagrid Hub (Distributed Runtime)

| Feature | Status |
|---------|--------|
| Hub REST API (`POST /tasks`, `GET /tasks/{id}`) | `[DONE]` |
| `WorkflowInvocationEvent` (UUID, parent_id, lifecycle) | `[DONE]` |
| Call tree (`parent_event_id`) | `[DONE]` |
| Hub-to-Hub peering | `[DONE]` |
| `ACCOUNTING: BILLABLE_TO` / `BUDGET_LIMIT` | `[DONE]` |
| Moma Points compute currency | `[TODO]` |

---

## Code-RAG (Text2SPL)

| Feature | Status |
|---------|--------|
| `CodeRAGStore` — index `.spl` files as (description, source) pairs | `[PARTIAL]` — depends on embed provider |
| `seed_from_dir()` / `seed_from_catalog()` | `[PARTIAL]` |
| `retrieve(query, top_k)` | `[PARTIAL]` |
| `text2spl.spl` workflow (intent → SPL) | `[TODO]` |

---

## splc Compiler

| Target | Status | Notes |
|--------|--------|-------|
| `splc --target go` (prototype) | `[PARTIAL]` | `self_refine.go` hand-crafted reference; compiler not yet written |
| `splc --target ts` | `[TODO]` | SPL.ts is the hand-crafted reference target |
| `splc --target python/langgraph` | `[PARTIAL]` | `self_refine_langgraph.py` hand-crafted |
| `splc --target snap` | `[TODO]` | Ubuntu 26.04 |
| `splc --target swift` | `[TODO]` | Apple M4/M5 |
| NDD closure test (compiler correctness) | `[PARTIAL]` | `self_refine.go` not yet diff-tested against `spl3 run --adapter echo` |

---

## NDD Closure

| Feature | Status |
|---------|--------|
| `--adapter echo` (deterministic oracle) | `[DONE]` — all runtimes |
| SPL20 self-validation (4 gaps found and closed) | `[DONE]` — see `SPL20/docs/NDD-closure/` |
| `07_spec_judge.spl` (LLM-based fuzzy judge) | `[DONE]` — recipe 56 |
| `splc` NDD closure test script | `[TODO]` |
| Formal NDD closure module | `[TODO]` |

---

## Cookbook Recipes

| id | Recipe | Constructs exercised | Status |
|----|--------|---------------------|--------|
| 05 | `self_refine` | WORKFLOW, GENERATE, WHILE, EVALUATE, CALL, EXCEPTION | `[DONE]` |
| 50 | `image_caption` | IMAGE param, multi-modal adapter | `[DONE]` |
| 51 | `audio_summary` | AUDIO param | `[DONE]` |
| 52 | `text_to_image` | GENERATE + external tool call | `[DONE]` |
| 53 | `text_to_speech` | GENERATE + TTS adapter | `[DONE]` |
| 54 | `image_restyle` | IMAGE + TEXT → IMAGE pipeline | `[DONE]` |
| 55 | `voice_dialogue` | AUDIO + TEXT → TEXT + AUDIO pipeline | `[DONE]` |
| 56 | `code_pipeline` | CALL chain, WHILE @item IN @items, write_file, clean_code, spec_judge | `[DONE]` |
