"""
tools.py — Python tool implementations for the arXiv Morning Brief recipe.

Register with the SPL executor:

    from spl.tools import load_tools_from_file
    load_tools_from_file("tools.py")

Or import directly so @spl_tool side-effects run:

    import cookbook.arxiv_morning_brief.tools  # noqa: F401
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from spl.executor import SPLWorkflowError
from spl.tools import spl_tool
from dd_cache import DiskCache
from dd_extract.pdf import PDFExtractor

_log = logging.getLogger("arxiv_morning_brief.tools")

# ── Cache and rate-limit state ──────────────────────────────────────────────
_CACHE_DIR = Path.home() / ".cache" / "dd_arxiv_morning_brief"
_PDF_DIR   = _CACHE_DIR / "pdfs"
_PDF_DIR.mkdir(parents=True, exist_ok=True)

_url_cache = DiskCache(str(_CACHE_DIR / "url_cache.db"))

_RATE_LIMIT_SECS = 3.0
_PDF_TTL_SECS    = 86_400  # 24 hours
_last_download: float = 0.0


class ToolError(SPLWorkflowError):
    """Raised when a Python tool encounters a non-recoverable error.

    Caught by EXCEPTION WHEN ToolError THEN in .spl scripts.
    """


# ── Tools ───────────────────────────────────────────────────────────────────

@spl_tool
def download_arxiv_pdf(url: str) -> str:
    """Download an arXiv PDF and return its absolute local path.

    Caches by URL (TTL 24h).  Rate-limits uncached downloads to >= 3s apart.
    Raises ToolError on HTTP error or network failure.
    """
    global _last_download

    # Cache hit: return immediately if the file still exists on disk
    cached_path = _url_cache.get(url)
    if cached_path and Path(cached_path).exists():
        _log.debug("Cache hit %s -> %s", url, cached_path)
        return cached_path

    # Rate limit
    elapsed = time.time() - _last_download
    if elapsed < _RATE_LIMIT_SECS:
        wait = _RATE_LIMIT_SECS - elapsed
        _log.debug("Rate limiting: sleeping %.1fs", wait)
        time.sleep(wait)

    # Download
    import httpx
    try:
        resp = httpx.get(url, timeout=30.0, follow_redirects=True)
    except Exception as e:
        raise ToolError(f"Network error downloading {url}: {e}") from e

    if resp.status_code != 200:
        raise ToolError(f"HTTP {resp.status_code} downloading {url}")

    # Save to disk
    safe_name = url.rstrip("/").split("/")[-1]
    if not safe_name.endswith(".pdf"):
        safe_name += ".pdf"
    pdf_path = str(_PDF_DIR / safe_name)
    Path(pdf_path).write_bytes(resp.content)

    _last_download = time.time()
    _url_cache.set(url, pdf_path, ttl=_PDF_TTL_SECS)
    _log.info("Downloaded %s -> %s", url, pdf_path)
    return pdf_path


@spl_tool
def semantic_chunk_plan(pdf_path: str) -> str:
    """Parse a PDF into structural chunks (header/paragraph-based, NOT embedding).

    Uses dd-extract (pypdf engine) for text extraction, then splits on
    section headers (numbered or ALL-CAPS) or paragraph boundaries.

    Returns a JSON string: [{"title": str, "text": str, "page": int}, ...]
    Raises ToolError if pdf_path does not exist or extraction fails.
    """
    import re

    path = Path(pdf_path)
    if not path.exists():
        raise ToolError(f"PDF not found: {pdf_path}")

    try:
        extractor = PDFExtractor(engine="pypdf", max_chars=40_000)
        text = extractor.from_file(pdf_path)
    except Exception as e:
        raise ToolError(f"dd-extract failed on {pdf_path}: {e}") from e

    if not text.strip():
        raise ToolError(f"No text extracted from {pdf_path}")

    # Try header-based splitting (numbered sections "1. Introduction" or ALL-CAPS)
    header_re = re.compile(
        r'^(?:\d+\.?\s+[A-Z][A-Za-z\s]{2,60}|[A-Z][A-Z\s]{4,60})$',
        re.MULTILINE,
    )
    matches = list(header_re.finditer(text))

    chunks: list[dict] = []

    if len(matches) >= 2:
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            chunk_text = text[m.start():end].strip()
            if chunk_text:
                chunks.append({
                    "title": m.group().strip(),
                    "text":  chunk_text,
                    "page":  i + 1,
                })
    else:
        # Fallback: group paragraphs (3 per chunk)
        paragraphs = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        group_size = 3
        for idx in range(0, len(paragraphs), group_size):
            group = paragraphs[idx: idx + group_size]
            chunks.append({
                "title": f"Section {idx // group_size + 1}",
                "text":  "\n\n".join(group),
                "page":  idx // group_size + 1,
            })

    if not chunks:
        chunks = [{"title": "Document", "text": text.strip(), "page": 1}]

    return json.dumps(chunks)


@spl_tool
def list_count(json_list: str) -> str:
    """Return len(json.loads(json_list)) as a string integer.

    SPL has no built-in len(); use: CALL list_count(@list) INTO @n
    """
    try:
        return str(len(json.loads(json_list)))
    except (json.JSONDecodeError, TypeError):
        return "0"


@spl_tool
def get_item(json_list: str, index: str) -> str:
    """Return json.loads(json_list)[int(index)] as a JSON or plain string.

    Raises ToolError on IndexError.
    Use: CALL get_item(@list, @i) INTO @item
    """
    try:
        lst  = json.loads(json_list)
        item = lst[int(index)]
        return item if isinstance(item, str) else json.dumps(item)
    except IndexError as e:
        raise ToolError(
            f"get_item: index {index} out of range (len={len(json.loads(json_list))})"
        ) from e
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        raise ToolError(f"get_item: {e}") from e


@spl_tool
def list_append(json_list: str, item: str) -> str:
    """Return json.dumps(json.loads(json_list) + [item]). Pure/functional.

    Use: CALL list_append(@list, @item) INTO @list
    """
    try:
        lst = json.loads(json_list)
    except (json.JSONDecodeError, TypeError):
        lst = []
    return json.dumps(lst + [item])


@spl_tool
def parse_urls(raw: str) -> str:
    """Normalise the @urls parameter to a JSON array string.

    Accepts three formats:
      1. JSON array (pass-through):  '["https://...", "https://..."]'
      2. Comma or space delimited:   'https://... https://...'
                                     'https://..., https://...'
      3. File path (relative to CWD, one URL per line):
                                     'my_papers.txt'

    Lines starting with '#' and blank lines are ignored in file mode.
    Returns a JSON array string ready for list_count / get_item.
    """
    import re

    raw = raw.strip()

    # 1. Already a JSON array
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            urls = [u.strip() for u in parsed if str(u).strip()]
            return json.dumps(urls)
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. File path — relative to CWD, must not look like a URL
    if not raw.startswith("http") and not raw.startswith("["):
        candidate = Path.cwd() / raw
        if candidate.is_file():
            lines = candidate.read_text(encoding="utf-8").splitlines()
            urls = [
                ln.strip() for ln in lines
                if ln.strip() and not ln.strip().startswith("#")
            ]
            _log.info("parse_urls: loaded %d URLs from %s", len(urls), candidate)
            return json.dumps(urls)

    # 3. Comma or whitespace delimited string
    urls = [u.strip() for u in re.split(r"[,\s]+", raw) if u.strip()]
    return json.dumps(urls)


@spl_tool
def build_brief_date_header(date: str) -> str:
    """Return a Markdown H1 header string for the morning brief.

    If date is empty, uses today's ISO date.
    Returns e.g. '# arXiv Morning Brief \u2014 2026-03-31\\n\\n'
    """
    import datetime
    if not date or not date.strip():
        date = datetime.date.today().isoformat()
    return f"# arXiv Morning Brief \u2014 {date.strip()}\n\n"
