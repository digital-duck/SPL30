# Recipe 05 — Self-Refine

**Pattern:** Draft → Critique → Refine (loop until satisfactory)

The self-refine pattern is one of the most powerful agentic techniques: an LLM generates
a draft, a critic evaluates it, and the writer improves it — repeating until the critic
is satisfied or a maximum iteration count is reached.

In SPL, the entire pattern fits in ~50 lines of declarative code with no Python required.

---

## The SPL Program

```sql
CREATE FUNCTION draft(task TEXT) RETURNS TEXT AS $$ ... $$;
CREATE FUNCTION critique(current TEXT) RETURNS TEXT AS $$ ... $$;
CREATE FUNCTION refined(current TEXT, feedback TEXT) RETURNS TEXT AS $$ ... $$;

WORKFLOW self_refine
  INPUT:
    @task          TEXT    DEFAULT 'What are the benefits of meditation?',
    @output_budget INTEGER DEFAULT 2000,
    @max_iterations INTEGER DEFAULT 5,
    @writer_model  TEXT    DEFAULT 'gemma3',
    @critic_model  TEXT    DEFAULT 'llama3.2',
    @log_dir       TEXT    DEFAULT 'cookbook/05_self_refine/logs'
  OUTPUT: @result TEXT
DO
  GENERATE draft(@task)   USING MODEL @writer_model INTO @current
  WHILE @iteration < @max_iterations DO
    GENERATE critique(@current) USING MODEL @critic_model INTO @feedback
    EVALUATE @feedback
      WHEN contains('satisfactory') THEN
        COMMIT @current WITH status = 'complete', iterations = @iteration
      ELSE
        GENERATE refined(@current, @feedback) USING MODEL @writer_model INTO @current
        @iteration := @iteration + 1
    END
  END
  COMMIT @current WITH status = 'max_iterations', iterations = @iteration
END
```

Key SPL features at work:
- `USING MODEL @writer_model` — per-step model selection, resolved at runtime from INPUT params
- `WHILE / EVALUATE / WHEN contains(...)` — deterministic loop control, no LLM judge overhead
- `CALL write_file(...)` — artifact logging at every step, built-in
- `EXCEPTION WHEN` — graceful handling of budget or iteration overruns

---

## Running It

### Ollama (local, free)

```bash
spl run cookbook/05_self_refine/self_refine.spl \
    --adapter ollama \
    task="Write an executive summary of the benefits of SPL" \
    max_iterations=3 \
    output_budget=2000 \
    writer_model=gemma3 \
    critic_model=llama3.2 \
    log_dir=cookbook/05_self_refine/logs-spl
```

### Claude (claude_cli adapter — uses Claude Code subscription)

```bash
spl run cookbook/05_self_refine/self_refine.spl \
    --adapter claude_cli \
    task="Who is Srinivasa Ramanujan" \
    max_iterations=3 \
    output_budget=3000 \
    writer_model=claude-sonnet-4-6 \
    critic_model=claude-sonnet-4-6 \
    log_dir=cookbook/05_self_refine/logs-ramanujan
```

### OpenAI

> **Note:** If `OPENAI_BASE_URL` is set in your environment (e.g. pointing to OpenRouter),
> the SPL openai adapter ignores it and always calls `https://api.openai.com/v1` directly.
> Requires a real OpenAI API key in `OPENAI_API_KEY`.

```bash
export OPENAI_API_KEY=sk-...
spl run cookbook/05_self_refine/self_refine.spl \
    --adapter openai \
    task="How does Transformer work in deep learning" \
    max_iterations=3 \
    output_budget=2000 \
    writer_model=gpt-4o \
    critic_model=gpt-4o-mini \
    log_dir=cookbook/05_self_refine/logs-openai
```

### Anthropic API

> **Note:** Requires a valid `ANTHROPIC_API_KEY` (not the same as OpenRouter key).
> Model names use Anthropic's format (e.g. `claude-sonnet-4-5-20250929`).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
spl run cookbook/05_self_refine/self_refine.spl \
    --adapter anthropic \
    task="How does Transformer work in deep learning" \
    max_iterations=3 \
    output_budget=2000 \
    writer_model=claude-sonnet-4-5-20250929 \
    critic_model=claude-haiku-4-5-20251001 \
    log_dir=cookbook/05_self_refine/logs-anthropic
```

### OpenRouter

> **Note:** Model names use `provider/model` dot notation (e.g. `anthropic/claude-sonnet-4.6`).
> Run `spl adapters` or check https://openrouter.ai/models for available model IDs.

```bash
export OPENROUTER_API_KEY=sk-or-...
spl run cookbook/05_self_refine/self_refine.spl \
    --adapter openrouter \
    task="How does Transformer work in deep learning" \
    max_iterations=3 \
    output_budget=2000 \
    writer_model=anthropic/claude-sonnet-4.6 \
    critic_model=anthropic/claude-haiku-4.5 \
    log_dir=cookbook/05_self_refine/logs-openrouter
```

### Global model override (all GENERATE calls use the same model)

```bash
spl run cookbook/05_self_refine/self_refine.spl \
    --adapter ollama -m gemma3 \
    task="Explain recursion" \
    log_dir=cookbook/05_self_refine/logs-gemma3
```

---

## Model Flexibility

`@writer_model` and `@critic_model` are first-class workflow inputs — you can mix and
match models across adapters, tiers, and roles from the CLI with no code changes:

| Strategy | writer_model | critic_model |
|---|---|---|
| Same model (simplest) | `claude-sonnet-4-6` | `claude-sonnet-4-6` |
| Powerful writer, cheap critic | `claude-opus-4-6` | `claude-haiku-4-5` |
| Cheap writer, strict critic | `gpt-4o-mini` | `gpt-4o` |
| Local writer, cloud critic | `gemma3` (ollama) | n/a — pick one adapter |

> **Note:** `writer_model` and `critic_model` must be valid model names for the chosen
> adapter. The `--model` / `-m` CLI flag overrides both when set.

---

## What the Logs Show

Each run writes intermediate artifacts to `@log_dir`:

```
logs/
  draft_0.md          ← initial draft
  feedback_0.md       ← critic's first review
  draft_1.md          ← refined draft (if needed)
  feedback_1.md       ← critic's second review (if needed)
  ...
  final.md            ← committed output
```

---

## Observed Results

| Run | Adapter | Models | Iterations | Notes |
|---|---|---|---|---|
| SPL executive summary | ollama | gemma3 / llama3.2 | 3 | Draft grew 3,857 → 5,113 bytes |
| Meditation benefits | ollama | gemma3 / llama3.2 | 3 | Draft grew 4,985 → 6,761 bytes |
| Ramanujan | claude_cli | sonnet-4-6 / sonnet-4-6 | **0** | First draft accepted immediately |
| Transformer (deep learning) | openrouter | claude-sonnet-4.6 / claude-haiku-4.5 | **0** (false positive) | haiku critique contained "satisfactory" in prose; triggered early exit |

Claude's first draft on "Who is Srinivasa Ramanujan" was comprehensive enough that
a claude-sonnet-4-6 critic returned `satisfactory` with zero refinement — a striking
demonstration of the quality difference between frontier and local models, achieved
by changing two CLI parameters.

The OpenRouter run exposed a robustness issue: `contains('satisfactory')` matched the
phrase "prevent it from being satisfactory" in haiku's critique prose, committing the
unrefined draft. Fix: changed the approval signal to `[APPROVED]` — bracket notation
that never appears in narrative feedback. Updated in `self_refine.spl`.

---

## Adapter Support Status

| Adapter | Status | Notes |
|---|---|---|
| `ollama` | ✅ Ready | Local models via Ollama |
| `claude_cli` | ✅ Ready | Claude Code subscription (zero marginal cost) |
| `openai` | ✅ Ready | Requires `OPENAI_API_KEY` |
| `anthropic` | ✅ Ready | Requires `ANTHROPIC_API_KEY` |
| `openrouter` | ✅ Ready | Requires `OPENROUTER_API_KEY` |
| `google` | ✅ Ready | Requires `GOOGLE_API_KEY` |
| `bedrock` | ✅ Ready | Requires AWS credentials |
| `vertex` | ✅ Ready | Requires GCP credentials |
