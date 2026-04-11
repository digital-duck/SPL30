"""Ubuntu AI Inference Snap adapter for SPL 3.0.  [PLACEHOLDER]

Target platform: Ubuntu 26.04 LTS (Noble+) with the Canonical AI inference snap.

STATUS: Not yet implemented — Ubuntu 26.04 is not GA and Canonical has not
published a stable inference API spec.  This file is a typed placeholder that
documents the expected interface and will be completed when:

  1. Ubuntu 26.04 ships (expected H1 2026).
  2. Canonical publishes the `ubuntu-inference` (or `ubuntu-ai`) snap API.
  3. The snap's local endpoint format is confirmed (OpenAI-compatible assumed).

What we know so far
-------------------
- Ubuntu 26.04 is expected to ship with an opt-in AI inference engine,
  likely powered by Intel OpenVINO / ONNX Runtime on x86 and ARM compute
  libraries on ARM-based hardware.
- Canonical is developing snap-based AI tooling under the "AI workloads on
  Ubuntu" initiative announced at Ubuntu Summit 2025.
- The inference engine will likely expose a local HTTP endpoint — similar to
  Ollama — using an OpenAI-compatible `/v1/chat/completions` API.
- Model management will probably use `snap install <model-snap>` and models
  will be accessible by name (e.g. `gemma3:4b`, `llama3.2:3b`).

Assumed API (subject to change)
--------------------------------
  Base URL:   http://localhost:<port>/v1          (port TBD, env: UBUNTU_AI_URL)
  Auth:       None (local, Unix socket possible)
  Models:     Named by installed model snaps
  Protocol:   OpenAI chat completions (streaming optional)

References
----------
  https://ubuntu.com/blog/ubuntu-ai-workloads           (Ubuntu AI initiative)
  https://snapcraft.io/                                  (Snap packaging)
  https://ubuntu.com/download/server (26.04 release info)

When implementing
-----------------
  1. Replace the `raise NotImplementedError` bodies with real httpx calls.
  2. Mirror OllamaAdapter (spl/adapters/ollama.py) — same OpenAI-compat pattern.
  3. Add "snap" to _bootstrap() in spl/adapters/__init__.py.
  4. Add "snap" to SUPPORTED_MODELS in spl/splc/cli.py.
  5. Update spl/splc/README.md supported targets table.
  6. Remove this docstring WARNING block and update the module docstring.
"""

from __future__ import annotations

import logging
import os

from spl3.adapters.base import LLMAdapter, GenerationResult

logger = logging.getLogger(__name__)

# ── Known model snaps (placeholder — update when Ubuntu 26.04 ships) ──────────
_KNOWN_MODEL_SNAPS: list[str] = [
    # These are speculative — will be confirmed from snapcraft.io
    "gemma3:4b",
    "llama3.2:3b",
    "phi3:mini",
    "mistral:7b",
]

_DEFAULT_BASE_URL = "http://localhost:11500"   # port TBD — placeholder
_DEFAULT_MODEL    = "gemma3:4b"                # placeholder


class SnapAdapter(LLMAdapter):
    """LLM adapter for the Ubuntu 26.04 AI Inference Snap.

    [PLACEHOLDER — not yet functional]

    Args:
        base_url:  Override the inference snap's local HTTP endpoint.
                   Defaults to UBUNTU_AI_URL env var, then localhost:11500.
        model:     Model snap name (e.g. "gemma3:4b").
        timeout:   HTTP timeout in seconds.
    """

    _NOT_IMPLEMENTED_MSG = (
        "SnapAdapter is a placeholder.  Ubuntu 26.04 AI inference snap is not "
        "yet released.  Implement this adapter once the snap API is confirmed."
    )

    def __init__(
        self,
        base_url: str | None = None,
        model: str = _DEFAULT_MODEL,
        timeout: int = 120,
    ):
        self.base_url = (
            base_url
            or os.environ.get("UBUNTU_AI_URL")
            or _DEFAULT_BASE_URL
        )
        self.model = model
        self.timeout = timeout
        logger.warning(
            "SnapAdapter is a placeholder — Ubuntu 26.04 AI inference snap "
            "is not yet available.  Calls will raise NotImplementedError."
        )

    async def generate(
        self,
        prompt: str,
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system: str | None = None,
    ) -> GenerationResult:
        # TODO: implement once Ubuntu 26.04 snap API is confirmed.
        # Expected: POST {base_url}/v1/chat/completions  (OpenAI-compatible)
        # Mirror OllamaAdapter.generate() — same payload structure.
        raise NotImplementedError(self._NOT_IMPLEMENTED_MSG)

    def count_tokens(self, text: str, model: str = "") -> int:
        # TODO: query the snap's tokeniser endpoint if available.
        return len(text) // 4   # rough estimate until real tokeniser is known

    def list_models(self) -> list[str]:
        # TODO: query installed model snaps via `snap list` or a local API.
        # snap list --all | grep model-snap-prefix
        return list(_KNOWN_MODEL_SNAPS)

    def __repr__(self) -> str:
        return f"SnapAdapter(base_url={self.base_url!r}, model={self.model!r}) [placeholder]"
