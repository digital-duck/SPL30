# SPL-by-Spec

**Spec-Driven Development for SPL workflows.**

SPL-by-Spec is our methodology for building reliable AI workflows: instead of going directly from a user idea to a `.spl` script, we insert a structured specification step that makes intent explicit, auditable, and reusable before any code is generated.

The name is intentional — it mirrors "infrastructure-as-code" thinking applied to AI pipelines.

---

## Why Spec-First

Direct text → .spl generation forces the LLM to simultaneously do requirements elicitation, design, and implementation in one shot. It fills ambiguities silently with plausible-but-wrong assumptions. Moving to a spec-first pipeline separates those concerns:

```
multi-turn chat   →   spec.md   →   .spl script   →   tests
(requirements)       (design)      (implementation)
```

Benefits:
- **Human review gate** — catch misunderstandings in prose, not in a failing workflow
- **Richer LLM prompt** — `spec.md` gives the generator explicit workflow signatures, tool interfaces, data flow, and error-handling rules; nothing is guessed
- **Reproducibility** — same `spec.md` produces consistent `.spl`
- **Auditability** — specs are Markdown files, git-versioned alongside the workflow
- **Test generation** — the spec's testing strategy section drives both `.spl` generation and `test_*.py` generation from the same artifact

---

## Relationship to spec-kit

[spec-kit by GitHub](https://github.com/github/spec-kit) (84k stars) popularised the same pattern for general-purpose software: NL → spec → implementation. SPL-by-Spec applies the same discipline to AI workflow scripts, with one important advantage: `.spl` is 10–50× more concise than equivalent Python, so the spec → code translation step has far less surface area for generation errors. SPL also has native constructs for the hard parts (EXCEPTION WHEN, WHILE with semantic conditions, CALL PARALLEL) that general-purpose generators must figure out per-language.

---

## The Pipeline

SPL-by-Spec spans **two layers of translation**:

```
multi-turn chat → spec.md → .spl (logical view) → splc → physical deployment → tests
(requirements)   (design)  (implementation)      (compile)  (run anywhere)
```

The `.spl` script is the **logical view**: it declares *what* the agentic workflow does — agents, data flow, error handling, orchestration — but says nothing about hardware, runtime, or model quantization. `splc` is the **structural layer** that translates the logical view into a hardware-specific artifact for the target device (Intel Mini-PC, Apple Silicon, Ubuntu Snap, cloud cluster).

This separation means spec authors, `.spl` generators, and deployment engineers work independently. The spec and `.spl` are deployment-agnostic; `splc` handles the rest.

### 1. Constitution

Project-level principles inherited by every workflow in the cookbook. Lives in `cookbook/CONSTITUTION.md`. Constrains all spec and code generation.

Examples of constitution rules:
- Always add `EXCEPTION WHEN RefusalToAnswer` in DO blocks that CALL sub-workflows
- Rate-limit all external HTTP tool calls (≥ 3s between requests)
- Use structural chunking only — no embedding-based chunking (`dd-extract` structural backend)
- Default LLM adapter: `dd-llm` → Liquid AI LFM; OpenAI as fallback
- All tools return JSON strings for lists/maps (SPL has no native collection literals beyond `[]` and `{}`)

### 2. Multi-Turn Chat (Requirements Elicitation)

User converses with an LLM to clarify intent. The chat phase must resolve:

- Workflow inputs and outputs (names, types, defaults)
- Sub-workflow boundaries (what is a separate WORKFLOW vs inline logic)
- Tool responsibilities (what Python code does vs what SPL orchestrates)
- Error handling strategy (skip / retry / raise / COMMIT with status)
- Execution model (sequential WHILE loop vs CALL PARALLEL for Momagrid)
- Output routing (stdout / file / Slack webhook / memory store)

Unresolved ambiguities here become silent wrong assumptions in generated code.

### 3. spec.md (Design Artifact)

The spec is the central artifact. It is human-readable, human-reviewable, and the sole input to `.spl` generation.

**Canonical spec.md structure:**

```
# <Workflow Name> — Recipe Spec

## 1. Overview
## 2. File Structure
## 3. Workflow Signatures        ← SPL WORKFLOW blocks with INPUT/OUTPUT
## 4. Tool Interface (tools.py)  ← Python function signatures + contracts
## 5. LLM Function Definitions   ← CREATE FUNCTION blocks
## 6. Data Flow                  ← ASCII or TikZ diagram
## 7. Testing Strategy           ← 3-level: unit / dry-run / integration
## 8. Dependencies
## 9. Open Questions for the Builder
## 10. Example Output
```

The spec explicitly states what the LLM generator does NOT need to invent: parameter types, return shapes, exception types, tool error behaviour, and token budgets.

### 4. .spl Generation

With an approved `spec.md`, the LLM generates the `.spl` script(s). The prompt is simply:

```
Given the attached spec.md and the SPL 3.0 grammar, generate:
1. <workflow_name>.spl  (orchestrator)
2. <sub_workflow>.spl   (sub-workflow, one per workflow signature in the spec)
Follow the SPL-by-Spec CONSTITUTION rules.
```

Because the spec contains workflow signatures, tool contracts, and error-handling rules, the generator has a fully-constrained design to translate — not a blank canvas to fill.

### 5. Test Generation

The spec's Section 7 (Testing Strategy) drives parallel generation of `tests/test_tools.py` and `tests/test_workflow.py`. Same spec → two outputs (workflow + tests), ensuring they're aligned by construction.

Tests validate the **logical view** — they run against the `.spl` directly via `spl test`, independent of deployment target. A workflow that passes logical tests is then handed to `splc` for physical compilation; target-specific integration tests are a separate concern.

### 6. splc Compilation (Physical Deployment)

With a validated `.spl` script, `splc` translates the logical view to a physical artifact for the target device. The spec may include a deployment manifest in an optional **Section 11**:

```markdown
## 11. Deployment Manifest
- target: intel-mini-pc
- model: liquid-ai/lfm-2-2.6b
- quantize: int4
- runtime: openvino
- fallback: aws-bedrock
```

If no manifest is present, `splc` uses auto-detection at compile time. The `.spl` script is never modified by this step — only the compiled output changes.

### 7. Iterate

Human reviews generated `.spl` and tests. Corrections feed back into `spec.md` (not directly into code), keeping the spec as the source of truth. Deployment changes (different hardware target, model swap) only touch the deployment manifest — the spec and `.spl` remain stable.

---

## Text2SPL Integration

SPL-by-Spec is the recommended backend for any Text2SPL feature. Text2SPL operates entirely in the **logical layer**: it takes human intent and produces a valid `.spl` script (the logical view). It does not concern itself with hardware targets or model selection — those are `splc`'s domain.

### text2SPL → Logical View

```sql
WORKFLOW text2spl
    INPUT:  @user_intent TEXT
    OUTPUT: @spl_script  TEXT
DO
    -- Phase 1: elicit a structured spec via multi-turn chat
    GENERATE spec_elicitor(@user_intent) INTO @spec_md

    -- Human review gate: pause and surface the spec for approval
    COMMIT @spec_md WITH status = 'review'

    -- Phase 2: generate .spl from the approved spec
    GENERATE spl_generator(@spec_md) INTO @spl_script
    COMMIT @spl_script
END
```

The `COMMIT ... WITH status='review'` pause maps directly to the SPL execution model and makes the human gate a first-class workflow step, not an out-of-band process.

### text2SPL → splc: The Full Pipeline

When a deployment target is known at generation time, text2SPL v2 accepts an optional `--target-profile` and injects `splc` annotations as comments at the top of the generated `.spl`. These annotations are inert to the SPL runtime but consumed by `splc` at compilation:

```sql
-- @splc-target: go
-- @splc-model: liquid-ai/lfm-2-2.6b
-- @splc-quantize: int4
WORKFLOW arxiv_morning_brief
    INPUT: @date TEXT DEFAULT 'today'
    OUTPUT: @brief TEXT
DO
    ...
END
```

The full three-layer pipeline in one view:

```
Human Intent
    │
    ▼  text2SPL (Semantic Layer)
    │  phase 1: spec elicitation → spec.md
    │  phase 2: spl generation → .spl (logical view)
    │
    ▼  splc Compiler (Structural Layer)
    │  hardware detection → optimized binary / snap / service
    │
    ▼  Momagrid Execution
       Intel Mini-PC / Apple M4 / Ubuntu Snap / Cloud — same .spl, different silicon
```

The `.spl` file is the stable contract between the two layers. Changing it requires re-running the spec → code pipeline. Changing the deployment target only requires re-running `splc`.

---

## Use Cases

### arXiv Morning Brief (`cookbook/arxiv_morning_brief/`)

**Status:** spec written, implementation pending.

The arXiv morning brief was the first workflow developed using SPL-by-Spec end-to-end:

1. **Chat phase** — two-session critique and discussion surfaced the key design decisions: structural (not embedding-based) chunking, 3s rate limiting on downloads, dd-cache for PDF caching, graceful skip on ToolError/RefusalToAnswer, sequential WHILE loop with a CALL PARALLEL upgrade flagged for SPL 3.1.

2. **spec.md** — `cookbook/arxiv_morning_brief/spec.md` documents all 10 sections: workflow signatures for `summarize_paper` and `arxiv_morning_brief`, 6 tool interfaces, 3 CREATE FUNCTION LLM blocks, TikZ data flow diagram, 3-level test strategy, open questions for the builder.

3. **Next step** — hand `spec.md` to a builder session to generate the `.spl` scripts and `tests/`.

This use case demonstrates the core value proposition: the spec survived a full critic review and a layout iteration on the flowchart before a single line of `.spl` was written. The implementation session starts with zero ambiguity.

---

## File Conventions

| File | Purpose |
|------|---------|
| `cookbook/CONSTITUTION.md` | Project-wide rules inherited by all specs |
| `cookbook/<name>/spec.md` | Canonical spec for the workflow |
| `cookbook/<name>/<name>.spl` | Generated orchestrator workflow |
| `cookbook/<name>/<sub>.spl` | Generated sub-workflow(s) |
| `cookbook/<name>/tools.py` | Python tool implementations |
| `cookbook/<name>/tests/` | Generated + hand-tuned tests |
| `cookbook/<name>/flowchart.tex` | TikZ diagram (optional, generated from spec) |

---

## Status

| Stage | Layer | Tooling | Notes |
|-------|-------|---------|-------|
| Constitution | logical | manual `CONSTITUTION.md` | to be created |
| Multi-turn chat | logical | any LLM (Claude recommended) | no tooling yet |
| spec.md generation | logical | LLM-assisted, human-reviewed | arXiv brief: done manually |
| .spl generation | logical | `spl_generator` prompt (TBD) | not yet implemented |
| Test generation | logical | `test_generator` prompt (TBD) | not yet implemented |
| Text2SPL workflow | logical | `text2spl.spl` (TBD) | design above, not yet coded |
| splc `--target go` | physical | `splc` compiler (TBD) | v3.1 milestone; Intel Mini-PC primary target |
| splc `--target snap` | physical | `splc` compiler (TBD) | v3.1 milestone; Ubuntu 26.04 Inference Snap |
| splc `--target swift` | physical | `splc` compiler (TBD) | v3.2 milestone; Apple M4/M5 Metal backend |
| Deployment manifest in spec | physical | Section 11 in spec.md | design above, not yet standardized |
