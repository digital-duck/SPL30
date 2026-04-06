"""Thin wrapper around spl.code_rag.CodeRAGStore for the Streamlit app.

Resolves the storage_dir absolutely (relative to the repo root) so the app
works regardless of the working directory it was launched from.

Handles the case where chromadb is not installed — all public functions return
safe fallback values and `is_available()` returns False.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

# ── Repo root — four levels up from this file ─────────────────────────────────
# streamlit/ → ui/ → spl/ → SPL30/
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent

if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ── Config defaults (mirrors spl/config.py) ───────────────────────────────────
_DEFAULT_STORAGE_REL = ".spl/code_rag"
_DEFAULT_COLLECTION  = "spl_code_rag"

# ── Optional import ───────────────────────────────────────────────────────────
_AVAILABLE = False
_IMPORT_ERROR = ""

try:
    from spl.code_rag import CodeRAGStore as _CodeRAGStore
    _AVAILABLE = True
except ImportError as _e:
    _IMPORT_ERROR = str(_e)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _storage_dir() -> str:
    """Absolute path to the Code-RAG ChromaDB directory."""
    try:
        from spl.config import load_config
        cfg = load_config()
        # dd_config uses dot-path access
        sd = cfg.get("code_rag.storage_dir") or _DEFAULT_STORAGE_REL
    except Exception:
        sd = _DEFAULT_STORAGE_REL
    p = Path(sd)
    return str(p if p.is_absolute() else _REPO_ROOT / p)


def _collection() -> str:
    try:
        from spl.config import load_config
        cfg = load_config()
        return cfg.get("code_rag.collection") or _DEFAULT_COLLECTION
    except Exception:
        return _DEFAULT_COLLECTION


def _store() -> "_CodeRAGStore":
    if not _AVAILABLE:
        raise ImportError(f"chromadb not installed: {_IMPORT_ERROR}")
    return _CodeRAGStore(storage_dir=_storage_dir(), collection_name=_collection())


def _doc_id(description: str) -> str:
    """Replicate the doc_id scheme used by CodeRAGStore.add_pair()."""
    return "user_" + hashlib.sha1(description.encode()).hexdigest()[:12]


# ── Public API ────────────────────────────────────────────────────────────────

def is_available() -> bool:
    """Return True if chromadb is installed and CodeRAGStore can be used."""
    return _AVAILABLE


def import_error() -> str:
    return _IMPORT_ERROR


def count() -> int:
    """Total number of indexed (description, SPL) pairs. Returns -1 on error."""
    try:
        return _store().count()
    except Exception:
        return -1


def query(description: str, top_k: int = 4) -> list[dict]:
    """Retrieve top-k similar examples for a description.

    Each result is a dict with:
        description, spl_source, name, category, source, score (cosine distance)
    Returns [] if store is empty or unavailable.
    """
    try:
        return _store().retrieve(description, top_k=top_k)
    except Exception:
        return []


def add(
    description: str,
    spl_source: str,
    name: str = "",
    source: str = "app",
) -> tuple[bool, str]:
    """Add a (description, SPL) pair to the store.

    Returns (success, message).
    """
    try:
        _store().add_pair(
            description=description,
            spl_source=spl_source,
            metadata={"name": name, "source": source},
        )
        return True, "Added."
    except Exception as e:
        return False, str(e)


def is_indexed(description: str) -> bool:
    """Return True if this description's doc_id is already in the store."""
    try:
        store = _store()
        result = store._col.get(ids=[_doc_id(description)], include=[])
        return len(result.get("ids", [])) > 0
    except Exception:
        return False


def seed_cookbook() -> tuple[int, str]:
    """Index all cookbook recipes.  Returns (pairs_added, message)."""
    try:
        cookbook_dir = str(_REPO_ROOT / "cookbook")
        added = _store().index_recipes(cookbook_dir=cookbook_dir)
        return added, f"Added {added} recipe(s) from cookbook."
    except Exception as e:
        return -1, str(e)


def export_jsonl() -> str:
    """Export all indexed pairs as a JSONL string (suitable for st.download_button)."""
    try:
        store = _store()
        with tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False, mode="w") as f:
            tmp = f.name
        store.export_jsonl(tmp)
        return Path(tmp).read_text(encoding="utf-8")
    except Exception:
        return ""
