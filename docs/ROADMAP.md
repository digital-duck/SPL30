# SPL Future Work — Design Ideas

*Captured: 2026-03-30. Last updated: 2026-04-18 (session 7).*

**Implementation progress:** see [FEATURES.md](FEATURES.md) for what is currently implemented and tested.
- ROADMAP.md tracks *design intent*;
- FEATURES.md tracks *build status* (test results, known failures, and what remains TODO).

---

## The Expanded SPL Vision (2026-04-13)

SPL has grown from a prompt-query language into a three-axis research and engineering project:

```
Axis 1: Language Evolution
  SPL v1.0 → v2.0 → v3.0 → v3.1 → ...
  Python is the lab. Each version experiments with new constructs and methodology.
  Stable constructs graduate to the multi-runtime tier.

Axis 2: Research Contributions
  NDD Closure  — deterministic oracle-based runtime correctness testing
  Agentic Integrity — behavioral equivalence metric for AI safety
  splc / DODA  — compile once, run anywhere across heterogeneous silicon

Axis 3: Multi-Runtime Expansion
  SPL (Python / SPL30)  — reference implementation, lab for new features
  SPL.go                — production backend, Hub runtime, high-concurrency
  SPL.ts                — browser + Node.js frontend, web application platform
```

**Feature flow:**
```
Python prototype → tested + stable → port to Go → port to TypeScript
```

Python is always first. Go follows when a feature is proven. TypeScript follows Go (or in parallel for browser-critical features). FEATURES.md tracks which tier each feature has reached.

**The browser bridge:** SPL.ts unlocks a class of use cases impossible with Python or Go:
- In-browser SPL execution (no server required)
- Web-based SPL playground and editor
- SPL-powered web applications (not just Streamlit)
- Progressive Web Apps running local LLM workflows via WebLLM/WASM

This is the moment SPL stops being a CLI tool and becomes a platform.

---

## splc — Compiler Milestones and Next Steps

*Updated: 2026-04-15 (session 5).*

### What shipped (session 5)

| Item | Detail |
|------|--------|
| Go transpiler — 10 issues fixed | `// SPL:` traceability, CALL PARALLEL (goroutines+WaitGroup), EXCEPTION (defer/recover), named-arg resolution, backtick escaping, HTTP error body, writeFile errors, `"sync"` conditional import, int type inference, correct `--ollama-host` flag |
| TypeScript transpiler — new | `transpiler_ts.py`: CALL PARALLEL → `Promise.all()`, EXCEPTION → try/catch+SPLError, all 3 recipes pass `tsc --strict` and run live via `tsx` |
| Default behavior flipped | Deterministic is now default for `go`, `ts`, `python/langgraph`; `--llm` opts into LLM compilation |
| CLI simplified | SPL path is positional: `splc x.spl --lang go` (no `--spl` prefix) |
| LangGraph transpiler plan | Design documented in `docs/plan-for-splc-python-by-claude.md`; Opus implementing in parallel session |

### Gaming PC validation milestone (next)

The mini-PC (current dev machine) is too slow for full LLM runs against splc output.
The gaming PC is the validation target for:

| Test | Command | What it proves |
|------|---------|----------------|
| Go — self_refine live | `go run self_refine_go.go --writer-model gemma3 --task "..."` | NDD closure: splc Go output ≡ `spl3 run` |
| Go — parallel_news_digest live | `go run parallel_news_digest_go.go --digest-model gemma3` | CALL PARALLEL goroutines work end-to-end |
| TS — self_refine live | `npx tsx self_refine_ts.ts --writer-model gemma3 --task "..."` | NDD closure: splc TS output ≡ `spl3 run` |
| TS — parallel_news_digest live | `npx tsx parallel_news_digest_ts.ts --digest-model gemma3` | Promise.all parallel branches work |
| LangGraph live | `python self_refine_python_langgraph.py --task "..."` | NDD closure: LangGraph output ≡ `spl3 run` |

All five tests use the same `--task "What are the benefits of meditation?"` so logs can be
`diff`-compared for structural equivalence (iteration count, approval token, `final.md` presence).

### Next splc features after gaming PC validation

| Feature | Priority | Notes |
|---------|----------|-------|
| `splc judge` command | High | Automate NDD closure check: run echo oracle, run compiled artifact, compare structure |
| Python/crewai deterministic transpiler | Medium | Follow same pattern as LangGraph transpiler |
| `go.mod` generation alongside `.go` output | Medium | Currently missing; needed for `go mod tidy` |
| `package.json` / `tsconfig.json` alongside `.ts` output | Medium | Makes the TS target self-contained |
| Type inference beyond `iteration` (Go) | Low | Done in session 5; verify with recipe 50 counter vars |

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

**SPL is the application layer.** Workflows run on this compute OS without knowing which Hub or node executes them. The same `.spl` file runs on a single laptop, a LAN grid, or routes through a peer Hub —
the runtime resolves the target transparently.

### Hub-to-Hub Peering = The Internet of Agents

Each Hub manages its own cluster of GPU nodes — an autonomous compute domain,
like an AS (Autonomous System) on the internet. Hub-to-Hub peering connects
these domains:

```
[LAN Hub A]──peer──[LAN Hub B]
  duck, dog, cat    goose, ...
```

A workflow on Hub A can dispatch sub-workflows to Hub B via peering — the same
POST /tasks → GET /tasks protocol, extended with a `peer_hub` routing field.
WAN deployment is not a different architecture; it is Hub-to-Hub peering over
the public internet.

**Next step:** validate Hub-to-Hub peering between two local Hubs before scaling
to WAN. The architecture scales to any number of peers without protocol changes.

### Moma Points as Compute Currency

On the real internet, bandwidth has cost. On the Momagrid compute internet,
inference has cost — measured in Moma Points. Points flow:
- From workflow submitters (consumers) to Hub operators (providers)
- Across Hub-to-Hub peering boundaries (inter-Hub settlement)
- Enforced by the existing `ACCOUNTING: BILLABLE_TO` and `BUDGET_LIMIT` clauses

This is the economic layer that makes decentralized, open compute sustainable —
analogous to how peering agreements and transit pricing sustain the internet.

---

## School Momagrid — AI for Every Kid, Everywhere

*Added: 2026-04-13. Education is the planned launch platform for SPL + Momagrid.*

The same Hub-to-Hub federation that powers the broader Momagrid works at school scale.

### School Hub Architecture

```
School Campus
├── Momagrid Hub  (one mini-PC in the server room)
├── Ollama        (local LLM inference — gemma4 or equivalent)
└── Students      (any device on the school network — browser-based SPL UI)
```

No internet required. No data leaves the campus. No per-token bill — ever.

### The Gaming PC Flip

Student gaming PCs contribute GPU to the Hub during school hours. The machine goes
from "the thing that ruins my kid" to "the thing my kid contributes to the school."

| Metric | What it means |
|--------|--------------|
| GPU contributed 10,000 inference calls | You powered your classmates' learning |
| Your workflow was used by 47 students | You built something useful |
| Top contributor in your class | Your hardware + your creativity matter |

### Cost Model

| Setup | Cost model | 1,000 student queries |
|-------|-----------|----------------------|
| OpenAI API direct | Per token | $5–$50 |
| Anthropic API direct | Per token | Similar range |
| `claude_cli` adapter | Flat subscription | Same cost as 1 query |
| Ollama local | Zero | Zero |

The `claude_cli` adapter routes complex reasoning through Claude at flat subscription
cost — no per-token billing. Schools get local speed+privacy for routine tasks and
Claude-level reasoning for demanding tasks, all within a predictable budget.

### School Federation

Individual school hubs peer into district/national Momagrids via the standard
Hub-to-Hub peering protocol — no new infrastructure. A workflow written by a teacher
in one school is available to every school in the federation immediately.

### Roadmap

| Feature | Status |
|---------|--------|
| Hub architecture + Ollama local inference | `[DONE]` — works today |
| `claude_cli` flat-subscription adapter | `[DONE]` — adapter exists |
| Zero-data-leaves-campus by design | `[DONE]` — local inference |
| Hub-to-Hub federation (district Momagrids) | `[DONE]` — peering protocol |
| School deployment guide + mini-PC setup doc | `[TODO]` |
| Student gaming PC enrollment flow (volunteer node) | `[TODO]` |
| Gamification / leaderboard (contribution metrics) | `[TODO]` |
| Browser-based SPL workflow editor for students | `[TODO]` — needs SPL.ts browser bundle |

*Vision document: `SPL20/docs/School-Momagrid.md`*

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
top-level invocation (`spl run`):

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

See `spl/event.py` for the full dataclass implementation including:
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
    RETURN @code
END

WORKFLOW review_code
    INPUT: @code TEXT
    OUTPUT: @feedback TEXT
DO
    GENERATE reviewer(@code) INTO @feedback
    RETURN @feedback
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
    GENERATE quality_judge(@code) INTO @quality      -- initialize before WHILE
    WHILE @quality < 0.9 DO
        CALL improve_code(@code, @feedback, @test_result) INTO @code
        GENERATE quality_judge(@code) INTO @quality
    END
    RETURN @code
END
```

**Why CALL (not a new keyword):** CALL already means "deterministic, synchronous,
testable, free." A workflow invocation from the caller's perspective *is* deterministic
dispatch — the callee may contain GENERATE internally, but the call boundary is
deterministic. Reusing CALL keeps the language minimal and consistent.

---

### Design Idea 2: Resolving the RETURN status question

**Current behavior (v2.0):**
`RETURN @result WITH status = 'complete'` attaches runtime metadata to the
workflow's terminal state. This status is currently used by the runner/CLI
for reporting — it does not flow into the calling scope.

**Problem for v2.1:**
When a sub-workflow is invoked via `CALL workflow_name() INTO @var`, the caller
receives the OUTPUT value. But what about the status? Two cases matter:

1. Sub-workflow uses RETURN with `status = 'complete'` → caller gets `@var`, proceeds normally.
2. Sub-workflow uses RETURN with `status = 'refused'` or `status = 'partial'` →
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
        RETURN 'Generation refused.' WITH status = 'blocked'
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

**Runtime fallback for unhandled exceptions:**
`EXCEPTION WHEN` is opt-in — if the user does not handle a given exception type,
the runtime's default handler takes over rather than crashing the workflow with a
raw Python traceback. The fallback chain is:

| Scope | Behavior |
|---|---|
| User defines `EXCEPTION WHEN X THEN ...` | Handled by SPL user code |
| Unhandled exception type | Runtime catches it; issues RETURN with `status = 'failed'` and the exception type + message as metadata |
| Top-level workflow (no parent) | Runtime surfaces a readable error to the CLI — no raw stack trace |
| Called via CALL (has parent) | Failure propagates up the EXCEPTION channel; parent may catch or also fall through |

SPL users should not need to enumerate every possible LLM error mode. Unhandled =
runtime takes over is the safe, explicit default. The behavior is documented so it
is never surprising: *unhandled exceptions mark the workflow failed and surface the
error message; they do not silently swallow the error or raise an unformatted crash.*

**Simplification for RETURN inside sub-workflows:**
When a WORKFLOW is called via CALL (not run standalone), the `WITH status = ...`
clause on RETURN can be dropped — it becomes optional metadata only meaningful
to the CLI runner. Inside a composition, the EXCEPTION mechanism handles
non-happy-path outcomes. This means sub-workflow authors do not need to change
their code: `RETURN @result` (no status) works correctly in both standalone
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
| Status-to-exception mapping | Executor | Non-complete RETURN status raises typed exception in caller scope |
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

**NONE serializes to `''`** — SPL's variable store is string-based. `NONE` serializes to the empty string `''` at runtime. `is_none_value()` in `spl/types.py` centralizes this check. SQL developers can write `EVALUATE @x WHEN = NONE THEN ...`; Python developers can check `@x = ''` after assignment.

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
    RETURN @summary
END

-- SET literal  ({...} without colons)
@seen_topics := {'introduction', 'methods', 'results'}

-- Multimodal INPUT for Liquid AI LFM adapter
WORKFLOW describe_image
    INPUT:  @photo IMAGE, @question TEXT DEFAULT 'What is in this image?'
    OUTPUT: @answer TEXT
DO
    GENERATE vision_describe(@photo, @question) INTO @answer
    RETURN @answer
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
    RETURN @review
END
```

### Implementation Scope for SPL 3.0

| Change | File | Status |
|---|---|---|
| `SPL3Type` enum + coerce helpers | `spl3/types.py` | **done** |
| Grammar spec additions | `specs/grammar-additions.ebnf` | **done** |
| Token keywords: NONE, NULL, IMAGE, AUDIO, VIDEO | lexer extension | **done** (Python+Go+TS) |
| `SetLiteral` AST node | `spl3/ast_nodes.py` | **done** (Python); todo Go/TS |
| `{a, b}` SET vs `{k: v}` MAP disambiguation | `spl3/parser.py` | **done** (Python); todo Go/TS |
| `NONE` literal → `NoneLiteral` AST node | `spl3/parser.py` | **done** (Python+Go+TS) |
| INT/FLOAT coercion in workflow INPUT processing | `spl3/executor.py` | **done** |
| `SPL3Executor._exec_generate_into` multimodal override | `spl3/executor.py` | **done** |
| `MultiModalDDLLMBridge.generate_multimodal()` | `spl3/adapters/dd_llm_bridge.py` | **done** |
| Ollama WAV-only auto-convert (pydub) | `spl3/adapters/dd_llm_bridge.py` | **done** |
| `spl3/codecs/image_codec.py` | IMAGE → base64 ImagePart | **done** |
| `spl3/codecs/audio_codec.py` | AUDIO → base64 AudioPart | **done** |
| `spl3/codecs/video_codec.py` | VIDEO → frame ImageParts | todo |
| Liquid AI LFM adapter (Ollama + OpenRouter) | `spl/adapters/liquid.py` | **done** |
| `MultiModalMixin` + `ContentPart` types | `spl/adapters/base_multimodal.py` | **done** |
| Ubuntu 26.04 snap adapter (placeholder) | `spl/adapters/snap.py` | placeholder |
| `generate_multimodal()` in Go/TS (codec pipeline) | `SPL.go` / `SPL.ts` | todo |
| `DATACLASS` / `CREATE TYPE` | parser + executor | v3.1 |

---

---

## SPL 3.0 Multi-Modal Support

*Added: 2026-04-06. Perfect timing — Gemma 4 and Liquid LFM both released with native multi-modal.*

### Why Now

Two model releases make on-device multi-modal practical for DODA workflows:

| Model | Provider | Modalities | Access |
|---|---|---|---|
| **Gemma 4** (just released) | Google | image + text | Ollama (`ollama pull gemma4`) |
| **Liquid LFM-2.5** | Liquid AI | audio + image | Ollama + OpenRouter |

Both are available locally via Ollama — no cloud API key required for prototyping. This is the right moment to validate SPL 3.0's `IMAGE` and `AUDIO` type annotations end-to-end.

### Adapter Architecture

Multi-modal support is additive — all SPL 2.0 adapters continue to work unchanged.

```
spl/adapters/
  base_multimodal.py   ← MultiModalMixin, MultiModalAdapter, ContentPart union
  liquid.py            ← LiquidAdapter (ready for generate_multimodal override)
  ollama.py            ← OllamaAdapter (SPL20, Gemma 4 passes content array through)
```

**`ContentPart` union** (mirrors OpenAI / Anthropic content-array format):
- `TextPart`  — `{"type": "text", "text": "..."}`
- `ImagePart` — `{"type": "image", "source": "base64"|"url", "media_type": "image/jpeg", "data": "..."}`
- `AudioPart` — `{"type": "audio", "source": "base64", "media_type": "audio/wav", "data": "..."}`
- `VideoPart` — `{"type": "video", "frames": [...], "fps": 1.0}`

**`MultiModalMixin`** adds `generate_multimodal(content: list[ContentPart], ...)` to any adapter. The default implementation extracts text parts and falls back to `generate()` — text-only adapters degrade gracefully, no code changes required.

**`supports_multimodal` property** — `True` only if the adapter has overridden `generate_multimodal`. Adapters that natively handle multi-modal input inherit from `MultiModalAdapter(MultiModalMixin, LLMAdapter)`.

### Codecs Layer (earmarked)

Raw data conversion belongs in `spl/codecs/`, separate from the LLM adapter layer:

| Codec | Input | Output | Status |
|---|---|---|---|
| `image_codec.py` | PIL Image / file path | base64 `ImagePart` | todo |
| `audio_codec.py` | WAV / MP3 file path | base64 `AudioPart` | todo |
| `video_codec.py` | video file path | list of `ImagePart` frames | todo |

The adapter never handles raw files — it receives pre-encoded `ContentPart` dicts from the codec layer. This keeps the LLM API boundary clean.

### DODA Multi-Modal Compile Targets

| Device | Runtime | Model | splc Target | Modality |
|---|---|---|---|---|
| Intel Mini-PC | Ollama + OpenVINO | Gemma 4 E4B | `go` | image + text |
| Mac Mini M4 | Ollama Metal | Gemma 4 27B | `swift` | image + text |
| Laptop / ARM edge | Ollama | LFM-2.5 | `python/liquid` | audio + image |
| Ubuntu 26.04 | Inference Snap (future) | LFM-2 2.6B | `snap` | TBD |

### Ubuntu Snap: Wait for GA

`SnapAdapter` is a documented placeholder. Ubuntu 26.04 "Resolute Raccoon" is not yet GA and Canonical has not published a stable inference API spec. Implementation will follow when:
1. Ubuntu 26.04 ships (expected H1 2026).
2. Canonical publishes the `ubuntu-ai` snap API.
3. The snap's local endpoint format is confirmed.

`UBUNTU_AI_URL` env var is reserved. The adapter docstring includes a full "When implementing" checklist.

### Multi-Modal Cookbook Prototypes

SPL30 multi-modal recipes (50–64) validated end-to-end as of 2026-04-13:

| id | Recipe | Flow | Model | spl3 run status |
|---|---|---|---|---|
| 51 | `image_caption` | IMAGE→TEXT | gemma4:e4b (Ollama) | **`[DONE]`** — `spl3 run` + `run.py` both working |
| 52 | `audio_summary` | AUDIO→TEXT | gemma4:e4b (Ollama) | **`[DONE]`** — WAV and MP3 (auto-converted) |
| 53 | `video_summary` | VIDEO→TEXT | gemma4 (Ollama) | `[TODO]` — run.py scaffolded |
| 54 | `text_to_image` | TEXT→IMAGE | DALL-E 3 | `[TODO]` — requires OpenAI key |
| 55 | `text_to_speech` | TEXT→AUDIO | OpenAI TTS | `[TODO]` — requires OpenAI key |
| 56 | `text_to_video` | TEXT→VIDEO | Veo 2 / RunwayML | `[TODO]` — requires Google key |

Key implementation details confirmed working:
- `encode_image()` in `spl3/codecs/image_codec.py` — Pillow optional, JPEG resize to ≤1568px
- `encode_audio()` in `spl3/codecs/audio_codec.py` — WAV/MP3/OGG/FLAC → base64 AudioPart
- `SPL3Executor._exec_generate_into` override — detects IMAGE/AUDIO typed params, calls `generate_multimodal()`
- `MultiModalDDLLMBridge` in `spl3/adapters/dd_llm_bridge.py` — Ollama WAV-only constraint handled (pydub auto-convert)

---

## splc Compiler & DODA: Design Once, Deploy Anywhere

*Added: 2026-04-05. The "Java Moment" for AI — hardware-agnostic SPL execution.*

### The Logical / Physical Separation

SPL 3.0 introduces a fundamental two-layer architecture. The `.spl` file is the **logical view** — it describes *what* the agentic workflow does, agnostic of hardware, runtime, or model. The `splc` compiler produces the **physical view** — optimized, hardware-specific artifacts that run the workflow on actual silicon.

```
[Human Intent]
      │
      ▼  text2SPL (Semantic Layer)
[.spl Script]  ← Logical View: declarative, hardware-agnostic
      │
      ▼  splc Compiler (Structural Layer)
 ┌────┴────────────────────────────────────┐
 │  Target Detection (hardware-aware)      │
 └─────┬──────┬──────┬───────┬────────────┘
       ▼      ▼      ▼       ▼
  OpenVINO  Metal  Snap   vLLM/Triton
  (Intel)  (Apple) (Ubuntu) (Cloud)
       └──────┴──────┴───────┘
              Momagrid Execution
```

This separation is the "Java Moment" for AI: the same `.spl` file runs on a 10-node heterogeneous grid, a single laptop, or routes to a cloud cluster — the runtime resolves the target transparently.

### DODA: Design Once, Deploy Anywhere

The **DODA** philosophy has one invariant: the logic in a `.spl` file never changes based on deployment target. Physical adaptation is entirely `splc`'s responsibility.

| Device Class | Runtime Profile | Recommended Model | splc Target |
| :--- | :--- | :--- | :--- |
| Mac Mini M4/M5 | Unified Memory / Metal | Gemma 4 31B / LFM-2 24B | `--target swift` or `--target ts` |
| Intel Mini-PC | CPU+iGPU / OpenVINO | Gemma 4 E4B / LFM-2 2.6B | `--target go` + OpenVINO |
| Laptop / ARM edge | Ollama | LFM-2 2.6B / LFM-2.5 | `--target python/liquid` |
| Ubuntu 26.04 | Inference Snap (immutable) | LFM-2 2.6B | `--target snap` |
| Edge / IoT | ARM / Android AICore | Gemma 4 E2B | `--target edge` |
| Cloud Cluster | vLLM / Triton | Any | `--target vllm` |

### Dynamic Fallback (The Resolute Path)

`splc` embeds a runtime fallback chain into the compiled artifact:

1. **Local High-Density:** utilize all CPU cores (Intel Mini-PC, iGPU via OpenVINO).
2. **Local Sparse:** shift to LFM-2 2.6B if available memory is <4GB.
3. **Cloud Failover:** fall back to AWS Bedrock / OpenAI if local nodes are offline.

The `.spl` author never writes this logic — it is injected by `splc` based on the deployment manifest.

### splc Implementation Roadmap

| Phase | Milestone | Deliverable |
|-------|-----------|-------------|
| v3.0 | Logical IR | Define `.spl` as the stable intermediate representation |
| v3.1 | `splc --target go` | Go binary for high-concurrency Intel Mini-PC (banking / batch) |
| v3.1 | `splc --target snap` | Ubuntu 26.04 inference snap: weights + logic as one artifact |
| v3.2 | `splc --target swift` | Apple Metal backend for M4/M5 unified memory |
| v3.2 | Hardware-aware optimizer | Auto-selects model quantization (INT4/INT8) per target profile |
| v3.3 | `splc --target edge` | ARM / Android AICore for IoT deployment |
| v3.x | Momagrid orchestration | Multi-node DODA: distribute sub-workflows across device tiers |

### Snap Inference (Ubuntu 26.04 Integration)

For Ubuntu 26.04 "Resolute Raccoon", `splc --target snap` outputs a `.snap` package that encapsulates:
- The compiled SPL logic (Go/C++ binary).
- Quantized model weights for the target device class.
- The `inference-snap` interface to bind directly to host GPU/NPU drivers.

One-click deployment on Ubuntu: `sudo snap install my-workflow.snap && spl run my-workflow`.


---

## text2SPL Enhancement: Intent → SPL Logical View

*Added: 2026-04-05. Closing the full pipeline from human intent to deployed agentic workflow.*

### The Full Three-Layer Pipeline

text2SPL is the entry point to the DODA pipeline. Its role is precisely scoped: translate natural-language intent into a valid, auditable `.spl` script (the logical view). It knows nothing about deployment targets — that is `splc`'s domain.

```
[Human Intent]  →  text2SPL  →  [.spl Logical View]  →  splc  →  [Physical Deployment]
(Semantic Layer)                                        (Structural Layer)
```

This clean boundary means text2SPL can be evaluated independently of deployment: a generated `.spl` is correct if it expresses the right agentic logic, regardless of where it will run.

### text2SPL v2: Agentic Workflow Intent

text2SPL v1 handled single-workflow generation from intent. v2 targets **agentic workflow composition**: multi-agent patterns with orchestrator + sub-workflow structure, CALL PARALLEL branches, WHILE refinement loops, and exception handling strategies.

The enhancements:

| Capability | v1 | v2 |
|---|---|---|
| Single WORKFLOW generation | yes | yes |
| Multi-workflow orchestrator + sub-agents | no | **yes** |
| CALL PARALLEL branch suggestion | no | **yes** |
| WHILE refinement loop detection | no | **yes** |
| EXCEPTION WHEN strategy elicitation | no | **yes** |
| splc deployment target annotation | no | **yes** (`-- @target: go/snap/swift`) |
| SPL-by-Spec integration (spec.md → .spl) | partial | **full** |

### Generating the Deployment Annotation

text2SPL v2 accepts an optional `--target-profile` hint from the user (e.g., `--target-profile intel-mini-pc`). When provided, it injects `splc` target annotations as comments at the top of the generated `.spl`:

```sql
-- @splc-target: go
-- @splc-model: liquid-ai/lfm-2-2.6b
-- @splc-quantize: int4
WORKFLOW arxiv_morning_brief
    INPUT: @date TEXT DEFAULT 'today'
    ...
```

`splc` reads these annotations to seed its hardware-aware compilation without changing the workflow logic.

### RAG + Agentic Pattern Library

text2SPL v2 extends the cookbook RAG corpus with an **agentic pattern index**: named multi-agent patterns (code pipeline, research summarizer, debate loop, judge-retry) stored as `(intent description, orchestrator .spl + sub-workflow .spl)` pairs. At generation time, text2SPL retrieves the closest agentic pattern as a structural template, then fills in domain-specific workflow logic.

```
Intent → Pattern Retrieval (RAG) → Structural Template → Domain Fill → .spl Logical View
```

This means text2SPL v2 rarely generates orchestrators from scratch — it instantiates a validated pattern.

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
| RETURN status → EXCEPTION channel | Clean error propagation in composed workflows; unhandled types fall through to runtime default handler |
| `spl run` CLI | Loads registry, resolves imports, dispatches orchestrator workflow |
| `spl registry list/register` | Introspect and manage the workflow registry |
| `STORE @var IN memory.key` | Fully implement workflow memory writes (was stubbed in v2.0) |
| `spl test` pipeline runner | Test orchestrator workflows end-to-end with expected output matching |
| Code-RAG seeded from cookbook | 40+ recipes → vector DB; Text2SPL quality leap enabled by composition |

---

### v3.0 Out-of-Scope (defer to v3.x)

| Feature | Why deferred |
|---------|-------------|
| `STREAM INTO @var` | Requires streaming-aware Hub protocol; separate design needed |
| Dedicated Text2SPL model config | Config schema change; can ship as a patch after v3.0 |
| `PARALLEL DO ... END` (within WORKFLOW) | Subsumed by `CALL PARALLEL`; not needed independently |
| Specialty SPL fine-tuned model | Requires training data volume not yet available |
| Hub-to-Hub peering (WAN routing) | Testing peering between 2 local Hubs first; v3.1 companion to WAN paper |
| Tool Connectors (`tool.pdf_to_md()`) | Orthogonal to composition; can ship independently |
| `dd-*` library migration (SPL20 tech debt) | SPL20 concern; SPL30 builds on dd-* from day one |

---

### New Keywords: Exactly Two

SPL 3.0 introduces exactly two new keywords:

| Keyword | Construct | What it enables |
|---------|-----------|-----------------|
| `IMPORT` | `IMPORT 'lib/agents.spl'` | Multi-file workflow loading at parse time |
| `PARALLEL` | `CALL PARALLEL ... END` | Concurrent sub-workflow dispatch |

Everything else — `CALL`, `RETURN`, `EXCEPTION`, `WHILE`, `WORKFLOW`, `INPUT`, `OUTPUT` — is unchanged syntax with extended runtime semantics. The grammar is minimal; the power comes from the runtime and registry.

---

### SPL30 Tech Debt: Start Clean, Not Clean Up

SPL30 (`spl` package) is a greenfield Python package. Unlike SPL20, it uses `dd-*` libraries from day one — no bespoke wrappers:

| Layer | SPL20 (tech debt) | SPL30 (clean) |
|-------|------------------|---------------|
| LLM backends | `spl/adapters/` bespoke clients | `dd-llm` via `UnifiedLLMProvider` |
| Vector store | FAISS wrapper + ChromaDB | `dd-vectordb` (`FAISSVectorDB` / `ChromaVectorDB`) |
| Embeddings | Duplicate sentence-transformers calls | `dd-embed` single embedding layer |
| Database | Hand-rolled SQLite in `streamlit/db.py` | `dd-db` (`SQLiteDB`) |
| Caching | `prompt_cache` table in `.spl/memory.db` | `dd-cache` (`DiskCache`) |
| File extraction | Raw UTF-8 read for `--dataset` | `dd-extract` (`PDFExtractor`, etc.) |

This means SPL30's `pyproject.toml` lists `dd-llm`, `dd-vectordb`, `dd-embed`, `dd-db`, `dd-cache`, `dd-extract` as direct dependencies — not internal code.

---

## Multi-Runtime Expansion: SPL.ts (TypeScript / Browser / Node.js)

*Added: 2026-04-13. SPL.ts is a complete hand-port of SPL 3.0 targeting browser + Node.js.*

### What Exists Today

SPL.ts (`SPL.ts/` repo, CLI: `spl-ts`) is a fully working SPL 3.0 implementation in TypeScript:
- Lexer, parser, executor, stdlib (48 functions), registry, loader — all browser-safe
- Adapters: `echo`, `ollama`, `openai`
- 42 tests passing; `npm run test` is green

The architecture constraint: **only `cli.ts` imports `node:fs` / `node:path`.** All other modules use only Web APIs (`fetch`, `console`, `Map`, `Promise`). This means the core runtime bundles to a browser-compatible ES module without modification.

### SPL.ts is the `splc --target ts` Reference

Every design decision in SPL.ts is a template for `splc --target ts`:
- `const enum TokenType` → zero-overhead token constants in generated code
- `FileReader = (path: string) => Promise<string>` → injected dependency (browser vs. Node.js)
- `CommitSignal` control flow → RETURN without polluting the EXCEPTION channel
- `Promise.all()` for `CALL PARALLEL` → maps directly to Go's `goroutine + WaitGroup`
- Variable store as `Map<string, string>` → same loosely-typed runtime model as Python/Go

Keep `[splc note]` annotations in SPL.ts source to document the template decisions.

### NDD Closure Validation (Priority: High)

SPL.ts correctness is validated by NDD closure — the same oracle used for SPL.go:

```bash
# Oracle (Python)
spl3 run self_refine.spl --adapter echo > oracle.txt

# Candidate (TypeScript)
spl-ts run self_refine.spl --adapter echo > candidate.txt

diff oracle.txt candidate.txt   # must be empty
```

Status: `[TODO]` — NDD closure diff test script not yet written.
Target file: `SPL.ts/tests/ndd_closure.sh`

### SPL.ts Roadmap

| Feature | Status | Notes |
|---------|--------|-------|
| Core runtime (lexer/parser/executor/stdlib) | `[DONE]` | 42 tests passing |
| `echo`, `ollama`, `openai` adapters | `[DONE]` | fetch-based, browser-compatible |
| NDD closure diff test against `spl3 --adapter echo` | `[TODO]` | Priority — validates correctness |
| `anthropic` adapter | `[TODO]` | Mirrors Python/Go adapter |
| `openrouter` adapter | `[TODO]` | Same OpenAI-compatible REST |
| `FederatedRegistry` (local + Hub fallback) | `[TODO]` | Mirrors Python `FederatedRegistry` |
| `HubRegistry` (REST-backed) | `[TODO]` | `POST /tasks` / `GET /tasks/{id}` |
| Browser WASM bundle (`spl-ts.bundle.js`) | `[TODO]` | Zero-dependency browser embed |
| `IMPORT` multi-file loading in browser context | `[TODO]` | Needs virtual FS / fetch-based resolver |
| `NONE` / `NULL` literal full support | `[TODO]` | Parser gap inherited from SPL2 base |
| `DATACLASS` type | `[TODO]` | SPL 3.1; requires `CREATE TYPE` in parser |

---

## NDD Closure as a Formal Module

*Added: 2026-04-13. NDD closure is SPL's primary theoretical contribution — it should be a first-class testable artifact.*

### What NDD Closure Means

NDD = **Non-Determinism Decoupled**. The insight is that an LLM call is a pure, observable side effect:

```
echo adapter  →  f(prompt) = prompt          (deterministic, oracle)
real adapter  →  f(prompt) = LLM(prompt)     (stochastic, candidate)
```

With `--adapter echo`, any SPL runtime becomes deterministic. Two runtimes running the same `.spl` against `echo` must produce identical output — if they differ, one has a bug. The `diff` of their echo-adapter outputs is the correctness judge.

This is the same oracle/judge pattern used in:
- Compiler correctness testing (reference interpreter vs. compiled binary)
- Protocol conformance testing (reference implementation vs. candidate)
- Database query planning (logical result vs. physical plan result)

SPL's contribution is applying this to **agentic workflow runtimes** — where non-determinism (LLM calls) is the dominant source of unreliability.

### Formal Module Design

```
spl3/ndd_closure/
  oracle.py      — run workflow with echo adapter, capture output
  judge.py       — diff two outputs; LLM-based fuzzy judge for non-exact cases
  harness.py     — automated multi-recipe closure test (all cookbook recipes)
  report.py      — structured JSON report (pass/fail/diff per recipe, per runtime)
```

The harness runs all cookbook recipes with `--adapter echo`, captures outputs from all runtimes (Python, Go, TypeScript), and diffs them pair-wise. Any non-empty diff is a test failure.

### Roadmap

| Feature | Status |
|---------|--------|
| `spl3 run --adapter echo` oracle | `[DONE]` — all runtimes |
| Manual NDD closure tests (SPL20 gaps found and closed) | `[DONE]` |
| `07_spec_judge.spl` LLM-based fuzzy judge | `[DONE]` — sub-workflow in recipe 50 (`code_pipeline`) |
| `ndd_closure.sh` automated test script (Python vs. Go) | `[TODO]` |
| `ndd_closure.sh` TypeScript leg | `[TODO]` — after SPL.ts NDD test passes |
| Formal `ndd_closure/` Python module | `[TODO]` |
| Per-recipe JSON closure report | `[TODO]` |
| Integration with CI (GitHub Actions or similar) | `[TODO]` |

---

## Agentic Integrity

*Added: 2026-04-13. A research contribution to AI safety — the behavioral correctness metric for agentic systems.*

### The Concept

**Agentic integrity** is the property that an agentic workflow produces the same *logical* result across:
- Different runtimes (Python, Go, TypeScript)
- Different hardware (Intel, Apple Silicon, ARM)
- Different LLM backends (Gemma 4, LFM-2, GPT-4o)
- Different deployment modes (local, Hub, cloud)

It is a **behavioral equivalence** metric: given the same logical specification (`.spl` file) and the same input, the observable output is invariant across all physical instantiations.

NDD closure is the *operational definition* of agentic integrity: two runtimes have agentic integrity w.r.t. a workflow if their echo-adapter outputs are identical. A workflow that passes NDD closure on all runtimes is *agentically integral*.

### Why This Is an AI Safety Contribution

The dominant AI safety discourse focuses on model alignment (what the LLM does). Agentic integrity focuses on **workflow alignment** — what the *system* does, independent of which model powers it.

Current AI safety gaps that agentic integrity addresses:

| Gap | Agentic Integrity solution |
|-----|--------------------------|
| Runtime bugs manifest as behavioral differences, invisible in stochastic output | NDD closure catches them deterministically, model-independently |
| Behavior changes when deploying from dev (GPU server) to prod (edge device) | Agentic integrity requirement: same `.spl` must produce same logical result |
| "I trust the model but not the plumbing" | Verifiable claim: runtime is certified agentically integral against a reference |
| No formal correctness criterion for compiled AI workflows | `splc` correctness = NDD closure between compiled artifact and SPL3 reference |
| LLM benchmarks don't test the orchestration layer | NDD closure specifically isolates the orchestration layer from LLM variance |

This is a contribution *orthogonal* to model alignment — it is the correctness theory for the **agentic layer** above the LLM.

### The Three Levels of Agentic Integrity

```
Level 1: Runtime integrity
  Same .spl → same echo output across Python, Go, TypeScript
  Test: NDD closure diff

Level 2: Compiler integrity
  splc-compiled artifact → same echo output as SPL3 reference runtime
  Test: NDD closure on compiled target

Level 3: Deployment integrity
  Same .spl → same logical behavior across hardware tiers (laptop, Mini-PC, cloud)
  Test: NDD closure + semantic judge (recipe 56's spec_judge.spl pattern)
```

SPL currently has Level 1 partially validated, Level 2 defined but not yet automated, Level 3 as a research goal.

### Agentic Integrity Metric (Formal)

Define `AIM(W, R1, R2)` — the Agentic Integrity Metric for workflow W between runtimes R1 and R2:

```
AIM(W, R1, R2) = 1   if R1(W, echo) == R2(W, echo) for all inputs
AIM(W, R1, R2) = 0   otherwise (divergence detected, with diff as evidence)
```

For workflows with stochastic elements that cannot be fully determinized by echo:

```
AIM_fuzzy(W, R1, R2, judge) = judge(R1(W, real), R2(W, real)) ∈ [0, 1]
```

where `judge` is an LLM-based semantic equivalence judge (the `07_spec_judge.spl` pattern).

This metric can be computed, tracked over time, and reported — making agentic integrity measurable, not just claimed.

### Research Agenda

1. **Formal definition paper** — define agentic integrity precisely, position against related work (compiler correctness, protocol conformance, LLM evaluation)
2. **NDD closure module** — `spl3/ndd_closure/` Python package; automate AIM computation for all cookbook recipes across all runtimes
3. **AIM over time** — track AIM as the codebase evolves; regressions in AIM signal porting divergence before they manifest in production
4. **Deployment integrity experiments** — run same workflows on Intel Mini-PC, Mac M4, cloud; measure semantic equivalence with `spec_judge.spl`
5. **Safety paper** — position agentic integrity as a complementary dimension to model alignment: "alignment of the orchestration layer"

### Literature Connections

- **CompCert / certified compilation** — formal compiler correctness; `splc` has the same obligation
- **Observational equivalence** — programs are equivalent if no observer distinguishes them; echo adapter is the observer
- **Property-based testing (QuickCheck, Hypothesis)** — oracle-based random testing; NDD closure is deterministic oracle testing
- **LLM evaluation methodology** — why output-based benchmarks fail (stochastic); why oracle-based testing is the alternative
- **AI safety specification alignment** — `.spl` as a behavioral specification; agentic integrity as its verification
- **Protocol conformance testing (RFC test suites)** — NDD closure is to SPL runtimes what RFC conformance tests are to network stacks

---

## splc Compiler: Next Steps

*Updated: 2026-04-13. Complements the DODA section above with concrete implementation priorities.*

### Current State

| Target | Status | Notes |
|--------|--------|-------|
| `splc --target go` | `[DONE]` | Deterministic transpiler + LLM-based CLI integration |
| `splc --target ts` | `[PARTIAL]` | SPL.ts is the hand-crafted reference; every design decision annotated |
| `splc --target python/langgraph` | `[PARTIAL]` | `self_refine_langgraph.py` hand-crafted |
| `splc --target snap` | `[TODO]` | Ubuntu 26.04 |
| `splc --target swift` | `[TODO]` | Apple M4/M5 |
| NDD closure test (compiler correctness) | `[DONE]` | Manual validation of compiled Go against `spl3 --adapter echo` |

### What "Writing splc" Means

`splc` is a **source-to-source transpiler**: `.spl` → target language (Go, TypeScript, Swift, etc.). The hand-crafted ports (SPL.go, SPL.ts, `self_refine_langgraph.py`) are the reference implementations — they define what the compiler must generate.

The implementation approach:
1. Define an **IR** (intermediate representation) for SPL 3.0 AST nodes
2. Write a **code generator** for each target language, walking the IR
3. Test each generator's output against the hand-crafted reference (structural diff)
4. Validate correctness with NDD closure (behavioral diff)

### Priority: Go Target First

`splc --target go` is the highest-priority target because:
- SPL.go is already complete and NDD-validated (most recipes passing)
- Go is the Hub runtime — compiled Go workflows can run as Hub-native tasks without the Python interpreter
- The Go AST (`go/ast`) and `text/template` make code generation straightforward
- Intel Mini-PC deployment (`spl3 run` → `spl-go run`) is the immediate DODA use case

### TypeScript Target Second

`splc --target ts` benefits from SPL.ts's `[splc note]` annotations — the template is already documented. The generated TypeScript should be browser-runnable, unlocking SPL workflows as web components.

### Recipe-Driven Development

Each `splc` target is validated by generating all cookbook recipes and running NDD closure. The recipe set provides immediate, comprehensive test coverage without writing separate test cases.

---

## SPL 3.1: DATACLASS Type

*Added: 2026-04-13. Deferred from SPL 3.0 — requires stable CALL composition runtime first.*

### Design

```sql
-- Type definition (DDL)
CREATE TYPE CodeReview AS (
    score   FLOAT,
    verdict TEXT,
    passed  BOOL
)

-- Usage in workflow
WORKFLOW review_code
    INPUT:  @code TEXT
    OUTPUT: @review CodeReview
DO
    GENERATE reviewer(@code) WITH FORMAT JSON SCHEMA CodeReview INTO @review
    RETURN @review
END

-- Caller accesses fields via JSON path
CALL review_code(@code) INTO @review
@score := json_get(@review, 'score')
```

### Implementation Scope

| Change | File | Notes |
|--------|------|-------|
| `CreateTypeStatement` AST node | `ast_nodes.py` | DDL statement |
| `TypeRegistry` in executor | `executor.py` | `name → {field: type}` schema map |
| `WITH FORMAT JSON SCHEMA T` clause | parser + executor | Injects JSON schema into prompt |
| Field access via `json_get()` | stdlib | Already exists; use as accessor |
| Type-checked RETURN for DATACLASS OUTPUT | executor | Validate against schema at runtime |

### Dependencies

DATACLASS requires `CALL` composition to be stable (done in SPL 3.0) and `WITH FORMAT JSON SCHEMA` to be reliable across LLM adapters. The latter depends on structured output support, which varies by model. Defer to SPL 3.1 when structured output is standardized across Ollama, OpenAI, and Anthropic adapters.

---

## Momagrid: Moma Points Compute Currency

*Added: 2026-04-13. The economic layer for the Compute OS.*

### Design (Recap)

Moma Points are the compute currency of the Momagrid internet. They flow from:
- Workflow submitters (consumers) → Hub operators (providers)
- Across Hub-to-Hub peering boundaries (inter-Hub settlement)

The existing `ACCOUNTING: BILLABLE_TO` and `BUDGET_LIMIT` clauses in SPL are the user-facing interface. The Hub's event log already attributes every LLM call to `event_id → requester_id`.

### Implementation Roadmap

| Feature | Status | Notes |
|---------|--------|-------|
| `ACCOUNTING: BILLABLE_TO` / `BUDGET_LIMIT` parsing | `[DONE]` | SPL 2.0 |
| Event-level cost attribution in Hub event log | `[TODO]` | `event_id → cost_moma_points` |
| Per-call cost metering (token count × rate) | `[TODO]` | Requires token usage from LLM response |
| Hub wallet balance + debit API | `[TODO]` | `GET /wallet`, `POST /wallet/debit` |
| Inter-Hub settlement protocol | `[TODO]` | Peering payment for cross-Hub CALL dispatch |
| Moma Points faucet for development | `[TODO]` | Test allocation endpoint |
| `BUDGET_LIMIT` enforcement at Hub | `[TODO]` | Reject task if budget exceeded |

---

## Feature Graduation Policy: Python → Go → TypeScript

*Added: 2026-04-13. Makes the "Python is the lab" strategy explicit and manageable.*

### The Three Tiers

| Tier | Criteria | Runtimes |
|------|----------|----------|
| **Experimental** | Implemented in Python, no tests or known gaps | Python only |
| **Stable** | Implemented in Python, tests passing, NDD-validated, no known gaps | Python |
| **Multi-Runtime** | Ported to Go and TypeScript, NDD closure passes on all three | Python + Go + TypeScript |

A feature moves from Experimental → Stable when:
1. At least one cookbook recipe exercises it end-to-end
2. The relevant unit tests pass (`pytest -k <feature>`)
3. NDD closure passes for that recipe (`spl3 run --adapter echo` diff is empty)

A feature moves from Stable → Multi-Runtime when:
1. Ported to SPL.go — NDD closure passes
2. Ported to SPL.ts — NDD closure passes
3. FEATURES.md updated with `[DONE]` across all three columns

### What This Means in Practice

- **Don't port prematurely.** New constructs (e.g., DATACLASS, STREAM INTO) stay Python-only until they are stable. Porting unstable features causes thrash in all three repos simultaneously.
- **Don't let Go/TypeScript fall behind indefinitely.** Once a feature has been stable in Python for two or more cookbook recipes, it is ready to port.
- **NDD closure is the promotion gate.** No feature graduates to Multi-Runtime without a passing NDD closure test in all runtimes.

### Current Tier Status (updated 2026-04-18)

| Feature | Python | Go | TypeScript | Tier |
|---------|--------|----|------------|------|
| SPL 1.0 prompt/query constructs | `[DONE]` | `[DONE]` | `[DONE]` | Multi-Runtime |
| SPL 2.0 workflow/procedural | `[DONE]` | `[DONE]` | `[DONE]` | Multi-Runtime |
| SPL 3.0 IMPORT, CALL PARALLEL | `[DONE]` | `[DONE]` | `[DONE]` | Multi-Runtime |
| **Cross-runtime run log parity** (`~/.spl/logs/`) | `[DONE]` | `[DONE]` | `[DONE]` | **Multi-Runtime ✓ 2026-04-18** |
| **Recipe 1 + 2 verified on all runtimes** | `[DONE]` | `[DONE]` | `[DONE]` | **Multi-Runtime ✓ 2026-04-18** |
| `spl3` SPL 2.0 PROMPT fallback | `[DONE]` | — | — | Stable |
| Multi-modal (IMAGE/AUDIO/VIDEO) | `[DONE]` | `[PARTIAL]` | `[TODO]` | Stable |
| NDD closure automated test | `[PARTIAL]` | `[PARTIAL]` | `[TODO]` | Experimental |
| FederatedRegistry / HubRegistry | `[DONE]` | `[DONE]` | `[TODO]` | Stable |
| DATACLASS / CREATE TYPE | `[TODO]` | `[TODO]` | `[TODO]` | Experimental (design) |
| **splc `--lang go`** (deterministic) | `[DONE]` | — | — | **Stable ✓ 2026-04-18** |
| **splc `--lang ts`** (deterministic) | `[DONE]` | — | — | **Stable ✓ 2026-04-18** |
| **splc `--lang python/langgraph`** (deterministic) | `[DONE]` | — | — | **Stable ✓ 2026-04-18** |
| splc `--lang python/crewai` (LLM) | `[DONE]` | — | — | Stable |
| splc `--lang python/autogen` (LLM) | `[DONE]` | — | — | Stable |
| splc NDD closure validation (`splc judge`) | `[TODO]` | — | — | Experimental |
| **Web-UI frontend** (`spl-ui`) | `[TODO]` | — | — | Planned (see below) |

---

## SPL Language Specification: text2SPL + Code-RAG as the Living Spec

*Added: 2026-04-13. The language spec is not a static document — it is the text2SPL system itself.*

### The Insight

Traditional languages (JavaScript/ECMAScript, SQL/ISO) separate the language spec from implementations. SPL takes a different path: the **cookbook recipes are the executable specification**, and **text2SPL + Code-RAG is the living spec engine**.

- 60+ cookbook recipes covering all SPL constructs → the empirical corpus
- Code-RAG indexes each recipe as `(description, source)` pair → the spec is queryable
- `spl3 code-rag query "WHILE refinement loop"` → retrieves canonical examples
- text2SPL generates new SPL from intent by retrieving the closest pattern — the spec guides generation, not just documentation

This means the spec is always in sync with the implementation (recipes are tested against the runtime) and is directly useful for generation (Code-RAG serves the spec at generation time).

### Fine-Tuning for a Robust text2SPL

The next step beyond RAG retrieval is **fine-tuning an open-source model on the SPL corpus**:

- Tool: [unsloth.ai](https://unsloth.ai) — efficient LoRA fine-tuning on consumer hardware
- Base model: Gemma 3 or LFM-2 (already in use via Ollama)
- Training data: all cookbook `.spl` files paired with their descriptions and comments
- Expected outcome: a model that generates syntactically correct, idiomatic SPL from natural language, without retrieval

| Approach | Pros | Cons |
|----------|------|------|
| Code-RAG (current) | No training; works today; generalizes to new patterns via retrieval | Quality limited by retrieval accuracy; struggles with novel compositions |
| Fine-tuned model | Robust generation; understands SPL idioms natively | Requires training data volume; needs periodic retraining as language evolves |
| Both (RAG + fine-tune) | Fine-tuned base + RAG for novel patterns | Best results; correct approach once corpus is large enough |

Target: fine-tune once the cookbook reaches 100+ recipes (enough training signal).

### NDD Closure as Conformance Test

NDD closure is the mechanical spec conformance test: a runtime is "spec-conformant" if it passes NDD closure on all cookbook recipes with `--adapter echo`. No separate test suite needed — the recipes *are* the test suite.

---

## Developer Ecosystem: Book, arXiv, and Two Untapped Audiences

*Added: 2026-04-13. SPL's adoption path is through academic publishing, open source, and a book targeting two underserved communities.*

### The Two Target Audiences

#### 1. SQL Professionals (30–50 million worldwide)

Every AI orchestration framework today — LangGraph, LangChain, AutoGen, CrewAI — targets Python developers. Nobody is seriously pursuing the SQL community. SPL is positioned to own that space.

The mental model transfer is direct:

| SQL | SPL | What it does |
|-----|-----|--------------|
| `SELECT col FROM table WHERE cond` | `SELECT expr FROM source WHERE cond` | Declarative data query |
| `WITH cte AS (...)` | `WITH cte AS (...)` | Composable sub-queries |
| `INSERT INTO` | `STORE RESULT IN memory.key` | Persist results |
| `CASE WHEN ... THEN ... END` | `EVALUATE @var WHEN ... THEN ... END` | Conditional branching |
| Stored procedure | `WORKFLOW name DO ... END` | Named, reusable logic |
| Function | `CREATE FUNCTION name(...) AS $$ ... $$` | Prompt templates |

A data professional already knows 70% of SPL. The book's message to this audience: *the language you know is now an AI orchestration language*.

SQL is a global language — taught in CS programs worldwide, used in banking, finance, government, and enterprise on every continent. This is not a niche audience. It is the largest single group of developers who have been systematically excluded from the "AI era" because all its tooling is Python-first and imperative.

#### 2. The Global Community Beyond Big Tech Cloud

China, India, Brazil, Nigeria, Indonesia, Vietnam, Egypt, Mexico, and every developer community where cloud AI costs are prohibitive or where data sovereignty makes local inference preferable — all have large, SQL-fluent data professional communities. They know SQL deeply. They need AI tools. And they have strong reasons to run inference locally.

**China deserves explicit mention.** China has one of the largest developer populations in the world, a deep SQL/data engineering culture (Alibaba, Tencent, ByteDance built on SQL-first data stacks), and has already produced leading open-source models — DeepSeek and Qwen are both in SPL's adapter list today. Chinese developers have strong data sovereignty motivations for local inference that align perfectly with the SPL + Ollama stack. The Qwen adapter means a Chinese developer can run SPL workflows entirely on domestic open-source models with zero cloud dependency.

The parallel to the LAMP stack era is precise:
- **LAMP** (Linux + Apache + MySQL + PHP): free, composable, ran on commodity hardware → democratized web development globally → the world became a contributor base
- **SPL + Ollama + Gemma/Qwen/LFM + Momagrid**: free, composable, runs on consumer hardware → democratizes AI development globally → the world becomes a contributor base

The Momahub Moment blog already named the problem: *"AI capability rationed by ability to pay."* SPL + local inference is the answer. Zero cloud costs. No API keys. No monthly bills.

**Momagrid as economic inclusion:** Node operators anywhere in the world can join Momagrid and earn Moma Points by contributing inference compute. The decentralized network is not just technically egalitarian — it is economically egalitarian. Idle compute in Lagos, Jakarta, São Paulo, and Shenzhen contributing to and earning from the global inference network.

#### The Overlap

The two audiences are not separate — they converge at the most impactful point:

```
SQL-fluent data professional outside the Big Tech cloud ecosystem
= knows the language + needs the tool + motivated to run locally
= ideal SPL contributor and Momagrid node operator
```

This is not a coincidence. This is the community SPL is built for.

### The Publishing Strategy

SPL is being built in public from day one:
- **All repos MIT / Apache 2 licensed** — open for use, contribution, and derivative works
- **arXiv papers** — each major innovation (SPL 2.0, NDD closure, Agentic Integrity, DODA/splc) published as a preprint; citable, discoverable, indexable by Google Scholar and Semantic Scholar
- **Book project** — comprehensive reference for SPL practitioners; SQL-first framing; accessible to non-Python backgrounds

Recognition and adoption of new languages takes years, not months. The academic route (arXiv → conference → journal) builds the citation foundation that makes SPL a legitimate research contribution. The book reaches the practitioner community that papers don't. Together they are mutually reinforcing: practitioners cite the paper to legitimize their use; researchers read the book to understand the practice.

### Book Outline (Draft Framing)

| Chapter | Topic | SQL Audience Hook |
|---------|-------|-------------------|
| 1 | What is SPL? | "SQL for LLMs — you already know the syntax" |
| 2 | SPL 1.0: Prompt Queries | SELECT + GENERATE = a query that thinks |
| 3 | SPL 2.0: Workflows | Stored procedures for AI pipelines |
| 4 | SPL 3.0: Composition | Microservice orchestration in 10 lines |
| 5 | NDD Closure | Testing AI workflows like testing SQL queries |
| 6 | Multi-Runtime | spl3 / spl-go / spl-ts — one language, any platform |
| 7 | Momagrid | Running SPL on a decentralized inference grid |
| 8 | AI@Home | Your Mini-PC as an AI node |
| 9 | Liquid + Snap adapters | Edge devices and Ubuntu deployment |
| 10 | DODA + splc | Compile once, deploy anywhere |
| 11 | Building your own cookbook | RAG, text2SPL, contributing recipes |
| 12 | Agentic Integrity | Why correctness matters for AI safety |

### Accessibility Considerations

The book and ecosystem should be accessible along two dimensions:
- **Technical**: SQL-first, not Python-first; minimal installation (Ollama + `spl3` or `spl-ts` in browser)
- **Economic**: local inference = zero ongoing cost; Momagrid means you don't need to *own* hardware to participate; browser runtime means a phone is sufficient to run SPL

### What SPL.ts Adds to Reach

Each runtime opens SPL to a new audience segment:
- `spl3` → Python/data science community
- `spl-go` → backend engineers and Hub operators
- `spl-ts` → JavaScript/TypeScript developers (largest developer population globally), and critically: **browser users with no installation at all**

A browser-based SPL playground lowers the barrier from "install Python + Ollama" to "open a URL." For the Global South audience specifically, this is the difference between reachable and unreachable.

---

## New Adapter Roadmap: Liquid and Snap

*Added: 2026-04-13. Two platform-specific adapters that extend SPL to new runtime environments and modalities.*

### Why These Two Matter

Every adapter in SPL is a gateway to a new platform:
- `echo` → deterministic testing (NDD closure oracle)
- `ollama` → local inference on any hardware
- `openai` → cloud-compatible REST (works with OpenAI, Groq, Together, Mistral)
- `anthropic` / `claude_cli` → Anthropic API and Claude tooling

The next two adapters open SPL to **new hardware classes** and **new modalities**:
- `liquid` → Liquid AI LFM models; audio + video on edge devices
- `snap` → Ubuntu's upcoming inference snap; immutable, installable AI runtime

### Liquid Adapter (`liquid`) — Edge Multimodal

**Model family:** Liquid AI LFM (Language-Free Model) — LFM-2 2.6B, LFM-2 8B, LFM-2 24B, LFM-2.5
**Access:** Ollama (local) and OpenRouter (cloud)
**Unique capability:** Native audio + video modality support — not just text and image

```sql
-- LFM-2.5 audio summary via liquid adapter
WORKFLOW transcribe_and_summarize
    INPUT:  @audio_file AUDIO
    OUTPUT: @summary TEXT
DO
    GENERATE audio_summarizer(@audio_file) INTO @summary
    RETURN @summary
END
```

**Why Liquid AI specifically:**
Liquid's state-space architecture (not transformer-based) is designed for efficient on-device inference. LFM-2 2.6B runs on devices with 4GB RAM — phones, Raspberry Pi, IoT. This is the edge deployment tier in the DODA matrix that no transformer model has reached at comparable quality.

| Component | Status | Notes |
|-----------|--------|-------|
| `LiquidAdapter` base class (Python) | `[DONE]` | Ollama + OpenRouter backends |
| `MultiModalMixin` + `ContentPart` types | `[DONE]` | `IMAGE`, `AUDIO`, `VIDEO` content parts |
| `generate_multimodal()` override | `[TODO]` | Full audio/video content-array pass-through |
| `spl/codecs/audio_codec.py` | `[TODO]` | WAV/MP3 → base64 `AudioPart` |
| `spl/codecs/video_codec.py` | `[TODO]` | Video frames → list of `ImagePart` |
| Cookbook recipe 51 (`audio_summary`) | `[DONE]` | End-to-end audio workflow |
| Liquid adapter in SPL.go | `[TODO]` | Port from Python |
| Liquid adapter in SPL.ts | `[TODO]` | Browser-compatible audio encoding |
| NDD closure test with Liquid model | `[TODO]` | Echo adapter still works; real test with LFM-2 |

### Snap Adapter (`snap`) — Ubuntu Immutable Inference

**Platform:** Ubuntu 26.04 "Resolute Raccoon" (expected H1 2026)
**Mechanism:** `ubuntu-ai` inference snap — model weights + runtime as a single installable package
**CLI target:** `splc --target snap` produces a `.snap` package (compiled workflow + model)

```bash
# Future: install an SPL workflow as a native Ubuntu snap
sudo snap install arxiv-morning-brief --channel=stable
arxiv-morning-brief run --param topic="AI safety"
```

This is the Ubuntu equivalent of an iPhone App Store app: one-click install, sandboxed, auto-updates, hardware-accelerated (NPU/GPU via snap interface).

**Why this matters for Momagrid:**
Snap packages are distribution-agnostic and auto-updating. A Momagrid node on Ubuntu 26.04 could receive workflow updates as snap revisions — no manual deployment, no version drift. The snap is the atom of the Momagrid network on Ubuntu.

| Component | Status | Notes |
|-----------|--------|-------|
| `SnapAdapter` placeholder | `[DONE]` | Documented; `UBUNTU_AI_URL` env var reserved |
| Ubuntu 26.04 GA | `[TODO]` | Canonical target: H1 2026 |
| `ubuntu-ai` snap API spec | `[TODO]` | Awaiting Canonical publication |
| `splc --target snap` compiler | `[TODO]` | Blocked on snap API + Ubuntu GA |
| End-to-end snap install test | `[TODO]` | Cook when Ubuntu 26.04 is available |
| Momagrid node snap auto-update | `[TODO]` | Snap revisions as workflow deployment channel |

### Platform-to-Adapter Matrix

The target is the full range of **consumer-grade CPU/GPU/NPU** hardware — not specific form factors. Any device a person already owns is a potential SPL node.

| Device Class | Example Hardware | Model | Adapter | SPL Target | Status |
|--------------|-----------------|-------|---------|-----------|--------|
| Consumer GPU (gaming PC) | RTX 4070/4090 | Gemma 4 27B, LFM-2 24B | `ollama` | `spl-go` / `spl3` | `[DONE]` |
| Consumer CPU (Mini-PC) | Intel N100/N305 | Gemma 4 E4B, LFM-2 2.6B | `ollama` | `spl-go` / `spl3` | `[DONE]` |
| Apple Silicon (laptop/desktop) | M4 / M5 (unified memory) | Gemma 4 27B, LFM-2 24B | `ollama` | `spl3` / `spl-ts` | `[DONE]` |
| ARM edge / low-power CPU | Raspberry Pi 5, Laptop | LFM-2 2.6B | `liquid` | `spl3` / `spl-go` | `[PARTIAL]` |
| Phone / IoT (4GB RAM) | Android, ARM NPU | LFM-2 2.6B | `liquid` (edge) | `splc --target edge` | `[TODO]` |
| Ubuntu 26.04 (any CPU/GPU) | Any Ubuntu machine | LFM-2 2.6B via snap | `snap` | `splc --target snap` | `[TODO]` |
| Browser (any device) | Any phone or laptop | WebLLM WASM | `wasm` (future) | `spl-ts` bundle | `[TODO]` |
| Cloud (fallback) | OpenAI / Anthropic / OpenRouter | GPT-4o / Claude / Qwen | `openai` / `anthropic` | any | `[DONE]` |

**The principle:** SPL runs where the hardware is, not where the cloud is. Consumer-grade CPU, GPU, and the emerging NPU generation (Qualcomm, Apple, Intel) are all first-class targets. The user does not need to upgrade hardware — they need software that meets them where they are.

---

## SPL.ts Browser Platform (Technical Roadmap)

*Added: 2026-04-13. The technical plan for browser-native SPL execution.*

### What SPL.ts Enables

The architecture constraint (zero Node.js APIs in core) was a deliberate design choice. Its consequence: the SPL runtime is a browser-native JavaScript library. Any web page can embed it.

```html
<script type="module">
  import { Lexer, Parser, Executor, EchoAdapter, Registry } from 'spl-ts';
  // Run SPL workflows in the browser — no server, no Python, no Go
</script>
```

### Web Platform Roadmap

| Milestone | Description | Status |
|-----------|-------------|--------|
| `spl-ts` npm package (public) | Publish to npm; browser and Node.js entry points | `[TODO]` |
| WASM-compiled LLM backend | WebLLM / llama.cpp WASM as an SPL adapter | `[TODO]` |
| In-browser SPL playground | Monaco editor + EchoAdapter + live output | `[TODO]` |
| Progressive Web App shell | Installable SPL workflow runner (desktop PWA) | `[TODO]` |
| Web-based workflow catalog | Browse, fork, and run cookbook recipes in browser | `[TODO]` |
| SPL-powered web components | `<spl-workflow>` custom element for embedding workflows in any web page | `[TODO]` |

### The WASM Adapter

A `WasmAdapter` that wraps WebLLM (llama.cpp compiled to WASM) would make SPL fully self-contained in the browser — no network calls, no API keys. This is the zero-dependency edge deployment vision applied to the web:

```
Browser tab → SPL.ts runtime → WasmAdapter → llama.cpp WASM → local inference
```

This mirrors the Ubuntu Snap adapter vision (weights + runtime as one artifact), but for the browser tab instead of the OS package.

### In-Browser SPL Playground (Priority: High)

The highest-leverage developer experience investment:
1. Monaco editor with SPL syntax highlighting
2. EchoAdapter for instant, deterministic output (no LLM key required)
3. OllamaAdapter via `OLLAMA_ORIGINS=*` for users with local Ollama
4. OpenAI-compatible adapter for users with API keys
5. Pre-loaded cookbook recipes as examples

This is the fastest path to SPL discoverability outside the current circle of contributors.

### Streamlit is Not the Web

The existing Streamlit UI is a Python process — it requires the server-side Python runtime, cannot be deployed as a static site, and is not mobile-friendly. SPL.ts + a React/Vue/Svelte frontend is the path to:
- GitHub Pages deployable documentation with live examples
- Mobile-responsive SPL playground
- Embeddable workflow widgets for documentation sites

---

## The AI Quartet: Ecosystem and Operational Domain

*Added: 2026-04-13. The four pillars of the SPL ecosystem, and how they compose into a coherent whole.*

### The Four Pillars

```
┌─────────────────────────────────────────────────────────────┐
│                    SPL Ecosystem                            │
│                                                             │
│  Language Layer         Runtime Layer                       │
│  ─────────────          ─────────────                       │
│  SPL (Python / SPL30)   spl3      — reference, lab          │
│  SPL.go                 spl-go    — backend, Hub runtime    │
│  SPL.ts                 spl-ts    — browser, Node.js        │
│                                                             │
│  Infrastructure Layer                                       │
│  ────────────────────                                       │
│  Momagrid               Hub       — decentralized           │
│                                     inference network       │
└─────────────────────────────────────────────────────────────┘
```

Each pillar is independently useful but gains power from the others:
- A `.spl` file runs on `spl3`, `spl-go`, or `spl-ts` identically (NDD closure guarantee)
- Any SPL runtime can dispatch to a Momagrid Hub — local execution or distributed, same syntax
- Momagrid connects AI@Home nodes into a larger inference network — without any cloud dependency

This is a **one-person shop** achievement: three production runtimes, a distributed infrastructure layer, a 60+ recipe cookbook, and active arXiv publication — all open source (MIT / Apache 2), all running on commodity hardware.

### Momagrid as Decentralized Inference Network

*See also: "Momagrid as a Compute OS" section above for the OS analogy.*

The AI@Home vision (blog: ["AI@Home with Gemma"](https://medium.com/@wen.g.gong/ai-home-with-gemma-369fa8c27e2b)) establishes the premise:

> "The AI that once lived only in data centers now runs in your garage, your village, your workplace."

A $500 Intel Mini-PC running Ollama + Gemma 4 is a fully capable AI inference node. The gap between "one home node" and "a network of home nodes" is exactly what Momagrid fills.

```
AI@Home Node (Mini-PC, Ollama + spl-go)
        │
        ▼  registers with Hub
  Momagrid Hub  ◄──── peer ────►  Another Hub
        │
  ┌─────┴─────┐
  Node A      Node B       (GPU nodes, home machines, edge devices)
```

**Momagrid is the infrastructure that turns AI@Home nodes into a decentralized inference network.** Each node:
- Runs `spl-go` or `spl3` as the workflow executor
- Registers available models and VRAM with the Hub (`WITH VRAM n`)
- Accepts tasks dispatched by the Hub's scheduler
- Can peer with other Hubs for cross-network workflow dispatch

No central cloud required. No API keys. No monthly bills. The compute is owned by the people running it.

### The Decentralized Inference Stack

| Layer | Component | Role |
|-------|-----------|------|
| Model | Gemma 4, LFM-2, Llama 3 via Ollama | Inference engine on local hardware |
| Workflow | SPL 3.0 (`.spl` files) | Declarative agentic logic |
| Runtime | `spl3` / `spl-go` / `spl-ts` | Executes SPL on any OS/hardware |
| Node | AI@Home machine (Mini-PC, Mac, Laptop) | Physical compute unit |
| Network | Momagrid Hub + Hub-to-Hub peering | Distributed task dispatch |
| Economy | Moma Points | Compute currency for node operators |
| Frontend | SPL.ts in browser | User interface without cloud dependency |

### Origin: The Momahub Moment (March 8, 2026)

The vision predates SPL v2.0. Blog: ["The Momahub Moment"](https://medium.com/@wen.g.gong/the-momahub-moment-df852c42f3da) (published 2026-03-08).

The core argument: hundreds of millions of consumer-grade GPUs in gaming PCs worldwide sit idle. Frontier AI labs are building prohibitively expensive centralized infrastructure. Momahub applies the same logic as GNU/Linux (democratized the OS) and the World Wide Web (democratized information) — unlock latent value from already-purchased, idle hardware through a coordination protocol. One credit per 1,000 tokens processed; a gaming GPU running 8 hours costs ~$0.15 in electricity.

Then on 2026-04-13, Google released Gemma 4. A state-of-the-art multimodal model — free, Apache 2.0 licensed, running locally on Ollama on a consumer-grade Mini-PC. The vision became a demonstration: ["AI@Home with Gemma"](https://medium.com/@wen.g.gong/ai-home-with-gemma-369fa8c27e2b).

The seed was planted in March. The tree is growing.

### Why This Is Meaningful

The standard AI deployment story is: cloud → API → application. Every inference call sends data to a third party and costs money.

The Momagrid story inverts this: **the compute is at the edge, the network is decentralized, the data never leaves the owner's hardware.** This matters for:
- **Privacy**: health workers, legal professionals, journalists — data stays local
- **Cost**: zero inference cost beyond electricity for node operators
- **Resilience**: no single point of failure; Hub-to-Hub peering means the network routes around outages
- **Sovereignty**: countries, communities, and individuals own their AI compute

SPL is the language of this network. Momagrid is the operating system. The AI quartet makes it real.

### Operational Roadmap for Momagrid

| Milestone | Status | Notes |
|-----------|--------|-------|
| Single Hub + multiple GPU nodes | `[DONE]` | Used in production for cookbook runs |
| Hub REST API (`POST /tasks`, `GET /tasks/{id}`) | `[DONE]` | Protocol stable |
| `WorkflowInvocationEvent` call tree | `[DONE]` | Parent-child event linkage |
| Hub-to-Hub peering (local LAN) | `[DONE]` | Two Hubs on same network |
| Hub-to-Hub peering (WAN / internet) | `[TODO]` | Validate with two internet-connected Hubs |
| Node health / VRAM reporting to Hub | `[TODO]` | Real-time node capability advertising |
| Hub workflow registry (name → definition) | `[TODO]` | Persistent workflow store, not just in-memory |
| Moma Points metering | `[TODO]` | Per-call token counting → cost attribution |
| Moma Points wallet + settlement | `[TODO]` | Node operator payment |
| Public Hub discovery / DNS | `[TODO]` | Find peer Hubs by name, not just IP |
| `spl-ts` Hub adapter | `[TODO]` | Browser workflows dispatching to Momagrid |
| Node auto-registration script | `[TODO]` | `curl install.momagrid.sh | bash` for new nodes |

---

## Web-UI Frontend for SPL v3.0 Launch

*Added: 2026-04-18 (session 7). SPL.ts makes this achievable without a Python backend.*

### Vision

The Streamlit UI (`spl3 ui`) is a Python-only development tool — it requires the server-side
Python runtime, can't be deployed as a static site, and is not mobile-friendly.
For the SPL v3.0 public launch, the Web-UI must be a first-class product:

- Shareable via a URL (GitHub Pages or static hosting — zero server cost)
- Mobile-friendly and installable as a PWA
- No installation required to try SPL for the first time
- Connected to Ollama for users with local inference, or cloud adapters as fallback

**SPL.ts is the enabler.** The browser-safe core (zero Node.js APIs) means
the same runtime that powers `spl-ts` CLI powers the Web-UI in the browser.

### Architecture

```
Browser Tab
├── Monaco Editor              — SPL source (.spl) with syntax highlighting
├── SPL.ts Runtime (ESM)       — lexer / parser / executor (already browser-safe)
│     ├── EchoAdapter          — instant deterministic feedback, no LLM needed
│     ├── OllamaAdapter        — local Ollama (OLLAMA_ORIGINS=* required)
│     └── OpenAI-compat        — OpenAI / Groq / Together / Mistral with API key
├── Cookbook Browser           — browse + fork recipes from cookbook_catalog_ts.json
└── Output Panel               — live run output, log viewer, token/latency stats
```

Static hosting (GitHub Pages, Netlify, Vercel) — no backend server required.
Momagrid Hub integration via `HubRegistry` (future) — dispatch from browser to LAN grid.

### Milestones

| Milestone | Description | Depends on | Status |
|-----------|-------------|------------|--------|
| `spl-ts` ESM bundle | `npm run build` → `dist/spl-ts.esm.js` (browser entry point) | SPL.ts complete | `[TODO]` |
| Monaco SPL syntax | `.tmLanguage` grammar for SPL keywords + token highlighting | — | `[TODO]` |
| React/Vue/Svelte shell | Single-page app: editor + output + adapter selector | ESM bundle | `[TODO]` |
| Cookbook browser panel | Load `cookbook_catalog_ts.json`, browse + click-to-load recipe | SPL.ts catalog | `[TODO]` |
| EchoAdapter live output | Run SPL with echo — instant, no LLM, zero config | Shell complete | `[TODO]` |
| Ollama integration | `OLLAMA_ORIGINS=*` guide + OllamaAdapter in browser | Shell complete | `[TODO]` |
| API key adapter | OpenAI-compat adapter with in-browser key storage (localStorage) | Shell complete | `[TODO]` |
| GitHub Pages deploy | `gh-pages` branch auto-deploy via GitHub Actions | Shell + bundle | `[TODO]` |
| PWA manifest + service worker | Installable on desktop and mobile | Deploy | `[TODO]` |
| Momagrid dispatch | `HubRegistry` in SPL.ts → submit workflow to LAN Hub from browser | HubRegistry | `[TODO]` |

### Front-End Technology Choice

| Option | Pros | Cons | Recommendation |
|--------|------|------|----------------|
| **React + Vite** | Largest ecosystem; Monaco integration well documented | Bundle size; JSX toolchain | **Recommended** — fastest to working prototype |
| Svelte | Smaller bundle; less boilerplate | Smaller community; Monaco integration less mature | Good alternative if bundle size matters |
| Vanilla JS + Web Components | Zero framework dependency | More code; harder to maintain | Only if framework is a hard constraint |

Recommendation: **React + Vite** for the initial launch. The SPL.ts runtime is framework-agnostic —
switching the shell later is possible without touching the runtime.

### Priority for Launch

The minimum viable Web-UI for SPL v3.0 launch:
1. Monaco editor with SPL highlighting
2. EchoAdapter run (no LLM) — proves the runtime works in browser
3. Cookbook recipe browser — browse + load any recipe
4. OllamaAdapter — for users with local Ollama
5. GitHub Pages deploy

Items 1–5 can be built on top of the existing SPL.ts ESM export with ~500 lines of React.
The LLM adapters, Momagrid integration, and PWA features are follow-on.

### Repo Strategy

| Option | Approach |
|--------|----------|
| New repo `SPL.ui` | Clean separation; own npm package; deploys independently |
| Add `web/` to `SPL.ts` repo | Easier to share types; single repo; simpler CI |

Recommendation: **`web/` directory inside `SPL.ts` repo** for the initial launch.
The `spl-ts` CLI and the `web/` frontend share the same compiled ESM bundle — no duplication.
Promote to its own repo if the Web-UI grows into a distinct product.

---

## Cookbook Expansion

*Added: 2026-04-13. Next recipes to build for SPL 3.0 coverage.*

| id | Recipe | Target | Constructs exercised | Priority |
|----|--------|--------|---------------------|----------|
| 57 | `debate_loop` | SPL30 | Two-agent debate: CALL PARALLEL, WHILE refinement, EVALUATE judge | High |
| 58 | `research_summarizer` | SPL30 | RAG + GENERATE + multi-doc WHILE iteration | High |
| 59 | `spec_to_code` | SPL30 + splc | text2SPL pipeline end-to-end (NDD closure anchor for splc) | High |
| 60 | `hub_dispatch` | SPL30 + SPL.go | CALL across Hub boundary; validates Hub-to-Hub peering | Medium |
| 61 | `browser_chat` | SPL.ts | Browser-native SPL workflow; validates WASM bundle | Medium |
| 62 | `multimodal_pipeline` | SPL30 | IMAGE → TEXT → AUDIO pipeline (Gemma 4 + LFM-2.5) | Medium |

Recipe 57 (`debate_loop`) is the natural successor to recipe 56 (`code_pipeline`) — it exercises `CALL PARALLEL` with two independent agent roles and a judge loop, which is the canonical multi-agent pattern.

Recipe 59 (`spec_to_code`) is the NDD closure anchor for `splc`: the generated Go/TypeScript code for this recipe is the primary target for the compiler's correctness test.

