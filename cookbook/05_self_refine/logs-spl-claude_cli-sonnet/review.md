# Run Review — self_refine · claude-sonnet-4-6 · claude_cli adapter

**Task:** What are the benefits of meditation?
**Model:** claude-sonnet-4-6 (writer + critic)
**Iterations:** 3 (max reached — critic never issued `[APPROVED]`)
**Date:** 2026-04-11

---

## Content quality across iterations

### Draft 0 (draft_0.md)
Compact, well-structured bullet list. Covers the right categories (mental, physical, emotional, long-term). Concise enough to read in 30 seconds. The closing sentence about "10–15 minutes daily" is practically grounded.

**Weakness at this stage:** reads like a wellness brochure — all claims stated with equal confidence regardless of evidence strength. "Strengthened immune function" sits alongside "improved sleep quality" as if they're equally settled.

---

### Iteration 1 (draft_1.md)
Largest single-step improvement. The critic correctly identified:
- Overclaiming without qualification
- Vagueness (cortisol)
- Missing meditation-type heterogeneity
- Adverse effects entirely absent

The refined draft addressed all of these. The critic's feedback was sharp and actionable — "structural brain changes" qualified to "cross-sectional studies with mixed replication," immune function honestly called unresolved, adverse effects added. The structure held; the epistemic calibration improved substantially.

---

### Iteration 2 (draft_2.md)
More targeted improvements — the critic found real gaps in an already-good document:
- Publication bias in the meditation literature (notably absent in most popular accounts)
- "Effect sizes comparable to other active interventions" quantified against aerobic exercise / CBT / antidepressants specifically
- Adverse effect risk stratified by practice intensity, with the Lindahl et al. (2017) citation
- Pain parenthetical reframed (was accidentally underselling a real finding)

The addition of the opening evidence-quality caveat (`> Note on the evidence base`) is a structurally important move — it frames the entire document correctly rather than relying on per-bullet qualifiers.

---

### Iteration 3 / Final (final.md)
Further refinements, all substantive:
- Lindahl (2017) sampling caveat added — the 25% figure is from a self-selected sample; the study is a qualitative catalog of adverse effect *types*, not a prevalence estimate
- Clinical vs. non-clinical populations distinguished for depression/anxiety effect sizes
- App-based vs. MBSR/structured-program evidence distinguished
- Dropout rates in RCTs noted (20–40%) — changes how to read "requires sustained practice"
- Attention/focus claim qualified to lab tasks (flanker tasks etc.) that may not generalize

The final document is a fundamentally different artifact from the draft — appropriately hedged, internally consistent in its evidence quality signaling, and practically useful without being misleading.

---

## Self-refine pattern observations

**The critic never approved.** All 3 iterations ran to completion. At each step there were genuine, substantive improvements to find — this is a hard epistemic calibration task and Sonnet's critic was consistently finding real issues rather than nitpicking. The pattern worked as designed.

**Critic > writer asymmetry.** The critic's output was noticeably more analytical than the writer's. The writer produced clean, organized prose; the critic produced structured argumentation with specific named weaknesses. This is a healthy asymmetry — critique is harder than generation, and both modes performed well.

**Conciseness held under pressure.** Each refinement added nuance without inflating length disproportionately. The final document is roughly 2× the length of the draft — that ratio is good given the complexity added.

---

## Prompt log file observation

The `--log-prompts` files (`draft_001.md`, `critique_002.md`, etc.) capture the **assembled user-side prompt** but not the **system prompt** from the SPL function definitions. For example, `draft_001.md` shows:

```
Task: draft
Input 1: What are the benefits of meditation?
```

The function's system prompt (`You are a professional writer. Write a comprehensive article...`) is passed as a separate `system` parameter to the adapter and is not included in the logged file.

**Practical implication:** if you paste the logged prompt body into a web UI without the system prompt, you'll get a different response than the API produced. To reproduce faithfully, you also need to prefix the system prompt from the corresponding SPL function definition.

**Suggestion:** extend `_log_prompt()` in `spl/executor.py` to include a `## System` section above the `---` fence when a system prompt is present.

---

## Verdict

The run demonstrates the self-refine pattern working well with a capable model. The content output is genuinely better than what a single-shot prompt would produce for this topic. The main engineering note is the missing system prompt in the log files.
