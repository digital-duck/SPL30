# splc — Test Instructions

Human verification guide for the SPL Compiler (`splc`).

`splc` translates a `.spl` logical view into a physical implementation in a
target language. These tests validate each stage of that pipeline: prompt
assembly, deterministic transpilation, LLM-based compilation, and output
correctness.

Reference recipe: **`cookbook/05_self_refine/self_refine.spl`** — the most
completely exercised recipe across all targets.

**Implemented targets (2026-04-18):**

| Target (`--lang`) | Transpiler | Status |
|-------------------|-----------|--------|
| `go` | `transpiler_go.py` (deterministic) | `[DONE]` |
| `ts` | `transpiler_ts.py` (deterministic) | `[DONE]` |
| `python/langgraph` | `transpiler_langgraph.py` (deterministic) | `[DONE]` |
| `python/crewai` | LLM-based (`--llm` required) | `[DONE]` |
| `python/autogen` | LLM-based (`--llm` required) | `[DONE]` |

---

## Setup

```bash
conda activate spl3
cd ~/projects/digital-duck/SPL30

# Verify splc is accessible
splc --help
# or via module:
python -m spl3.splc.cli --help
```

---

## Test 1 — Dry Run (prompt assembly, no LLM)

Verifies that `splc` correctly assembles its compilation prompt without calling
any LLM. Fast and free.

```bash
splc cookbook/05_self_refine/self_refine.spl --lang go --dry-run --verbose
```

**Expected:** Prints the full prompt (system rules + SPL source + generation
cue). No LLM call. Prompt should contain:

- The `splc` system rules block
- The `self_refine.spl` source verbatim
- "Generate the Go (stdlib + Ollama REST API) implementation now."

```bash
# Dry-run all three deterministic targets
for lang in go ts python/langgraph; do
    echo "--- $lang ---"
    splc cookbook/05_self_refine/self_refine.spl \
        --lang "$lang" --dry-run 2>&1 | grep -E "DRY RUN|Generate|ERROR"
done
```

**Expected:** Each target prints `DRY RUN` header and generation cue. No errors.

---

## Test 2a — Deterministic Go Transpiler

Uses the rule-based `GoTranspiler` — no LLM, instant, fully reproducible.
This is the reference implementation of DODA: `.spl → Go` without any model.

```bash
splc cookbook/05_self_refine/self_refine.spl \
    --lang go \
    --out-dir /tmp/splc-test-go \
    --overwrite \
    --verbose
```

**Expected:**
```
splc: using deterministic Go transpiler for self_refine.spl
  Written: /tmp/splc-test-go/self_refine_go.go
  Written: /tmp/splc-test-go/splc_manifest.json
splc done: self_refine.spl → go [Go (stdlib + Ollama REST API)]
```

**Inspect and run:**
```bash
cat /tmp/splc-test-go/self_refine_go.go   # should be valid Go
cat /tmp/splc-test-go/splc_manifest.json  # source SHA, target, timestamp

# Run (requires Ollama):
cd /tmp/splc-test-go
go run self_refine_go.go \
    --writer-model gemma3 \
    --critic-model gemma3 \
    --task "What are the benefits of daily exercise?"
```

**Expected:** Multi-iteration self-refine loop completes, prints final output.

---

## Test 2b — Deterministic TypeScript Transpiler

Uses the rule-based `TypeScriptTranspiler` — no LLM, zero-dependency `.ts` output,
browser-compatible (fetch-only).

```bash
splc cookbook/05_self_refine/self_refine.spl \
    --lang ts \
    --out-dir /tmp/splc-test-ts \
    --overwrite \
    --verbose
```

**Expected:**
```
splc: using deterministic TypeScript transpiler for self_refine.spl
  Written: /tmp/splc-test-ts/self_refine_ts.ts
  Written: /tmp/splc-test-ts/splc_manifest.json
splc done: self_refine.spl → ts [TypeScript (Node.js / Browser, fetch-only)]
```

**Inspect and run:**
```bash
cat /tmp/splc-test-ts/self_refine_ts.ts   # should be valid TypeScript

# Run (requires Node.js + tsx + Ollama):
cd /tmp/splc-test-ts
npx tsx self_refine_ts.ts \
    --writer-model gemma3 \
    --critic-model gemma3 \
    --task "What are the benefits of daily exercise?"
```

**Type-check (no Ollama required):**
```bash
cd /tmp/splc-test-ts && npx tsc --strict --noEmit self_refine_ts.ts
```

---

## Test 2c — Deterministic Python/LangGraph Transpiler

```bash
splc cookbook/05_self_refine/self_refine.spl \
    --lang python/langgraph \
    --out-dir /tmp/splc-test-lg \
    --overwrite \
    --verbose
```

**Expected:**
```
splc: using deterministic LangGraph transpiler for self_refine.spl
  Written: /tmp/splc-test-lg/self_refine_python_langgraph.py
  Written: /tmp/splc-test-lg/splc_manifest.json
splc done: self_refine.spl → python/langgraph [Python / LangGraph]
```

**Inspect and run:**
```bash
python -m py_compile /tmp/splc-test-lg/self_refine_python_langgraph.py  # must be silent

# Run (requires LangGraph + Ollama):
cd /tmp/splc-test-lg
pip install langchain-ollama langgraph
python self_refine_python_langgraph.py \
    --writer-model gemma3 \
    --task "What are the benefits of daily exercise?"
```

---

## Test 3 — LLM Compilation (Go target)

Compiles `self_refine.spl` to Go using Claude. Requires an active Claude Code
session (uses the `claude_cli` adapter).

```bash
splc cookbook/05_self_refine/self_refine.spl \
    --lang go \
    --llm \
    --out-dir /tmp/splc-llm-go \
    --model claude-sonnet-4-6 \
    --no-rag \
    --verbose
```

**Human verification checklist:**
- [ ] `self_refine_go.go` compiles: `cd /tmp/splc-llm-go && go build .`
- [ ] Every SPL construct has an inline `// SPL: ...` comment
- [ ] WHILE loop present (iterative refinement)
- [ ] EVALUATE block present (check for `[APPROVED]` token)
- [ ] EXCEPTION handling present (at least `ModelUnavailable`)
- [ ] INPUT params match the `.spl` INPUT block (`writer_model`, `critic_model`, etc.)
- [ ] `readme.md` contains setup instructions and SPL→Go mapping table
- [ ] `splc_manifest.json` has correct `spl_sha256` and `generated_at`

---

## Test 4 — LLM Compilation (LangGraph target)

```bash
splc cookbook/05_self_refine/self_refine.spl \
    --lang python/langgraph \
    --llm \
    --out-dir /tmp/splc-llm-langgraph \
    --model claude-sonnet-4-6 \
    --no-rag \
    --verbose
```

**Human verification checklist:**
- [ ] Valid Python: `python -m py_compile /tmp/splc-llm-langgraph/self_refine_python_langgraph.py`
- [ ] Uses LangGraph `StateGraph` or equivalent node/edge structure
- [ ] WHILE loop → graph cycle or conditional edge
- [ ] CALL sub-workflow → node or sub-graph invocation
- [ ] INPUT params (`writer_model`, `critic_model`) appear as function arguments or config
- [ ] `readme.md` includes `pip install` instructions

---

## Test 5 — NDD Closure Verification

The gold standard: the compiled physical artifact must produce semantically
equivalent **control flow** to `spl3 run --adapter echo` on the same `.spl`
source. Content will differ (echo vs real LLM); structure must match.

**Step 1: Run the reference (echo oracle)**
```bash
spl3 run cookbook/05_self_refine/self_refine.spl \
    --adapter echo \
    --param writer_model=x \
    --param critic_model=x \
    2>&1 | tee /tmp/spl3-echo-output.txt
```

**Step 2a: Run the compiled Go artifact**
```bash
cd /tmp/splc-test-go
go run self_refine_go.go \
    --writer-model x --critic-model x \
    --task "test" \
    2>&1 | tee /tmp/go-echo-output.txt
```

**Step 2b: Run the compiled TypeScript artifact**
```bash
cd /tmp/splc-test-ts
npx tsx self_refine_ts.ts \
    --adapter echo --writer-model x --critic-model x \
    --task "test" \
    2>&1 | tee /tmp/ts-echo-output.txt
```

**Step 2c: Run the compiled LangGraph artifact**
```bash
cd /tmp/splc-test-lg
python self_refine_python_langgraph.py --adapter echo \
    --writer-model x --task "test" \
    2>&1 | tee /tmp/lg-echo-output.txt
```

**Step 3: Structural comparison**

| Property | spl3 echo | Go | TypeScript | LangGraph | Match? |
|----------|-----------|----|-----------|-----------| -------|
| Workflow completes without crash | ✓ | ? | ? | ? | |
| WHILE loop executes at least once | ✓ | ? | ? | ? | |
| Iterates up to `max_iterations` limit | ✓ | ? | ? | ? | |
| Exits on `[APPROVED]` token | ✓ | ? | ? | ? | |
| EXCEPTION handler reachable | ✓ | ? | ? | ? | |
| Final output written to stdout | ✓ | ? | ? | ? | |

A future `splc judge` command will automate this comparison.

---

## Test 6 — Overwrite Guard

```bash
# First compilation (should succeed)
splc cookbook/05_self_refine/self_refine.spl \
    --lang go --out-dir /tmp/splc-overwrite-test --verbose

# Second run without --overwrite (should abort with error)
splc cookbook/05_self_refine/self_refine.spl \
    --lang go --out-dir /tmp/splc-overwrite-test --verbose
```

**Expected (second run):**
```
ERROR: /tmp/splc-overwrite-test/self_refine_go.go already exists. Use --overwrite to replace it.
```

---

## Test 7 — Manifest Provenance

After any successful compilation, verify the manifest:

```bash
cat /tmp/splc-test-go/splc_manifest.json | python -m json.tool
```

**Expected fields:**
- `splc_version` — `"0.1.0"`
- `generated_at` — ISO 8601 UTC timestamp
- `source.spl_file` — absolute path to `self_refine.spl`
- `source.spl_sha256` — 16-char hex hash (non-empty)
- `target.lang` — `"go"`
- `target.output_file` — absolute path to generated file
- `doda_note` — present and non-empty

---

## Test 8 — Multi-Recipe Smoke Test (all three deterministic targets)

```bash
for recipe in \
    cookbook/05_self_refine/self_refine.spl \
    cookbook/63_parallel_code_review/parallel_code_review.spl \
    cookbook/64_parallel_news_digest/parallel_news_digest.spl; do
    for lang in go ts python/langgraph; do
        echo "--- $(basename $recipe) → $lang ---"
        splc "$recipe" --lang "$lang" \
            --out-dir /tmp/splc-multi/$(basename ${recipe%.spl})/$lang \
            --overwrite 2>&1 | tail -1
    done
done
```

**Expected:** Each run prints `splc done: ... → ...` with no errors.

---

## Test Matrix

| Test | LLM required | Ollama required | Est. time |
|------|-------------|-----------------|-----------|
| 1 — Dry run (all targets) | No | No | ~3s |
| 2a — Deterministic Go | No | No (compile only) | ~2s |
| 2b — Deterministic TypeScript | No | No (compile only) | ~2s |
| 2c — Deterministic LangGraph | No | No (compile only) | ~2s |
| 3 — LLM Go | Yes (Claude) | No | ~30s |
| 4 — LLM LangGraph | Yes (Claude) | No | ~30s |
| 5 — NDD Closure | No (echo) + Ollama | Yes (run) | ~5 min |
| 6 — Overwrite guard | No | No | ~2s |
| 7 — Manifest | No | No | ~1s |
| 8 — Multi-recipe smoke | No | No | ~10s |

**Recommended order:** Run Tests 1, 2a–2c, 6, 7, 8 first — no dependencies beyond
the `spl3` conda environment. Add Tests 3 and 4 when a Claude session is
active. Test 5 is the integration milestone.
