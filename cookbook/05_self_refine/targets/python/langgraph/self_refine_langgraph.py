"""
LangGraph equivalent of self_refine.spl

Pattern: draft → critique → (satisfactory? commit : refine → critique)

Usage:
    pip install langgraph langchain-ollama
    python cookbook/05_self_refine/self_refine_langgraph.py \\
        --task "Write a haiku about coding"
    python cookbook/05_self_refine/self_refine_langgraph.py \\
        --task "Explain recursion in one paragraph" --max-iterations 3 --model llama3.2
"""

import argparse
from pathlib import Path
from typing import TypedDict

from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph


# ── Prompts (mirrors PROMPT blocks in self_refine.spl) ────────────────────────

DRAFT_PROMPT = """\
You are an expert writer. Complete the following task thoroughly and well.

Task: {task}"""

CRITIQUE_PROMPT = """\
You are a strict critic. Review the following draft.

Draft:
{current}

If the draft is satisfactory, reply with exactly one word: satisfactory
Otherwise, provide specific, actionable feedback on how to improve it."""

REFINE_PROMPT = """\
You are an expert writer. Improve the following draft based on the feedback.

Draft:
{current}

Feedback:
{feedback}

Write the improved version now."""


# ── State  (SPL manages @variables implicitly) ────────────────────────────────

class RefineState(TypedDict):
    task:           str
    max_iterations: int
    model:          str
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
    # GENERATE draft(@task) INTO @current
    print("Generating initial draft ...")
    current = _invoke(state["model"], DRAFT_PROMPT.format(task=state["task"]))
    _write(f"{state['log_dir']}/draft_0.md", current)
    return {"current": current, "iteration": 0}

def node_critique(state: RefineState) -> dict:
    # GENERATE critique(@current) INTO @feedback
    i = state["iteration"]
    print(f"Iteration {i} | critiquing ...")
    feedback = _invoke(state["model"], CRITIQUE_PROMPT.format(current=state["current"]))
    _write(f"{state['log_dir']}/feedback_{i}.md", feedback)
    return {"feedback": feedback}

def node_refine(state: RefineState) -> dict:
    # GENERATE refined(@current, @feedback) INTO @current
    i = state["iteration"] + 1
    print(f"Iteration {i} | refining ...")
    current = _invoke(state["model"], REFINE_PROMPT.format(
        current=state["current"], feedback=state["feedback"],
    ))
    _write(f"{state['log_dir']}/draft_{i}.md", current)
    return {"current": current, "iteration": i}

def node_commit(state: RefineState) -> dict:
    # COMMIT @current
    _write(f"{state['log_dir']}/final.md", state["current"])
    satisfied = "satisfactory" in state["feedback"].lower()
    status = "complete" if satisfied else "max_iterations"
    print(f"Committed | status={status}  iterations={state['iteration']}")
    return {}


# ── Conditional edge  (mirrors EVALUATE + WHILE logic) ───────────────────────

def _route(state: RefineState) -> str:
    # EVALUATE @feedback WHEN 'satisfactory' THEN COMMIT
    if "satisfactory" in state["feedback"].lower():
        return "commit"
    if state["iteration"] >= state["max_iterations"]:
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

def main():
    p = argparse.ArgumentParser(description="Self-refine — LangGraph edition")
    p.add_argument("--task",           required=True)
    p.add_argument("--max-iterations", type=int, default=5)
    p.add_argument("--model",          default="gemma3")
    p.add_argument("--log-dir",        default="cookbook/05_self_refine/logs")
    args = p.parse_args()

    result = build_graph().invoke({
        "task":           args.task,
        "max_iterations": args.max_iterations,
        "model":          args.model,
        "log_dir":        args.log_dir,
        "current":        "",
        "feedback":       "",
        "iteration":      0,
    })
    print("\n" + "=" * 60)
    print(result["current"])

if __name__ == "__main__":
    main()
