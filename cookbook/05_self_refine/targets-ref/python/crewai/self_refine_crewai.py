"""
CrewAI equivalent of self_refine.spl

Two Agents (Writer, Critic) with a manual refinement loop — CrewAI does not
have native loop/conditional constructs, so the WHILE + EVALUATE logic from
SPL is implemented explicitly in Python.

Usage:
    pip install crewai langchain-ollama
    python cookbook/05_self_refine/targets/python/crewai/self_refine_crewai.py \\
        --task "Write a haiku about coding"
    python cookbook/05_self_refine/targets/python/crewai/self_refine_crewai.py \\
        --task "Explain recursion in one paragraph" --max-iterations 3
"""

import click
from pathlib import Path

from crewai import Agent, Crew, Process, Task


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

def run(task: str, max_iterations: int, writer_model: str, critic_model: str, log_dir: str) -> str:
    writer_llm = f"ollama/{writer_model}"
    critic_llm = f"ollama/{critic_model}"

    # SPL: GENERATE draft(@task) via Writer
    writer = Agent(
        role="Professional Writer",
        goal="Write a comprehensive article and improve it based on feedback.",
        backstory=(
            "You are a professional writer. You write comprehensive articles on given topics. "
            "Output only the article — no preamble, no notes after."
        ),
        llm=writer_llm,
        verbose=False,
    )
    # SPL: GENERATE critique(@current) via Critic + EVALUATE @feedback WHEN contains('[APPROVED]')
    critic = Agent(
        role="Professional Editor",
        goal="Critique articles and output actionable improvements or [APPROVED].",
        backstory=(
            "You are a professional editor. The article may have meta-commentary or questions "
            "appended at the end — ignore those, critique only the article body. "
            "If the article needs no further improvement, reply with exactly: [APPROVED]. "
            "Otherwise output a numbered list of specific, actionable improvements. Nothing else."
        ),
        llm=critic_llm,
        verbose=False,
    )

    # GENERATE draft(@task) INTO @current
    print("Generating initial draft ...")
    current = _run_task(
        writer,
        description=(
            f"Write a comprehensive article on the topic below.\n"
            f"Output only the article — no preamble, no notes after.\n\n"
            f"Topic: {task}"
        ),
        expected_output="A comprehensive article on the topic with no preamble or notes.",
    )
    _write(f"{log_dir}/draft_0.md", current)
    print("Initial draft ready")

    # WHILE @iteration < @max_iterations DO
    for iteration in range(max_iterations):
        print(f"\nIteration {iteration} | critiquing ...")
        # GENERATE critique(@current) INTO @feedback
        feedback = _run_task(
            critic,
            description=(
                f"ARTICLE:\n{current}\n\n"
                "IMPROVEMENTS:\n1."
            ),
            expected_output="Either '[APPROVED]' or a numbered list of specific, actionable improvements.",
        )
        _write(f"{log_dir}/feedback_{iteration}.md", feedback)

        # EVALUATE @feedback WHEN contains('[APPROVED]') THEN
        if "[APPROVED]" in feedback:
            print(f"Approved at iteration {iteration}")
            _write(f"{log_dir}/final.md", current)
            return current

        print(f"Iteration {iteration} | refining ...")
        # GENERATE refined(@task, @current, @feedback) INTO @current
        current = _run_task(
            writer,
            description=(
                f"Rewrite the draft below incorporating the feedback.\n"
                f"Stay true to the original topic: {task}\n"
                f"Output only the rewritten article — no preamble, no notes after.\n\n"
                f"DRAFT:\n```\n{current}\n```\n\n"
                f"FEEDBACK:\n```\n{feedback}\n```"
            ),
            expected_output="The rewritten article with no preamble or notes.",
        )
        _write(f"{log_dir}/draft_{iteration + 1}.md", current)
        print(f"Refined | iteration={iteration + 1}")
    else:
        # LOGGING 'Max iterations reached' LEVEL WARN
        print(f"\nMax iterations reached | iterations={max_iterations}")

    _write(f"{log_dir}/final.md", current)
    return current


# ── Entry point  (SPL: built into CLI — `spl run ...`) ────────────────────────

@click.command()
@click.option("--task",           required=True,   help="Task for the writer")
@click.option("--max-iterations", default=3,       show_default=True, type=int)
@click.option("--writer-model",   default="llama3.2", show_default=True, help="Ollama model for draft + refine")
@click.option("--critic-model",   default="llama3.2", show_default=True, help="Ollama model for critique")
@click.option("--log-dir",        default="cookbook/05_self_refine/logs-crewai", show_default=True)
def main(task: str, max_iterations: int, writer_model: str, critic_model: str, log_dir: str):
    result = run(task, max_iterations, writer_model, critic_model, log_dir)
    print("\n" + "=" * 60)
    print(result)

if __name__ == "__main__":
    main()
