"""
CrewAI equivalent of self_refine.spl

Two Agents (Writer, Critic) with a manual refinement loop — CrewAI does not
have native loop/conditional constructs, so the WHILE + EVALUATE logic from
SPL is implemented explicitly in Python.

Usage:
    pip install crewai langchain-ollama
    python cookbook/05_self_refine/self_refine_crewai.py \\
        --task "Write a haiku about coding"
    python cookbook/05_self_refine/self_refine_crewai.py \\
        --task "Explain recursion in one paragraph" --max-iterations 3 --model llama3.2
"""

import argparse
from pathlib import Path

from crewai import Agent, Crew, Process, Task
from langchain_ollama import ChatOllama


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def _run_task(agent: Agent, description: str, expected_output: str) -> str:
    t = Task(description=description, expected_output=expected_output, agent=agent)
    result = Crew(agents=[agent], tasks=[t], process=Process.sequential, verbose=False).kickoff()
    return str(result).strip()


# ── Main runner ───────────────────────────────────────────────────────────────

def run(task: str, max_iterations: int, model: str, log_dir: str) -> str:
    # Standardize to the 'ollama/' prefix for more robust local model support
    # and to avoid Pydantic validation errors in newer CrewAI versions.
    llm = f"ollama/{model}"

    # SPL: GENERATE draft(@task) via Writer
    writer = Agent(
        role="Expert Writer",
        goal="Produce high-quality written content and improve it based on feedback.",
        backstory="You are a skilled writer who crafts clear, accurate, well-structured content.",
        llm=llm,
        verbose=False,
    )
    # SPL: GENERATE critique(@current) via Critic + EVALUATE @feedback
    critic = Agent(
        role="Strict Critic",
        goal="Evaluate written content and give actionable feedback.",
        backstory=(
            "You are a strict critic. "
            "Reply with exactly 'satisfactory' if the content meets the bar, "
            "otherwise give specific improvement feedback."
        ),
        llm=llm,
        verbose=False,
    )

    # GENERATE draft(@task) INTO @current
    print("Generating initial draft ...")
    current = _run_task(
        writer,
        description=f"Complete this task thoroughly and well:\n\n{task}",
        expected_output="A well-written response to the task.",
    )
    _write(f"{log_dir}/draft_0.md", current)

    # WHILE @iteration < @max_iterations DO
    for iteration in range(max_iterations):
        print(f"Iteration {iteration} | critiquing ...")
        # GENERATE critique(@current) INTO @feedback
        feedback = _run_task(
            critic,
            description=(
                f"Review this draft:\n\n{current}\n\n"
                "Reply 'satisfactory' if it meets the bar, otherwise give specific feedback."
            ),
            expected_output="Either 'satisfactory' or specific improvement feedback.",
        )
        _write(f"{log_dir}/feedback_{iteration}.md", feedback)

        # EVALUATE @feedback WHEN 'satisfactory' THEN COMMIT
        if "satisfactory" in feedback.lower():
            print(f"Satisfactory at iteration {iteration}")
            break

        print(f"Iteration {iteration} | refining ...")
        # GENERATE refined(@current, @feedback) INTO @current
        current = _run_task(
            writer,
            description=(
                f"Improve this draft based on the feedback.\n\n"
                f"Draft:\n{current}\n\nFeedback:\n{feedback}"
            ),
            expected_output="An improved version of the draft.",
        )
        _write(f"{log_dir}/draft_{iteration + 1}.md", current)
    else:
        # LOGGING 'Max iterations reached' LEVEL WARN
        print(f"Max iterations reached | iterations={max_iterations}")

    # COMMIT @current
    _write(f"{log_dir}/final.md", current)
    return current


# ── Entry point  (SPL: built into CLI — `spl run ...`) ────────────────────────

def main():
    p = argparse.ArgumentParser(description="Self-refine — CrewAI edition")
    p.add_argument("--task",           required=True)
    p.add_argument("--max-iterations", type=int, default=5)
    p.add_argument("--model",          default="gemma3")
    p.add_argument("--log-dir",        default="cookbook/05_self_refine/logs")
    args = p.parse_args()

    result = run(args.task, args.max_iterations, args.model, args.log_dir)
    print("\n" + "=" * 60)
    print(result)

if __name__ == "__main__":
    main()
