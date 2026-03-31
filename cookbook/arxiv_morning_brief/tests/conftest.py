"""Shared fixtures for arXiv Morning Brief tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

# Ensure SPL20 and SPL30 packages are importable, even when pytest is run
# from within the SPL30 tree.  These paths are added only if not already present.
_SPL20_PATH = str(Path(__file__).parent.parent.parent.parent.parent / "SPL20")
_SPL30_PATH = str(Path(__file__).parent.parent.parent.parent.parent / "SPL30")
for _p in (_SPL20_PATH, _SPL30_PATH):
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory) -> Path:
    """Create a minimal 2-page PDF with section headers for testing.

    Uses pypdf PdfWriter to create blank pages — text extraction will
    return empty string, so tests that need real text should mock
    PDFExtractor.from_file directly.
    """
    try:
        from pypdf import PdfWriter
    except ImportError:
        pytest.skip("pypdf not installed")

    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)

    pdf_path = tmp_path_factory.mktemp("fixtures") / "sample.pdf"
    with open(pdf_path, "wb") as f:
        writer.write(f)
    return pdf_path


@pytest.fixture(scope="session")
def sample_chunks_json() -> str:
    """Known structured chunk output for use in workflow dry-run mocks."""
    chunks = [
        {"title": "ABSTRACT",        "text": "We propose a novel method.",    "page": 1},
        {"title": "1. INTRODUCTION", "text": "This is the introduction.",      "page": 2},
        {"title": "2. METHODS",      "text": "We use the following approach.", "page": 3},
    ]
    return json.dumps(chunks)
