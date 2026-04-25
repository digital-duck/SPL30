"""Code-RAG for SPL 3.0: cookbook-seeded vector index for Text2SPL.

Indexes (description, SPL source) pairs from the cookbook so Text2SPL
can retrieve semantically similar examples at compile time.

Backed by dd-vectordb (ChromaVectorDB) + dd-embed (sentence-transformers).

Usage:
    store = CodeRAGStore()
    store.seed_from_dir("cookbook/code_pipeline/")
    examples = store.retrieve("orchestrate review and test concurrently", top_k=3)
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

_log = logging.getLogger("spl.code_rag")

_EMBED_PROVIDER = "sentence_transformers"
_EMBED_MODEL    = "all-MiniLM-L6-v2"


class CodeRAGStore:
    """dd-vectordb (ChromaVectorDB) + dd-embed backed store for (description, SPL source) pairs.

    Parameters
    ----------
    storage_dir : str
        Directory for the persistent Chroma database.
    collection_name : str
        Chroma collection name.
    """

    COLLECTION_NAME = "spl_code_rag"

    def __init__(
        self,
        storage_dir: str = ".spl/code_rag",
        collection_name: str = COLLECTION_NAME,
    ) -> None:
        from dd_vectordb.adapters.chroma_db import ChromaVectorDB
        from dd_embed import get_adapter

        Path(storage_dir).mkdir(parents=True, exist_ok=True)
        self._db = ChromaVectorDB(
            persist_directory=storage_dir,
            collection_name=collection_name,
        )
        self._embed = get_adapter(_EMBED_PROVIDER, model_name=_EMBED_MODEL)
        _log.info("CodeRAGStore ready: dir=%s collection=%s", storage_dir, collection_name)

    # ------------------------------------------------------------------ #
    # Indexing                                                             #
    # ------------------------------------------------------------------ #

    def add_pair(
        self,
        description: str,
        spl_source: str,
        metadata: dict | None = None,
    ) -> str:
        """Index a (description, SPL source) pair. Returns the document ID."""
        from dd_vectordb.models import Document

        doc_id = hashlib.sha1(description.encode()).hexdigest()[:16]
        emb_result = self._embed.embed([description])
        if not emb_result.success:
            raise RuntimeError(f"dd-embed error: {emb_result.error}")

        meta = {"spl_source": spl_source, **(metadata or {})}
        self._db.add_documents([
            Document(
                id=doc_id,
                text=description,
                embedding=emb_result.embeddings[0],
                metadata=meta,
            )
        ])
        _log.debug("CodeRAGStore: indexed pair id=%s desc=%r", doc_id, description[:60])
        return doc_id

    def seed_from_dir(self, cookbook_dir: str | Path, pattern: str = "*.spl") -> int:
        """Index all .spl files in a directory. Extracts description from file header.

        Returns the number of pairs indexed.
        """
        cookbook_dir = Path(cookbook_dir)
        if not cookbook_dir.is_dir():
            raise FileNotFoundError(f"Not a directory: {cookbook_dir}")

        count = 0
        for spl_file in sorted(cookbook_dir.rglob(pattern)):
            source = spl_file.read_text(encoding="utf-8")
            description = _extract_description(source, spl_file.stem)
            self.add_pair(
                description=description,
                spl_source=source,
                metadata={"source_file": str(spl_file), "source": "cookbook"},
            )
            count += 1
            _log.debug("Indexed: %s", spl_file.name)

        _log.info("CodeRAGStore: seeded %d workflow(s) from %s", count, cookbook_dir)
        return count

    def seed_from_catalog(self, catalog_path: str | Path,
                          only_active: bool = True) -> int:
        """Index recipes from a JSON catalog file (cookbook_catalog.json format).

        Supports two catalog shapes:
        - Legacy:  list of {"name", "description", "file"} objects
        - Current: {"recipes": [...]} where each entry has "description", "args"
                   (args[2] is the .spl path), and optional "is_active" /
                   "approval_status" fields.

        Parameters
        ----------
        only_active:
            When True (default), skip entries where ``is_active`` is False or
            ``approval_status`` is "disabled" / "rejected".
        """
        catalog_path = Path(catalog_path)
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))

        # Support both top-level list and {"recipes": [...]} wrapper
        entries = raw if isinstance(raw, list) else raw.get("recipes", [])

        count = 0
        for entry in entries:
            # Honour active/approval filters
            if only_active:
                if not entry.get("is_active", True):
                    continue
                if entry.get("approval_status", "approved") in ("disabled", "rejected"):
                    continue

            # Resolve .spl file path — try "file" key first, then args[2], then dir+log
            spl_file: Path | None = None
            if "file" in entry:
                spl_file = Path(entry["file"])
            elif "args" in entry and len(entry["args"]) > 2:
                # args[2] is project-root-relative, e.g. "./cookbook/05_.../self_refine.spl"
                spl_file = Path(entry["args"][2].lstrip("./"))
            elif "dir" in entry and "log" in entry:
                spl_file = Path("cookbook") / entry["dir"] / f"{entry['log']}.spl"

            if spl_file is None or not spl_file.exists():
                _log.warning("Catalog entry file not found: %s (entry: %s)",
                             spl_file, entry.get("name", "?"))
                continue

            source = spl_file.read_text(encoding="utf-8")
            self.add_pair(
                description=entry["description"],
                spl_source=source,
                metadata={
                    "name": entry.get("name", spl_file.stem),
                    "category": entry.get("category", ""),
                    "source_file": str(spl_file),
                    "source": "catalog",
                },
            )
            count += 1

        _log.info("CodeRAGStore: seeded %d workflow(s) from %s", count, catalog_path.name)
        return count

    def seed_from_specs(self, specs_root: str | Path,
                        pattern: str = "**/*-spec.md") -> int:
        """Index recipes using Section 0 from describe-generated spec files.

        For each ``*-spec.md`` found under ``specs_root``, the matching
        ``*.spl`` file (same directory, same stem without ``-spec``) is paired
        with the extracted ``## 0. High-level Description`` prose and indexed.

        This gives the richest semantic descriptions for RAG because Section 0
        is written in SPL-native vocabulary by the describe pipeline.

        Returns the number of pairs indexed.
        """
        specs_root = Path(specs_root)
        count = 0
        for spec_file in sorted(specs_root.rglob(pattern)):
            spl_file = spec_file.parent / (spec_file.stem.replace("-spec", "") + ".spl")
            if not spl_file.exists():
                _log.warning("No matching .spl for spec: %s", spec_file)
                continue

            description = _extract_spec_section0(spec_file.read_text(encoding="utf-8"))
            if not description:
                _log.warning("No Section 0 found in %s — skipping", spec_file.name)
                continue

            source = spl_file.read_text(encoding="utf-8")
            self.add_pair(
                description=description,
                spl_source=source,
                metadata={
                    "source_file": str(spl_file),
                    "spec_file": str(spec_file),
                    "source": "describe-spec",
                },
            )
            count += 1
            _log.debug("Indexed from spec: %s", spec_file.name)

        _log.info("CodeRAGStore: seeded %d workflow(s) from specs under %s",
                  count, specs_root)
        return count

    # ------------------------------------------------------------------ #
    # Retrieval                                                            #
    # ------------------------------------------------------------------ #

    def retrieve(self, query: str, top_k: int = 4) -> list[dict]:
        """Retrieve top-k most similar SPL examples for a natural-language query.

        Returns list of dicts: {"description", "spl_source", "score", "metadata"}.
        """
        emb_result = self._embed.embed([query])
        if not emb_result.success:
            raise RuntimeError(f"dd-embed error: {emb_result.error}")

        results = self._db.search(emb_result.embeddings[0], k=top_k)
        return [
            {
                "description": r.document.text,
                "spl_source": r.document.metadata.get("spl_source", ""),
                "score": r.score,
                "metadata": {k: v for k, v in r.document.metadata.items()
                             if k != "spl_source"},
            }
            for r in results
        ]

    def count(self) -> int:
        return self._db.count()

    def format_examples(self, query: str, top_k: int = 4) -> str:
        """Format retrieved examples as a few-shot prompt block for Text2SPL."""
        hits = self.retrieve(query, top_k=top_k)
        if not hits:
            return ""
        parts = []
        for i, hit in enumerate(hits, 1):
            parts.append(
                f"-- Example {i}: {hit['description']}\n{hit['spl_source'].strip()}"
            )
        return "\n\n".join(parts)


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _extract_spec_section0(spec_text: str) -> str:
    """Extract the prose body of '## 0. High-level Description' from a spec file.

    Returns the concatenated non-heading lines of that section, or '' if not found.
    """
    lines = spec_text.splitlines()
    in_section = False
    body: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## 0"):
            in_section = True
            continue
        if in_section:
            if stripped.startswith("## "):
                break
            if stripped in ("---", ""):
                if not body:
                    continue
            body.append(stripped)
    return " ".join(body).strip()


def _extract_description(spl_source: str, fallback_name: str) -> str:
    """Extract a description from a .spl file's leading comment or WORKFLOW name."""
    for line in spl_source.splitlines():
        stripped = line.strip()
        if stripped.startswith("--") and len(stripped) > 2:
            desc = stripped.lstrip("- ").strip()
            if len(desc) > 10:   # skip trivial one-word comments
                return desc
    # Fall back to workflow name as description
    import re
    m = re.search(r"WORKFLOW\s+(\w+)", spl_source, re.IGNORECASE)
    name = m.group(1) if m else fallback_name
    return name.replace("_", " ")
