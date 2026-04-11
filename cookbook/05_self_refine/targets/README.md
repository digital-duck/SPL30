# Self-Refine — Target Implementations

This directory contains four runtime implementations of
`cookbook/05_self_refine/self_refine.spl`, each faithfully reproducing the SPL
workflow in a different target language or AI framework.

```
targets/
├── go/
│   ├── self_refine.go          ← Go (Ollama REST, no external deps)
│   └── go.mod
└── python/
    ├── autogen/
    │   └── self_refine_autogen.py
    ├── crewai/
    │   └── self_refine_crewai.py
    └── langgraph/
        └── self_refine_langgraph.py
```

---

## Prerequisites — all targets

### Ollama

All targets call local Ollama models. Ollama must be running before any target
is invoked.

```bash
ollama serve                      # start if not already running
curl -s http://localhost:11434/api/tags   # verify
```

Pull the default models (SPL defaults: `llama3.2` for both writer and critic):

```bash
ollama pull llama3.2
```

Pull `gemma3` if you want to experiment with a separate writer model:

```bash
ollama pull gemma3
```

---

## SPL baseline

All targets must produce equivalent behaviour to:

```bash
# From the SPL30/ root
spl3 run cookbook/05_self_refine/self_refine.spl \
    task="What are the benefits of meditation?"
```

SPL defaults (the canonical reference values):

| Parameter | Default |
|-----------|---------|
| `task` | `What are the benefits of meditation?` |
| `max_iterations` | `3` |
| `writer_model` | `llama3.2` |
| `critic_model` | `llama3.2` |
| `log_dir` | `cookbook/05_self_refine/logs-spl` |

---

## Go target

### Setup

Go 1.22+ required. No external dependencies — uses only the standard library.

```bash
cd cookbook/05_self_refine/targets/go
go build -o self_refine           # optional: compile to binary
```

### Run

```bash
# From cookbook/05_self_refine/targets/go/
go run self_refine.go \
    --task "What are the benefits of meditation?"

# All options (matching SPL defaults)
go run self_refine.go \
    --task "What are the benefits of meditation?" \
    --max-iterations 3 \
    --writer-model llama3.2 \
    --critic-model llama3.2 \
    --log-dir logs-go \
    --ollama-host http://localhost:11434
```

### Expected console output

```
2006/01/02 15:04:05 Self-refine started | max_iterations=3 for task:
What are the benefits of meditation?
2006/01/02 15:04:05 Generating initial draft ...
2006/01/02 15:04:12 Initial draft ready
2006/01/02 15:04:12 Iteration 0 | critiquing ...
2006/01/02 15:04:18 Iteration 0 | refining ...
2006/01/02 15:04:25 Refined | iteration=1
2006/01/02 15:04:25 Iteration 1 | critiquing ...
2006/01/02 15:04:30 Approved at iteration 1
2006/01/02 15:04:30 Done | status=complete  iterations=1  elapsed=25.1s
============================================================
<final article text>
```

### Log files

```
logs-go/
├── draft_0.md          ← initial draft
├── feedback_0.md       ← first critique
├── draft_1.md          ← refined draft (written before next critique)
└── final.md            ← committed output (copy of last approved draft)
```

---

## AutoGen target

### Setup

```bash
conda create -n autogen python=3.11 -y
conda activate autogen
pip install pyautogen
```

> AutoGen uses Ollama's OpenAI-compatible endpoint at
> `http://localhost:11434/v1`. No real API key is required; `"ollama"` is used
> as a placeholder.

### Run

```bash
# From the SPL30/ root
conda activate autogen
python cookbook/05_self_refine/targets/python/autogen/self_refine_autogen.py \
    --task "What are the benefits of meditation?"

# All options (matching SPL defaults)
python cookbook/05_self_refine/targets/python/autogen/self_refine_autogen.py \
    --task "What are the benefits of meditation?" \
    --max-iterations 3 \
    --writer-model llama3.2 \
    --critic-model llama3.2 \
    --log-dir cookbook/05_self_refine/logs-autogen
```

### Expected console output

```
Writer (to Critic):
<initial article>
----
Critic (to Writer):
1. ...
2. ...
----
Writer (to Critic):
<refined article>
----
Critic (to Writer):
[APPROVED]
----
Done | iterations=1
============================================================
<final article text>
```

### Log files

```
cookbook/05_self_refine/logs-autogen/
├── draft_0.md          ← initial draft (first Writer message)
├── feedback_0.md       ← first critique (first Critic message)
├── draft_1.md          ← refined draft (second Writer message, if any)
└── final.md            ← last Writer message before termination
```

---

## CrewAI target

### Setup

```bash
conda create -n crewai python=3.11 -y
conda activate crewai
pip install crewai
```

> CrewAI uses the `"ollama/<model>"` prefix to route to the local Ollama
> server. No `langchain-ollama` package is needed.

### Run

```bash
# From the SPL30/ root
conda activate crewai
python cookbook/05_self_refine/targets/python/crewai/self_refine_crewai.py \
    --task "What are the benefits of meditation?"

# All options (matching SPL defaults)
python cookbook/05_self_refine/targets/python/crewai/self_refine_crewai.py \
    --task "What are the benefits of meditation?" \
    --max-iterations 3 \
    --writer-model llama3.2 \
    --critic-model llama3.2 \
    --log-dir cookbook/05_self_refine/logs-crewai
```

### Expected console output

```
Generating initial draft ...
Initial draft ready

Iteration 0 | critiquing ...
Iteration 0 | refining ...
Refined | iteration=1

Iteration 1 | critiquing ...
Approved at iteration 1
============================================================
<final article text>
```

If the loop exhausts max iterations without approval:

```
...
Max iterations reached | iterations=3
============================================================
<best-effort article text>
```

### Log files

```
cookbook/05_self_refine/logs-crewai/
├── draft_0.md          ← initial draft
├── feedback_0.md       ← first critique
├── draft_1.md          ← refined draft (written per iteration)
└── final.md            ← committed output
```

---

## LangGraph target

### Setup

```bash
conda create -n langgraph python=3.11 -y
conda activate langgraph
pip install langgraph langchain-ollama
```

### Run

```bash
# From the SPL30/ root
conda activate langgraph
python cookbook/05_self_refine/targets/python/langgraph/self_refine_langgraph.py \
    --task "What are the benefits of meditation?"

# All options (matching SPL defaults)
python cookbook/05_self_refine/targets/python/langgraph/self_refine_langgraph.py \
    --task "What are the benefits of meditation?" \
    --max-iterations 3 \
    --writer-model llama3.2 \
    --critic-model llama3.2 \
    --log-dir cookbook/05_self_refine/logs-langgraph
```

### Expected console output

```
Generating initial draft ...
Initial draft ready

Iteration 0 | critiquing ...
Iteration 1 | refining ...
Refined | iteration=1

Iteration 1 | critiquing ...
Committed | status=complete  iterations=1
============================================================
<final article text>
```

If the loop exhausts max iterations:

```
...
Max iterations reached | iterations=3
Committed | status=max_iterations  iterations=3
============================================================
<best-effort article text>
```

### Log files

```
cookbook/05_self_refine/logs-langgraph/
├── draft_0.md          ← initial draft (node_draft)
├── feedback_0.md       ← first critique (node_critique, iteration 0)
├── draft_1.md          ← refined draft (node_refine, iteration 1)
└── final.md            ← committed output (node_commit)
```

---

## Verifying faithfulness to SPL

Run the SPL baseline and any target with the same task and parameters, then
compare the log artefacts and console behaviour against these invariants.

### Behavioural invariants

| Invariant | How to check |
|-----------|-------------|
| Approval token is `[APPROVED]` — not `satisfactory` | `grep '\[APPROVED\]' logs-*/feedback_*.md` |
| `draft_0.md` always written before any critique | file exists after first LLM call |
| `feedback_N.md` index matches the iteration that produced it | filenames are `feedback_0`, `feedback_1`, … |
| `draft_N.md` written **after** refinement, so N > 0 | `draft_1.md` appears only after a refine step |
| `final.md` is written on both approval and max-iterations exit | file always present after run |
| Loop stops at or before `max_iterations` | count `draft_*.md` files ≤ `max_iterations + 1` |
| Writer model used for draft + refine, critic model for critique | check `--writer-model` / `--critic-model` flags |

### Quick smoke test (all targets, same task)

```bash
TASK="What are the benefits of meditation?"

# SPL baseline
spl3 run cookbook/05_self_refine/self_refine.spl task="$TASK"

# Go
(cd cookbook/05_self_refine/targets/go && \
  go run self_refine.go --task "$TASK" --log-dir ../../logs-go)

# AutoGen
conda run -n autogen \
  python cookbook/05_self_refine/targets/python/autogen/self_refine_autogen.py \
    --task "$TASK" --log-dir cookbook/05_self_refine/logs-autogen

# CrewAI
conda run -n crewai \
  python cookbook/05_self_refine/targets/python/crewai/self_refine_crewai.py \
    --task "$TASK" --log-dir cookbook/05_self_refine/logs-crewai

# LangGraph
conda run -n langgraph \
  python cookbook/05_self_refine/targets/python/langgraph/self_refine_langgraph.py \
    --task "$TASK" --log-dir cookbook/05_self_refine/logs-langgraph
```

After each run, verify:

```bash
# All runs should produce a final.md
ls cookbook/05_self_refine/logs-*/final.md
ls cookbook/05_self_refine/targets/go/logs-go/final.md

# Feedback files should contain [APPROVED] on the terminating iteration
grep -l '\[APPROVED\]' cookbook/05_self_refine/logs-*/feedback_*.md

# Draft count should be <= max_iterations + 1 (default: <= 4)
ls cookbook/05_self_refine/logs-*/draft_*.md | wc -l
```

### Prompt fidelity checklist

Each target must use the exact prompt text from the SPL function bodies:

| SPL function | Key phrases to verify in source |
|---|---|
| `draft` | "professional writer", "comprehensive article", "no preamble, no notes after" |
| `critique` | "professional editor", "meta-commentary or questions … ignore those", ends with `IMPROVEMENTS:\n1.` |
| `refined` | "seasoned writer", "Stay true to the original topic:", triple-backtick fencing for draft and feedback |

---

## Cross-target comparison

| | SPL | Go | AutoGen | CrewAI | LangGraph |
|---|---|---|---|---|---|
| **Runtime** | spl3 | Go 1.22+ binary | Python 3.11 + pyautogen | Python 3.11 + crewai | Python 3.11 + langgraph |
| **Ollama API** | native adapter | REST `/api/generate` | OpenAI-compat `/v1` | `ollama/<model>` prefix | `ChatOllama` |
| **Loop construct** | `WHILE` | `for` loop | `max_turns` (implicit) | explicit `for` | graph cycle |
| **Approval check** | `EVALUATE WHEN contains('[APPROVED]')` | `strings.Contains` | `is_termination_msg` | `if "[APPROVED]" in` | conditional edge |
| **Separate writer/critic models** | yes | yes | yes | yes | yes |
| **Default max_iterations** | 3 | 3 | 3 | 3 | 3 |
| **External deps** | none | none | pyautogen | crewai | langgraph, langchain-ollama |
| **Log dir default** | `logs-spl` | `logs-go` | `logs-autogen` | `logs-crewai` | `logs-langgraph` |
