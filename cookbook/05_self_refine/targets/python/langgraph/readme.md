# Self-Refine — LangGraph Edition

Implements the same `self_refine.spl` pattern using LangGraph:
a state graph with four nodes (`draft → critique → refine → commit`)
and a conditional edge that mirrors SPL's `EVALUATE ... WHEN 'satisfactory'`.

## Setup

```bash
conda create -n langgraph python=3.11 -y
conda activate langgraph
pip install langgraph langchain-ollama
```

Requires Ollama running locally:
```bash
ollama serve
ollama pull gemma3   # or any model you prefer
```

## Run

```bash
# From SPL20/ root
python cookbook/05_self_refine/langgraph/self_refine_langgraph.py \
    --task "Write a haiku about coding"

# Custom model and iteration limit
python cookbook/05_self_refine/langgraph/self_refine_langgraph.py \
    --task "Explain recursion in one paragraph" \
    --max-iterations 3 \
    --model llama3.2 \
    --log-dir cookbook/05_self_refine/langgraph/logs
```

## Validate

Expected console output pattern:
```
Generating initial draft ...
Iteration 0 | critiquing ...
Iteration 1 | refining ...      ← appears 0–N times
Iteration 1 | critiquing ...
Committed | status=complete  iterations=1
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
| `self_refine_langgraph.py` | ~80 |

Extra lines come from: explicit `TypedDict` state definition, node functions,
graph wiring (`add_node` / `add_edge`), and the `argparse` boilerplate that
`spl run` handles automatically.
