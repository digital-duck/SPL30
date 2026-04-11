# text2spl — Intent → SPL Logical View

`text2spl` is the **semantic layer** of the DODA pipeline. It translates a
natural-language description of an AI workflow into a valid `.spl` script
(the logical view).

```
Human Intent  →  text2spl  →  .spl (logical view)  →  splc  →  physical artifact
              (semantic layer)                       (structural layer)
```

`text2spl` produces the invariant logical view. `splc` consumes it. They are
independent layers — `splc` does not care how the `.spl` was generated.

---

## Shared RAG store (`spl/rag/`)

`text2spl` uses a persistent ChromaDB vector store to retrieve similar SPL
recipes as few-shot examples at generation time. This shared store is also
consumed by `splc` for few-shot compilation context.

### Contents

41 SPL v2.0 cookbook recipes (indexed from `SPL20/cookbook/cookbook_catalog.json`):
- Workflow patterns: self-refine, plan-and-execute, reflection, ensemble voting
- Categories: `agentic`, `prompt`, `workflow`, `tool_use`, `rag`

### Storage

```
spl/rag/
├── .chroma/          # Persistent ChromaDB (created by index_recipes.py)
├── index_recipes.py  # Indexer: reads catalog.json → embeds → upserts to ChromaDB
└── search.py         # Search API: query → list[RecipeHit]
```

### Setup (one-time)

```bash
# From SPL30 root, in the spl2 conda env
conda run -n spl2 python spl/rag/index_recipes.py
```

To re-index from scratch (e.g. after adding recipes to the catalog):

```bash
conda run -n spl2 python spl/rag/index_recipes.py --reset
```

Options:

```
--catalog PATH       Path to cookbook_catalog.json (default: SPL20/cookbook/cookbook_catalog.json)
--embed-model NAME   Ollama embedding model (default: nomic-embed-text)
--reset              Clear the collection before re-indexing
-v / --verbose       Print per-recipe progress
```

### Embedding model

Uses `dd_embed` with `OllamaEmbedAdapter` and `nomic-embed-text` (768-dim,
~8 192-token context window). SPL sources are truncated to 6 000 chars before
embedding to stay within the context window.

### Search API

```python
from rag.search import search_recipes, RecipeHit

hits: list[RecipeHit] = search_recipes(
    query   = "iterative critique and refinement",
    k       = 3,
    category = None,   # optional: filter by category
)

for h in hits:
    print(h.rank, h.score, h.name, h.category)
    print(h.spl_source)
```

`RecipeHit` fields: `rank`, `score` (cosine distance, lower = more similar),
`id`, `name`, `description`, `category`, `spl_source`, `metadata`.

CLI smoke test:

```bash
conda run -n spl2 python spl/rag/search.py "iterative critique and refine" --k 3
```

Expected output for that query:
```
[1] score=0.245  #05 Self-Refine Pattern                [agentic]
[2] score=0.360  #16 Reflection Agent                   [agentic]
[3] score=0.412  #12 Plan and Execute Agent              [agentic]
```

### Who queries this store

| Consumer | Why |
|---|---|
| `text2spl` (SPL compiler) | Retrieves similar SPL patterns to guide NL→SPL generation |
| `splc` (SPL compiler) | Retrieves similar SPL patterns as few-shot context for `.spl`→target translation |

**One store, two consumers** — the retrieval question is the same for both:
*"Given a description/snippet, find the most similar SPL recipes."*

The store does **not** hold user-generated scripts. Those live in the SPL20
`code_rag_bridge` store (knowledge.db), which is `text2spl`-only.

---

## RAG vs. other context sources

| Source | What it contains | Used by |
|---|---|---|
| `rag/.chroma` | SPL v2.0 cookbook recipes (logical patterns) | `text2spl` + `splc` |
| SPL20 `code_rag_bridge` | User-generated (description → SPL) pairs | `text2spl` only |
| `splc --references` | Target framework code / docs (GitHub URLs or local paths) | `splc` only |

---

## v1 → v2 capability roadmap

| Capability | v1 (current) | v2 (planned) |
|---|---|---|
| RAG source | SPL v2.0 cookbook (41 recipes) | + user-generated scripts |
| Embedding | nomic-embed-text (Ollama local) | + cloud embedding fallback |
| Query scope | Single description string | + structured intent fields |
| Output | `.spl` file | + validation report |
| Agentic patterns | All SPL v2.0 patterns | + SPL v3.0 type system patterns |
