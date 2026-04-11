# Recipe 05: Self-Refine

**Category:** agentic / iterative refinement  
**SPL version:** 3.0  
**Type:** TEXT → TEXT  
**LLM required:** Yes — gemma3 (writer) + llama3.2 (critic) via Ollama  
**Demonstrates:** First `CALL` sub-workflow in SPL30 cookbook, `WHILE` refinement loop, `EVALUATE contains()`, `[APPROVED]` sentinel pattern

---

## What it does

Iteratively improves a text response through a draft–critique–refine loop,
using two separate LLMs in different roles.

```
[task prompt]
      │
      ▼  gemma3 (writer)
[initial draft]
      │
      ┌─────────────────────────────────────────┐
      │  WHILE @iteration < @max_iterations      │
      │                                          │
      │  ▼  llama3.2 (critic)                   │
      │  [feedback or [APPROVED]]                │
      │                                          │
      │  if [APPROVED] → EXIT LOOP               │
      │  else                                    │
      │  ▼  gemma3 (writer)                     │
      │  [refined draft]                         │
      └─────────────────────────────────────────┘
      │
      ▼  RETURN @current WITH status = 'complete'
```

The critic outputs the exact token `[APPROVED]` when the content needs no
further improvement. The `EVALUATE contains('[APPROVED]')` check in the
orchestrator exits the loop early — often at iteration 1 or 2 for
well-specified tasks.

### SPL 3.0 significance

This is the **first recipe in the SPL30 cookbook to use `CALL` sub-workflow
dispatch**. The `critique_workflow` is a self-contained `WORKFLOW` registered
in the Hub and called via:

```sql
CALL critique_workflow(@current, @output_budget, @critic_model) INTO @feedback
```

This demonstrates that sub-workflow composition works end-to-end in the SPL
runtime — a foundational capability for the `code_pipeline` recipe (56) and
the NDD closure architecture.

---

## Files

| File | Role |
|------|------|
| `self_refine.spl` | SPL orchestrator + `critique_workflow` sub-workflow |
| `run.py` | Physical runner — Ollama adapter |
| `sample/` | (no sample input required) |
| `logs-spl/` | Draft, feedback, and final output written here |

---

## Prerequisites

```bash
ollama serve
ollama pull gemma3           # writer model
ollama pull llama3.2         # critic model
ollama list                  # verify both are present
```

---

## Running

```bash
cd ~/projects/digital-duck/SPL30

pip install -e ~/projects/digital-duck/SPL20
pip install -e ~/projects/digital-duck/SPL30

pip show spl-llm
# Version: 2.0.0
pip show spl
# Version: 3.0.0a0

which spl
# /home/gong-mini/anaconda3/envs/spl3/bin/spl
which spl3
# /home/gong-mini/anaconda3/envs/spl3/bin/spl3

# Default task — benefits of meditation, 5 iterations max
spl3 run cookbook/05_self_refine/self_refine.spl \
    --adapter ollama \
    --param task="What are the benefits of meditation?" \
    --param writer_model="gemma3" \
    --param critic_model="gemma3"
# see `logs-spl-01` where critic_model="llama3.2"
# see `logs-spl-gemma3` where critic_model="gemma3" , flawed

spl3 run cookbook/05_self_refine/self_refine.spl \
    --adapter ollama \
    --param writer_model="gemma4:e2b" \
    --param critic_model="gemma4:e2b" \
    --param log_dir="cookbook/05_self_refine/logs-spl-gemma4-e2b" 

spl3 run cookbook/05_self_refine/self_refine.spl \
    --adapter ollama \
    --param writer_model="gemma4:e4b" \
    --param critic_model="gemma4:e4b" \
    --param log_dir="cookbook/05_self_refine/logs-spl-gemma4-e4b" 

spl3 run cookbook/05_self_refine/self_refine.spl \
    --adapter claude_cli \
    --param writer_model="claude-sonnet-4-6" \
    --param critic_model="claude-sonnet-4-6" \
    --log-prompts "cookbook/05_self_refine/logs-spl-claude_cli-sonnet" \
    --param log_dir="cookbook/05_self_refine/logs-spl-claude_cli-sonnet" 

export LOG_DIR="cookbook/05_self_refine/logs-spl-claude_cli-sonnet-2"
mkdir -p "$LOG_DIR"
spl3 run cookbook/05_self_refine/self_refine.spl \
    --adapter claude_cli \
    --param writer_model="claude-sonnet-4-6" \
    --param critic_model="claude-sonnet-4-6" \
    --log-prompts "$LOG_DIR" \
    --param log_dir="$LOG_DIR" \
    2>&1 | tee "$LOG_DIR/run-$(date +%Y%m%d-%H%M%S).log"


# Custom task
spl run cookbook/05_self_refine/self_refine.spl \
    --param task="Explain the NDD closure principle in plain language"

# Fewer iterations
spl run cookbook/05_self_refine/self_refine.spl \
    --param task="What is DODA?" \
    --param max_iterations=3

# Same model for writer and critic (single-model self-critique)
spl run cookbook/05_self_refine/self_refine.spl \
    --param task="Write a haiku about distributed computing" \
    --param writer_model=gemma3 \
    --param critic_model=gemma3

# Larger output budget
spl run cookbook/05_self_refine/self_refine.spl \
    --param task="Explain quantum entanglement for a general audience" \
    --param output_budget=3000 \
    --param max_iterations=4

# Custom log directory
spl run cookbook/05_self_refine/self_refine.spl \
    --param task="Summarise the benefits of SPL 3.0" \
    --param log_dir=/tmp/self_refine_logs
```

---

## Testing — LangGraph Edition

A Python/LangGraph implementation of the same self-refine pattern lives at
`targets/python/langgraph/`. It maps directly to `self_refine.spl`:
`draft → critique → refine → commit` nodes with a conditional edge that
mirrors SPL's `EVALUATE ... WHEN 'satisfactory'`.

### Setup

```bash
cd ~/projects/digital-duck/SPL30

conda create -n langgraph python=3.11 -y
conda activate langgraph
pip install langgraph langchain-ollama click
```

### Single run

```bash
python cookbook/05_self_refine/targets/python/langgraph/self_refine_langgraph.py \
    --task "What are the benefits of meditation?" \
    --max-iterations 3 \
    --writer-model llama3.2 \
    --critic-model llama3.2 \
    --log-dir cookbook/05_self_refine/targets/python/langgraph/logs
```

### Benchmark across models

```bash
bash cookbook/05_self_refine/benchmark-langgraph.sh
```

Runs `gemma3`, `gemma4:e2b`, and `gemma4:e4b` sequentially. Logs are written
to per-model directories alongside the script:

```
targets/python/langgraph/logs-gemma3/
targets/python/langgraph/logs-gemma4_e2b/
targets/python/langgraph/logs-gemma4_e4b/
```

Each directory contains `draft_0.md`, `feedback_0.md`, `draft_N.md`, and
`final.md` — same schema as the SPL log output.

### LOC comparison

| File | LOC (non-blank, non-comment) |
|------|------------------------------|
| `self_refine.spl` | 117 |
| `self_refine_langgraph.py` | 168 |

Extra lines in the Python version come from explicit `TypedDict` state
definition, node functions, graph wiring (`add_node` / `add_edge`), and
`argparse` boilerplate that `spl run` handles automatically.

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@task` | TEXT | `What are the benefits of meditation?` | The writing task for the LLM |
| `@output_budget` | INTEGER | `2000` | Max output tokens per GENERATE call |
| `@max_iterations` | INTEGER | `5` | Maximum critique–refine cycles |
| `@writer_model` | TEXT | `gemma3` | Ollama model for drafting and refining |
| `@critic_model` | TEXT | `llama3.2` | Ollama model for critique |
| `@log_dir` | TEXT | `cookbook/05_self_refine/logs-spl` | Directory for log files |

---

## Output

`@result TEXT` — the final approved (or best-effort) response.

**Log files written to `@log_dir`:**

| File | Contents |
|------|----------|
| `draft_0.md` | Initial draft before any critique |
| `feedback_<n>.md` | Critic feedback at each iteration |
| `draft_<n>.md` | Refined draft after each round of feedback |
| `final.md` | The approved final output |

---

## Return status values

| Status | Meaning |
|--------|---------|
| `complete` | Critic approved before `@max_iterations` reached |
| `max_iterations` | Loop exhausted; returning best-effort result |
| `partial` | `MaxIterationsReached` exception caught |
| `budget_limit` | `BudgetExceeded` exception caught |

---

## Error handling

| Exception | Cause | Behaviour |
|-----------|-------|-----------|
| `MaxIterationsReached` | Loop hit `@max_iterations` without `[APPROVED]` | Returns current best draft with `status = 'partial'` |
| `BudgetExceeded` | Token budget exceeded mid-generation | Returns current draft with `status = 'budget_limit'` |
