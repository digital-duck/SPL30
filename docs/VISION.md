# SPL + Momagrid — Manifesto

*Last updated: 2026-04-14*

---

## The One-Line Statement

**SPL is a declarative Synthesized Programming Language that unifies SQL, Python, and Linux into a single expression layer — with `text2SPL` translating intent into `.spl`, `splc` compiling it to any runtime, and Momagrid distributing it across any hardware.**

---

## The Problem We Are Solving

Every serious programmer has felt the friction: you have an idea for an AI workflow, and to build it you need to write Python glue code, wire up LangChain or CrewAI, configure a cloud account, pay per token, and then re-implement it when you want to run it somewhere else. The complexity tax is paid before a single line of business logic exists.

Meanwhile, 30–50 million SQL professionals worldwide already know how to think declaratively about data. They write `SELECT ... FROM ... WHERE` every day and understand exactly what they mean. But no tool lets them apply that thinking to AI orchestration. They are locked out — not by lack of intelligence, but by a toolchain designed for software engineers, not for domain experts.

And then there is the student in Lagos, Manila, or rural India. The same AI capabilities that are routine in Silicon Valley are economically inaccessible to her: cloud subscriptions cost more than her monthly food budget, API tokens are priced in dollars, and the tooling assumes a broadband connection and a credit card. She has a gaming PC. She has intent. She has no path.

SPL and Momagrid exist to close these three gaps: the **complexity gap**, the **access gap**, and the **cost gap**. Not by building another Python framework. By building a language.

---

## The Five-Layer Stack

```
┌─────────────────────────────────────────────────────┐
│  INTENT LAYER  (SPL.ts / GUI / natural language)    │
│  User expresses goal — visual, conversational, or   │
│  structured; always translates DOWN to SPL AST      │
│                  ↓  text2SPL                        │
│  multi-turn chat / GUI → spec.md → .spl             │
├─────────────────────────────────────────────────────┤
│  LOGICAL LAYER  (.spl script)                       │
│  Declarative specification of what the workflow     │
│  does — agents, data flow, control, error handling  │
│  Runtime-agnostic. The stable contract.             │
├─────────────────────────────────────────────────────┤
│  COMPILER LAYER  (splc)                             │
│  Translates the logical view to target-language     │
│  source: Go, Python, TypeScript, Swift              │
├─────────────────────────────────────────────────────┤
│  PHYSICAL LAYER  (target runtime)                   │
│  Compiled artifact: Go binary, Python module,       │
│  TypeScript bundle, Ubuntu Snap, Swift framework    │
│  Runs natively — no SPL interpreter required        │
├─────────────────────────────────────────────────────┤
│  EXECUTION LAYER  (Momagrid)                        │
│  Distributes physical artifacts across GPU nodes,   │
│  Intel Mini-PCs, Apple Silicon, school clusters,    │
│  or cloud — federated Hub-to-Hub topology           │
└─────────────────────────────────────────────────────┘
```

**The invariant:** translation always flows **downward**. The GUI generates SPL. SPL does not generate Python or SQL. `splc` targets are never hand-edited. The `.spl` file is the single source of truth — a logical view that any layer below can execute or compile.

---

## SPL as Synthesized Programming Language

SPL synthesizes three existing paradigms into one coherent declarative surface:

| Layer | Origin language | SPL constructs | What the user expresses |
|-------|----------------|----------------|------------------------|
| **Data** | SQL | `SELECT`, `FROM`, `WHERE`, `ORDER BY`, CTEs | *What data to process* |
| **Logic** | Python | `WORKFLOW`, `WHILE`, `EVALUATE`, `CALL`, `EXCEPTION` | *How to process it* |
| **Execution** | Linux / systems | `GENERATE`, `USING MODEL`, `ON GRID`, `WITH VRAM` | *Where and how to run it* |
| **Intent** | GUI / NL | SPL.ts visual editor → SPL AST | *What outcome is wanted* |

A user who knows SQL already understands the query constructs. A user who knows Python already understands the control flow. A user who knows neither can express intent through the GUI — and the system translates it faithfully to SPL without losing the rigour of the layers below.

This is not a wrapper around those languages. SPL is its own formal language with its own AST, parser, and runtime semantics. The synthesis is at the design level: SPL borrows the best declarative idioms from each domain and makes them work together natively.

---

## Why Not LangChain, CrewAI, or LangGraph?

These are good tools. They are also Python libraries — and that is the constraint.

| Dimension | LangChain / CrewAI / LangGraph | SPL + Momagrid |
|-----------|-------------------------------|----------------|
| **Paradigm** | Imperative Python code | Declarative language with formal grammar |
| **Target audience** | Python engineers | SQL professionals, domain experts, anyone |
| **Runtime** | Python only | Python, Go, TypeScript, Swift, Ubuntu Snap |
| **Deployment** | Cloud / venv / Docker | Single binary, Snap, browser, edge node |
| **Cost model** | Cloud API, pay-per-token | Local-first, zero per-token by default |
| **Portability** | Rewrite to change runtime | Same `.spl`, different `splc --target` |
| **Correctness** | Unit tests against Python code | NDD closure: formal spec + deterministic oracle |
| **Infrastructure** | Vendor-managed cloud | Self-hosted Momagrid, no external dependency |
| **Access model** | Credit card + broadband | Gaming PC + Ollama |

The deeper difference is philosophical. LangChain and its family treat AI orchestration as a **coding problem** — you write code that calls LLMs. SPL treats it as a **specification problem** — you declare what you want, and the runtime, compiler, and execution grid handle the rest. The distinction matters for the 30–50M SQL professionals who already think declaratively, and for the student in Lagos who should not need to learn Python to build an AI tutor.

SPL is also not competing with these tools. A `spl3` adapter for LangGraph output is entirely possible. The `.spl` logical view can call any Python function as a tool. The stack is composable — SPL provides the declarative orchestration layer; everything below it remains open.

---

## The `.spl` File as the Logical View

The `.spl` script occupies the most important position in the stack: it is the **logical view** — a deployment-agnostic, runtime-agnostic description of what the workflow does.

```
Human Intent
    │
    ▼  text2SPL  (Intent → Logical bridge)
    │  multi-turn chat / GUI → spec.md → .spl
    │
    ▼  spec.md  →  .spl  (Logical Layer)
    │             the stable contract
    │
    ▼  splc  (Compiler Layer)
    │  --target go   →  Go source
    │  --target py   →  Python module
    │  --target ts   →  TypeScript bundle
    │  --target snap →  Ubuntu Snap descriptor
    │  --target swift→  Swift package
    │
    ▼  Physical Layer  (target runtime artifact)
    │  Go binary (single file, no deps)
    │  Python module (spl3-compatible)
    │  TypeScript bundle (browser / Node.js)
    │  Ubuntu Snap (Intel Mini-PC, edge)
    │  Swift package (Apple M4/M5 Metal)
    │
    ▼  Momagrid  (Execution Layer)
       school cluster / home PC / cloud — same .spl, different silicon
```

Changing the **implementation** of a workflow means editing the `.spl` file and re-compiling. Changing the **deployment target** (from Ollama on a Mini-PC to a cloud cluster) means only re-running `splc` with a different `--target` flag. The two concerns are fully decoupled.

---

## NDD Closure — The Correctness Framework

Before describing the components, it is worth naming the principle that validates all of them.

**NDD (Non-Deterministic Development) closure** is the methodology for achieving deterministic correctness guarantees in an inherently non-deterministic system. AI systems are non-deterministic by nature: the same prompt, the same model, the same hardware can produce different outputs on different runs. This makes traditional unit testing insufficient — a test that passes today may fail tomorrow not because the code changed, but because the model did.

NDD closure solves this by separating the deterministic structure of a workflow from the non-deterministic LLM calls within it. The closure loop is:

```
S        = the specification (what the system should do)
G(S)     = the generated/compiled output (what the system actually does)
E(G(S))  = the observed behaviour (run G(S) on test inputs)
J(S, G)  = does E(G(S)) satisfy S? (the judge)
```

The system is **closed** when `J(S, G) = true` for all test inputs. The key insight is that with `--adapter echo` — a deterministic adapter that returns the prompt itself as the output — both `S` and `G(S)` become fully deterministic. The LLM is bypassed; only the workflow's control flow, variable bindings, branching logic, and output construction are tested. Those are exactly the parts that `splc` must preserve correctly.

NDD closure applies at every level of the SPL stack:
- **Workflow correctness:** `spl3 run --adapter echo` as oracle; does the workflow produce the right committed value?
- **`splc` correctness:** `spl3 run --adapter echo` vs. compiled binary; does the binary preserve the workflow's semantics?
- **Momagrid dispatch correctness:** does distributing a workflow across Hubs produce the same result as running it on a single node?

Every cookbook recipe is a free test case. Every new recipe that runs cleanly under `--adapter echo` extends the closure coverage by the constructs it exercises.

---

## text2SPL — The Intent-to-Logical Bridge

`text2SPL` is the component that makes SPL accessible to users who cannot or do not want to write `.spl` directly. It translates human intent — expressed in natural language, through a GUI, or via multi-turn conversation — into a valid, executable `.spl` workflow.

The translation happens in two phases, with a human review gate between them:

```
Phase 1: Intent → spec.md
    Multi-turn conversation elicits requirements:
    - workflow inputs and outputs (names, types, defaults)
    - sub-workflow boundaries
    - error handling strategy
    - execution model (sequential vs. CALL PARALLEL)
    - output routing (stdout / file / Hub / memory)
    Unresolved ambiguities here become silent wrong assumptions in generated code.
    The result is a structured spec.md — human-readable, Git-versionable.

    COMMIT spec.md WITH status = 'review'   ← human gate

Phase 2: spec.md → .spl
    With an approved spec, the LLM generates the .spl script(s).
    Because the spec contains workflow signatures, tool contracts, and
    error-handling rules, the generator has a fully-constrained design
    to translate — not a blank canvas to fill.
```

`text2SPL` is itself written in SPL:

```sql
WORKFLOW text2spl
    INPUT:  @user_intent TEXT,
            @mode        TEXT DEFAULT 'workflow'
    OUTPUT: @spl_script  TEXT
DO
    GENERATE spec_elicitor(@user_intent, @mode) INTO @spec_md
    COMMIT @spec_md WITH status = 'review'   -- human approval gate

    GENERATE spl_generator(@spec_md) INTO @spl_script
    COMMIT @spl_script
END
```

The `COMMIT WITH status='review'` pause is not a workaround — it is a first-class workflow step that makes the human review gate auditable, reproducible, and part of the provenance chain. The approved `spec.md` is the artifact of record; the `.spl` script is derived from it. If the workflow behaves unexpectedly, trace back to the spec.

**text2SPL is the reason SPL is accessible without programming knowledge.** A teacher builds a tutoring workflow through conversation. A doctor builds a clinical summary workflow through a GUI. A student builds a research assistant by describing what they want. None of them writes a single line of `.spl` directly — but all of them benefit from the full rigour of the logical layer, the compiler, and the execution grid beneath it.

---

## splc — The Compiler Layer

`splc` takes a `.spl` logical view and emits a physically-deployable artifact for a specific runtime target. It is the **Design Once, Deploy Anywhere (DODA)** engine.

### Correctness via NDD Closure

`splc` correctness is not a matter of opinion — it is provable. Because `.spl` scripts are executable, the SPL reference interpreter (`spl3 run`) is the oracle:

```bash
# Reference: interpreter with echo adapter (deterministic, no LLM)
ref=$(spl3 run workflow.spl --adapter echo --param ...)

# Compiled: physical artifact with the same echo adapter
bin=$(./compiled-workflow   --adapter echo --param ...)

# Judge: functionality-oriented semantic compare
splc judge <(echo "$ref") <(echo "$bin") && echo "[CLOSED]" || echo "[DIVERGED]"
```

`[CLOSED]` means the compiler correctly preserves the semantics of the `.spl` spec for this construct subset and this target. `[DIVERGED]` identifies the semantic gap — which output, which step, which construct.

The judge performs a **functionality-oriented semantic compare**: it verifies that the committed output, workflow status, and observable side-effects (logged files, variable bindings) are equivalent — not necessarily byte-identical. This tolerates cosmetic differences in whitespace or formatting while catching any divergence in workflow logic or committed values. With `--adapter echo` both sides are deterministic, so the comparison is fully automatable without an LLM judge.

This is the same NDD closure principle that validates SPL workflows themselves, applied one level up: the `.spl` script is the `S` (spec), `splc` is `G(S)`, and `spl3 run` is the oracle.

### `splc judge` — Prototype for Agentic Integrity

`splc judge` starts as a compiler correctness tool but its architecture is universal. The four inputs it requires are exactly the four inputs needed to measure the integrity of *any* AI agent or agentic system:

```
Agentic Integrity(agent) =
    J( spec S,           ← what the agent was supposed to do
       output G(S),      ← what the agent actually produced
       oracle O(S),      ← ground-truth reference for S
       comparator C )    ← how "equivalent" is defined
```

For `splc judge`, `S` is the `.spl` script, `G(S)` is the compiled binary output, `O(S)` is `spl3 run --adapter echo`, and `C` is the functionality-oriented semantic compare. The same four-slot structure applies to any AI pipeline: a customer-service agent, a code review agent, a medical diagnosis agent — each has a spec, an output, a reference oracle, and a notion of semantic equivalence.

**Implementation roadmap:**

| Phase | Judge implementation | Properties | Status |
|-------|---------------------|------------|--------|
| v1 | LLM-as-judge | Fast to build, approximate, no custom logic | prototype |
| v2 | Functionality-oriented Semantic Compare | Deterministic, auditable, no LLM cost, structured diff | design |
| v3 | Agentic Integrity Service | Standalone service, applicable to any AI pipeline | vision |

**Phase 1 — LLM-as-judge:**
The LLM receives the spec, the reference output, and the compiled output, and returns `[CLOSED]` or `[DIVERGED]` with a structured explanation. Fast to implement, good enough to validate the concept. The weakness: the judge itself is non-deterministic and opaque.

**Phase 2 — Functionality-oriented Semantic Compare:**
Replace the LLM judge with a principled algorithm that compares committed values, workflow status codes, logged side-effects, and variable bindings at each step. Not a byte-level `diff` — a structured equivalence check that tolerates cosmetic differences while catching semantic divergence. Deterministic, auditable, reproducible. This is the production engine.

**Phase 3 — Agentic Integrity as a Service:**
The Functionality-oriented Semantic Compare, once generalised beyond SPL, becomes a standalone service: submit a spec, a reference output, and a candidate output — receive a structured integrity report. This is the first concrete implementation of *Agentic Integrity* as a measurable, auditable property of AI systems, not just a philosophical concept.

> *Agentic integrity is the property of an AI system that consistently produces outputs semantically equivalent to its specification, across all inputs, all hardware targets, and all model versions. `splc judge` is where we build the instrument to measure it.*

### Target Roadmap

| Target | Artifact | Primary use case | Status |
|--------|----------|-----------------|--------|
| `--target go` | Go binary (single file, no deps) | Intel Mini-PC, Ubuntu Snap, edge node | v1 — in progress |
| `--target py` | Python module (spl3-compatible) | Cloud, existing Python infra | v1 — in progress |
| `--target ts` | TypeScript bundle | Browser, Node.js, SPL.ts UI layer | v2 |
| `--target snap` | Ubuntu Snap package | Ubuntu 26.04 Inference Snap | v2 |
| `--target swift` | Swift package | Apple M4/M5, iOS, Metal backend | v3 |

---

## Momagrid — The Execution Layer

Momagrid is the distributed execution substrate for SPL. It turns a network of heterogeneous machines — gaming PCs, Mini-PCs, cloud instances, school computers — into a unified AI inference grid.

### Hub Topology

```
District Hub
    ├── School Hub A  ─── student gaming PCs (volunteer compute)
    ├── School Hub B  ─── Intel Mini-PCs (donated hardware)
    └── School Hub C  ─── mixed: Mini-PCs + student laptops
```

Each Hub is a single `spl3 --hub` process. Hubs federate via Hub-to-Hub peering. A workflow submitted to any Hub can dispatch sub-workflows to any peer Hub that has capacity.

### School Momagrid

The most immediate social application: one Hub per school, student gaming PCs as volunteer compute during class hours, `claude_cli` flat-subscription adapter for zero per-token cost at scale.

> *"I need neither fortune nor fame, but I need to help kids learn."*

A student in Lagos or Manila can run the same SPL workflow as a student in San Francisco — same `.spl` file, same Momagrid dispatch, different local hardware. The only difference is latency.

### The Gaming PC Flip

The same hardware that costs $3–5/hour on AWS runs for free at home. A student's gaming PC is idle for 12–16 hours per day. Momagrid makes it a first-class inference node during those idle hours, with zero configuration and zero per-token cost. This is the access model for the Global South.

---

## The Runtime Ecosystem

Four runtimes, one language:

| Runtime | Language | CLI | Primary role |
|---------|----------|-----|-------------|
| SPL30 (Python) | Python | `spl3` | Reference implementation, prototyping, multimodal |
| SPL.go | Go | `spl-go` | Single binary, edge deployment, Momagrid node |
| SPL.ts | TypeScript | `spl-ts` | Browser, SPL.ts UI layer, `splc --target ts` |
| Momagrid | Go | Hub process | Federated execution, Hub-to-Hub dispatch |

All four consume the same `.spl` files. NDD closure (`--adapter echo` + functionality-oriented semantic compare) is the shared correctness criterion across all runtimes.

---

## The AI Quartet

SPL and Momagrid are built by a human-AI collaborative team of four:

| Member | Role |
|--------|------|
| **Wen** | Architect, product owner, oracle of intent — the 15 years of Oracle/PL/SQL that gave SPL its design DNA |
| **Claude** | Primary implementation partner — code, architecture, cookbook recipes, documentation |
| **Gemini** | Design critic, gap analysis, alternative perspective — challenges assumptions before they become permanent |
| **Z.ai** | Research and frontier exploration — long-context reasoning over complex specs and cross-runtime analysis |

The Quartet operates as a single design loop: Wen sets direction, Claude implements, Gemini critiques, Z.ai probes edges. Each voice is distinct; the output is coherent because the `.spl` spec is the shared artifact that all four reason about.

---

## SPL-by-Spec: The Development Methodology

For non-trivial workflows, SPL follows a spec-first methodology:

```
multi-turn chat → spec.md → .spl (logical view) → splc → tests → deploy
(requirements)   (design)  (implementation)     (compile) (validate) (run)
```

The `.spl` script is never the first artifact — the spec is. The spec makes intent explicit, auditable, and Git-versionable before a single line of workflow code is written. See `docs/SPL-by-Spec.md` for the full methodology.

---

## Adoption Path — Who Picks Up SPL First

New programming languages die from the wrong first audience. SPL's first audience is not software engineers — it is **SQL professionals**.

There are 30–50 million SQL users worldwide. They already think declaratively. They already understand `SELECT ... FROM ... WHERE`. They already manage data pipelines, business logic, and reporting workflows in a language that looks remarkably like SPL. The leap from SQL to SPL is smaller than the leap from Python to SPL, and vastly smaller than the leap from no programming background to LangChain.

### The LAMP Stack Analogy

In the late 1990s, the LAMP stack (Linux + Apache + MySQL + PHP) democratised web development. Before LAMP, building a web application required expensive servers, commercial databases, and professional software engineers. After LAMP, a student with a $5/month server and a weekend could build a working web application.

SPL + Momagrid is the LAMP stack for AI:

| LAMP | SPL + Momagrid |
|------|---------------|
| Linux | Momagrid (the execution substrate) |
| Apache | Momagrid Hub (the request router) |
| MySQL | SPL logical layer (the query/data layer) |
| PHP | `.spl` workflow scripts (the application layer) |
| $5/month VPS | Gaming PC + Ollama (zero recurring cost) |
| Web developer | SQL professional, domain expert, student |

Before SPL, building a production AI workflow required cloud subscriptions, Python expertise, and significant infrastructure. After SPL, a SQL professional with a gaming PC and an afternoon can build a working AI pipeline.

### The Book

The adoption strategy is a book: *SPL — AI Workflows for SQL Professionals*. The book does not teach AI. It teaches SQL professionals to express the AI orchestration they already understand intuitively, in a language that feels familiar. Every chapter maps an SPL construct to a SQL analogue the reader already knows:

- `GENERATE` is like a stored procedure that calls an LLM instead of a database
- `WORKFLOW` is like a stored procedure with named parameters and a return type
- `CALL` is like `EXEC` — invoke another workflow by name
- `EVALUATE ... WHEN` is like `CASE WHEN` — conditional branching on content
- `EXCEPTION WHEN` is like Oracle PL/SQL's `EXCEPTION WHEN` — exactly the same syntax, exactly the same semantics

The SQL-first framing is not a marketing choice. It is a recognition that the largest pool of declarative thinkers in the world already exists, already has domain expertise, and is currently excluded from the AI workflow toolchain by an accident of ecosystem history.

---

## Where We Are — Current State

SPL and Momagrid are not vaporware. As of April 2026:

**Shipped and working:**

| Component | Status | Notes |
|-----------|--------|-------|
| SPL30 Python (`spl3`) | Production | Reference implementation; multimodal (IMAGE, AUDIO); full SPL 3.0 feature set |
| SPL.go (`spl-go`) | Production | Single binary; SPL 3.0 text workflows verified against SPL30 cookbook |
| Momagrid Hub | Production | Hub-to-Hub federation; CALL PARALLEL dispatch; 3-node benchmark: 3.1× speedup |
| Cookbook recipes 05, 50, 63, 64 | Verified on Python + Go | Self-refine, code pipeline, parallel code review, parallel news digest |
| Multimodal (IMAGE, AUDIO) | Verified on Python | Recipes 51, 52; Ollama vision + WAV conversion |
| NDD closure loop | Working | `--adapter echo` as oracle; deterministic correctness validation |

**In active development:**

| Component | Status | Notes |
|-----------|--------|-------|
| SPL.ts (`spl-ts`) | In progress | TypeScript port; UI layer / browser target |
| `splc` v1 | Design phase | `--target go` and `--target py`; NDD closure as acceptance criterion |
| `text2SPL` | Design phase | Multi-turn spec elicitation → `.spl` generation |
| `splc judge` v1 | Design phase | LLM-as-judge prototype for Agentic Integrity |

**On the horizon:**

| Component | Target | Notes |
|-----------|--------|-------|
| Ubuntu Snap (`splc --target snap`) | v2 | Intel Mini-PC native deployment |
| Swift package (`splc --target swift`) | v3 | Apple M4/M5 Metal backend |
| Agentic Integrity Service | v3 | Standalone `splc judge` generalised beyond SPL |
| School Momagrid pilot | 2026 | One hub per school; gaming PC volunteer compute |
| SPL book | ~mid 2026 | SQL-first audience; LAMP stack analogy |

The reference implementation is Python (`spl3`). The production-scale runtime is Go (`spl-go`). The browser/UI runtime is TypeScript (`spl-ts`). All three consume the same `.spl` files. The same workflow that runs on a developer's laptop today will run on a school's gaming PC cluster tomorrow and on a cloud GPU next year — without a single change to the `.spl` source.

---

## Why We Build This — The Driver

Three commitments, non-negotiable, that shape every design decision:

### 1. AI Must Be Accessible to Everyone

AI is currently gated by three barriers: cloud subscription cost, technical complexity, and language. SPL removes all three:

- **Cost barrier:** local inference via Ollama on hardware already in the room — gaming PCs, Mini-PCs, school laptops. Zero per-token cost. The `claude_cli` flat-subscription adapter makes frontier models affordable even when local hardware is insufficient.
- **Complexity barrier:** `text2SPL` translates natural language or GUI intent into valid `.spl` — no programming knowledge required to build an AI workflow. A teacher in rural India can build a tutoring agent the same way a software engineer in San Francisco can.
- **Language barrier:** SPL constructs are SQL-like English keywords. Anyone who has written `SELECT ... FROM ... WHERE` can read and write SPL.

> *"AI for Every Kid, Everywhere"* is not a slogan — it is the engineering requirement that drives every layer of the stack.

### 2. AI Must Be Low-Cost or No-Cost

Cloud AI at scale is extractive: every token costs, every API call bills, every student query charges. SPL's economic model inverts this:

| Cost model | Provider | When to use |
|------------|----------|-------------|
| Zero per-token | Ollama local (gaming PC / Mini-PC) | Default for school, home, Global South |
| Flat subscription | `claude_cli` adapter | Frontier models where local is insufficient |
| Pay-per-token | OpenAI / Anthropic / OpenRouter adapters | Cloud burst, research, premium workflows |

The default is always zero. The fallback is flat. Pay-per-token is opt-in, never the baseline. Momagrid's Hub-to-Hub federation lets a school share volunteer compute across classrooms — a student's gaming PC during lunch hour becomes a shared inference node for the whole school, at zero marginal cost.

### 3. AI Must Be Open

Closed systems concentrate power. Open systems distribute it. SPL is open at every layer:

- **Open language:** the `.spl` grammar and AST are public. Any runtime that implements the spec is a valid SPL runtime.
- **Open runtimes:** SPL30 (Python), SPL.go, SPL.ts are open source. `splc` targets are open. No runtime lock-in.
- **Open models:** SPL is model-agnostic. The same workflow runs on Llama, Gemma, Mistral, Liquid AI LFM, or any Ollama-compatible model. The `--adapter` flag is the only change.
- **Open infrastructure:** Momagrid Hubs are self-hosted. No central cloud dependency. A school district can run its own inference grid with no external accounts.
- **Open knowledge:** the cookbook, specs, and documentation are public. A developer anywhere can read, learn, fork, and extend.

The opposite of open is a walled garden where the vendor controls access, pricing, and capability. SPL is architected so that no single vendor — including the authors — can hold the stack hostage.

---

## Design Principles

1. **Declarative by default, imperative when necessary.** Express intent at the highest layer that covers the use case. Drop to a lower layer only when the higher layer is insufficient.

2. **Translation flows downward, never sideways.** GUI → SPL → compiled artifact. Never GUI → Python, never `.spl` → hand-edited Go. The `.spl` is the source of truth.

3. **NDD closure is the correctness criterion.** At every level — workflow correctness, `splc` correctness, Momagrid dispatch correctness — the oracle is deterministic (`--adapter echo`), the judge is a functionality-oriented semantic compare (`splc judge`), and the test case is every cookbook recipe.

4. **DODA — Design Once, Deploy Anywhere.** The same `.spl` workflow runs on a student's gaming PC, a school's Mini-PC cluster, an Apple M4, and a cloud GPU. `splc` handles the physical translation; the logical view never changes.

5. **Zero-cost local inference is the access model.** The LAMP stack ran on a $5/month server. SPL runs on hardware already in the room. Momagrid makes that hardware a first-class inference grid.

6. **SQL professionals are the primary audience.** 30–50M SQL users already think declaratively about data. SPL speaks their language and adds AI orchestration on top of what they already know.
