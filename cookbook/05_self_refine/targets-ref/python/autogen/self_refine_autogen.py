"""
AutoGen equivalent of self_refine.spl

Two ConversableAgents — Writer and Critic — alternate turns.
The Critic's termination condition mirrors SPL's EVALUATE ... WHEN contains('[APPROVED]').

Usage:
    pip install pyautogen
    python cookbook/05_self_refine/targets/python/autogen/self_refine_autogen.py \\
        --task "Write a haiku about coding"
    python cookbook/05_self_refine/targets/python/autogen/self_refine_autogen.py \\
        --task "Explain recursion in one paragraph" --max-iterations 3
"""

import click
from pathlib import Path

from autogen import ConversableAgent


# ── Agent system messages (mirrors PROMPT blocks in self_refine.spl) ──────────

WRITER_SYSTEM = """\
You are a professional writer.
When given a task, write a comprehensive article on the topic.
Output only the article — no preamble, no notes after.
When given critique, rewrite the article incorporating the feedback.
Stay true to the original topic and output only the rewritten article — no preamble, no notes after."""

CRITIC_SYSTEM = """\
You are a professional editor. The article below may have meta-commentary or questions
appended at the end — ignore those, critique only the article body.

If the article needs no further improvement, reply with exactly: [APPROVED]

Otherwise output a numbered list of specific, actionable improvements. Nothing else."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def _is_approved(msg: dict) -> bool:
    # Mirrors: EVALUATE @feedback WHEN contains('[APPROVED]') THEN
    return "[APPROVED]" in msg.get("content", "")


# ── Main runner ───────────────────────────────────────────────────────────────

def run(task: str, max_iterations: int, writer_model: str, critic_model: str, log_dir: str) -> str:
    writer_llm_config = {
        "config_list": [{
            "model":    writer_model,
            "base_url": "http://localhost:11434/v1",
            "api_key":  "ollama",
        }]
    }
    critic_llm_config = {
        "config_list": [{
            "model":    critic_model,
            "base_url": "http://localhost:11434/v1",
            "api_key":  "ollama",
        }]
    }

    # SPL: GENERATE draft(@task) via Writer
    writer = ConversableAgent(
        name="Writer",
        system_message=WRITER_SYSTEM,
        llm_config=writer_llm_config,
        human_input_mode="NEVER",
    )
    # SPL: GENERATE critique(@current) via Critic + EVALUATE @feedback WHEN contains('[APPROVED]')
    critic = ConversableAgent(
        name="Critic",
        system_message=CRITIC_SYSTEM,
        llm_config=critic_llm_config,
        human_input_mode="NEVER",
        is_termination_msg=_is_approved,
    )

    # max_turns = 1 (draft) + max_iterations × 2 (critique + refine)
    result = writer.initiate_chat(
        critic,
        message=f"Write a comprehensive article on the topic below.\nOutput only the article — no preamble, no notes after.\n\nTopic: {task}",
        max_turns=1 + max_iterations * 2,
    )

    # Log each turn: writer turns → drafts, critic turns → feedback
    draft_idx = feedback_idx = 0
    for msg in result.chat_history:
        name    = msg.get("name", "")
        content = msg.get("content", "")
        if name == "Writer":
            _write(f"{log_dir}/draft_{draft_idx}.md", content)
            draft_idx += 1
        elif name == "Critic":
            _write(f"{log_dir}/feedback_{feedback_idx}.md", content)
            feedback_idx += 1

    # Final output is the last Writer message
    final = next(
        (m["content"] for m in reversed(result.chat_history) if m.get("name") == "Writer"),
        result.chat_history[-1]["content"] if result.chat_history else "",
    )
    _write(f"{log_dir}/final.md", final)

    iterations = draft_idx - 1
    print(f"Done | iterations={iterations}")
    return final


# ── Entry point  (SPL: built into CLI — `spl run ...`) ────────────────────────

@click.command()
@click.option("--task",           required=True,   help="Task for the writer")
@click.option("--max-iterations", default=3,       show_default=True, type=int)
@click.option("--writer-model",   default="llama3.2", show_default=True, help="Ollama model for draft + refine")
@click.option("--critic-model",   default="llama3.2", show_default=True, help="Ollama model for critique")
@click.option("--log-dir",        default="cookbook/05_self_refine/logs-autogen", show_default=True)
def main(task: str, max_iterations: int, writer_model: str, critic_model: str, log_dir: str):
    result = run(task, max_iterations, writer_model, critic_model, log_dir)
    print("\n" + "=" * 60)
    print(result)

if __name__ == "__main__":
    main()
