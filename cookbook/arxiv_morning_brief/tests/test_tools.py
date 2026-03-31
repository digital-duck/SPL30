"""Level 1 unit tests for tools.py — arXiv Morning Brief recipe."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add the recipe dir to path so we can import tools.py directly
sys.path.insert(0, str(Path(__file__).parent.parent))
import tools as ambt  # noqa: E402


class TestDownloadArxivPdf:
    def test_download_cached(self, tmp_path):
        """Cache hit returns path without making a network request."""
        fake_path = str(tmp_path / "fake.pdf")
        Path(fake_path).write_bytes(b"%PDF-1.4")  # file must exist on disk

        with patch.object(ambt._url_cache, "get", return_value=fake_path):
            with patch("httpx.get") as mock_get:
                result = ambt.download_arxiv_pdf("https://arxiv.org/pdf/2501.00001")
                mock_get.assert_not_called()
        assert result == fake_path

    def test_download_rate_limit(self, tmp_path):
        """Two uncached downloads sleep >= 3s apart from each other."""
        # Patch cache to always miss, patch httpx to return dummy content
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.content = b"%PDF-1.4"

        calls: list[float] = []

        def fake_get(url, **kwargs):
            calls.append(time.time())
            return fake_resp

        with patch.object(ambt._url_cache, "get", return_value=None):
            with patch.object(ambt._url_cache, "set"):
                with patch.object(ambt, "_PDF_DIR", tmp_path):
                    with patch("httpx.get", side_effect=fake_get):
                        # Reset last_download so first call has no wait
                        ambt._last_download = 0.0
                        ambt.download_arxiv_pdf("https://arxiv.org/pdf/0001")
                        ambt.download_arxiv_pdf("https://arxiv.org/pdf/0002")

        assert len(calls) == 2
        assert calls[1] - calls[0] >= ambt._RATE_LIMIT_SECS - 0.1  # 100ms tolerance

    def test_http_error_raises_tool_error(self):
        """Non-200 response raises ToolError."""
        fake_resp = MagicMock()
        fake_resp.status_code = 404

        with patch.object(ambt._url_cache, "get", return_value=None):
            with patch("httpx.get", return_value=fake_resp):
                with pytest.raises(ambt.ToolError, match="HTTP 404"):
                    ambt.download_arxiv_pdf("https://arxiv.org/pdf/notfound")


class TestSemanticChunkPlan:
    STRUCTURED_TEXT = (
        "ABSTRACT\n"
        "We propose a novel method for research.\n\n"
        "1. INTRODUCTION\n"
        "This paper introduces an approach.\n\n"
        "2. METHODS\n"
        "We applied the following technique.\n"
    )

    def test_header_based_chunks(self, sample_pdf):
        """Fixture PDF with mocked text yields header-based chunks."""
        with patch("dd_extract.pdf.PDFExtractor.from_file", return_value=self.STRUCTURED_TEXT):
            result = ambt.semantic_chunk_plan(str(sample_pdf))

        chunks = json.loads(result)
        assert len(chunks) >= 2
        for chunk in chunks:
            assert "title" in chunk
            assert "text"  in chunk
            assert "page"  in chunk

    def test_paragraph_fallback(self, sample_pdf):
        """Text with no headers falls back to paragraph-based chunking."""
        text = "First paragraph about something.\n\nSecond paragraph here.\n\nThird paragraph too."
        with patch("dd_extract.pdf.PDFExtractor.from_file", return_value=text):
            result = ambt.semantic_chunk_plan(str(sample_pdf))

        chunks = json.loads(result)
        assert len(chunks) >= 1
        assert all("title" in c and "text" in c and "page" in c for c in chunks)

    def test_missing_pdf_raises_tool_error(self):
        """Non-existent path raises ToolError."""
        with pytest.raises(ambt.ToolError, match="PDF not found"):
            ambt.semantic_chunk_plan("/no/such/file.pdf")

    def test_empty_extraction_raises_tool_error(self, sample_pdf):
        """Empty extraction result raises ToolError."""
        with patch("dd_extract.pdf.PDFExtractor.from_file", return_value="   "):
            with pytest.raises(ambt.ToolError, match="No text extracted"):
                ambt.semantic_chunk_plan(str(sample_pdf))


class TestListHelpers:
    def test_list_count(self):
        assert ambt.list_count('["a","b","c"]') == "3"
        assert ambt.list_count("[]") == "0"
        assert ambt.list_count("bad_json") == "0"

    def test_get_item(self):
        lst = '["apple", "banana", "cherry"]'
        assert ambt.get_item(lst, "0") == "apple"
        assert ambt.get_item(lst, "2") == "cherry"

    def test_get_item_object(self):
        lst = '[{"title":"A","text":"B","page":1}]'
        result = ambt.get_item(lst, "0")
        obj = json.loads(result)
        assert obj["title"] == "A"

    def test_get_item_out_of_range_raises(self):
        with pytest.raises(ambt.ToolError, match="out of range"):
            ambt.get_item('["a"]', "5")

    def test_list_append(self):
        result = ambt.list_append('["a", "b"]', "c")
        assert json.loads(result) == ["a", "b", "c"]

    def test_list_append_empty(self):
        result = ambt.list_append("[]", "x")
        assert json.loads(result) == ["x"]


class TestBuildBriefDateHeader:
    def test_explicit_date(self):
        result = ambt.build_brief_date_header("2026-01-01")
        assert "2026-01-01" in result
        assert result.startswith("# arXiv Morning Brief")
        assert result.endswith("\n\n")

    def test_empty_date_uses_today(self):
        import datetime
        result = ambt.build_brief_date_header("")
        today = datetime.date.today().isoformat()
        assert today in result

    def test_whitespace_date_uses_today(self):
        import datetime
        result = ambt.build_brief_date_header("   ")
        today = datetime.date.today().isoformat()
        assert today in result


class TestParseUrls:
    U1 = "https://arxiv.org/pdf/2501.00001"
    U2 = "https://arxiv.org/pdf/2501.00002"

    def test_json_array_passthrough(self):
        raw = json.dumps([self.U1, self.U2])
        result = json.loads(ambt.parse_urls(raw))
        assert result == [self.U1, self.U2]

    def test_single_url_no_delimiters(self):
        result = json.loads(ambt.parse_urls(self.U1))
        assert result == [self.U1]

    def test_space_delimited(self):
        result = json.loads(ambt.parse_urls(f"{self.U1} {self.U2}"))
        assert result == [self.U1, self.U2]

    def test_comma_delimited(self):
        result = json.loads(ambt.parse_urls(f"{self.U1},{self.U2}"))
        assert result == [self.U1, self.U2]

    def test_comma_space_delimited(self):
        result = json.loads(ambt.parse_urls(f"{self.U1}, {self.U2}"))
        assert result == [self.U1, self.U2]

    def test_file_path(self, tmp_path):
        url_file = tmp_path / "papers.txt"
        url_file.write_text(f"# My papers\n{self.U1}\n{self.U2}\n\n")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = json.loads(ambt.parse_urls("papers.txt"))
        finally:
            os.chdir(old_cwd)
        assert result == [self.U1, self.U2]

    def test_file_ignores_comments_and_blanks(self, tmp_path):
        url_file = tmp_path / "papers.txt"
        url_file.write_text(f"# header\n\n{self.U1}\n# skip this\n{self.U2}\n")
        import os
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = json.loads(ambt.parse_urls("papers.txt"))
        finally:
            os.chdir(old_cwd)
        assert result == [self.U1, self.U2]

    def test_json_array_strips_whitespace(self):
        raw = json.dumps([f"  {self.U1}  ", self.U2])
        result = json.loads(ambt.parse_urls(raw))
        assert result == [self.U1, self.U2]
