# Self-Refine LangGraph Benchmark — Run Review

**Date:** 2026-04-11  
**Task:** *"What are the benefits of meditation?"*  
**Max iterations:** 3  
**Framework:** LangGraph (`self_refine_langgraph.py`)  
**Hardware:** Intel mini-PC, Ubuntu 24.04, CPU only (no GPU)

---

## Run Summary

| Model | LLM Calls | Wall Time | Refinements | Exit Condition |
|-------|-----------|-----------|-------------|----------------|
| llama3.2 | 2 | ~13s | 0 | [APPROVED] on first critique |
| gemma3 | 4 | ~4 min | 1 | [APPROVED] on second critique (with 12 suggestions) |
| gemma4:e2b | 8 | ~9 min | 3 | Hit max\_iterations, never approved |
| gemma4:e4b | 8 | ~17 min | 3 | Hit max\_iterations, never approved |

Log directories: `targets/python/langgraph/logs-<model>/`

---

## Per-Model Analysis

### llama3.2 — `logs-llama3.2/`

**Exit:** Approved on the very first critique. `feedback_0.md` contains only `[APPROVED]`.

**Output quality:** A 9-section article, flat prose, no markdown formatting. Accurate but thin and repetitive — "neuroplasticity" and related concepts appear multiple times without development. There is no thesis, just a list of benefits stated as facts.

**Behaviour pattern:** The critic applied essentially no bar. The draft was approved without any suggestion for improvement. This is the fastest exit in the benchmark, but also the most permissive — the critic failed its role.

---

### gemma3 — `logs-gemma3/`

**Exit:** Approved on the second critique, but with an unusual behaviour: `feedback_1.md` lists 12 specific improvement suggestions and then ends with `[APPROVED]`. The critic simultaneously raised substantive concerns and granted approval — an ambiguous stance.

**Output quality (draft_0):** A well-structured article with markdown headers and science-backed framing — cortisol, neuroplasticity, MBSR, CBT. Readable, magazine-quality, clearly better than llama3.2.

**Refinement (draft_0 → draft_1):** `feedback_0.md` gave 6 actionable items. The refinement was genuine: MBSR description gained a mechanism ("teaching participants to observe thoughts without judgment"), the pain management section was expanded, and meditation types were regrouped thematically (focus-based vs. compassion-based). Quality improved measurably.

**The "12 suggestions + [APPROVED]" quirk:** The final critic response is interesting. It identified real issues (generic opener, "alarmingly commonplace" phrasing, insufficient citation specificity, redundancy between sections) but still approved. This suggests the gemma3 critic holds a moderate standard — it can identify weaknesses but doesn't hold itself to correcting them. It shows the tension in self-refine between thoroughness and decisiveness.

---

### gemma4:e2b — `logs-gemma4_e2b/`

**Exit:** Hit `max_iterations=3`. The critic never issued `[APPROVED]` across four critique rounds (feedback_0 through feedback_3).

**Output quality (draft_0):** Immediately professional. Five clearly delineated sections — cognitive clarity, emotional regulation, physical health, mindfulness/self-awareness, compassion and relationships — with a strong conclusion: *"Meditation is not merely a technique for relaxation; it is a transformative lifestyle."* This is the best initial draft of any local model.

**Refinement arc:**
- `feedback_0`: 6 suggestions — strengthen hook, vary sentence structure, smooth section transitions, expand cardiovascular mechanism, tighten mindfulness section, shift conclusion from description to empowerment.
- `draft_1` → `draft_2` → `draft_3`: Each round produced tangible improvements. The introduction grew sharper ("stress is no longer an occasional visitor; it is the persistent hum of modern existence"). The cardiovascular section gained a causal chain. The conclusion gained a direct call to action.
- `feedback_3`: 3 minor suggestions — smoother transition into section 4, punchier hook, reduce phrase repetition ("profound array of benefits"). Still no approval.

**Key observation:** The e2b critic is stricter than gemma3's critic. It identified diminishing but real issues at every pass. The final article (draft_3) is genuinely polished — but the critic's standard moved with the output, always finding the next level of refinement. This is the right dynamic for a self-improvement loop; it simply ran out of budget.

---

### gemma4:e4b — `logs-gemma4_e4b/`

**Exit:** Hit `max_iterations=3`. The critic never issued `[APPROVED]` across four critique rounds.

**Output quality (draft_0):** The richest initial draft — structured with emoji section headers (🧠 🫀 💪 💡), numbered sub-points within sections, and notably detailed scientific content: the HPA axis, cortisol management, gate control theory of pain, neuroplasticity framing. More depth per section than any other local model.

**Refinement arc:**
- `feedback_0`: 5 targeted suggestions. Notably: remove emojis for a professional editorial feel, add a transitional paragraph between intro and body, expand the "non-reactivity" concept with an analogy, end with a concrete measurable commitment (e.g., "3 minutes of mindful breathing for 7 days"), and break the HPA axis explanation into two clearer sentences.
- `draft_1`: Removed emojis, added the cloud/thought analogy ("the thoughts are merely passing clouds"), added the 7-day 3-minute challenge, restructured the HPA axis explanation. Substantial structural improvement.
- `draft_2` → `draft_3`: Further tightening of transitions, stronger motivational close, sharper section names.
- `feedback_3`: 5 more suggestions — better hook, tighter section transitions, consistent list grammar, punchier CTA framing, vary "inner peace" phrasing. No approval.

**Key observation:** gemma4:e4b started with the most ambitious structure of any local model but also attracted the most substantial first-round critique — the emojis and listicle format were a deliberate stylistic choice that the critic correctly flagged as misaligned with a professional tone. The subsequent 3 drafts represent a genuine transformation in voice and polish. Like e2b, the critic held a high bar throughout, moving the target as the output improved.

---

## Comparative Analysis

### Critic behaviour across models

| Model | Critic stance | Approval pattern |
|-------|--------------|-----------------|
| llama3.2 | Permissive — approved a mediocre draft immediately | Fast exit, low bar |
| gemma3 | Moderate — gave genuine feedback round 1, then approved with caveats | Exited at iteration 1; "approved with complaints" |
| gemma4:e2b | Strict — gave 5–6 actionable items per round, never approved in 3 iterations | Consistently raised the bar each round |
| gemma4:e4b | Strict — gave 5 detailed items per round including structural reframes, never approved in 3 iterations | Same pattern as e2b; started with bolder stylistic critique |

The self-critique faculty is clearly more developed in the gemma4 family. The e2b and e4b critics operate at a level where the output visibly improves between every round — but the bar keeps moving. More iterations (e.g., max=5 or max=7) would likely produce convergence for both.

### Output quality ranking (final articles)

1. **gemma4:e4b** — Deepest content, strongest narrative arc, most polished after 3 refinements. Best local output.
2. **gemma4:e2b** — Cleanest structure, most professional voice, excellent conclusion. Close second; reached this quality from a better starting point.
3. **gemma3** — Science-backed, readable, structured. Better than expected for model size. The "12 suggestions + approved" exit was a missed opportunity for one more refinement.
4. **llama3.2** — Accurate but thin. Self-approval on a mediocre draft disqualifies it from the improvement loop's value proposition.

### The e2b vs e4b comparison

Both gemma4 models share the same architecture family. The differences are consistent:
- **e4b starts more ambitiously** (emojis, numbered sub-points, HPA axis detail) and attracts bolder first-round critique.
- **e2b starts more conservatively** (clean five-section structure) and improves through incremental refinement.
- Both hold similar self-critique standards, neither willing to approve their own work within 3 iterations.
- **e4b takes roughly 2× longer** (~17 min vs ~9 min) — the larger model is slower on CPU, and the longer drafts take more time to generate and critique.

For a 3-iteration budget on CPU hardware, **e2b offers a better time/quality tradeoff**. For a longer budget where final quality is the only goal, **e4b's richer initial framing pays off**.

---

## Discrepancy With Prior Blog Numbers

The `medium-v0.2.md` blog contains an earlier results table showing gemma3 and gemma4:e2b as "approved immediately (2 LLM calls)". These do not match the benchmark run logs in this directory. The prior results were likely from a different run configuration. The current log-based numbers (table above) should be used for the updated blog.

---

## Suggested Follow-Up Runs

- Increase `--max-iterations` to 5 or 7 for gemma4:e2b and e4b to see if convergence occurs.
- Run with mixed writer/critic models (e.g., gemma4:e4b writer + gemma3 critic) to test cross-model critique quality.
- Add timing instrumentation to the script to capture per-call latency alongside file logs.
