# SPL Future Work — Design Ideas

*Captured: 2026-03-30. These ideas are beyond the current SPL 2.0 arXiv paper.*

---

## Momagrid as a Compute OS — The Big Picture

*This is the vision for the Momagrid paper, beyond SPL 2.0.*

Momagrid is not just a distributed GPU grid — it is a **compute OS at the agent level**.
The analogy to a conventional OS is precise, not merely metaphorical:

| Computing concept | Momagrid equivalent |
|---|---|
| CPU core | Single GPU node |
| OS kernel | Momagrid Hub (schedules tasks, manages IPC, workflow call stack) |
| Process | Running SPL WORKFLOW |
| System call | `CALL workflow_name()` → Hub dispatch |
| Shared memory / register | Hub workflow stack (holds OUTPUT between call frames) |
| Local network (LAN) | Single Hub + its GPU nodes |
| Internet (WAN) | Hub-to-Hub peering |
| BGP / autonomous system | Hub peer table: which workflows/nodes live where |
| DNS | Workflow name → Hub resolution |
| Cloud provider | A large Hub with many nodes and guaranteed uptime |
| Compute currency | Moma Points — economic layer of the compute internet |

**SPL is the application layer.** Workflows run on this compute OS without
knowing which Hub or node executes them. The same `.spl` file runs on a
single laptop, a LAN grid, or routes through a peer Hub on Oracle Cloud —
the runtime resolves the target transparently.

### Hub-to-Hub Peering = The Internet of Agents

Each Hub manages its own cluster of GPU nodes — an autonomous compute domain,
like an AS (Autonomous System) on the internet. Hub-to-Hub peering connects
these domains:

```
[LAN Hub A]──peer──[Oracle Cloud Hub B]──peer──[LAN Hub C]
  duck, dog, cat       free-tier VMs             goose, ...
```

A workflow on Hub A can dispatch sub-workflows to Hub B via peering — the same
POST /tasks → GET /tasks protocol, extended with a `peer_hub` routing field.
WAN deployment is not a different architecture; it is Hub-to-Hub peering over
the public internet.

**This also resolves the WAN deployment question:** Oracle Cloud free tier is
simply the first public peer Hub. The architecture scales to any number of peers
without protocol changes.

### Moma Points as Compute Currency

On the real internet, bandwidth has cost. On the Momagrid compute internet,
inference has cost — measured in Moma Points. Points flow:
- From workflow submitters (consumers) to Hub operators (providers)
- Across Hub-to-Hub peering boundaries (inter-Hub settlement)
- Enforced by the existing `ACCOUNTING: BILLABLE_TO` and `BUDGET_LIMIT` clauses

This is the economic layer that makes decentralized, open compute sustainable —
analogous to how peering agreements and transit pricing sustain the internet.

---

## Runtime Execution Model: Invocation as Event

*Key insight: separate definition (static) from invocation (dynamic).*

### Definition vs Invocation

| Aspect | Definition | Invocation |
|---|---|---|
| What | `.spl` WORKFLOW block | One runtime execution instance |
| Identity | Name (+ namespace) | `event_id` (UUID) |
| Lifecycle | Static, shared | PENDING → RUNNING → COMPLETE \| FAILED |
| State | None | Isolated variable scope per event |
| Concurrency | N/A | N concurrent invocations = N independent events |
| OS analogy | Program binary | Process (has PID) |

Two requesters calling `review_code` at the same time produce two independent
`WorkflowInvocationEvent` objects with completely isolated scopes. Name collision
is a design-time concern only — at runtime, identity is `event_id`, not name.

### The Call Tree (parent_event_id)

Every `CALL workflow_name()` inside a running workflow creates a child event
that records its `parent_event_id`. This forms a call tree rooted at the
top-level invocation (`spl3 run`):

```
code_pipeline [event: abc-001, root]
  ├── generate_code [event: abc-002, parent: abc-001]
  ├── review_code   [event: abc-003, parent: abc-001]  ← CALL PARALLEL
  ├── test_code     [event: abc-004, parent: abc-001]  ← CALL PARALLEL
  └── improve_code  [event: abc-005, parent: abc-001]
        └── quality_judge [event: abc-006, parent: abc-005]
```

`parent_event_id` is the `fork()` lineage in OS terms. The Hub's SQLite store
(already in `momahub.go`) becomes the event log — one row per invocation,
queryable by workflow / requester / status / time range.

### What the Event Model Gives for Free

**Concurrency isolation** — no shared state between concurrent invocations,
regardless of whether they run the same workflow name.

**Observability** — Hub event log queries:
```
GET /events?workflow=review_code&status=running     # who's running right now?
GET /events?parent=abc-001                          # full call tree
GET /events?requester=user-42&since=1h              # per-user audit trail
```

**Idempotency** — re-submitting a known `event_id` returns cached output
immediately. Natural retry semantics: same logical operation, same result.

**Moma Points attribution** — every LLM call within an event is attributed to
`event_id → requester_id → billing account`. Accounting is at the event level,
not the workflow definition level.

**Distributed tracing** — `parent_event_id` chain = OpenTelemetry trace span
hierarchy, for free. Each node in the call tree is a traceable span.

### Hub Protocol Extension

The existing POST /tasks → GET /tasks protocol is already event-oriented
(`task_id` is a UUID). SPL 3.0 adds three fields:

```json
POST /tasks:
{
  "type":            "workflow",       // was implicit "generate" in SPL 2.0
  "workflow":        "review_code",    // registry lookup key
  "args":            {"code": "..."},  // INPUT param bindings
  "event_id":        "abc-003",        // client-generated idempotency key
  "parent_event_id": "abc-001",        // NEW: call tree linkage
  "requester_id":    "user-42",        // NEW: attribution
  "peer_hub":        "https://..."     // optional: Hub-to-Hub routing
}
```

Backward compatible: SPL 2.0 nodes ignore unknown fields.

### Implementation: WorkflowInvocationEvent

See `spl3/event.py` for the full dataclass implementation including:
- Lifecycle transition methods (`mark_running`, `mark_complete`, `mark_failed`)
- Hub protocol serialization (`to_task_payload`, `from_task_response`)
- `EventCallTree.build()` — reconstruct call tree from flat event list
- `EventCallTree.print_tree()` — visual call tree for debugging

---

## SPL v2.1: Native Workflow Orchestration

---

### Background: SPL as a Synthesized Language

SPL is framed as a synthesis of three existing paradigms:

| Layer | Source language | What SPL borrows |
|-------|----------------|-----------------|
| Data | SQL | SELECT, WITH, GENERATE (≈ query), EVALUATE (≈ CASE) |
| Logic | Python | CALL, @spl_tool, deterministic functions, type system |
| Orchestration | Linux shell | workflow pipelines, stdio piping, exit codes |

The Linux shell analogy is key: `cmd1 | cmd2 | cmd3` is workflow composition.
SPL v2.0 already has individual WORKFLOWs; v2.1 makes them composable natively —
the same way shell scripts compose commands without needing a new language.

---

### Design Idea 1: Workflow-to-Workflow Composition via CALL

**Problem:** SPL v2.0 has no way to invoke one WORKFLOW from another.
Today, multi-workflow pipelines require an external shell script or Python runner.

**Proposal:** Extend `CALL` to resolve WORKFLOW definitions, not just `@spl_tool` Python functions.

```sql
-- Sub-workflows (each independently testable)
WORKFLOW generate_code
    INPUT: @spec TEXT
    OUTPUT: @code TEXT
DO
    GENERATE coder(@spec) INTO @code
    COMMIT @code
END

WORKFLOW review_code
    INPUT: @code TEXT
    OUTPUT: @feedback TEXT
DO
    GENERATE reviewer(@code) INTO @feedback
    COMMIT @feedback
END

-- Orchestrator workflow
WORKFLOW code_pipeline
    INPUT: @spec TEXT
    OUTPUT: @final TEXT
DO
    CALL generate_code(@spec) INTO @code
    CALL review_code(@code) INTO @feedback
    CALL test_code(@code) INTO @test_result
    CALL document_code(@code) INTO @docs
    WHILE @quality < 0.9 DO
        CALL improve_code(@code, @feedback, @test_result) INTO @code
        GENERATE quality_judge(@code) INTO @quality
    END
    COMMIT @code
END
```

**Why CALL (not a new keyword):** CALL already means "deterministic, synchronous,
testable, free." A workflow invocation from the caller's perspective *is* deterministic
dispatch — the callee may contain GENERATE internally, but the call boundary is
deterministic. Reusing CALL keeps the language minimal and consistent.

---

### Design Idea 2: Resolving the COMMIT status question

**Current behavior (v2.0):**
`COMMIT @result WITH status = 'complete'` attaches runtime metadata to the
workflow's terminal state. This status is currently used by the runner/CLI
for reporting — it does not flow into the calling scope.

**Problem for v2.1:**
When a sub-workflow is invoked via `CALL workflow_name() INTO @var`, the caller
receives the OUTPUT value. But what about the status? Two cases matter:

1. Sub-workflow COMMITs with `status = 'complete'` → caller gets `@var`, proceeds normally.
2. Sub-workflow COMMITs with `status = 'refused'` or `status = 'partial'` →
   what does the caller see?

**Proposed resolution:**

- **OUTPUT is the data channel.** `INTO @var` binds the callee's OUTPUT variable
  to the caller's local variable. Status is not part of OUTPUT.
- **Status maps to the EXCEPTION channel.** Non-`complete` statuses raise typed
  exceptions in the calling scope, catchable via `EXCEPTION WHEN`:

```sql
WORKFLOW code_pipeline
    INPUT: @spec TEXT
    OUTPUT: @final TEXT
DO
    CALL generate_code(@spec) INTO @code
    EXCEPTION WHEN RefusalToAnswer THEN
        COMMIT 'Generation refused.' WITH status = 'blocked'
    END

    CALL review_code(@code) INTO @feedback
    EXCEPTION WHEN QualityBelowThreshold THEN
        -- reviewer couldn't assess; use empty feedback and continue
        SET @feedback = ''
    END
    ...
END
```

This keeps OUTPUT clean (single value, typed) and uses the existing EXCEPTION
hierarchy as the error/status channel — no new primitives needed.

**Simplification for COMMIT inside sub-workflows:**
When a WORKFLOW is called via CALL (not run standalone), the `WITH status = ...`
clause on COMMIT can be dropped — it becomes optional metadata only meaningful
to the CLI runner. Inside a composition, the EXCEPTION mechanism handles
non-happy-path outcomes. This means sub-workflow authors do not need to change
their code: `COMMIT @result` (no status) works correctly in both standalone
and composed contexts.

---

### Design Idea 3: Text2SPL + Recipe RAG — Virtuous Cycle

**Insight:** The cookbook recipes are a dual-purpose artifact:
1. Empirical validation corpus (current use in v2.0 paper)
2. RAG training ground for Text2SPL

Each recipe is a labeled example: `(natural-language description, SPL source)`.
As the cookbook grows (40 → 100+ recipes), Text2SPL can retrieve the closest
pattern by semantic similarity and use it as a few-shot template — no fine-tuning required.

**Virtuous cycle:**
```
More recipes → richer RAG corpus → more accurate Text2SPL
→ more users can generate workflows → community contributes recipes → ...
```

**Implication for v2.1:** The Text2SPL compiler should be explicitly designed
around this RAG architecture:
- Recipe index: embed all `.spl` files + their docstrings/comments
- At generation time: retrieve top-k similar recipes, inject as few-shot examples
- The `spl text2spl` command already scaffolds this; the RAG backend is the next step

---

### Design Idea 4: Workflow Orchestration as the "Linux Shell" Layer

**Framing:** SPL's three-layer synthesis maps cleanly to the orchestration hierarchy:

```
Single PROMPT      ≈  a shell command         (SQL layer: query + generate)
Single WORKFLOW    ≈  a shell function/script  (Python layer: logic + CALL)
Composed WORKFLOWs ≈  a pipeline / Makefile   (Linux layer: orchestration)
```

v2.0 covers the first two layers fully.
v2.1 closes the third: native workflow composition replaces the need for
`.sh` wrapper scripts or Python runner glue.

**What this means for multi-agent patterns:**
Each agent role becomes a named WORKFLOW (generate_code, review_code, test_code,
document_code, improve_code). The orchestrator WORKFLOW composes them, with
WHILE enabling iterative refinement across agents. This is multi-agent
orchestration expressed purely in SPL — no LangGraph, no AutoGen, no shell.

---

### Runtime Changes Required for v2.1

The Hub-and-spoke architecture already provides the registry and IPC mechanism.
Sub-workflows become tasks in the Hub's task queue — the existing
POST /tasks → GET /tasks protocol handles dispatch and result return.
No new infrastructure is needed; only a small schema extension:

| Change | Scope | Notes |
|--------|-------|-------|
| Workflow registry in Hub | Hub | Hub maintains workflow name → definition map; `CALL name()` resolves via Hub lookup |
| Task type flag | Protocol | Extend POST /tasks payload with `"type": "workflow" \| "generate"` |
| Scoped variable binding | Executor | Caller's args → callee's INPUT; callee's OUTPUT → caller's INTO @var via Hub register |
| Status-to-exception mapping | Executor | Non-complete COMMIT status raises typed exception in caller scope |
| Multi-file workflow loading | CLI | `spl run orchestrator.spl --workflows lib/*.spl` or an `IMPORT` directive |
| Hub-to-Hub routing (v2.2+) | Hub peering | `peer_hub` field on task payload enables WAN workflow dispatch |

---

### Open Questions for v2.1 Design

1. **IMPORT directive vs. CLI flag:** Should workflows be composed in a single
   `.spl` file, or imported from separate files?
   - Single file: simpler, self-contained, easier for Text2SPL to generate
   - Import: better for large codebases, reuse across projects
   - Proposed: both — `IMPORT 'lib/code_agents.spl'` directive + CLI `--workflows` flag

2. **Parallel CALL:** Should the orchestrator be able to call sub-workflows in
   parallel (e.g., run review and test simultaneously)?
   ```sql
   CALL PARALLEL review_code(@code) INTO @feedback,
                 test_code(@code)   INTO @test_result
   END
   ```
   This maps to the Momagrid parallel GENERATE optimization from Section 5.3.

3. **Typed OUTPUT:** Should OUTPUT support multiple named fields (like a struct),
   or stay as a single typed value?
   - Single value keeps composition simple and consistent with CALL's current contract
   - Multiple fields would require destructuring syntax in the caller
   - Recommendation: keep single value for v2.1; multi-field can be v2.2

---

## SPL 3.0 Extended Type System

*Added: 2026-03-31. Extends SPL 2.0 to feel natural for Python, SQL, and Linux developers.*

SPL is framed as a synthesis language — it should feel natural to developers from all three backgrounds:

| Background | What they expect |
|---|---|
| SQL | Typed columns, NULL, structured records |
| Python | `int`, `float`, `None`, `set`, dataclasses |
| Linux/bash | File paths as first-class values for piping multimodal data |

### SPL 2.0 → SPL 3.0 Type Matrix

| SPL 3.0 Type | Python | SQL | New in 3.0 | Notes |
|---|---|---|---|---|
| `TEXT` | `str` | `VARCHAR` | no | unchanged |
| `NUMBER` | `int\|float` | `NUMERIC` | no | kept as v2.0 alias |
| `INT` | `int` | `INTEGER` | **yes** | precision split from NUMBER |
| `FLOAT` | `float` | `FLOAT` | **yes** | precision split from NUMBER |
| `BOOL` | `bool` | `BOOLEAN` | no | unchanged; TRUE/FALSE literals |
| `LIST` | `list` | `ARRAY` | no | unchanged; `[a, b, c]` literal |
| `MAP` | `dict` | `JSON` | no | unchanged; `{'k': v}` literal |
| `SET` | `set` | — | **yes** | `{a, b, c}` literal (no colons) |
| `NONE` / `NULL` | `None` | `NULL` | **yes** | first-class null literal |
| `IMAGE` | `bytes\|str` | — | **yes** | multimodal; Liquid AI LFM |
| `AUDIO` | `bytes\|str` | — | **yes** | multimodal; Liquid AI LFM |
| `VIDEO` | `bytes\|str` | — | **yes** | multimodal; Liquid AI LFM |
| `STORAGE` | `Connection` | — | no | unchanged; compound type |
| `DATACLASS` | `dataclass` | `RECORD` | **v3.1** | `CREATE TYPE ... AS (...)` |

### Design Decisions

**INT and FLOAT split NUMBER** — `NUMBER` is kept as a backward-compatible alias that accepts both int and float. New SPL 3.0 workflows should prefer `INT` for counters/budgets and `FLOAT` for scores/ratios/temperatures. The executor coerces `INT`-typed params via `int(value)` and `FLOAT`-typed params via `float(value)`.

**NONE serializes to `''`** — SPL's variable store is string-based. `NONE` serializes to the empty string `''` at runtime. `is_none_value()` in `spl3/types.py` centralizes this check. SQL developers can write `EVALUATE @x WHEN = NONE THEN ...`; Python developers can check `@x = ''` after assignment.

**SET `{a, b}` vs MAP `{k: v}` disambiguation** — same rule as Python: if the first element after `{` is followed by `:` it's a MAP; if by `,` or `}` it's a SET. Empty `{}` → MAP (consistent with Python). At runtime, SET serializes as a sorted, deduplicated JSON array.

**Multimodal types for Liquid AI LFM** — `IMAGE`, `AUDIO`, `VIDEO` are type annotations that tell the adapter the param carries media, not text. The executor passes the value (file path or data URI) to the LLM adapter as-is; encoding (base64, content-type negotiation) is an adapter responsibility. This keeps the language clean: `GENERATE describe(@photo) INTO @answer` works without new syntax.

**DATACLASS is SPL 3.1** — requires a `CREATE TYPE` DDL statement and schema-driven `FORMAT JSON SCHEMA` injection in GENERATE. Architecturally clean, but depends on a stable CALL composition runtime first. Defer to v3.1.

### Syntax Examples

```sql
-- NONE literal
@threshold := NONE
EVALUATE @score WHEN = NONE THEN
    LOGGING 'score not set' LEVEL WARN
END

-- INT / FLOAT type annotations
WORKFLOW summarize_budget
    INPUT:  @text TEXT, @max_tokens INT DEFAULT 512
    OUTPUT: @summary TEXT, @compression_ratio FLOAT
DO
    GENERATE summarizer(@text, @max_tokens) INTO @summary
    @compression_ratio := len(@summary) / len(@text)
    COMMIT @summary
END

-- SET literal  ({...} without colons)
@seen_topics := {'introduction', 'methods', 'results'}

-- Multimodal INPUT for Liquid AI LFM adapter
WORKFLOW describe_image
    INPUT:  @photo IMAGE, @question TEXT DEFAULT 'What is in this image?'
    OUTPUT: @answer TEXT
DO
    GENERATE vision_describe(@photo, @question) INTO @answer
    COMMIT @answer
END

-- DATACLASS (v3.1 design preview)
CREATE TYPE CodeReview AS (
    score   FLOAT,
    verdict TEXT,
    passed  BOOL
)

WORKFLOW review_code
    INPUT:  @code TEXT
    OUTPUT: @review CodeReview
DO
    GENERATE reviewer(@code) WITH FORMAT JSON SCHEMA CodeReview INTO @review
    COMMIT @review
END
```

### Implementation Scope for SPL 3.0

| Change | File | Status |
|---|---|---|
| `SPL3Type` enum + coerce helpers | `spl3/types.py` | done |
| Grammar spec additions | `specs/grammar-additions.ebnf` | done |
| Token keywords: NONE, NULL, IMAGE, AUDIO, VIDEO | lexer extension | todo |
| `SetLiteral` AST node | AST extension | todo |
| `{a, b}` SET vs `{k: v}` MAP disambiguation | parser extension | todo |
| `NONE` literal → `Literal(value=None, literal_type='none')` | parser extension | todo |
| INT/FLOAT coercion in workflow INPUT processing | executor extension | todo |
| Multimodal param pass-through to LLM adapter | executor + adapters | todo |
| Liquid AI LFM adapter (`dd-llm` backend) | `dd-llm` package | todo |
| `DATACLASS` / `CREATE TYPE` | parser + executor | v3.1 |

---

## SPL 3.0 Release Scope

*Analysis: which features from the SPL 2.0 roadmap belong in v3.0.*

### Scope Decision Framework

SPL 3.0 is defined by one architectural leap: **native workflow composition**. Everything else that ships with v3.0 is support infrastructure for that leap, or long-overdue backlog items that fit naturally alongside it.

The guiding question for each feature: "Does this require, enable, or clean up workflow composition?" If yes → v3.0. If speculative → v3.x.

---

### v3.0 In-Scope (ship with composition)

| Feature | Rationale |
|---------|-----------|
| `CALL workflow_name()` resolution | Core v3.0 primitive — resolves WORKFLOW defs, not just `@spl_tool` |
| `CALL PARALLEL ... END` | Natural companion to CALL; maps to parallel GENERATE already tested |
| `IMPORT 'file.spl'` directive | Multi-file workflow loading; required for composable codebases |
| `WorkflowInvocationEvent` runtime model | Separates definition from invocation; required for concurrent safety |
| `LocalRegistry` + `FederatedRegistry` | Workflow name → definition resolution; v3.0 foundation |
| COMMIT status → EXCEPTION channel | Clean error propagation in composed workflows |
| `spl3 run` CLI | Loads registry, resolves imports, dispatches orchestrator workflow |
| `spl3 registry list/register` | Introspect and manage the workflow registry |
| `STORE @var IN memory.key` | Fully implement workflow memory writes (was stubbed in v2.0) |
| `spl3 test` pipeline runner | Test orchestrator workflows end-to-end with expected output matching |
| Code-RAG seeded from cookbook | 40+ recipes → vector DB; Text2SPL quality leap enabled by composition |

---

### v3.0 Out-of-Scope (defer to v3.x)

| Feature | Why deferred |
|---------|-------------|
| `STREAM INTO @var` | Requires streaming-aware Hub protocol; separate design needed |
| Dedicated Text2SPL model config | Config schema change; can ship as a patch after v3.0 |
| `PARALLEL DO ... END` (within WORKFLOW) | Subsumed by `CALL PARALLEL`; not needed independently |
| Specialty SPL fine-tuned model | Requires training data volume not yet available |
| Hub-to-Hub peering (WAN routing) | Protocol work in progress (Oracle Cloud); v3.1 companion to WAN paper |
| Tool Connectors (`tool.pdf_to_md()`) | Orthogonal to composition; can ship independently |
| `dd-*` library migration (SPL20 tech debt) | SPL20 concern; SPL30 builds on dd-* from day one |

---

### New Keywords: Exactly Two

SPL 3.0 introduces exactly two new keywords:

| Keyword | Construct | What it enables |
|---------|-----------|-----------------|
| `IMPORT` | `IMPORT 'lib/agents.spl'` | Multi-file workflow loading at parse time |
| `PARALLEL` | `CALL PARALLEL ... END` | Concurrent sub-workflow dispatch |

Everything else — `CALL`, `COMMIT`, `EXCEPTION`, `WHILE`, `WORKFLOW`, `INPUT`, `OUTPUT` — is unchanged syntax with extended runtime semantics. The grammar is minimal; the power comes from the runtime and registry.

---

### SPL30 Tech Debt: Start Clean, Not Clean Up

SPL30 (`spl3` package) is a greenfield Python package. Unlike SPL20, it uses `dd-*` libraries from day one — no bespoke wrappers:

| Layer | SPL20 (tech debt) | SPL30 (clean) |
|-------|------------------|---------------|
| LLM backends | `spl/adapters/` bespoke clients | `dd-llm` via `UnifiedLLMProvider` |
| Vector store | FAISS wrapper + ChromaDB | `dd-vectordb` (`FAISSVectorDB` / `ChromaVectorDB`) |
| Embeddings | Duplicate sentence-transformers calls | `dd-embed` single embedding layer |
| Database | Hand-rolled SQLite in `streamlit/db.py` | `dd-db` (`SQLiteDB`) |
| Caching | `prompt_cache` table in `.spl/memory.db` | `dd-cache` (`DiskCache`) |
| File extraction | Raw UTF-8 read for `--dataset` | `dd-extract` (`PDFExtractor`, etc.) |

This means SPL30's `pyproject.toml` lists `dd-llm`, `dd-vectordb`, `dd-embed`, `dd-db`, `dd-cache`, `dd-extract` as direct dependencies — not internal code.

