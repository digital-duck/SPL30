# SPL Future Work — Design Ideas

*Captured: 2026-03-30. These ideas are beyond the current SPL 2.0 arXiv paper.*

**Implementation progress:** see [FEATURES.md](FEATURES.md) for what is currently implemented and tested. 
- ROADMAP.md tracks *design intent*; 
- FEATURES.md tracks *build status* (test results, known failures, and what remains TODO).

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
| `SPL3Type` enum + coerce helpers | `spl/types.py` | done |
| Grammar spec additions | `specs/grammar-additions.ebnf` | done |
| Token keywords: NONE, NULL, IMAGE, AUDIO, VIDEO | lexer extension | todo |
| `SetLiteral` AST node | AST extension | todo |
| `{a, b}` SET vs `{k: v}` MAP disambiguation | parser extension | todo |
| `NONE` literal → `Literal(value=None, literal_type='none')` | parser extension | todo |
| INT/FLOAT coercion in workflow INPUT processing | executor extension | todo |
| Multimodal param pass-through to LLM adapter | executor + adapters | todo |
| Liquid AI LFM adapter (Ollama + OpenRouter) | `spl/adapters/liquid.py` | done |
| `MultiModalMixin` + `ContentPart` types | `spl/adapters/base_multimodal.py` | done |
| Ubuntu 26.04 snap adapter (placeholder) | `spl/adapters/snap.py` | placeholder |
| `spl/codecs/` data transform layer (PIL, WAV, video frames) | `spl/codecs/` | todo |
| `generate_multimodal()` override in LiquidAdapter | `spl/adapters/liquid.py` | todo |
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

Start prototyping immediately to validate SPL 3.0 multi-modal support end-to-end. New `multimodal` category, recipes starting at id 50 (after SPL20's last recipe id 49):

| id | Recipe | Type | Model | Status |
|---|---|---|---|---|
| 50 | `image_caption` | IMAGE | Gemma 4 via Ollama | todo — immediately actionable |
| 51 | `audio_summary` | AUDIO | Liquid LFM-2.5 via Ollama | todo — near-term |
| 52 | `visual_qa` | IMAGE | Gemma 4 via Ollama | todo — multi-turn vision RAG |
| 53 | `video_scene` | VIDEO (frames) | Gemma 4 via Ollama | todo — planned |

Recipe 50 (`image_caption`) is the unblocked starting point: Gemma 4 is available on Ollama today, `IMAGE` type is already in `spl/types.py`, and `OllamaAdapter` passes the content array through the `/v1/chat/completions` endpoint unchanged.

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

