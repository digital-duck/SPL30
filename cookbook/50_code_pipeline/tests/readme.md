# Unit Tests — `cookbook/56_code_pipeline`

SPL workflows have explicit `INPUT` / `OUTPUT` contracts, which makes each sub-workflow independently testable. This directory exercises every `.spl` file in isolation before wiring them together into the full pipeline.

## Philosophy

```
spec ──► 00_analyze_spec ──► 01_generate_code ──► 02_review_code
                                                         │
              ◄──────────────── 03_improve_code ◄────────┘
                                      │
         04_test_code ◄───────────────┘
              │
         05_document_code ──► 06_extract_spec ──► 07_spec_judge
```

Each node is a black box: feed it inputs, assert the output matches a sentinel token or keyword pattern. No mocking of LLM internals — the workflow runs end-to-end with a real model, so these are integration-style unit tests (fast enough for local CI with a small model like `llama3.2`).

## Mock Data (`mock/`)

| File | Purpose |
|------|---------|
| `spec_clear.txt` | Well-defined `binary_search` spec → triggers `[READY]` |
| `spec_vague.txt` | "Write something useful with AI" → triggers `[VAGUE]` |
| `code_good.py` | Correct binary search implementation |
| `code_buggy.py` | Intentionally broken: wrong bounds, wrong comparison direction |
| `feedback.txt` | Explicit bug list referencing the 4 defects in `code_buggy.py` |
| `spec_extracted.txt` | Close paraphrase of `spec_clear.txt` → triggers `[CLOSED]` in spec judge |

## Sentinel Tokens

| Workflow | Token(s) |
|----------|---------|
| `00_analyze_spec` | `[READY]` / `[VAGUE]` |
| `04_test_code` | `[PASSED]` / `[FAILED]` |
| `07_spec_judge` | `[CLOSED]` / `[DIVERGED]` |

Other workflows (`01`–`03`, `05`–`06`) are checked with keyword patterns (function names, doc section headers, domain terms).

## Test Scripts

| Script | Workflow under test | Cases |
|--------|---------------------|-------|
| `00_analyze_spec_test.sh` | `00_analyze_spec.spl` | clear spec → `[READY]`, vague spec → `[VAGUE]` |
| `01_generate_code_test.sh` | `01_generate_code.spl` | Python `def binary_search`, Go `func binary` |
| `02_review_code_test.sh` | `02_review_code.spl` | good code → non-empty output, buggy code → bug keywords |
| `03_improve_code_test.sh` | `03_improve_code.spl` | buggy code + feedback → `def binary_search` in output |
| `04_test_code_test.sh` | `04_test_code.spl` | good code → `[PASSED]`, buggy code → `[FAILED]` |
| `05_document_code_test.sh` | `05_document_code.spl` | output contains Markdown doc sections |
| `06_extract_spec_test.sh` | `06_extract_spec.spl` | output mentions `binary`, `search`, `sorted`, or `index` |
| `07_spec_judge_test.sh` | `07_spec_judge.spl` | matching specs → `[CLOSED]`, diverged specs → `[DIVERGED]` |

## Running Tests

Run a single test (defaults to `llama3.2`):

```bash
bash tests/00_analyze_spec_test.sh
bash tests/04_test_code_test.sh gemma3
```

Run the full suite:

```bash
# default model
bash tests/run_all_tests.sh

# specific model
bash tests/run_all_tests.sh gemma3
```

Logs are written to `tests/logs/<workflow>/<case>/` for post-run inspection.

## Two-Phase Strategy

1. **Unit tests** (this directory) — one `.spl` at a time, small model, fast feedback.
2. **End-to-end test** — run the full `code_pipeline.spl` orchestrator once all units pass; validates that `WorkflowComposer` wires the sub-workflows correctly and that sentinel tokens propagate across CALL boundaries.
