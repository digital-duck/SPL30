# Recipe 63: Parallel Code Review

**Category:** agentic / SPL 3.0  
**SPL version:** 3.0  
**Type:** TEXT → TEXT  
**LLM required:** Yes — any text model (default: `gemma4`)  
**Demonstrates:** `IMPORT`, `CALL PARALLEL`, heterogeneous fan-out + merge

---

## What it does

Runs three independent quality checks on a code snippet **concurrently**, then
merges the results into a single prioritised action plan.

```
@code ──┬── style_review    ──► @style_fb  ──┐
        ├── security_audit  ──► @sec_fb    ──┼── merge ──► @report
        └── test_generator  ──► @test_fb   ──┘
```

The three reviewers are **heterogeneous** — each is its own imported sub-workflow
with its own prompt and output budget — but they all take the same `@code` input.
Because they don't depend on each other's output, they run in parallel.

---

## Files

| File | Role |
|---|---|
| `parallel_code_review.spl` | Main orchestrator — imports sub-workflows, fans out, merges |
| `00_style_review.spl` | Sub-workflow: style, readability, correctness |
| `01_security_audit.spl` | Sub-workflow: security vulnerability scan |
| `02_test_generator.spl` | Sub-workflow: unit test case generation |
| `logs-spl/` | Execution logs (auto-created on run) |

---

## Prerequisites

```bash
ollama serve
ollama pull gemma4      # or llama3.2, qwen3, deepseek-r1, etc.
```

No API keys required for local runs.

---

## Running

```bash
# Inline code snippet
spl3 run cookbook/63_parallel_code_review/parallel_code_review.spl \
    --param code="def add(a, b): return a - b" \
    --param review_model="gemma3"

# From a file
spl3 run cookbook/63_parallel_code_review/parallel_code_review.spl \
    --param code="$(cat my_module.py)" lang=python

# Go code
spl3 run cookbook/63_parallel_code_review/parallel_code_review.spl \
    --param code="$(cat main.go)" lang=go model=gemma4

# With spl-go
spl-go run cookbook/63_parallel_code_review/parallel_code_review.spl \
    --param code="def add(a, b): return a - b" --adapter ollama -m gemma4

# Dry-run
spl-go run cookbook/63_parallel_code_review/parallel_code_review.spl \
    --param code="def add(a, b): return a - b" --adapter echo
```

---

## Expected output

```
============================================================
Workflow Status: complete
LLM Calls: 4 | Tokens: ~1200 in / ~600 out
Latency: ~4000ms (parallel branches) | Cost: $0.000000
------------------------------------------------------------
Committed Output:
## Action Items
1. [CRITICAL] Function name `add` returns `a - b` — subtraction, not addition. ...
2. [LOW] No input validation for non-numeric types.

## Test Coverage
```python
import pytest
from module import add

def test_add_positive():
    assert add(2, 3) == 5
...
```

## Summary
The code contains a critical logic error ...
============================================================
```

LLM calls breakdown: 3 parallel sub-workflow calls + 1 serial merge.

---

## SPL 3.0 concepts illustrated

| Concept | Where |
|---|---|
| `IMPORT 'file'` | Load 3 sub-workflow definitions before execution |
| `CALL PARALLEL ... END` | Fan-out to `style_review`, `security_audit`, `test_generator` |
| Heterogeneous branches | Each branch has its own prompt, output budget, and focus |
| Branch isolation | All branches read `@code`; each writes only to its own `INTO @var` |
| Named arguments in `CALL` | `lang=@lang, model=@model, log_dir=@log_dir` |
| Fan-out → merge | 3 parallel outputs feed 1 final `GENERATE merge_reviews(...)` |
