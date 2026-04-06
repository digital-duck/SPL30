"""
text2spl/rag/index_recipes.py — Populate the code-RAG vector store from SPL v2.0 cookbook.

Reads all recipes from cookbook_catalog.json, embeds each one (name + description +
SPL source), and upserts into a persistent ChromaDB collection.

The indexed store is what text2SPL queries at generation time to retrieve the
closest few-shot template for a user's intent.

Usage (from SPL30 root):
    conda run -n spl2 python spl3/text2spl/rag/index_recipes.py
    conda run -n spl2 python spl3/text2spl/rag/index_recipes.py --catalog /path/to/catalog.json
    conda run -n spl2 python spl3/text2spl/rag/index_recipes.py --embed-model nomic-embed-text
    conda run -n spl2 python spl3/text2spl/rag/index_recipes.py --reset   # drop + re-index

Architecture
------------
  dd_embed (OllamaEmbedAdapter)  →  embeddings (float[])
  dd_vectordb (ChromaVectorDB)   →  persistent vector store
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────

SPL30_ROOT    = Path(__file__).resolve().parents[3]   # spl3/text2spl/rag/index_recipes.py → SPL30/
SPL20_ROOT    = SPL30_ROOT.parent / "SPL20"
DEFAULT_CATALOG = SPL20_ROOT / "cookbook" / "cookbook_catalog.json"
CHROMA_DIR    = Path(__file__).parent / ".chroma"
COLLECTION    = "spl_recipes"


# ── Document builder ──────────────────────────────────────────────────────────

def _build_doc_text(recipe: dict, spl_source: str, max_spl_chars: int = 6000) -> str:
    """Combine recipe metadata + SPL source into a single embeddable document.

    Layout mirrors a few-shot template so that retrieved docs are immediately
    usable as context by the text2SPL generator.

    SPL source is truncated to ``max_spl_chars`` to stay within the embedding
    model's context window (nomic-embed-text: ~8 192 tokens).
    """
    if len(spl_source) > max_spl_chars:
        spl_source = spl_source[:max_spl_chars] + "\n-- [truncated for embedding]"
    return (
        f"# Recipe {recipe['id']}: {recipe['name']}\n"
        f"Category: {recipe['category']}\n"
        f"Description: {recipe['description']}\n\n"
        f"```spl\n{spl_source}\n```"
    )


def _load_spl_source(recipe: dict, catalog_dir: Path) -> str | None:
    """Return the concatenated content of all .spl files in the recipe dir."""
    recipe_dir = catalog_dir / recipe["dir"]
    spl_files = sorted(recipe_dir.glob("*.spl"))
    if not spl_files:
        return None
    parts = []
    for f in spl_files:
        parts.append(f"-- File: {f.name}\n" + f.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


# ── Indexer ───────────────────────────────────────────────────────────────────

def index_recipes(
    catalog_path: Path,
    embed_model: str,
    reset: bool,
    verbose: bool,
) -> None:
    # ── Load catalog ──────────────────────────────────────────────────────────
    with open(catalog_path, encoding="utf-8") as f:
        catalog = json.load(f)
    recipes = catalog["recipes"]
    catalog_dir = catalog_path.parent

    print(f"Catalog: {catalog_path}  ({len(recipes)} recipes)")
    print(f"Embed model: {embed_model}  →  ChromaDB at {CHROMA_DIR}")

    # ── Init dd_embed + dd_vectordb ───────────────────────────────────────────
    import dd_embed
    from dd_vectordb import ChromaVectorDB
    from dd_vectordb.models import Document

    embedder = dd_embed.get_adapter("ollama", model_name=embed_model)

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    db = ChromaVectorDB(
        collection_name=COLLECTION,
        persist_directory=str(CHROMA_DIR),
        metric="cosine",
    )

    if reset:
        db.clear()
        print("Collection cleared.")

    # ── Index each recipe ─────────────────────────────────────────────────────
    indexed = skipped = 0
    docs_to_add: list[Document] = []

    for recipe in recipes:
        rid = recipe["id"]
        spl_source = _load_spl_source(recipe, catalog_dir)
        if spl_source is None:
            if verbose:
                print(f"  SKIP {rid} {recipe['name']} — no .spl files found")
            skipped += 1
            continue

        doc_text = _build_doc_text(recipe, spl_source)

        # Embed
        result = embedder.embed([doc_text])
        if not result.success:
            print(f"  ERROR {rid} {recipe['name']}: {result.error}", file=sys.stderr)
            skipped += 1
            continue

        emb = result.embeddings[0].tolist()
        docs_to_add.append(Document(
            id=f"recipe_{rid}",
            text=doc_text,
            embedding=emb,
            metadata={
                "id":          rid,
                "name":        recipe["name"],
                "description": recipe["description"],
                "category":    recipe["category"],
                "dir":         recipe["dir"],
                "status":      recipe.get("approval_status", "unknown"),
            },
        ))
        indexed += 1
        if verbose:
            print(f"  OK  {rid} {recipe['name']}  ({len(emb)}d)")

    if docs_to_add:
        db.add_documents(docs_to_add)

    print(f"\nIndexed: {indexed}  Skipped: {skipped}  Total in store: {db.count()}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(
        description="Index SPL v2.0 cookbook recipes into the text2SPL RAG store."
    )
    p.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help=f"Path to cookbook_catalog.json (default: {DEFAULT_CATALOG})",
    )
    p.add_argument(
        "--embed-model",
        default="nomic-embed-text",
        help="Ollama embedding model (default: nomic-embed-text)",
    )
    p.add_argument(
        "--reset",
        action="store_true",
        help="Clear the collection before re-indexing",
    )
    p.add_argument("-v", "--verbose", action="store_true")
    args = p.parse_args()

    if not args.catalog.exists():
        print(f"ERROR: catalog not found: {args.catalog}", file=sys.stderr)
        sys.exit(1)

    index_recipes(
        catalog_path=args.catalog,
        embed_model=args.embed_model,
        reset=args.reset,
        verbose=args.verbose,
    )


if __name__ == "__main__":
    main()
