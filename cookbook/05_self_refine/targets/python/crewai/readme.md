# Self-Refine — CrewAI Edition

Implements the same `self_refine.spl` pattern using CrewAI:
a `Writer` and `Critic` Agent with a manual Python loop —
CrewAI has no native loop or conditional construct, so SPL's
`WHILE` + `EVALUATE ... WHEN 'satisfactory'` must be written
explicitly in Python.

## Setup

```bash
conda create -n crewai python=3.11 -y
conda activate crewai
pip install crewai langchain-ollama
```

Requires Ollama running locally:
```bash
ollama serve
ollama pull gemma3   # or any model you prefer
```

## Run

```bash
# From SPL20/ root
python cookbook/05_self_refine/crewai/self_refine_crewai.py \
    --task "Write a haiku about coding"

# Custom model and iteration limit
python cookbook/05_self_refine/crewai/self_refine_crewai.py \
    --task "Explain recursion in one paragraph" \
    --max-iterations 3 \
    --model llama3.2 \
    --log-dir cookbook/05_self_refine/crewai/logs
```

## Validate

Expected console output pattern:
```
Generating initial draft ...
Iteration 0 | critiquing ...
Iteration 0 | refining ...      ← appears 0–N times
Iteration 1 | critiquing ...
Satisfactory at iteration 1     ← or: Max iterations reached
============================================================
<final output text>
```

Check log files written to `--log-dir`:
```
logs/draft_0.md       ← initial draft
logs/feedback_0.md    ← first critique
logs/draft_1.md       ← refined draft  (if needed)
logs/final.md         ← committed output
```

## SPL equivalent

```bash
spl run cookbook/05_self_refine/self_refine.spl \
    --adapter ollama -m gemma3 \
    task="Write a haiku about coding"
```

## LOC comparison

| File | LOC (non-blank, non-comment) |
|------|------------------------------|
| `self_refine.spl` | ~35 |
| `self_refine_crewai.py` | ~75 |

Extra lines come from: Agent/Task/Crew object construction per iteration
(CrewAI requires a new `Task` and `Crew` instance for each LLM call),
explicit Python `for` loop replacing SPL's `WHILE`, explicit `if` replacing
SPL's `EVALUATE`, and `argparse` boilerplate. The absence of native loop/
conditional constructs in CrewAI is the primary driver of extra LOC.
