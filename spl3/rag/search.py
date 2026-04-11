"""
spl/rag/search.py — Retrieval interface for the text2SPL code-RAG store.

This is what the text2SPL generator calls to find the closest few-shot template
for a user's intent before generating a new .spl script.

Usage (programmatic):
    from spl3.rag.search import search_recipes

    hits = search_recipes("iterative self-improvement loop with critique", k=3)
    for h in hits:
        print(h["name"], h["score"])
        print(h["spl_source"])   # inject as few-shot context

Usage (CLI — smoke test):
    conda run -n spl2 python spl/rag/search.py "plan and execute agent"
    conda run -n spl2 python spl/rag/search.py "RAG over documents" --k 5
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import click

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

@click.command()
@click.argument("query")
@click.option("--k",           default=3, show_default=True, type=int)
@click.option("--category",    default=None, help="Filter by category (basics|agentic|reasoning|...)")
@click.option("--embed-model", default="nomic-embed-text", show_default=True)
@click.option("--show-source", is_flag=True, help="Print the full SPL source for each hit")
def main(query, k, category, embed_model, show_source) -> None:
    """Search the text2SPL RAG store by natural-language intent."""
    try:
        hits = search_recipes(query, k=k, embed_model=embed_model, category=category)
    except RuntimeError as e:
        click.echo(f"ERROR: {e}", err=True)
        sys.exit(1)

    if not hits:
        click.echo("No results found.")
        return

    click.echo(f"Top {len(hits)} results for: \"{query}\"\n")
    for h in hits:
        click.echo(f"  [{h.rank}] score={h.score:.4f}  #{h.id} {h.name}  [{h.category}]")
        click.echo(f"       {h.description}")
        if show_source:
            click.echo()
            click.echo(h.spl_source)
            click.echo()
    click.echo()


if __name__ == "__main__":
    main()
