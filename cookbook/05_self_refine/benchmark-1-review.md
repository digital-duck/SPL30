# Benchmark 1 Review — Self-Refine Pattern
## SPL 3.0 · Ollama local models vs Claude Sonnet 4.6 via claude_cli

**Task:** "What are the benefits of meditation?"  
**Pattern:** draft → critique → (refine → critique)* → final  
**Max iterations:** 3  
**Date:** 2026-04-11

---

## Run Summary

| Model | Adapter | LLM Calls | Latency | Iterations | Exit condition |
|-------|---------|-----------|---------|------------|----------------|
| claude-sonnet-4-6 | claude_cli | 2 | 81s | 1 | `[APPROVED]` after first critique |
| llama3.2 | ollama | 2 | 69s | 1 | `[APPROVED]` after first critique |
| gemma3 | ollama | 2 | 125s | 1 | `[APPROVED]` after first critique |
| gemma4:e2b | ollama | 2 | 121s | 1 | `[APPROVED]` after first critique |
| gemma4:e4b | ollama | 7 | 1154s (~19 min) | 3 | max_iterations reached |

**Note:** All Ollama models ran on consumer-grade local GPU. Claude ran via the `claude_cli` adapter (Claude Code subscription, no API cost per call).

---

## Quality Assessment

### 1. claude-sonnet-4-6 — Exceptional

The gold standard for this run. Produced a **1,600+ word structured article** on the first draft with:
- Named research citations (JAMA Internal Medicine, Clifford Saron's 7-year follow-up, Lindahl et al. 2017)
- Careful evidence qualification — distinguishing well-replicated findings from preliminary ones
- Sections on cognitive aging, relational benefits, spiritual/existential dimensions
- Strong closing argument: *"The question is no longer whether meditation works. The question is why more people are not doing it."*

The critic issued `[APPROVED]` immediately. First draft was final draft. This sets the ceiling for what the self-refine pattern can produce.

**Weakness:** None at this task complexity. At harder tasks (code generation, multi-step reasoning) the gap with local models would be larger.

---

### 2. gemma4:e4b — Best local model, highest self-standard

The most interesting run. gemma4:e4b was the **only local model that never approved its own output** — it ran all 3 iterations and still hit `max_iterations`. The critic kept finding genuine, substantive issues each round:

- Round 1 feedback: sharpen the introduction hook, add simplified analogies for technical terms, improve section transitions
- Round 2 feedback: strengthen the conclusion, ensure parallel structure in bullet points, add bridging sentences

The final output is the richest of the local models — emoji-decorated section headers, good depth on neuroplasticity and the Default Mode Network, engaging prose style. But the model's own critic was never satisfied with it.

**Key insight:** gemma4:e4b has the strongest self-critical faculty of the local models — it applies a higher standard than its peers. This is a double-edged sword: better final quality, but 19 minutes of wall-clock time and 7 LLM calls. The same self-critical capacity that makes it improve is what prevents it from approving.

**Latency note:** Each critique call took ~100s; the final critique took 141s. The model is slow on this hardware at e4b size.

---

### 3. gemma4:e2b — Sweet spot for local use

Produced a **well-structured, professional article** on the first draft:
- Clean section headers with numbered subsections
- Dedicated "Mechanism" section explaining neuroplasticity, prefrontal cortex, amygdala, Default Mode Network
- Solid conclusion that reframes what meditation is (*"changing the relationship we have with our thoughts"*)
- Immediate `[APPROVED]`

For a 2B-parameter model running locally, this is impressive. The output is meaningfully better than llama3.2 and comparable in structure (if not depth) to gemma3. The 2-minute latency is workable for interactive use.

**Weakness:** Claims are stated with uniform confidence regardless of evidence strength — the kind of calibration that sonnet does naturally is absent. No citations.

---

### 4. gemma3 — Competent, wellness-brochure tone

Produced a readable, well-formatted article with science-backed framing. Covers the right ground: stress, cognitive enhancement, physical health, emotional regulation, getting started. The critique noted 7 specific improvements but then appended `[APPROVED]` — suggesting the critic views these as nice-to-haves rather than essential fixes.

The output reads like a polished wellness magazine piece. Accurate, accessible, but no citations and no nuance on evidence quality. The section "The Science-Backed Benefits: A Holistic Approach" promises more rigour than it delivers.

**Interesting behaviour:** The critic feedback included `[APPROVED]` at the end of a numbered critique list — a hedge that says "these are improvements but the article is already good enough." This is a softer standard than gemma4:e4b's critic.

---

### 5. llama3.2 — Functional but thin

Produced a **10-section numbered list** rather than a prose article. The content is accurate but shallow — each section is 2-3 sentences with no depth, no citations, and significant repetition (gray matter appears in both section 4 and section 8). The critique identified all of this correctly: no thesis, abrupt transitions, overlapping paragraphs, no concrete examples.

Then approved it anyway.

This is the clearest example of the **weak self-critique problem**: the model can identify what's wrong but applies a low bar for "good enough." The self-refine loop cannot improve what the critic is willing to accept.

**Practical implication:** llama3.2 at its current size is better suited as a fast reasoning component (routing, classification, tool use) than as a writer or quality judge.

---

## Cross-Model Observations

### 1. Self-critique calibration varies widely — and it matters more than raw output quality

The self-refine pattern only works as well as the critic. llama3.2 and gemma3 both approved mediocre outputs on the first pass. gemma4:e4b never approved its own output even after 3 refinements. Sonnet approved a genuinely excellent first draft.

The critic's standard is the binding constraint. A weak critic produces early exits regardless of output quality. A strong critic produces better outputs but more iterations and longer latency.

### 2. Gemma4 represents a meaningful capability step for local models

gemma4:e2b at 2B parameters produces output quality that would have required a much larger model a year ago. gemma4:e4b's self-critique faculty is qualitatively different from llama3.2 and gemma3 — it finds genuine structural issues rather than surface suggestions. This is the story for the blog: Gemma4 changes what's possible on consumer hardware.

### 3. Latency reality check

| Model | Per-call average |
|-------|-----------------|
| claude-sonnet-4-6 | ~40s |
| llama3.2 | ~35s |
| gemma3 | ~63s |
| gemma4:e2b | ~60s |
| gemma4:e4b | ~165s |

Local models at e4b size are slow on single consumer GPU. For interactive agentic workflows, gemma4:e2b is the better choice — comparable quality ceiling at ~3× the speed of e4b.

### 4. The `CREATE FUNCTION` bug (fixed mid-run)

Run 1 (sonnet, logs-spl-claude_cli-sonnet) used the generic `Task:/Input N:` fallback prompt because `CREATE FUNCTION` definitions were not being registered before `execute_workflow()` was called. The model still produced usable output, but the full function template (`You are a professional writer...`) was not being applied.

Run 2 (sonnet, logs-spl-claude_cli-sonnet-2) used the fixed code. The prompt log correctly shows `You are a professional writer. Write a comprehensive article on the topic below.` — and the output quality jumped visibly. **All Ollama benchmark runs also benefited from the fix**, as benchmark-1.sh ran after the fix was applied.

---

## What's Missing from This Benchmark

1. **Writer ≠ Critic** — all runs used the same model for both roles. A stronger critic (e.g. gemma4:e4b) paired with a faster writer (gemma4:e2b) might give better quality/latency tradeoff.

2. **Harder tasks** — "benefits of meditation" is a well-worn topic every model has seen extensively in training. A novel or domain-specific task would better differentiate the models.

3. **LangGraph baseline** — the same experiment via LangGraph will confirm that the pattern (not the framework) is what drives results, and will give a reproducible reference for the blog post.

4. **Token counts** — latency is captured but input/output token counts per call are not surfaced in the current logs. These would let us compute tokens/second per model for a cleaner hardware benchmark.

---

## Verdict

**For production local AI today:** gemma4:e2b is the pragmatic choice — good quality, 2-minute total latency, consumer GPU.

**For best local quality:** gemma4:e4b if you have the patience — richer output, stronger self-critique, but 19 minutes per run.

**The Gemma4 story:** Even the smallest Gemma4 variant (e2b) surpasses llama3.2 on this task in structure, depth, and self-critique quality. The gap between cloud (sonnet) and local (gemma4:e4b) is real but narrowing. That's the headline.
