# arXiv Morning Brief — Recipe Spec

**Status:** Draft v1.0 (2026-03-31)
**Intended builder:** separate session
**Critic sign-off:** yes

---

## 1. Overview

A daily workflow that:
1. Downloads a list of arXiv PDFs (today's or a supplied date)
2. Semantically chunks each PDF into plan-sized sections
3. Summarizes each chunk with an LLM, then reduces to a per-paper abstract
4. Aggregates all per-paper abstracts into a single morning brief

Output is Markdown, suitable for piping to a file, a Slack webhook, or an email.

---

## 2. File Structure

```
cookbook/arxiv_morning_brief/
├── spec.md                      ← this file
├── arxiv_morning_brief.spl      ← top-level orchestrator workflow
├── summarize_paper.spl          ← per-paper sub-workflow
├── tools.py                     ← Python tool implementations
└── tests/
    ├── fixtures/
    │   ├── sample.pdf           ← small real PDF (≤ 5 pages) for unit tests
    │   └── expected_chunks.json ← expected chunk count / structure
    ├── test_tools.py
    └── test_workflow.py
```

---

## 3. Workflow Signatures

### 3.1 `summarize_paper` (sub-workflow)

```sql
WORKFLOW summarize_paper
    INPUT:  @pdf_url TEXT,
            @max_tokens INT DEFAULT 512
    OUTPUT: @paper_summary TEXT
DO
    -- download PDF bytes (dd-extract handles the fetch)
    CALL download_arxiv_pdf(@pdf_url) INTO @pdf_path

    -- get structural chunk plan (header/paragraph-based, NOT embedding-based)
    CALL semantic_chunk_plan(@pdf_path) INTO @chunks

    @summaries := []
    @i := 0
    WHILE @i < list_count(@chunks) DO
        @chunk := get_item(@chunks, @i)
        GENERATE chunk_summarizer(@chunk, @max_tokens) INTO @summary
        @summaries := list_append(@summaries, @summary)
        @i := @i + 1
    END

    -- reduce all chunk summaries to one paper abstract
    GENERATE paper_reducer(@summaries) INTO @paper_summary
    COMMIT @paper_summary
END
```

### 3.2 `arxiv_morning_brief` (orchestrator)

```sql
IMPORT 'summarize_paper.spl'

WORKFLOW arxiv_morning_brief
    INPUT:  @urls  TEXT,         -- JSON array of arXiv PDF URLs
            @date  TEXT DEFAULT '',
            @brief_tokens INT DEFAULT 1024
    OUTPUT: @brief TEXT
DO
    @header := build_brief_date_header(@date)
    @paper_summaries := []
    @i := 0

    WHILE @i < list_count(@urls) DO
        @url := get_item(@urls, @i)
        DO
            CALL summarize_paper(@url) INTO @summary
            @paper_summaries := list_append(@paper_summaries, @summary)
            EXCEPTION WHEN RefusalToAnswer THEN
                LOGGING 'Skipping ' || @url || ': refused' LEVEL WARN
            EXCEPTION WHEN ToolError THEN
                LOGGING 'Skipping ' || @url || ': tool error' LEVEL WARN
        END
        @i := @i + 1
    END

    GENERATE brief_writer(@header, @paper_summaries, @brief_tokens) INTO @brief
    COMMIT @brief
END
```

> **Momagrid dispatch** — run with parallel sub-workflow dispatch:
> ```bash
> spl3 run arxiv_morning_brief.spl \
>     --adapter momagrid --hub http://momagrid-lan:8080 \
>     --param urls='["https://arxiv.org/pdf/2501.00001","https://arxiv.org/pdf/2501.00002"]' \
>     --param date='2026-03-31'
> ```

---

## 4. Tool Interface (`tools.py`)

All six functions are registered as SPL tools via `@spl_tool` (or equivalent dd-* decorator).

### 4.1 `download_arxiv_pdf(url: str) -> str`

- **Purpose:** Download a PDF from arXiv and return the local path.
- **Rate limit:** 3-second sleep between calls to respect arXiv ToS.
- **Caching:** Cache by URL using `dd-cache` (TTL = 24 h). If cached path still exists on disk, return immediately without sleeping or downloading.
- **Returns:** Absolute path string to the downloaded `.pdf` file.
- **Raises:** `ToolError` if HTTP status is not 200.

```python
def download_arxiv_pdf(url: str) -> str:
    """Download arXiv PDF with caching and rate limiting."""
    ...
```

### 4.2 `semantic_chunk_plan(pdf_path: str) -> str`

- **Purpose:** Parse the PDF and return a JSON array of chunk dicts.
- **Method:** Uses `dd-extract` structural chunker (header/paragraph boundaries, NOT embedding-based).
- **Returns:** JSON string — `[{"title": str, "text": str, "page": int}, ...]`
- **Min chunks:** 1 (single-section paper is valid).
- **Raises:** `ToolError` if pdf_path does not exist or dd-extract fails.

```python
def semantic_chunk_plan(pdf_path: str) -> str:
    """Return JSON array of structural chunks from PDF."""
    ...
```

### 4.3 `list_count(json_list: str) -> int`

- **Purpose:** Return `len(json.loads(json_list))`.
- **Why in tools.py:** SPL has no built-in `len()`. Keep it trivial.

### 4.4 `get_item(json_list: str, index: int) -> str`

- **Purpose:** Return `json.loads(json_list)[index]` as a JSON string (or plain string if element is already a string).
- **Raises:** `ToolError` on IndexError.

### 4.5 `list_append(json_list: str, item: str) -> str`

- **Purpose:** Return `json.dumps(json.loads(json_list) + [item])`.
- **Pure/functional** — does not mutate.

### 4.6 `build_brief_date_header(date: str) -> str`

- **Purpose:** Return a Markdown H1 header string.
- **Logic:** If `date` is empty, use today's date (`datetime.date.today()`).
- **Returns:** e.g. `"# arXiv Morning Brief — 2026-03-31\n\n"`

---

## 5. LLM Function Definitions

All three are `CREATE FUNCTION` blocks to be defined inline or in a shared `functions.spl`.

### 5.1 `chunk_summarizer`

```sql
CREATE FUNCTION chunk_summarizer(@chunk TEXT, @max_tokens INT)
RETURNS TEXT
AS $$
    PROMPT chunk_sum
        SELECT system_role('You are a technical summarizer. Produce a concise summary
                            of the provided research paper section in plain English.
                            Focus on methods and findings.')
        SELECT @chunk AS content
        GENERATE llm(chunk_sum) WITH output_budget=@max_tokens
$$;
```

### 5.2 `paper_reducer`

```sql
CREATE FUNCTION paper_reducer(@summaries TEXT)
RETURNS TEXT
AS $$
    PROMPT reduce
        SELECT system_role('You are a research editor. Given a list of section summaries
                            from a single paper, write a 150-word abstract that captures
                            the core contribution, method, and key results.')
        SELECT @summaries AS content
        GENERATE llm(reduce) WITH output_budget=200
$$;
```

### 5.3 `brief_writer`

```sql
CREATE FUNCTION brief_writer(@header TEXT, @summaries TEXT, @tokens INT)
RETURNS TEXT
AS $$
    PROMPT brief
        SELECT system_role('You are a technical newsletter editor. Format the provided
                            paper abstracts into a clean Markdown morning brief.
                            Each paper gets a ### heading and 2-3 sentence summary.
                            End with a "Key Themes" section.')
        SELECT @header || @summaries AS content
        GENERATE llm(brief) WITH output_budget=@tokens
$$;
```

---

## 6. Data Flow

```
[urls JSON array]
      │
      ▼  (WHILE loop, one URL at a time)
download_arxiv_pdf(url)          ← dd-cache + rate limit
      │
      ▼
semantic_chunk_plan(pdf_path)    ← dd-extract structural chunker
      │  [chunks JSON array]
      ▼  (WHILE loop per chunk)
GENERATE chunk_summarizer()      ← LLM per chunk, output_budget=512
      │  [summaries JSON array]
      ▼
GENERATE paper_reducer()         ← LLM, reduces N summaries → 1 abstract
      │  @summary per paper
      ▼
GENERATE brief_writer()          ← LLM, formats full brief
      │
      ▼
COMMIT @brief                    ← final Markdown output
```

---

## 7. Testing Strategy

### Level 1 — Unit tests (`test_tools.py`)

| Test | What it checks |
|------|---------------|
| `test_download_cached` | Second call returns cached path without network |
| `test_download_rate_limit` | Two uncached calls take ≥ 3s combined |
| `test_semantic_chunk_plan_fixture` | Fixture PDF yields ≥ 1 chunk, each has `title`/`text`/`page` |
| `test_list_helpers` | `list_count`, `get_item`, `list_append` correctness |
| `test_build_header_today` | Empty date → today's ISO date in header |
| `test_build_header_explicit` | `date='2026-01-01'` → correct header |

### Level 2 — Workflow dry-run (`test_workflow.py`)

Mock all tools and LLM calls. Load `summarize_paper.spl` and `arxiv_morning_brief.spl` via `load_workflows_from_file`. Run with fixture URLs. Assert:
- `@brief` is non-empty Markdown
- Skips gracefully when `download_arxiv_pdf` raises `ToolError`
- Skips gracefully when LLM raises `RefusalToAnswer`

### Level 3 — Integration (manual / CI nightly)

Run against 2 real arXiv URLs. Assert output length > 200 chars. Gate on `ARXIV_INTEGRATION=1` env var.

---

## 8. Dependencies

| Package | Why |
|---------|-----|
| `spl-llm>=2.0.0` | SPL20 base (lexer, parser, executor) |
| `spl3>=0.1.0` | SPL30 runtime, CALL PARALLEL, IMPORT |
| `dd-extract` | Structural PDF chunking |
| `dd-cache` | URL-keyed download cache |
| `dd-llm` | LLM adapter (Liquid AI LFM or OpenAI fallback) |
| `requests` | PDF download |
| `pytest` | Test runner |

---

## 9. Open Questions for the Builder

1. **Parallel per-paper dispatch:** Should `summarize_paper` sub-workflows be dispatched via `CALL PARALLEL` once the paper list is known? The current spec uses a WHILE loop (sequential). Parallel is better for Momagrid but needs a list → branch fan-out pattern not yet in SPL30. Flag for SPL 3.1.

2. **arXiv list discovery:** The spec assumes the caller supplies `@urls`. A future enhancement: `fetch_arxiv_listings(category, date)` tool that hits the arXiv API and returns that day's paper URLs automatically.

3. **dd-extract version:** Confirm `semantic_chunk_plan` uses the paragraph-structural chunker, not the sentence-embedding chunker. The two are separate backends in dd-extract.

4. **Output routing:** COMMIT writes to stdout by default. For Slack/email delivery, the orchestrating script should capture stdout and pipe it. A `STORE RESULT IN` clause or a `notify_slack(brief)` tool call could be added as a post-commit step.

5. **Token budget tuning:** `chunk_summarizer` default is 512 tokens. Papers with 20+ sections will accumulate 10K+ tokens before `paper_reducer`. Consider a hard cap of 10 chunks per paper or a `max_chunks` parameter.

---

## 10. Example Output (abbreviated)

```markdown
# arXiv Morning Brief — 2026-03-31

### Efficient Attention via Sparse Routing (2501.00001)
This paper proposes a sparse routing mechanism that reduces attention complexity
from O(n²) to O(n log n) for sequences up to 128K tokens. Evaluated on LongBench,
the method matches dense attention within 0.3% while reducing GPU memory by 40%.

### Multimodal Grounding with Liquid Foundation Models (2501.00002)
The authors demonstrate that Liquid Foundation Models (LFMs) achieve competitive
zero-shot image-text grounding without vision-specific pretraining, leveraging
their continuous-time state space for pixel-level alignment.

## Key Themes
- Memory-efficient long-context transformers remain an active frontier.
- LFMs are gaining traction as unified multimodal architectures.
```
