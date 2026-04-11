"""Bridge to the shared SPL recipe RAG store (SPL30/spl/rag/).

Uses dd_embed (OllamaEmbedAdapter, nomic-embed-text) + dd_vectordb (ChromaDB).
Powers recipe retrieval for both text2spl (NL → .spl) and splc (.spl → target).

Storage: SPL30/spl/rag/.chroma  (persistent ChromaDB)
Index:   41+ SPL v2.0 cookbook recipes (indexed by spl/rag/index_recipes.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
# streamlit/ → ui/ → spl/ → SPL30/
_SPL30_ROOT = Path(__file__).resolve().parents[3]
_SPL20_ROOT = _SPL30_ROOT.parent / "SPL20"   # for cookbook access if needed
_SPL_DIR    = _SPL30_ROOT / "spl"
_CHROMA_DIR = _SPL_DIR / "rag" / ".chroma"

for _p in [str(_SPL30_ROOT), str(_SPL_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ── Optional import ────────────────────────────────────────────────────────────
_AVAILABLE    = False
_IMPORT_ERROR = ""

try:
    from rag.search import search_recipes as _search
    _AVAILABLE = True
except ImportError as _e:
    _IMPORT_ERROR = str(_e)


# ── Public API ─────────────────────────────────────────────────────────────────

def is_available() -> bool:
    return _AVAILABLE and _CHROMA_DIR.exists()


def import_error() -> str:
    if not _AVAILABLE:
        return _IMPORT_ERROR
    if not _CHROMA_DIR.exists():
        return f"RAG store not indexed yet: {_CHROMA_DIR}"
    return ""


def count() -> int:
    """Number of indexed recipes. Returns -1 on error."""
    if not is_available():
        return -1
    try:
        from dd_vectordb import ChromaVectorDB
        db = ChromaVectorDB(collection_name="spl_recipes",
                            persist_directory=str(_CHROMA_DIR), metric="cosine")
        return db.count()
    except Exception:
        return -1


def query(description: str, top_k: int = 5) -> list[dict]:
    """Retrieve top-k similar SPL recipes for a description.

    Returns list of dicts: {name, description, category, spl_source, score}
    """
    if not is_available():
        return []
    try:
        hits = _search(description, k=top_k)
        return [
            {
                "name":        h.name,
                "description": h.description,
                "category":    h.category,
                "spl_source":  h.spl_source,
                "score":       h.score,
                "source":      "spl_cookbook",
            }
            for h in hits
        ]
    except Exception:
        return []


def seed_cookbook() -> tuple[int, str]:
    """(Re-)index all SPL v2.0 cookbook recipes into the shared RAG store.

    Calls spl/rag/index_recipes.py with --reset to rebuild from scratch.
    Returns (count_indexed, message).
    """
    import subprocess
    script = _SPL_DIR / "rag" / "index_recipes.py"
    if not script.exists():
        return -1, f"index_recipes.py not found at {script}"
    try:
        proc = subprocess.run(
            ["python", str(script), "--reset"],
            capture_output=True, text=True, timeout=300,
        )
        c = count()
        if proc.returncode == 0:
            return c, f"Indexed {c} recipes into SPL RAG store."
        return -1, proc.stderr or proc.stdout or "Indexing failed."
    except Exception as e:
        return -1, str(e)


def spl3_root() -> Path:
    """Return SPL30 root path (kept for backwards compat with callers)."""
    return _SPL30_ROOT


def chroma_dir() -> Path:
    return _CHROMA_DIR
