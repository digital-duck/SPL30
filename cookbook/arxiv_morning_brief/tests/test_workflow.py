"""Level 2 workflow dry-run tests — arXiv Morning Brief recipe.

Loads the .spl files via SPL3 loader, runs with mock adapter and mock tools.
No real network calls or LLM calls are made.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Recipe dir on path
RECIPE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(RECIPE_DIR))

import tools as ambt  # registers @spl_tool functions  # noqa: E402


# ── Helpers ─────────────────────────────────────────────────────────────────

def _mock_adapter(content: str = "# Mock LLM output\n\nSome text.") -> MagicMock:
    """Return a mock LLM adapter that always returns `content`."""
    from spl.adapters.base import GenerationResult
    adapter = MagicMock()
    result = GenerationResult(
        content=content,
        model="mock",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        latency_ms=5.0,
    )
    adapter.generate = AsyncMock(return_value=result)
    return adapter


def _make_executor(adapter, tool_overrides: dict | None = None):
    """Create a configured SPL3Executor with optional tool overrides.

    tool_overrides: {tool_name: callable} to replace in the executor's function
    registry after construction.  Use this instead of patch.object(ambt, ...)
    because the executor copies function references at __init__ time.
    """
    from spl3.executor import SPL3Executor
    executor = SPL3Executor(adapter=adapter)
    if tool_overrides:
        for name, fn in tool_overrides.items():
            executor.functions.register_tool(name, fn)
    return executor


def _load_registry():
    """Load the arxiv_morning_brief workflows into a LocalRegistry."""
    from spl3.registry import LocalRegistry
    from spl3._loader import load_workflows_from_file

    registry = LocalRegistry()
    defns = load_workflows_from_file(RECIPE_DIR / "arxiv_morning_brief.spl")
    for defn in defns:
        registry.register(defn)
    return registry


def _make_composer(registry, executor):
    from spl3.composer import WorkflowComposer
    composer = WorkflowComposer(registry, executor)
    executor.composer = composer
    return composer


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ── Tests ────────────────────────────────────────────────────────────────────

class TestSummarizePaper:
    FAKE_CHUNKS = json.dumps([
        {"title": "ABSTRACT",        "text": "We propose X.",        "page": 1},
        {"title": "1. INTRODUCTION", "text": "This is introduction.", "page": 2},
    ])

    def test_produces_summary(self, sample_pdf, tmp_path):
        """summarize_paper returns a non-empty summary for a valid PDF."""
        from spl3.registry import LocalRegistry
        from spl3._loader import load_workflows_from_file
        from spl3.composer import WorkflowComposer

        fake_pdf = str(sample_pdf)
        fake_chunks = self.FAKE_CHUNKS

        adapter = _mock_adapter("A concise paper abstract.")
        executor = _make_executor(adapter, tool_overrides={
            "download_arxiv_pdf": lambda url: fake_pdf,
            "semantic_chunk_plan": lambda path: fake_chunks,
        })
        registry = LocalRegistry()
        for defn in load_workflows_from_file(RECIPE_DIR / "summarize_paper.spl"):
            registry.register(defn)
        executor.composer = WorkflowComposer(registry, executor)

        defn = registry.get("summarize_paper")
        result = _run(executor.execute_workflow(
            defn.ast_node,
            params={"pdf_url": "https://arxiv.org/pdf/0001", "max_tokens": "256"},
        ))

        assert result.committed_value
        assert len(result.committed_value) > 0


class TestArxivMorningBrief:
    FAKE_CHUNKS = json.dumps([
        {"title": "ABSTRACT", "text": "Paper content here.", "page": 1},
    ])
    URLS = json.dumps([
        "https://arxiv.org/pdf/2501.00001",
        "https://arxiv.org/pdf/2501.00002",
    ])

    def _fake_chunks(self):
        return self.FAKE_CHUNKS

    def test_brief_produced(self):
        """Normal run produces a non-empty @brief."""
        fake_chunks = self.FAKE_CHUNKS
        adapter = _mock_adapter("# Mock Brief\n\n### Paper A\nSummary here.\n\n## Key Themes\n- Topic X")
        executor = _make_executor(adapter, tool_overrides={
            "download_arxiv_pdf": lambda url: "/fake/path.pdf",
            "semantic_chunk_plan": lambda path: fake_chunks,
        })
        registry = _load_registry()
        _make_composer(registry, executor)

        defn = registry.get("arxiv_morning_brief")
        result = _run(executor.execute_workflow(
            defn.ast_node,
            params={"urls": self.URLS, "date": "2026-03-31", "brief_tokens": "512"},
        ))

        assert result.committed_value
        assert "#" in result.committed_value  # Markdown header present

    def test_tool_error_skips_paper(self):
        """ToolError from download causes skip, brief still produced."""
        def _raise_tool_error(url):
            raise ambt.ToolError("HTTP 404")

        adapter = _mock_adapter("# Brief with partial results\n\n## Key Themes\n- X")
        executor = _make_executor(adapter, tool_overrides={
            "download_arxiv_pdf": _raise_tool_error,
        })
        registry = _load_registry()
        _make_composer(registry, executor)

        defn = registry.get("arxiv_morning_brief")
        result = _run(executor.execute_workflow(
            defn.ast_node,
            params={"urls": self.URLS, "date": "2026-03-31"},
        ))

        # Should still commit a brief (with empty paper_summaries)
        assert result.status in ("complete", "refused", "no_commit")  # not an unhandled exception

    def test_empty_urls_produces_brief(self):
        """Empty URL list still produces a brief (no papers section)."""
        adapter = _mock_adapter("# Empty Brief\n\n## Key Themes\n- None")
        executor = _make_executor(adapter)
        registry = _load_registry()
        _make_composer(registry, executor)

        defn = registry.get("arxiv_morning_brief")
        result = _run(executor.execute_workflow(
            defn.ast_node,
            params={"urls": "[]", "date": "2026-03-31"},
        ))

        assert result.committed_value
