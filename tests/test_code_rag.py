"""Tests for CodeRAGStore.

Run: pytest tests/test_code_rag.py -v
"""
import pytest
from pathlib import Path

COOKBOOK_DIR = Path(__file__).parent.parent / "cookbook" / "code_pipeline"


class TestCodeRAGStore:

    def test_add_pair_and_retrieve(self, tmp_path):
        pytest.importorskip("dd_vectordb")
        pytest.importorskip("dd_embed")
        from spl3.code_rag import CodeRAGStore

        store = CodeRAGStore(storage_dir=str(tmp_path / "rag"))
        store.add_pair(
            description="generate Python code from a spec",
            spl_source="WORKFLOW generate_code INPUT: @spec TEXT DO ... END",
        )
        results = store.retrieve("write Python code", top_k=1)
        assert len(results) == 1
        assert "generate" in results[0]["description"]
        assert results[0]["score"] > 0

    def test_seed_from_dir(self, tmp_path):
        pytest.importorskip("dd_vectordb")
        pytest.importorskip("dd_embed")
        if not COOKBOOK_DIR.exists():
            pytest.skip("cookbook directory not found")
        from spl3.code_rag import CodeRAGStore

        store = CodeRAGStore(storage_dir=str(tmp_path / "rag"))
        count = store.seed_from_dir(COOKBOOK_DIR)
        assert count >= 3
        assert store.count() >= 3

    def test_format_examples(self, tmp_path):
        pytest.importorskip("dd_vectordb")
        pytest.importorskip("dd_embed")
        from spl3.code_rag import CodeRAGStore

        store = CodeRAGStore(storage_dir=str(tmp_path / "rag"))
        store.add_pair(
            description="review code for quality issues",
            spl_source="WORKFLOW review_code INPUT: @code TEXT DO ... END",
        )
        block = store.format_examples("review code", top_k=1)
        assert "review_code" in block or "review code" in block.lower()

    def test_retrieve_empty_store(self, tmp_path):
        pytest.importorskip("dd_vectordb")
        pytest.importorskip("dd_embed")
        from spl3.code_rag import CodeRAGStore

        store = CodeRAGStore(storage_dir=str(tmp_path / "rag"))
        results = store.retrieve("any query", top_k=3)
        assert results == []

    def test_count(self, tmp_path):
        pytest.importorskip("dd_vectordb")
        pytest.importorskip("dd_embed")
        from spl3.code_rag import CodeRAGStore

        store = CodeRAGStore(storage_dir=str(tmp_path / "rag"))
        assert store.count() == 0
        store.add_pair("desc 1", "WORKFLOW wf1 DO END")
        store.add_pair("desc 2", "WORKFLOW wf2 DO END")
        assert store.count() == 2
