# text2mmd — Visual Intent Validation for the SPL Pipeline

## Executive Summary

Building agentic AI workflows is expensive. When intent is misunderstood early,
every downstream step — SPL generation, framework compilation, testing, deployment —
inherits the error and must be redone. **text2mmd** is a lightweight, optional
checkpoint that converts a natural language description into a human-readable Mermaid
diagram *before* any code is written. A 30-second diagram review can eliminate hours
of rework.

> **Core principle:** Make the structure visible and get human sign-off on it
> before committing to code. Diagrams are cheap. Rewrites are not.

---

## Business Value

### 1. Shift-left error detection

In traditional software development, bugs found in production cost 10–100× more to
fix than bugs found in design. The same multiplier applies to AI workflow development:

| Stage error is caught | Rework scope | Relative cost |
|---|---|---|
| Natural language description | Retype a sentence | 1× |
| **Mermaid diagram (text2mmd)** | **Edit a node or edge** | **2×** |
| Generated SPL | Rewrite prompt logic | 10× |
| splc-compiled target (LangGraph, Go…) | Rewrite framework code | 30× |
| Runtime / testing | Debug + recompile + re-test | 60× |
| Production deployment | Incident response + rollback | 100×+ |

A single `text2mmd` review catches errors at the 2× stage before they
cascade into the 30× or 100× range.

### 2. Shared vocabulary across roles

SPL code is readable only by technical practitioners. A Mermaid flowchart is
readable by everyone:

- **Product managers** can confirm the business logic matches requirements
- **Domain experts** can spot missing steps (e.g. "we always check for duplicates first")
- **Engineers** can identify over-engineering before writing a line of code
- **Compliance / legal** can review data flow and decision points for audit trails

This creates a **shared artifact** that replaces the misaligned back-and-forth between
business intent (English) and implementation (code).

### 3. Reduced iteration waste in the DODA pipeline

SPL's DODA principle (Design Once, Deploy Anywhere) only delivers its full value when
the design is *correct*. Every `splc` target compiled from a flawed `.spl` file
must be thrown away and regenerated. With text2mmd:

```
Without text2mmd:
  attempt 1: text → SPL (wrong structure) → splc × 3 targets → discard all
  attempt 2: text → SPL (closer) → splc × 3 targets → partial discard
  attempt 3: text → SPL (correct) → splc × 3 targets → ship
  Total: 9 splc compilations, 6 discarded

With text2mmd:
  attempt 1: text → diagram (wrong) → refine → approve
  attempt 2: diagram + text → SPL (correct) → splc × 3 targets → ship
  Total: 1 diagram refinement, 3 splc compilations, 0 discarded
```

### 4. Audit trail and institutional knowledge

Approved diagrams are persisted as `.mmd` files with metadata (description, model,
refinement rounds, timestamp). This creates a lightweight audit trail:
- What was the *intended* workflow before it became code?
- How many refinement rounds were needed — an indicator of requirement clarity
- Diagrams can be committed to version control alongside `.spl` files, making
  intent explicit in the repository for future maintainers

### 5. Lower barrier to entry for non-engineers

text2mmd makes SPL accessible to users who cannot read or write code.
They can describe a workflow in plain English, review the diagram, refine it
through natural language feedback, and approve it — without ever seeing SPL syntax.
The LLM handles the translation; the human handles the validation.

---

## Enhanced SDLC Process

### Current process (without text2mmd)

```
 User                    LLM                    System
  │                       │                       │
  │── description ────────▶│                       │
  │                       │── text2spl ───────────▶│
  │                       │                       │── validate SPL
  │                       │◀─ spl code ────────────│
  │◀─ spl code ───────────│                       │
  │                       │                       │
  │ [user reads SPL code — hard to validate]      │
  │                       │                       │
  │── "run it" ───────────────────────────────────▶│
  │                       │                       │── splc compile
  │                       │                       │── execute
  │◀─ wrong output ──────────────────────────────│
  │                       │                       │
  │ [user discovers structural error late]        │
  │── "fix it, different structure" ──────────────▶│  ← expensive
```

### Enhanced process (with text2mmd)

```
 User                    LLM                    System
  │                       │                       │
  │── description ────────▶│                       │
  │                       │── text2mmd ───────▶│
  │◀─ Mermaid diagram ────│                       │
  │                       │                       │
  │ [user reviews diagram — easy to validate] ✓  │
  │── feedback ───────────▶│                       │  ← cheap refinement
  │◀─ refined diagram ────│                       │
  │── "approve" ──────────────────────────────────▶│  ← structural contract locked
  │                       │                       │
  │                       │── text2spl ───────────▶│  (diagram as context)
  │                       │◀─ spl code ────────────│
  │                       │                       │── splc compile × N targets
  │◀─ targets (correct) ─────────────────────────│  ← first-time quality
```

### Where text2mmd fits in the SPL SDLC

```
┌─────────────────────────────────────────────────────────────────┐
│                     SPL Development Lifecycle                    │
├──────────┬──────────┬──────────┬──────────┬──────────┬──────────┤
│  Intent  │  Design  │  Logic   │ Physical │   Test   │  Deploy  │
│          │          │          │          │          │          │
│  Plain   │ Mermaid  │  .spl    │  splc    │  .test   │  target  │
│  English │ diagram  │  file    │ targets  │  .yaml   │ runtime  │
│          │          │          │          │          │          │
│          │    ◀ text2mmd ▶ │          │          │          │
│          │          │ ◀ text2spl ▶        │          │          │
│          │          │          │ ◀ splc ▶ │          │          │
│          │          │          │          │ ◀ spl test ▶        │
└──────────┴──────────┴──────────┴──────────┴──────────┴──────────┘
     ▲                    ▲                       ▲
  anyone           human approval            automated
 can author         gate here               validation
```

**Key insight:** the diagram approval is the only human gate before code generation.
Everything to the right of it can be fully automated. Getting it right unlocks the
entire DODA automation chain.

### Quality gates and feedback loops

```
text2mmd refinement loop (cheap — seconds each):
  description → diagram → [approve?]
                  ↑           │ No
                  └─ refine ◀─┘
                              │ Yes
                              ▼
text2spl (one-shot — guided by approved structure):
  diagram + description → SPL

splc compilation (deterministic — no LLM needed):
  SPL → LangGraph / Go / Python / CrewAI / AutoGen

spl test (automated):
  SPL + .test.yaml → pass/fail
```

Each stage has a clear input contract from the stage before it.
`text2mmd` makes that contract explicit and human-verified.

---

## Design

### Diagram type selection

| SPL pattern | Mermaid form | Rationale |
|---|---|---|
| `PROMPT` (single step) | `flowchart LR` — 2–3 nodes | Simple, clear |
| `WORKFLOW` (sequential) | `flowchart TD` | Top-down, natural reading |
| `WORKFLOW` (multi-agent) | `sequenceDiagram` | Shows who calls whom |
| `WORKFLOW` (state machine) | `stateDiagram-v2` | Explicit state transitions |

Default: **`flowchart TD`** for workflows, **`flowchart LR`** for prompts.
Auto-select based on keywords: *"agent"*, *"parallel"*, *"concurrent"* → prefer `sequenceDiagram`.

### SPL concept → Mermaid node mapping

| SPL concept | Mermaid node shape | Example |
|---|---|---|
| `INPUT` params | Parallelogram `[/input/]` | `I[/@task TEXT/]` |
| `GENERATE` (LLM call) | Rectangle | `G[Generate draft]` |
| `EVALUATE` (semantic) | Diamond | `E{Quality > 0.8?}` |
| `WHILE` loop | Arrow back to earlier node | `E -- No --> G` |
| `CALL` (tool/procedure) | Rounded rectangle | `C([write_file])` |
| `COMMIT` / `RETURN` | Parallelogram `[/output/]` | `O[/result/]` |
| `EXCEPTION` handler | Hexagon | `EX{{MaxIterations}}` |
| Parallel branches | `subgraph` | `subgraph parallel` |

---

## Pipeline integration

### As an optional step in `spl3 text2spl`

The text2mmd step is **opt-in** via a flag. It adds no latency when not used.
Existing workflows are completely unaffected.

```bash
# Standard: direct text → SPL (unchanged behaviour)
spl3 text2spl "build a self-refine agent"

# With diagram preview (interactive, blocks until user approves)
spl3 text2spl "build a self-refine agent" --via-mermaid

# Generate diagram only — useful for stakeholder review before any code
spl3 text2spl "build a self-refine agent" --mermaid-only -o diagram.md

# Generate diagram, save it alongside the SPL output
spl3 text2spl "build a self-refine agent" --via-mermaid --save-mermaid diagram.md -o agent.spl
```

### CLI feedback loop (`--via-mermaid` interactive mode)

```
$ spl3 text2spl "triage support tickets" --via-mermaid

Generating Mermaid diagram…

  flowchart TD
    I[/@ticket TEXT/] --> C{Classify severity}
    C -- critical --> E([escalate])
    C -- normal --> R[Generate response]
    R --> O[/response/]

Render at: https://mermaid.live/edit#...

[A]pprove  [R]efine  [S]kip diagram step  > _
```

If the user types `R`, they can provide free-text feedback:
```
Refine > Add a step to check for duplicate tickets before classifying
```
The diagram is regenerated with the feedback in context.

### Config keys (future `~/.spl/config.yaml`)

```yaml
text2mmd:
  enabled: false          # opt-in by default — no behaviour change for existing users
  adapter: claude_cli     # can differ from the text2spl adapter
  model: null             # inherits adapter default
  diagram_type: auto      # flowchart | sequence | state | auto
  save_diagram: false     # persist .mmd file alongside .spl for audit trail
  max_refine: 3           # max feedback rounds before forcing approval
```

---

## How it improves `splc` output quality

`splc` maps `.spl` constructs to framework-specific patterns (LangGraph nodes, CrewAI agents, etc.).
When the `.spl` has the right structure from the start, `splc` generates cleaner, smaller targets
with no structural dead-ends to work around:

| Scenario | Without text2mmd | With text2mmd |
|---|---|---|
| Missing loop | `splc` generates linear code; loop added manually | Caught at diagram stage |
| Wrong branching | Rewrite SPL + retranslate all targets | Fixed in one diagram edit |
| Over-engineered workflow | Discovered after full pipeline | Simplified before any code |
| Multi-agent confusion | Wrong agent boundaries in all targets | `sequenceDiagram` shows actors clearly |
| Missing exception path | Runtime error in production | Hexagon node triggers discussion |

The diagram is a **structural contract** between the user and the LLM compiler.
Locking it in before SPL generation means `text2spl` fills in the SPL *syntax*,
not the *architecture* — that decision has already been made and approved by a human.

---

## Implementation plan

### Phase 1 — Streamlit sandbox (SPL30) ✅ complete

- `spl3/ui/streamlit/pages/0_🗺️_Text2Mermaid.py`
  - LLM generates Mermaid diagram from description
  - Rendered live via mermaid.js (CDN, no install required)
  - Editable source with immediate re-render
  - Free-text feedback → regenerate loop (up to N rounds)
  - "Approve & Proceed" → stores diagram in `session_state`, visible on Text2SPL page
  - Approved diagrams saved to `data/diagrams/` for audit trail with metadata frontmatter

- `spl3/ui/streamlit/pages/1_⚡_Text2SPL` (updated)
  - Detects approved diagram in `session_state`
  - Injects it as a structural blueprint into the compiler description
  - Shows collapsible banner with active diagram and clear button

- `spl3/ui/streamlit/SPL_UI.py` (updated)
  - Text2Mermaid added to nav table as the first step in the pipeline
  - "Diagrams approved" counter added to landing metrics

### Phase 2 — CLI integration (SPL)

- `spl/text2mmd.py` — `Text2Mermaid` class
  - `generate(description, diagram_type="auto") → str`
  - `refine(diagram, feedback) → str`
  - `extract_mermaid(llm_output) → str` (strips code fences)
- `spl3/cli.py` — add `--via-mermaid`, `--mermaid-only`, `--save-mermaid` to `text2spl`
- `spl/config.py` — add `text2mmd.*` config section

### Phase 3 — Vue.js UI (SPL.ts)

- `src/components/MermaidPreview.vue` — renders Mermaid via `mermaid` npm package
- `src/components/Text2MermaidPanel.vue` — description input + generate + feedback loop
- `src/views/Text2SPLView.vue` — integrates MermaidPreview as optional pre-step
- WebSocket or REST bridge to LLM adapter for streaming diagram generation

---

## Mermaid rendering approaches

| Environment | Method | Notes |
|---|---|---|
| Streamlit | `st.components.v1.html()` with mermaid.js CDN | No extra package needed |
| CLI `--via-mermaid` | Print source + mermaid.live deep-link | Works anywhere |
| VS Code extension | Built-in Mermaid preview | `.mmd` file |
| Vue.js | `mermaid` npm package, `v-html` after render | Full control |
| GitHub / GitLab | Native Mermaid in Markdown fences | Free persistence in PRs |

---

## Example: self-refine agent

**Input description:**
> Build an agent that drafts a response, critiques it, and refines it until quality is approved or 5 iterations are exhausted.

**Generated diagram (round 1):**
```mermaid
flowchart TD
    I[/@task TEXT\n@max_iter INTEGER := 5/]
    I --> D[Generate draft]
    D --> C{Critique:\napproved?}
    C -- Yes --> O[/Commit result/]
    C -- No --> R[Refine with feedback]
    R --> Counter{iter < max_iter?}
    Counter -- Yes --> C
    Counter -- No --> O
```

**User feedback:**
> Add separate writer and critic models as inputs

**Refined diagram (round 2 — approved):**
```mermaid
flowchart TD
    I[/@task TEXT\n@writer_model TEXT\n@critic_model TEXT\n@max_iter INTEGER := 5/]
    I --> D[Generate draft\nUSING writer_model]
    D --> C{Critique\nUSING critic_model:\napproved?}
    C -- Yes --> O[/Commit result/]
    C -- No --> R[Refine with feedback\nUSING writer_model]
    R --> Counter{iter < max_iter?}
    Counter -- Yes --> C
    Counter -- No --> O
```

**Outcome:** `text2spl` receives the approved diagram alongside the description and generates
`self_refine.spl` with `@writer_model` and `@critic_model` INPUT params correctly wired —
no guesswork, no structural revision, `splc` compiles all targets in one pass.
