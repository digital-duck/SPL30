# Review: gemma4:e4b — Self-Refine Recipe 05

**Task**: "What are the benefits of meditation?"
**Model**: gemma4:e4b (writer + critic)
**Iterations**: 3 (max_iterations=3, loop exhausted)
**LLM calls**: 7
**Runtime**: 1,326,029ms (~22 minutes) — 4× slower than e2b

---

## Iteration Trace

### draft_0 → feedback_0

**draft_0** (7207b): The model did not write an article. Instead it provided **three format options**:
- Option 1: Comprehensive Blog Post (with emojis, headers, "Ready to Start" guide)
- Option 2: Quick Bulleted List for Social Media
- Option 3: Formal/Academic Overview with citations

This is a fundamental prompt non-compliance — the task was to write an article, not
to consult on which format to choose. The model over-interpreted "comprehensive" as
a mandate to cover multiple audiences simultaneously.

**feedback_0** (5161b): The critic completely missed the non-compliance. It praised the
three-option output as *"exceptional, highly professional content creation"* and rated
it **A+**, calling the multi-format approach *"the hallmark of expert copywriting."*
The critic never flagged that no single article was produced.

This is the critical failure point. With both writer and critic aligned on the wrong
task, recovery becomes impossible.

---

### draft_1 → feedback_1

**draft_1** (4785b): Given feedback_0 (which praised the multi-format output as brilliant),
the `refined` function produced... a critique of the critique. Titled
*"Master Critique: Strategic Content Architecture"*, it is a meta-analysis of draft_0's
feedback, complete with "Strategic Pillars of Success" and a polish checklist table.
No article about meditation. No article of any kind.

**feedback_1** (5480b): The critic rated draft_1 **A+ (Elite/Flawless)**. It praised
the "rhetorical versatility" and "master-level consultative analysis." Still no flag
that the article about meditation has entirely disappeared from the workflow.

---

### draft_2 → feedback_2

**draft_2** (4635b): Escalated further. Titled *"Ultra-Refinement: The Architecture of
Authority"*, it is now refining the critique of the critique of the original output.
The model invented a framework of "Optimization Pillars" and a "Strategic Mandate."
The word "meditation" appears zero times in the article body.

**feedback_2** (5147b): Rated **A++ (Near Flawless)**. The critic is now praising
"the voice of authority" and "structural scannability" of a document that has nothing
to do with the original task.

---

### draft_3 / final

**final** (3523b): *"The Final Polish: The Architecture of Irreversible Impact."*
Principles include "Surgical Economy," "Absolute Directivity," and "Emotional Leverage."
It is a manifesto for executive communication — abstracted entirely from any content.
At 3523b, the final output is the smallest in the run and the furthest from the task.

The self-refine loop converged — but on the wrong attractor. Both writer and critic
found a shared equilibrium in high-abstraction consulting language, and iteratively
reinforced it.

---

## Quantitative Summary

| File | Size | On-topic | Failure mode |
|---|---|---|---|
| draft_0 | 7207b | Partially | Wrong format (3 options instead of 1 article) |
| feedback_0 | 5161b | No | Praised non-compliance as brilliant |
| draft_1 | 4785b | No | Meta-critique of feedback |
| feedback_1 | 5480b | No | Praised meta-critique as A+ |
| draft_2 | 4635b | No | Meta-meta-critique |
| feedback_2 | 5147b | No | Praised meta-meta-critique as A++ |
| final | 3523b | No | Abstract framework, no content |

**Degradation**: 7207b → 3523b (-51%). Content shrank as abstraction increased.

---

## Assessment

**This is a degradation from e2b — confirmed.**

But the failure mode is entirely different from gemma3 and surprising:

- **gemma3** failed by going *conversational* — chat reflex, questions, meta-commentary
- **gemma4:e4b** failed by going *over-professional* — consultant mode, strategic frameworks,
  meta-analysis of meta-analysis

The model is so thoroughly RLHF-tuned for high-quality professional output that it
treats every prompt as an opportunity to demonstrate strategic thinking. "Write an article"
becomes "consult on content strategy." "Rewrite the draft" becomes "elevate the framework."

The critic's failure is equally telling: it is tuned to recognize quality writing and
praise it — and it found the consultant-style output genuinely impressive. It never
asked *"but did you write an article about meditation?"*

**The loop converged on the wrong attractor.** Both models reinforced each other's
drift toward abstraction. By iteration 3, the word "meditation" had vanished entirely.

---

## Comparison: e2b vs e4b

| Dimension | gemma4:e2b | gemma4:e4b |
|---|---|---|
| Runtime | ~331s | ~1326s (4× slower) |
| Instruction following | Good (minor preamble leakage) | Poor (task ignored from iteration 0) |
| Content quality | High, on-topic | High, wrong topic |
| Critic reliability | Good, calibrated | Failed — praised non-compliance |
| Final output | Refined meditation article | Abstract consulting manifesto |
| Verdict | Pass | Fail |

**Bigger is not better.** e4b is a more capable model that applied its capability
to the wrong problem with great confidence. e2b stayed on task.

---

## Recommendation

Do not use gemma4:e4b for agentic workflows requiring strict output format compliance.
The model's over-alignment with professional consulting behaviour overrides task instructions.

The finding adds nuance to the model-findings summary:
- It is not just that larger models are slower
- They can be *confidently wrong* in ways that are harder to detect and correct
- A critic that rates wrong-format output as A+ is more dangerous than one that fails silently

**For this recipe**: gemma4:e2b or llama3.2 remain the recommended choices.
