# New SPL Recipes from PocketFlow Cookbook

Candidate recipes identified from the PocketFlow cookbook (35 approved, tested on ollama/gemma3
and claude_cli) that fill gaps in the current SPL cookbook.

Source: `~/projects/wgong/PocketFlow/cookbook/`
SPL cookbook: `~/projects/digital-duck/SPL30/cookbook/`

---

## SPL Recipe Generation Pipeline

For each candidate below, follow this pipeline:

```
1. splc describe  <pocketflow-dir>          →  <name>-spec.md
2. text2spl       <name>-spec.md (§0)       →  <name>.spl   (review / refine / test)
3. splc compile   <name>.spl --target python/pocketflow  →  <name>.py
4. validate       <name>.py                 →  unit tests / smoke run
5. spl judge      original.py  vs  <name>.spl + <name>.py  →  NDD closure score
```

Step 1 uses `splc describe` to reverse-engineer a spec from the original PocketFlow recipe.
Step 2 uses `text2spl` with the Section 0 (problem description) to generate the `.spl` script.
Step 5 is the NDD closure test — the LLM judge compares outputs of the original PocketFlow
recipe (oracle) against the SPL-generated `.spl` and compiled `.py` to measure round-trip fidelity.

---

## Tier 1 — Priority (fill clear SPL gaps)

| ID | PocketFlow Recipe | SPL ID | Category | Gap filled |
|----|-------------------|--------|----------|------------|
| 04 | pocketflow-agentic-rag | 65 | retrieval | SPL has no RAG recipe |
| 40 | pocketflow-rag | 66 | retrieval | Simple RAG baseline to pair with agentic-rag |
| 47 | pocketflow-thinking | 67 | reasoning | Chain-of-thought / extended thinking |
| 16 | pocketflow-debate | 68 | reasoning | Multi-perspective adversarial reasoning |
| 27 | pocketflow-judge | 69 | reasoning | LLM-as-judge — directly useful for SPL benchmark scoring |
| 46 | pocketflow-text2sql | 70 | application | TEXT→SQL modality missing from SPL |
| 51 | pocketflow-tool-pdf-vision | 71 | multimodal | PDF+vision→TEXT bridges PF tools with SPL multimodal |
| 32 | pocketflow-mcp | 72 | tool | MCP integration — growing ecosystem, strategic fit |

---

## Tier 2 — Good additions (enrich agentic / batch coverage)

| ID | PocketFlow Recipe | SPL ID | Category | Notes |
|----|-------------------|--------|----------|-------|
| 02 | pocketflow-agent | 73 | agentic | Baseline web-search agent — SPL has code pipeline but no general agent |
| 44 | pocketflow-supervisor | 74 | multi-agent | Supervisor quality-gate pattern |
| 38 | pocketflow-parallel-batch | 75 | batch | Async parallel template — SPL has parallel code review but no general batch |
| 13 | pocketflow-code-generator | 76 | agentic | Complements SPL's existing code pipeline (recipe 50) |
| 17 | pocketflow-deep-research | 77 | agentic | Multi-step research loop — good complex agentic benchmark |
| 50 | pocketflow-tool-embeddings | 78 | tool | Embeddings — foundational for RAG and semantic search |

---

## Tier 3 — Optional / niche

| ID | PocketFlow Recipe | SPL ID | Category | Notes |
|----|-------------------|--------|----------|-------|
| 01 | pocketflow-a2a | 79 | multi-agent | A2A protocol — forward-looking, complex to port |
| 45 | pocketflow-tao | 80 | reasoning | Deep reasoning loop — interesting but slow |
| 43 | pocketflow-structured-output | 81 | application | Useful but overlaps existing SPL patterns |
| 35 | pocketflow-newsletter | 82 | application | Fun demo, narrower use case |

---

## Status Tracking

| SPL ID | PocketFlow Source | spec.md | .spl | compile | validate | judge | Notes |
|--------|-------------------|---------|------|---------|----------|-------|-------|
| 65 | pocketflow-agentic-rag | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 66 | pocketflow-rag | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 67 | pocketflow-thinking | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 68 | pocketflow-debate | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 69 | pocketflow-judge | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 70 | pocketflow-text2sql | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 71 | pocketflow-tool-pdf-vision | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 72 | pocketflow-mcp | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 73 | pocketflow-agent | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 74 | pocketflow-supervisor | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 75 | pocketflow-parallel-batch | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 76 | pocketflow-code-generator | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 77 | pocketflow-deep-research | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 78 | pocketflow-tool-embeddings | [ ] | [ ] | [ ] | [ ] | [ ] | |
| 79 | pocketflow-a2a | [ ] | [ ] | [ ] | [ ] | [ ] | tier 3 |
| 80 | pocketflow-tao | [ ] | [ ] | [ ] | [ ] | [ ] | tier 3 |
| 81 | pocketflow-structured-output | [ ] | [ ] | [ ] | [ ] | [ ] | tier 3 |
| 82 | pocketflow-newsletter | [ ] | [ ] | [ ] | [ ] | [ ] | tier 3 |

---

## References

- PocketFlow cookbook catalog: `~/projects/wgong/PocketFlow/cookbook/cookbook_catalog.json`
- SPL cookbook catalog: `~/projects/digital-duck/SPL30/cookbook/cookbook_catalog.json`
- PocketFlow test logs: `~/projects/wgong/PocketFlow/cookbook/logs/`
- SPL pipeline docs: `~/projects/digital-duck/SPL30/docs/SPL-by-spec.md`
