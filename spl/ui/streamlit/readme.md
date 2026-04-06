# text2SPL Knowledge Studio

A multi-page Streamlit app for compiling natural language descriptions into
SPL 2.0 scripts, running them interactively, and accumulating a knowledge
base of (description → SPL → execution) triples that can be used to
self-improve the text2SPL compiler over time.

## How to run

```bash
# From the repo root
streamlit run spl/ui/streamlit/SPL_UI.py
```

## Directory structure

```
streamlit/
  SPL_UI.py                   # Landing page — summary metrics (4 counters)
  db.py                     # Shared SQLite layer (schema, import/export)
  code_rag_bridge.py        # Thin wrapper around spl.code_rag.CodeRAGStore
  pages/
    1_Text_to_SPL.py        # Compiler + runner + Code-RAG context expander
    2_Review.py             # Knowledge base browser + import/export
    3_Code_RAG.py           # Code-RAG management: query, push, seed, export
  data/
    knowledge.db            # SQLite knowledge base (created on first run)
    scripts/                # Generated .spl files (named: {name}_v{n}_*.spl)
  readme.md                 # This file
```

The `.sh` script (`../text2spl_demo.sh`) is preserved for batch/CI use.

---

## Pages

### 3 · Code-RAG

Manages the ChromaDB vector store that the text2SPL compiler uses for
few-shot example retrieval.

- **Status metrics** — pair count, knowledge.db script count, coverage ratio
- **Seed from Cookbook** — indexes all 37 cookbook recipes as initial examples
- **Export for Fine-tuning** — downloads all pairs as JSONL
  (`{description, spl_source}` per line)
- **Query** — test-retrieve the top-k examples for any description, with
  similarity scores, to verify what the compiler will see
- **Push from knowledge.db** — promote scripts to the RAG store (useful when
  `auto_capture` is disabled or for selective curation); shows which scripts
  are already indexed; bulk-push or individual push per row

### 1 · Text-to-SPL

1. **Settings sidebar** — choose Adapter and Model used for both compilation
   and execution (shown as `Adapter: X  Model: Y`).
2. **Mode** — `auto`, `prompt`, or `workflow`.
3. **Description** — plain-English task description.  Placeholder shows an
   example for the selected mode.
4. **Script name** — logical identifier (snake_case).  Leave blank to
   auto-derive from the first 4 meaningful words of the description.
5. **Overwrite current version** checkbox — disabled when no version exists yet.
   - Unchecked (default): auto-increment → `v2 (revision of v1)`, `v3 (revision of v2)` etc.
   - Checked: update the latest version in-place; no new row is created.
6. **text2spl button** — calls `spl text2spl` and displays the result in a
   `st.code` block with SQL syntax highlighting.  The script is saved to
   `data/scripts/` and recorded in the `scripts` table.
7. **Code-RAG context expander** — shown when the store is non-empty; displays
   the top-4 similar examples retrieved and injected as few-shot context.
8. **Input fields** — auto-detected from the generated SPL:
   - `INPUT @var TYPE` declarations (WORKFLOW)
   - `SELECT @var` references (PROMPT fallback)
9. **Run button** — calls `spl run -p key=value …` for each non-empty input
   and records the result in the `executions` table.

### 2 · Review

- **Export** — downloads the full knowledge base as `text2spl_knowledge.yaml`.
- **Import** — upload a `.yaml` / `.yml` export file.  Duplicate
  `(name, version)` pairs are silently skipped; new records are merged in.
- **Scripts table** — all scripts sorted by name then version.
- **Script detail** — select a script to see its SPL code, metadata JSON,
  and full execution history with per-run inputs and outputs.

---

## Database schema

`data/knowledge.db` — SQLite, two tables.

### `scripts`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `name` | TEXT | Logical script name (snake_case) |
| `version` | INTEGER | Auto-incremented per name |
| `description` | TEXT | Original natural language input |
| `mode` | TEXT | `prompt` / `workflow` / `auto` |
| `spl_code` | TEXT | Generated SPL 2.0 source |
| `spl_file` | TEXT | Path to the `.spl` file on disk |
| `compiler_adapter` | TEXT | Adapter used by `spl text2spl` |
| `compiler_model` | TEXT | Model used by `spl text2spl` (null = adapter default) |
| `created_at` | TEXT | UTC timestamp |

**Unique key:** `(name, version)` — enforced by index `idx_name_version`.

Iterating on the same description reuses the same `name` and bumps `version`,
so you can track how the generated SPL evolves as you refine the wording.
Compiler and runtime adapters/models are stored independently so you can
compare, e.g., compiling with `claude_cli` but running with `ollama`.

### `executions`

| Column | Type | Notes |
|---|---|---|
| `id` | INTEGER PK | Auto-increment |
| `script_id` | INTEGER FK | References `scripts(id)` |
| `input_params` | TEXT | YAML-encoded `{param: value}` dict |
| `output` | TEXT | stdout from `spl run` |
| `return_code` | INTEGER | Exit code (0 = success) |
| `run_adapter` | TEXT | Adapter used by `spl run` |
| `run_model` | TEXT | Model used by `spl run` (null = adapter default) |
| `latency_ms` | INTEGER | Wall-clock time for the run |
| `created_at` | TEXT | UTC timestamp |

---

## Adapter and model options

Both the **compiler** (`spl text2spl`) and the **runtime** (`spl run`) accept
the same set of adapters, but they are configured independently — you can
compile with one LLM and execute with another.

### Compiler adapters + recommended models

| Adapter | Default model | Notes |
|---|---|---|
| `claude_cli` | `claude-sonnet-4-6` | **Recommended compiler.** Subscription billing, zero VRAM, highest SPL code quality. |
| `anthropic` | `claude-sonnet-4-20250514` | Anthropic API key required. |
| `ollama` | `llama3.2` | Local. For SPL generation prefer `qwen2.5-coder`. |
| `openai` | `gpt-4o` | OpenAI API key required. |
| `openrouter` | `anthropic/claude-sonnet-4-5` | OpenRouter API key required. |
| `google` | `gemini-2.5-flash` | Google API key required. |
| `deepseek` | `deepseek-chat` | DeepSeek API key required. |
| `qwen` | `qwen-plus` | Qwen API key required. |
| `bedrock` | `anthropic.claude-sonnet-4-20250514-v1:0` | AWS credentials required; region default `us-east-1`. |
| `vertex` | `gemini-2.5-flash` | GCP credentials required; location default `us-central1`. |
| `azure_openai` | `gpt-4o` | Azure endpoint + key required; API version `2025-01-01-preview`. |

### Runtime adapters + recommended models

Same adapter list as above.  Additional option:

| Adapter | Default model | Notes |
|---|---|---|
| `echo` | — | **Development default.** Returns the prompt unchanged; no LLM call. |

For runtime the adapter default in `~/.spl/config.yaml` is `echo`.  Override
per-run with the **Adapter** sidebar control.

Leave the **Model** field blank to use the adapter's default model shown above.

---

#### Why YAML for `input_params`?

JSON requires escaping every quote in multi-line text, making long documents
like `@document` or `@draft` painful to store and inspect.  YAML literal
block scalars (`|`) handle arbitrary multi-line text cleanly:

```yaml
document: |
  Chapter 1: The Beginning

  This document discusses the "importance" of proper quoting.
  It even handles apostrophes and "nested 'quotes'" without escaping.
draft: |
  Initial draft text here.
  Multiple paragraphs, no escaping needed.
```

`db.decode_params` falls back to JSON for any rows written by older versions
of the app that used JSON encoding.

---

## Import / Export format

The exported YAML nests executions inside their parent script:

```yaml
# text2SPL Knowledge Base Export
# Generated: 2026-03-23T10:00:00

scripts:
  - name: summarize_doc
    version: 1
    description: summarize a document with a 2000 token budget
    mode: prompt
    spl_code: |
      PROMPT summarize_doc WITH BUDGET 2000 TOKENS
      SELECT @document AS content LIMIT 1500 TOKENS
      GENERATE summarize(content) WITH OUTPUT BUDGET 500 TOKENS;
    spl_file: /path/to/scripts/summarize_doc_v1_abc123.spl
    compiler_adapter: claude_cli
    compiler_model: claude-sonnet-4-6
    created_at: '2026-03-23 10:00:00'
    executions:
      - input_params:
          document: |
            This is the document to summarize.
            It has multiple paragraphs and "quoted text".
        output: "A concise summary of the document."
        return_code: 0
        run_adapter: ollama
        run_model: gemma3
        latency_ms: 3421
        created_at: '2026-03-23 10:01:00'

  - name: summarize_doc
    version: 2          # refined description → new version
    description: summarize a document in bullet points with a 2000 token budget
    ...
```

Importing this file into another instance merges the records without
overwriting existing `(name, version)` pairs.  The file is the natural unit
for sharing knowledge across team members or instances.

---

## Dependencies

```
streamlit
pyyaml
pandas
chromadb      # optional — required for Code-RAG page
```

Install with:

```bash
pip install streamlit pyyaml pandas
pip install chromadb   # for Code-RAG support
```

If `chromadb` is not installed the app still runs fully — the Code-RAG page
shows an install prompt and the context expander on Text-to-SPL is hidden.
