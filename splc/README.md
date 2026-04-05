# splc — SPL Compiler

`splc` translates a `.spl` script (the **logical view** — declarative,
hardware-agnostic) into a working implementation in a target language or
framework (the **physical view**).

This is the DODA principle in practice:

```
[.spl logical view]  →  splc  →  [physical artifact]
     invariant                    language/framework-specific
```

The `.spl` file never changes when you retarget. Only the compiled output changes.

---

## Quick start

```bash
# Compile to Go (uses LLM pretrained knowledge)
python splc/cli.py \
    --spl cookbook/05_self_refine/self_refine.spl \
    --lang go

# Compile to LangGraph Python with a reference codebase
python splc/cli.py \
    --spl cookbook/05_self_refine/self_refine.spl \
    --lang python/langgraph \
    --references https://github.com/langchain-ai/langgraph

# Preview the prompt without calling the LLM
python splc/cli.py \
    --spl cookbook/05_self_refine/self_refine.spl \
    --lang python/crewai \
    --dry-run --verbose
```

---

## CLI reference

```
python splc/cli.py [OPTIONS]
```

### Required

| Option | Type | Description |
|--------|------|-------------|
| `--spl FILE` | path | Source `.spl` script (logical view). Must exist. |
| `--lang LANG` | choice | Target language / framework (see [Supported targets](#supported-targets)). |

### With defaults

| Option | Default | Description |
|--------|---------|-------------|
| `--out-dir DIR` | `targets/<lang>/` next to the `.spl` file | Output directory. Created if it does not exist. |
| `--model MODEL` | `claude-sonnet-4-6` | LLM model for compilation. Use `claude-opus-4-6` for complex workflows. |
| `--rag / --no-rag` | `--rag` (on) | Include few-shot SPL recipe examples from the text2spl RAG store as context. Requires the store to be indexed first (see [RAG context](#rag-context)). |
| `--rag-k N` | `3` | Number of RAG examples to include (1–10). |

### Optional

| Option | Description |
|--------|-------------|
| `--references URL_OR_PATH` | Reference codebase to ground the LLM's output. Repeatable — pass once per reference. Accepts GitHub repo URLs (fetches `README.md`) or local directory/file paths. If omitted, compilation relies on the LLM's pretrained knowledge. |
| `--overwrite` | Allow overwriting existing files in `--out-dir`. Default: abort if the output file already exists. |
| `--dry-run` | Print the full compiled prompt without calling the LLM. Use this to inspect and tune context before spending tokens. |
| `--no-readme` | Skip generating `readme.md` alongside the implementation. |
| `-v / --verbose` | Print progress: reference fetching, RAG query and scores, model call, response size. |
| `-h / --help` | Show this help and exit. |

---

## Supported targets

| `--lang` value | Runtime | Dependencies |
|---|---|---|
| `go` | Ollama REST API (stdlib only) | Go 1.22+, Ollama running locally |
| `python` | Plain Python, minimal deps | Python 3.11+ |
| `python/langgraph` | LangGraph | `pip install langgraph langchain-ollama` |
| `python/crewai` | CrewAI | `pip install crewai langchain-ollama` |
| `python/autogen` | AutoGen | `pip install pyautogen` |

Planned (not yet implemented):
- `swift` — Apple Metal / M4/M5 (v3.2)
- `snap` — Ubuntu 26.04 Inference Snap (v3.1)
- `edge` — ARM / Android AICore (v3.3)

---

## Output files

For each compilation, `splc` writes up to three files into `--out-dir`:

```
<out-dir>/
├── <recipe>_<lang>.<ext>     # Implementation (e.g. self_refine_go.go)
├── readme.md                 # Setup, run command, SPL→target mapping table
└── splc_manifest.json        # Provenance record (see below)
```

### `splc_manifest.json`

Captures full provenance of the compiled artifact so you always know how a
physical file was generated and can reproduce or retarget it:

```json
{
  "splc_version": "0.1.0",
  "generated_at": "2026-04-05T15:00:00+00:00",
  "source": {
    "spl_file":   "/path/to/self_refine.spl",
    "spl_sha256": "a1b2c3d4e5f6..."
  },
  "target": {
    "lang":        "go",
    "label":       "Go (stdlib + Ollama REST API)",
    "output_file": "/path/to/self_refine_go.go"
  },
  "compilation": {
    "model":       "claude-sonnet-4-6",
    "adapter":     "claude_cli",
    "references":  ["https://github.com/langchain-ai/langgraph"],
    "rag_enabled": true,
    "rag_k":       3
  },
  "doda_note": "This file is a splc-compiled physical artifact. ..."
}
```

---

## How references work

`--references` accepts GitHub repo URLs or local paths. `splc` fetches the
content and injects it into the LLM prompt as grounding context.

| Reference type | What is fetched | Char cap |
|---|---|---|
| GitHub URL (`https://github.com/...`) | `README.md` from the `main` branch | 8 000 |
| Local file | Full file content | 8 000 |
| Local directory | `README*` files + first 5 source files | 10 000 |

**When to use `--references`:**

- Targeting a framework the LLM may not know well — pass the framework's GitHub repo.
- You have an existing internal codebase implementation to match — pass the local path.
- Compiling to a new target for the first time — references anchor style, imports, and idioms.

**When to omit `--references`:**

- Well-known frameworks (LangGraph, CrewAI, AutoGen, Go stdlib) where pretrained
  knowledge is sufficient.
- Fast iteration / prototyping — skip refs, verify output, add refs only if the
  generated code has style issues.

Multiple references are supported — pass `--references` once per source:

```bash
python splc/cli.py \
    --spl my_workflow.spl \
    --lang python/crewai \
    --references https://github.com/crewAIInc/crewAI \
    --references https://github.com/langchain-ai/langchain \
    --references ./internal/agent_patterns/
```

---

## RAG context

`splc` optionally pulls similar SPL recipes from the `text2spl` RAG store as
few-shot examples. These are injected into the prompt *before* the source `.spl`,
giving the LLM concrete SPL patterns to ground its translation.

RAG context is **different from `--references`**:

| | RAG context (`--rag`) | References (`--references`) |
|---|---|---|
| What it contains | Similar SPL recipes (logical view) | Target framework code / docs |
| Purpose | Show the LLM what SPL patterns look like | Ground the LLM in how the target works |
| Source | `text2spl/rag/.chroma` (local vector store) | GitHub URLs or local paths |
| Requires setup | Yes — index the store first | No — fetched on demand |

### Setup (one-time)

```bash
# From SPL30 root, in spl2 conda env
conda run -n spl2 python text2spl/rag/index_recipes.py
```

This indexes all 41 SPL v2.0 recipes from `SPL20/cookbook/cookbook_catalog.json`
into a persistent ChromaDB store at `text2spl/rag/.chroma/`.

### How the RAG query works

`splc` extracts a description from the source `.spl` file's leading comment
(skipping generic headers like `Recipe Name:`) and uses it as the semantic query.
For example, `self_refine.spl` contains:

```sql
-- Iteratively improves output through critique and refinement
```

That text is embedded and matched against the store. For `self_refine.spl`:

```
RAG query: "Iteratively improves output through critique and refinement"
  [1] score=0.755  #05 Self-Refine       [agentic]
  [2] score=0.640  #16 Reflection Agent  [agentic]
  [3] score=0.588  #12 Plan and Execute  [agentic]
```

The top-k SPL sources are injected as few-shot examples before the target source.

---

## Prompt structure

The full prompt sent to the LLM is assembled in this order:

```
1. System prompt      — splc rules + target label + README instruction
       ↓
2. RAG examples       — top-k similar SPL recipes (if --rag)
       ↓
3. Reference context  — fetched codebase content (if --references)
       ↓
4. SPL source         — the actual .spl file to compile
       ↓
5. Generation cue     — "Generate the <target> implementation now."
```

Inspect the full assembled prompt with `--dry-run` before running a real
compilation. This is especially useful when tuning `--rag-k` or checking
whether reference content was fetched correctly.

---

## SPL → target construct mapping

Each compiled output file includes inline comments mapping SPL constructs to
their target-language equivalents. The pattern used by the LLM (rule 1 of the
system prompt):

```go
// SPL: GENERATE critique(@current) INTO @feedback
feedback, err := generate(ollamaHost, criticModel, fmt.Sprintf(critiquePrompt, current))
```

```python
# SPL: WHILE @iteration < @max_iterations DO
for iteration in range(max_iterations):
```

```python
# SPL: EVALUATE @feedback WHEN contains('[APPROVED]') THEN
if "[APPROVED]" in feedback:
```

This traceability is intentional: every physical artifact must remain auditable
back to its logical source.

---

## Existing compiled targets

`cookbook/05_self_refine/` serves as the reference recipe. It has been compiled
to all currently supported targets:

```
cookbook/05_self_refine/
├── self_refine.spl                         ← logical view (source of truth)
└── targets/
    ├── go/
    │   ├── self_refine.go                  ← splc --lang go (hand-written prototype)
    │   ├── go.mod
    │   └── readme.md
    └── python/
        ├── langgraph/
        │   ├── self_refine_langgraph.py    ← splc --lang python/langgraph
        │   └── readme.md
        ├── crewai/
        │   ├── self_refine_crewai.py       ← splc --lang python/crewai
        │   └── readme.md
        └── autogen/
            ├── self_refine_autogen.py      ← splc --lang python/autogen
            └── readme.md
```

The Go and Python targets were hand-written as prototypes to validate the
logical→physical translation. Future targets will be generated by `splc` itself.

---

## Architecture notes

### Relation to text2spl

`splc` and `text2spl` are the two layers of the DODA pipeline:

```
Human Intent  →  text2spl  →  .spl (logical)  →  splc  →  physical artifact
              (semantic layer)                  (structural layer)
```

`text2spl` produces the logical view. `splc` consumes it. They share the RAG
store (`text2spl/rag/`) but are otherwise independent — `splc` does not need
to know how the `.spl` was generated.

### LLM adapter

`splc` uses the `claude_cli` adapter from the SPL v2.0 runtime
(`spl.adapters.claude_cli`). This requires SPL20 on `PYTHONPATH`:

```bash
export PYTHONPATH=/path/to/SPL20:$PYTHONPATH
```

The adapter calls `claude` CLI under the hood (Claude Code / Sonnet 4.6 or
Opus 4.6). No API key management needed beyond the existing Claude Code session.

### Adding a new target

1. Add an entry to `SUPPORTED_LANGS` in `splc/cli.py`:
   ```python
   "swift": {
       "label":     "Swift — Apple Metal",
       "ext":       ".swift",
       "extras":    ["Package.swift"],
       "framework": None,
   },
   ```
2. Hand-write a prototype translation for `self_refine.spl` to validate the
   construct mapping.
3. Test with `--dry-run` to confirm the prompt is well-formed.
4. Run a real compilation and refine the system prompt rules if needed.
