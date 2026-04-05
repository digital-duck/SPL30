# Self-Refine — AutoGen Edition

Implements the same `self_refine.spl` pattern using AutoGen (pyautogen):
a `Writer` and `Critic` `ConversableAgent` alternate turns.
The Critic's `is_termination_msg` mirrors SPL's `EVALUATE ... WHEN 'satisfactory'`.

## Setup

```bash
conda create -n autogen python=3.11 -y
conda activate autogen
pip install pyautogen
```

Requires Ollama running locally with OpenAI-compatible endpoint:
```bash
ollama serve
ollama pull gemma3   # or any model you prefer
```

> AutoGen uses the OpenAI-compatible endpoint Ollama exposes at
> `http://localhost:11434/v1` — no API key needed (uses `"ollama"` as placeholder).

## Run

```bash
# From SPL20/ root
python cookbook/05_self_refine/autogen/self_refine_autogen.py \
    --task "Write a haiku about coding"

# Custom model and iteration limit
python cookbook/05_self_refine/autogen/self_refine_autogen.py \
    --task "Explain recursion in one paragraph" \
    --max-iterations 3 \
    --model llama3.2 \
    --log-dir cookbook/05_self_refine/autogen/logs
```

## Validate

Expected console output pattern:
```
Writer (to Critic):
<initial draft>
Critic (to Writer):
<feedback or 'satisfactory'>
Writer (to Critic):
<refined draft>    ← 0–N times
...
Done | iterations=1
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
| `self_refine_autogen.py` | ~65 |

Extra lines come from: explicit agent configuration dicts, `llm_config` wiring,
chat history post-processing to extract drafts/feedback, and `argparse` boilerplate.
Note: AutoGen's loop control (`max_turns`) is less expressive than SPL's
`WHILE` + `EVALUATE` — the termination condition is baked into the Critic agent
rather than being a first-class workflow construct.
