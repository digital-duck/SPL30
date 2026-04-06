"""
spl/rag/search.py — Retrieval interface for the text2SPL code-RAG store.

This is what the text2SPL generator calls to find the closest few-shot template
for a user's intent before generating a new .spl script.

Usage (programmatic):
    from spl.rag.search import search_recipes

    hits = search_recipes("iterative self-improvement loop with critique", k=3)
    for h in hits:
        print(h["name"], h["score"])
        print(h["spl_source"])   # inject as few-shot context

Usage (CLI — smoke test):
    conda run -n spl2 python spl/rag/search.py "plan and execute agent"
    conda run -n spl2 python spl/rag/search.py "RAG over documents" --k 5
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

CHROMA_DIR = Path(__file__).parent / ".chroma"
COLLECTION = "spl_recipes"


# ── Result type ───────────────────────────────────────────────────────────────

@dataclass
class RecipeHit:
    """A single retrieval result from the SPL recipe store."""
    rank:        int
    score:       float       # cosine similarity 0–1
    id:          str         # e.g. "05"
    name:        str
    description: str
    category:    str
    spl_source:  str         # full document text (metadata + SPL code)
    metadata:    dict[str, Any]


# ── Core retrieval ────────────────────────────────────────────────────────────

def search_recipes(
    query: str,
    *,
    k: int = 5,
    embed_model: str = "nomic-embed-text",
    category: str | None = None,
) -> list[RecipeHit]:
    """Retrieve the top-k most relevant SPL recipes for the given intent query.

    Parameters
    ----------
    query :       Natural-language description of the desired workflow.
    k :           Number of results to return.
    embed_model : Ollama embedding model (must match the one used at index time).
    category :    Optional filter — one of: basics | agentic | reasoning |
                  safety | retrieval | multi-agent | application | benchmarking

    Returns
    -------
    List of RecipeHit ordered by descending cosine similarity.
    """
    if not CHROMA_DIR.exists():
        raise RuntimeError(
            f"RAG store not found at {CHROMA_DIR}. "
            "Run `python spl/rag/index_recipes.py` first."
        )

    import dd_embed
    from dd_vectordb import ChromaVectorDB

    embedder = dd_embed.get_adapter("ollama", model_name=embed_model)
    result = embedder.embed([query])
    if not result.success:
        raise RuntimeError(f"Embedding failed: {result.error}")

    query_vec = result.embeddings[0].tolist()

    db = ChromaVectorDB(
        collection_name=COLLECTION,
        persist_directory=str(CHROMA_DIR),
        metric="cosine",
    )

    chroma_filter = {"category": category} if category else None
    raw = db.search(query_vec, k=k, filter=chroma_filter)

    hits = []
    for sr in raw:
        meta = sr.document.metadata
        hits.append(RecipeHit(
            rank=sr.rank,
            score=round(sr.score, 4),
            id=meta.get("id", ""),
            name=meta.get("name", ""),
            description=meta.get("description", ""),
            category=meta.get("category", ""),
            spl_source=sr.document.text,
            metadata=meta,
        ))
    return hits


# ── CLI smoke test ────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Search the text2SPL RAG store by natural-language intent."
    )
    p.add_argument("query",         help="Intent description")
    p.add_argument("--k",           type=int, default=3)
    p.add_argument("--category",    default=None,
                   help="Filter by category (basics|agentic|reasoning|...)")
    p.add_argument("--embed-model", default="nomic-embed-text")
    p.add_argument("--show-source", action="store_true",
                   help="Print the full SPL source for each hit")
    args = p.parse_args()

    try:
        hits = search_recipes(
            args.query,
            k=args.k,
            embed_model=args.embed_model,
            category=args.category,
        )
    except RuntimeError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    if not hits:
        print("No results found.")
        return

    print(f"Top {len(hits)} results for: \"{args.query}\"\n")
    for h in hits:
        print(f"  [{h.rank}] score={h.score:.4f}  #{h.id} {h.name}  [{h.category}]")
        print(f"       {h.description}")
        if args.show_source:
            print()
            print(h.spl_source)
            print()
    print()


if __name__ == "__main__":
    main()
