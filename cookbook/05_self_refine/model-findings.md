# Model Findings: Self-Refine Recipe (Recipe 05)

Tested on local Ollama, mini-PC Ubuntu. Task: "What are the benefits of meditation?"
Workflow: 3 iterations, writer + critic same model.

---

## gemma3 — FAIL

**Finding**: gemma3 cannot follow output-format instructions in an agentic workflow.
Regardless of prompt wording, the model treats every LLM call as a chat conversation turn.

**Observed behaviour across every run:**
- `draft_0`: Produces a valid article body, then appends "Notes on this Draft" + follow-up questions
- `draft_1`: Responds conversationally to feedback ("Okay, this is fantastic!"), does not rewrite the article
- `draft_2+`: Cascade failure — each iteration drifts further from the task (meta-analysis of meta-analysis)

**Prompt variations attempted** (none succeeded):
- Explicit instruction lists ("Do NOT ask questions", "Output only the article")
- Completion anchoring (prompt ending mid-line with `#` or `1.`)
- Role framing ("You are a seasoned writer")
- Task anchoring (passing original topic into `refined` function)
- Code-fence delimiters around draft and feedback

**Root cause**: gemma3's RLHF chat-mode training overrides instruction-following.
The model is tuned to be helpful and conversational — it appends meta-commentary and
questions as a reflex, independent of the system prompt content.

**Logs**: `logs-spl-gemma3/`

---

## llama3.2 — PASS

**Finding**: llama3.2 follows output-format instructions reliably.

**Observed behaviour:**
- `draft_0`: Clean article, no meta-commentary
- `feedback_0`: Clean numbered critique, no trailing questions
- `draft_1`: Produced improvement suggestions instead of full rewrite (prompt ambiguity: "improve" vs "rewrite") — fixed by changing one word in the prompt
- `draft_2+`: Clean articles, genuine improvement each iteration

**Caveat**: Smaller model, shallower content than gemma4. Output quality is competent but not rich.

**Logs**: `logs-spl/` (llama3.2 + llama3.2 run)

---

## gemma4:e2b — PASS (with minor tail leakage)

**Finding**: gemma4:e2b follows instructions and produces high-quality output.

**Observed behaviour:**
- `draft_0`: Clean structured article with summary table, no meta-commentary
- All drafts: Consistently 4500–5600 bytes (genuine articles, no conversational collapses)
- Iterative improvement: Real refinement each round — tighter section subheadings, added mechanisms, stronger framing
- **Minor issue**: `final.md` starts with one-paragraph preamble before the article body.
  Likely addressable with completion anchoring on the `refined` prompt.

**Logs**: `logs-spl-gemma4-e2b/`

---

## gemma4:e4b — FAIL (confidently wrong)

**Finding**: gemma4:e4b is a regression from e2b. Bigger model, worse agentic behaviour.

**Observed behaviour:**
- `draft_0`: Ignored the task. Produced three format options (blog/social/academic) instead
  of one article. The model over-interpreted "comprehensive" as a mandate to consult on strategy.
- `feedback_0`: Critic praised the non-compliant output as "A+ exceptional content planning."
  Never flagged that no article was written.
- `draft_1+`: Cascade into meta-analysis. Each iteration produced a critique of the critique,
  escalating in abstraction — "Master Critique", "Ultra-Refinement", "Architecture of Irreversible Impact."
- `final`: 3523b abstract consulting manifesto. The word "meditation" appears zero times.
  Smaller than draft_0 (-51%), further from the task.

**Runtime**: 1,326,029ms (~22 min) — 4× slower than e2b.

**Root cause**: Over-alignment with professional/consulting RLHF. The model treats every
prompt as an opportunity to demonstrate strategic thinking. "Write an article" becomes
"consult on content strategy." The critic is tuned to reward this behaviour, making the
wrong attractor self-reinforcing. Both writer and critic converged — on the wrong task.

**Key distinction from gemma3**: gemma3 failed visibly (tiny outputs, obvious chat responses).
e4b failed *confidently* — producing large, polished, impressive-sounding content about
the wrong thing entirely. The critic rated it A++ throughout. This is the more dangerous
failure mode in production.

**Logs**: `logs-spl-gemma4-e4b/`

---

## Summary

| Model | Runtime | Instruction Following | Output Quality | Recommended |
|---|---|---|---|---|
| gemma3 | ~10 min | FAIL — chat reflex | N/A | No |
| llama3.2 | ~5.5 min | PASS — clean | Competent | Yes (fast, reliable) |
| gemma4:e2b | ~5.5 min | PASS — minor preamble | High | Yes (best quality) |
| gemma4:e4b | ~22 min | FAIL — confidently wrong | High (wrong task) | No |

**Recommendation**: Use `llama3.2` as default for reliability and speed.
Use `gemma4:e2b` when output quality matters more than latency.
Avoid `gemma3` and `gemma4:e4b` for any agentic task requiring strict output format compliance.

**Broader finding**: Model size does not correlate with instruction-following in agentic
workflows. Larger models can be *more* misaligned — their RLHF training amplifies
behaviours (helpfulness, professionalism, consulting) that actively interfere with
format-constrained tasks. A critic that confidently approves wrong output is worse
than one that obviously fails.
