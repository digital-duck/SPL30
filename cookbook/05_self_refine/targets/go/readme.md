# Self-Refine — Go Edition (`splc --target go`)

This is the **physical view** of `self_refine.spl` compiled for the Go target.

`splc` translates the SPL logical view (`.spl` script) into a standalone Go binary
that calls the Ollama REST API directly — no Python runtime, no AI framework.

## Setup

Go 1.22+ required (standard library only — no external dependencies).

```bash
# Verify Ollama is running
curl -s http://localhost:11434/api/tags | grep -o '"name":"[^"]*"' | head -5

# Pull models if needed
ollama pull gemma3
ollama pull llama3.2
```

## Run

```bash
# From this directory
go run self_refine.go --task "Write a haiku about coding"

# Custom models and iteration limit
go run self_refine.go \
    --task "Explain recursion in one paragraph" \
    --max-iterations 3 \
    --writer-model gemma3 \
    --critic-model llama3.2 \
    --log-dir /tmp/self_refine_logs

# Compile to a binary (DODA: runs on any Linux/macOS/Windows with Ollama)
go build -o self_refine
./self_refine --task "Write a haiku about coding"
```

## SPL equivalent

```bash
spl run cookbook/05_self_refine/self_refine.spl \
    --adapter ollama \
    task="Write a haiku about coding"
```

## Expected output pattern

```
Self-refine started | max_iterations=5 for task: ...
Generating initial draft ...
Initial draft ready
Iteration 0 | critiquing ...
Iteration 0 | refining ...
Iteration 1 | critiquing ...
Approved at iteration 1
Done | status=complete  iterations=1  elapsed=12.3s
============================================================
<final output>
```

Log files written to `--log-dir`:
```
logs-go/draft_0.md        ← initial draft
logs-go/feedback_0.md     ← first critique
logs-go/draft_1.md        ← refined draft (if needed)
logs-go/final.md          ← committed output
```

## SPL → Go mapping

| SPL construct | Go equivalent |
|---|---|
| `WORKFLOW self_refine INPUT/OUTPUT` | `func selfRefine(...)` + CLI flags |
| `CREATE FUNCTION ... AS $$ ... $$` | `const draftPrompt = \`...\`` |
| `GENERATE f(@args) USING MODEL @m INTO @v` | `generate(host, model, fmt.Sprintf(prompt, args))` |
| `WHILE @iteration < @max DO` | `for iteration < maxIter {` |
| `EVALUATE @feedback WHEN contains('[APPROVED]')` | `strings.Contains(feedback, "[APPROVED]")` |
| `CALL write_file(@path, @content) INTO NONE` | `writeFile(path, content)` |
| `LOGGING 'msg' LEVEL INFO` | `log.Printf(...)` |
| `RETURN @current WITH status = 'complete'` | `return current, "complete", iteration, nil` |
| `EXCEPTION WHEN MaxIterationsReached` | loop exits, `status = "max_iterations"` |

## LOC comparison

| File | LOC (non-blank, non-comment) |
|---|---|
| `self_refine.spl` | ~35 |
| `self_refine_langgraph.py` | ~80 |
| `self_refine_crewai.py` | ~85 |
| `self_refine_autogen.py` | ~75 |
| `self_refine.go` | ~100 |

Go is slightly more verbose than Python frameworks due to explicit error handling,
but produces a single statically-linked binary with zero runtime dependencies —
ideal for DODA deployment on Intel Mini-PC or Ubuntu Snap targets.

## DODA notes

This file is the output of `splc --target go`. The source `.spl` is unchanged.
To deploy to a different hardware target, re-run `splc` with a different flag:

```bash
splc --target go     self_refine.spl   # this file
splc --target snap   self_refine.spl   # Ubuntu 26.04 Inference Snap
splc --target swift  self_refine.spl   # Apple M4/M5 Metal
```

The `.spl` file is the invariant. Only the compiled output changes.
