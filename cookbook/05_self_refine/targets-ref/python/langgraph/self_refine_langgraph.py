"""
LangGraph equivalent of self_refine.spl

Pattern: draft → critique → ([APPROVED]? commit : refine → critique)

Usage:
    pip install langgraph langchain-ollama
    python cookbook/05_self_refine/targets/python/langgraph/self_refine_langgraph.py \\
        --task "Write a haiku about coding"
    python cookbook/05_self_refine/targets/python/langgraph/self_refine_langgraph.py \\
        --task "Explain recursion in one paragraph" --max-iterations 3
"""

from pathlib import Path
from typing import TypedDict

import click

from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph


# ── Prompts (mirrors PROMPT blocks in self_refine.spl) ────────────────────────

DRAFT_PROMPT = """\
You are a professional writer. Write a comprehensive article on the topic below.
Output only the article — no preamble, no notes after.

Topic: {task}"""

CRITIQUE_PROMPT = """\
You are a professional editor. The article below may have meta-commentary or questions
appended at the end — ignore those, critique only the article body.

If the article needs no further improvement, reply with exactly: [APPROVED]

Otherwise output a numbered list of specific, actionable improvements. Nothing else.

ARTICLE:
{current}

IMPROVEMENTS:
1."""

REFINE_PROMPT = """\
You are a seasoned writer. Rewrite the draft below incorporating the feedback.
Stay true to the original topic: {task}
Output only the rewritten article — no preamble, no notes after.

DRAFT:
```
{current}
```

FEEDBACK:
```
{feedback}
```"""


# ── State  (SPL manages @variables implicitly) ────────────────────────────────

class RefineState(TypedDict):
    task:           str
    max_iterations: int
    writer_model:   str   # @writer_model — used for draft + refine
    critic_model:   str   # @critic_model — used for critique
    log_dir:        str
    current:        str   # @current
    feedback:       str   # @feedback
    iteration:      int   # @iteration


# ── Helpers ───────────────────────────────────────────────────────────────────

def _invoke(model: str, prompt: str) -> str:
    return ChatOllama(model=model).invoke(prompt).content.strip()

def _write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


# ── Nodes  (each mirrors one GENERATE / EVALUATE block) ──────────────────────

def node_draft(state: RefineState) -> dict:
    # GENERATE draft(@task) USING MODEL @writer_model INTO @current
    print("Generating initial draft ...")
    current = _invoke(state["writer_model"], DRAFT_PROMPT.format(task=state["task"]))
    _write(f"{state['log_dir']}/draft_0.md", current)
    print("Initial draft ready")
    return {"current": current, "iteration": 0}

def node_critique(state: RefineState) -> dict:
    # GENERATE critique(@current) USING MODEL @critic_model INTO @feedback
    i = state["iteration"]
    print(f"\nIteration {i} | critiquing ...")
    feedback = _invoke(state["critic_model"], CRITIQUE_PROMPT.format(current=state["current"]))
    _write(f"{state['log_dir']}/feedback_{i}.md", feedback)
    return {"feedback": feedback}

def node_refine(state: RefineState) -> dict:
    # GENERATE refined(@task, @current, @feedback) USING MODEL @writer_model INTO @current
    i = state["iteration"] + 1
    print(f"Iteration {i} | refining ...")
    current = _invoke(state["writer_model"], REFINE_PROMPT.format(
        task=state["task"],
        current=state["current"],
        feedback=state["feedback"],
    ))
    _write(f"{state['log_dir']}/draft_{i}.md", current)
    print(f"Refined | iteration={i}")
    return {"current": current, "iteration": i}

def node_commit(state: RefineState) -> dict:
    # COMMIT @current (write final.md and log status)
    _write(f"{state['log_dir']}/final.md", state["current"])
    approved = "[APPROVED]" in state["feedback"]
    status = "complete" if approved else "max_iterations"
    print(f"Committed | status={status}  iterations={state['iteration']}")
    return {}


# ── Conditional edge  (mirrors EVALUATE + WHILE logic) ───────────────────────

def _route(state: RefineState) -> str:
    # EVALUATE @feedback WHEN contains('[APPROVED]') THEN COMMIT
    if "[APPROVED]" in state["feedback"]:
        return "commit"
    if state["iteration"] >= state["max_iterations"]:
        # LOGGING 'Max iterations reached' LEVEL WARN
        print(f"\nMax iterations reached | iterations={state['iteration']}")
        return "commit"
    return "refine"


# ── Graph  (SPL: implicit sequential WORKFLOW layout) ─────────────────────────

def build_graph():
    g = StateGraph(RefineState)
    g.add_node("draft",    node_draft)
    g.add_node("critique", node_critique)
    g.add_node("refine",   node_refine)
    g.add_node("commit",   node_commit)

    g.set_entry_point("draft")
    g.add_edge("draft",   "critique")
    g.add_conditional_edges("critique", _route, {"commit": "commit", "refine": "refine"})
    g.add_edge("refine",  "critique")
    g.add_edge("commit",  END)
    return g.compile()


# ── Entry point  (SPL: built into CLI — `spl run ...`) ────────────────────────

@click.command()
@click.option("--task",           required=True,   help="Task for the writer")
@click.option("--max-iterations", default=3,       show_default=True, type=int)
@click.option("--writer-model",   default="llama3.2", show_default=True, help="Ollama model for draft + refine")
@click.option("--critic-model",   default="llama3.2", show_default=True, help="Ollama model for critique")
@click.option("--log-dir",        default="cookbook/05_self_refine/logs-langgraph", show_default=True)
def main(task: str, max_iterations: int, writer_model: str, critic_model: str, log_dir: str):
    result = build_graph().invoke({
        "task":           task,
        "max_iterations": max_iterations,
        "writer_model":   writer_model,
        "critic_model":   critic_model,
        "log_dir":        log_dir,
        "current":        "",
        "feedback":       "",
        "iteration":      0,
    })
    print("\n" + "=" * 60)
    print(result["current"])

if __name__ == "__main__":
    main()
