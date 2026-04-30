"""Gemini CLI adapter for SPL 3.0.

Wraps the `gemini` command-line tool for zero-marginal-cost development.
Implementation based on: @../SPL/docs/DEV/add-gemini_cli-adapter.md
"""

from __future__ import annotations

import asyncio
import logging
import os
import subprocess
import time

from spl3.adapters.base import GenerationResult
from spl3.adapters.base_multimodal import MultiModalAdapter
from spl.executor import ModelOverloaded

logger = logging.getLogger(__name__)


class GeminiCLIAdapter(MultiModalAdapter):
    """LLM adapter that wraps the Gemini CLI.

    Invocation Strategy:
    echo "your prompt" | gemini -p "" --output-format text --model <model_name>

    Benefits:
    - Cost: No per-token costs during local development (utilizes CLI auth/subscription).
    - Environment: Reuses existing `gemini` CLI configuration and authenticated sessions.
    - Workflow Compatibility: Fully supports `EXCEPTION WHEN ModelOverloaded` for robust retry logic.
    """

    DEFAULT_MODEL = "gemini-2.0-flash"

    def __init__(
        self,
        cli_path: str = "gemini",
        model: str = DEFAULT_MODEL,
        timeout: int = 120,
    ):
        self.cli_path = cli_path
        self.model = model
        self.timeout = timeout

    async def generate(
        self,
        prompt: str,
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system: str | None = None,
    ) -> GenerationResult:
        """Generate response by invoking gemini CLI."""
        start = time.perf_counter()

        # Build the full prompt with system instruction if provided
        full_prompt = prompt
        if system:
            full_prompt = f"System Instruction: {system}\n\nUser: {prompt}"

        # Build CLI command
        effective_model = model or self.model
        # -p "": Enters non-interactive mode and appends stdin input to the prompt
        # --output-format text: Clean text without interactive formatting
        cmd = [self.cli_path, "-p", "", "--output-format", "text", "--model", effective_model]

        # Run subprocess asynchronously
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=full_prompt.encode('utf-8')),
                timeout=self.timeout
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Gemini CLI not found at '{self.cli_path}'. "
                "Install Gemini CLI: https://github.com/google/gemini-cli"
            )
        except asyncio.TimeoutError:
            raise RuntimeError(f"Gemini CLI timed out after {self.timeout}s")

        stderr_text = stderr.decode('utf-8', errors='replace').strip()
        stdout_text = stdout.decode('utf-8', errors='replace').strip()

        latency_ms = int((time.perf_counter() - start) * 1000)

        if proc.returncode != 0:
            error_msg = stderr_text.lower()
            # Monitor stderr for common API and CLI limits
            if any(term in error_msg for term in ["rate limit", "quota", "exhausted"]):
                raise ModelOverloaded(f"Gemini CLI quota exhausted: {stderr_text}")
            raise RuntimeError(f"Gemini CLI error (exit {proc.returncode}): {stderr_text}")

        if not stdout_text:
            hint = f" stderr: {stderr_text[:300]}" if stderr_text else " (no stderr either)"
            raise RuntimeError(
                f"Gemini CLI returned empty response (rc=0, latency={latency_ms}ms).{hint}"
            )

        # Estimate tokens
        input_tokens = len(full_prompt) // 4
        output_tokens = len(stdout_text) // 4

        return GenerationResult(
            content=stdout_text,
            model=effective_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            latency_ms=latency_ms,
            cost_usd=0.0,  # Subscription/CLI billing
        )

    def count_tokens(self, text: str, model: str = "") -> int:
        """Estimate tokens using character-based heuristic."""
        if not text:
            return 0
        return max(1, len(text) // 4)

    def list_models(self) -> list[str]:
        """Return current Gemini model names."""
        return [
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-3-flash-preview",
            "gemini-3.1-flash-lite-preview",
        ]

    def __repr__(self) -> str:
        return f"GeminiCLIAdapter(cli_path={self.cli_path!r}, model={self.model!r})"
