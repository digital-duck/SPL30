"""
AutoGen equivalent of self_refine.spl

Two ConversableAgents — Writer and Critic — alternate turns.
The Critic's termination condition mirrors SPL's EVALUATE ... WHEN 'satisfactory'.

Usage:
    pip install pyautogen
    python cookbook/05_self_refine/self_refine_autogen.py \\
        --task "Write a haiku about coding"
    python cookbook/05_self_refine/self_refine_autogen.py \\
        --task "Explain recursion in one paragraph" --max-iterations 3 --model llama3.2
"""

import argparse
from pathlib import Path

from autogen import ConversableAgent


# ── Agent system messages (mirrors PROMPT blocks in self_refine.spl) ──────────

WRITER_SYSTEM = """\
You are an expert writer.
When given a task, produce a high-quality response.
When given critique, produce an improved version that addresses the feedback.
Output only the written content — no meta-commentary."""

CRITIC_SYSTEM = """\
You are a strict critic reviewing written content.
If the content meets the bar, reply with exactly one word: satisfactory
Otherwise, provide specific, actionable feedback on how to improve it."""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _write(path: str, content: str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")

def _is_satisfactory(msg: dict) -> bool:
    # Mirrors: EVALUATE @feedback WHEN 'satisfactory' THEN COMMIT
    return "satisfactory" in msg.get("content", "").lower()


# ── Main runner ───────────────────────────────────────────────────────────────

def run(task: str, max_iterations: int, model: str, log_dir: str) -> str:
    llm_config = {
        "config_list": [{
            "model":    model,
            "base_url": "http://localhost:11434/v1",
            "api_key":  "ollama",
        }]
    }

    # SPL: GENERATE draft(@task) + GENERATE critique(@current)
    writer = ConversableAgent(
        name="Writer",
        system_message=WRITER_SYSTEM,
        llm_config=llm_config,
        human_input_mode="NEVER",
    )
    # SPL: EVALUATE @feedback WHEN 'satisfactory' THEN COMMIT
    critic = ConversableAgent(
        name="Critic",
        system_message=CRITIC_SYSTEM,
        llm_config=llm_config,
        human_input_mode="NEVER",
        is_termination_msg=_is_satisfactory,
    )

    # max_turns = 1 (draft) + max_iterations × 2 (critique + refine)
    result = writer.initiate_chat(
        critic,
        message=f"Complete this task: {task}",
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

def main():
    p = argparse.ArgumentParser(description="Self-refine — AutoGen edition")
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
