"""Liquid AI LFM adapter for SPL 3.0.

Supports two backends:
  - "ollama"      Local inference via Ollama (v0.17.1-rc0+, LFM2 models loaded).
                  Uses the OpenAI-compatible endpoint at localhost:11434.
  - "openrouter"  Cloud inference via OpenRouter (OpenAI-compatible API).
                  Requires OPENROUTER_API_KEY env var.

Liquid Foundation Models (LFMs) are optimised for high-efficiency on-device
and edge-native inference.  LFM2 family:
  lfm2-8b      → small, fast, on-device (≈8B params, 1B active)
  lfm2-24b     → mid-range (≈24B params, 2B active)
  lfm-2.5      → production, multimodal

Usage:
  # Local via Ollama (pull the model first: ollama pull lfm2-8b)
  adapter = LiquidAdapter(backend="ollama", model="lfm2-8b")

  # Cloud via OpenRouter
  adapter = LiquidAdapter(backend="openrouter", model="liquid/lfm2-8b-a1b")

  result = await adapter.generate("Summarise this text: ...")
"""

from __future__ import annotations

import logging
import os

from spl.adapters.base import LLMAdapter, GenerationResult

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ── Model catalogue ────────────────────────────────────────────────────────────

_OLLAMA_MODELS = [
    "lfm2-8b",
    "lfm2-24b",
    "lfm-2.5",
]

_OPENROUTER_MODELS = [
    "liquid/lfm2-8b-a1b",
    "liquid/lfm2-24b-a2b",
    "liquid/lfm-2.5-1.2b-instruct:free",
]

_DEFAULT_MODEL: dict[str, str] = {
    "ollama":      "lfm2-8b",
    "openrouter":  "liquid/lfm2-8b-a1b",
}

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


class LiquidAdapter(LLMAdapter):
    """LLM adapter for Liquid AI Foundation Models (LFMs).

    Args:
        backend:      "ollama" (default) or "openrouter".
        model:        Model name for the chosen backend.  Defaults to the
                      smallest model for the backend.
        base_url:     Override the API base URL.  Useful for custom Ollama
                      installations or proxies.
        api_key:      OpenRouter API key.  Falls back to OPENROUTER_API_KEY
                      env var when backend="openrouter".
        timeout:      HTTP request timeout in seconds (default 120).
    """

    def __init__(
        self,
        backend: str = "ollama",
        model: str = "",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = 120,
    ):
        if httpx is None:
            raise ImportError(
                "httpx is required for LiquidAdapter. "
                "Install it with: pip install httpx"
            )

        backend = backend.lower()
        if backend not in ("ollama", "openrouter"):
            raise ValueError(
                f"LiquidAdapter backend must be 'ollama' or 'openrouter', got '{backend}'"
            )

        self.backend = backend
        self.model = model or _DEFAULT_MODEL[backend]
        self.timeout = timeout

        if backend == "ollama":
            self.base_url = (
                base_url
                or os.environ.get("OLLAMA_BASE_URL")
                or "http://localhost:11434"
            )
            self._api_key: str | None = None
        else:  # openrouter
            self.base_url = base_url or _OPENROUTER_BASE_URL
            self._api_key = (
                api_key
                or os.environ.get("OPENROUTER_API_KEY")
            )
            if not self._api_key:
                raise ValueError(
                    "LiquidAdapter(backend='openrouter') requires an API key. "
                    "Set OPENROUTER_API_KEY or pass api_key=..."
                )

        self._client = httpx.AsyncClient(timeout=timeout)

    # ── Core generation ────────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system: str | None = None,
    ) -> GenerationResult:
        """Generate a response from a Liquid AI LFM."""
        model = model or self.model

        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload: dict = {
            "model":       model,
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
            "stream":      False,
        }

        if self.backend == "ollama":
            url = f"{self.base_url}/v1/chat/completions"
            headers: dict[str, str] = {"Content-Type": "application/json"}
        else:
            url = f"{self.base_url}/chat/completions"
            headers = {
                "Content-Type":  "application/json",
                "Authorization": f"Bearer {self._api_key}",
                "HTTP-Referer":  "https://github.com/digital-duck/SPL30",
                "X-Title":       "SPL30 splc compiler",
            }

        start = self._measure_time()
        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        except httpx.ConnectError:
            if self.backend == "ollama":
                raise ConnectionError(
                    f"Cannot connect to Ollama at {self.base_url}. "
                    "Make sure Ollama is running (`ollama serve`) and the "
                    f"LFM model is pulled (`ollama pull {model}`)."
                )
            raise

        data = response.json()
        latency_ms = self._elapsed_ms(start)

        choice  = data.get("choices", [{}])[0]
        message = choice.get("message", {})
        content = message.get("content", "") or ""

        usage        = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", 0)
        output_tokens= usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

        # OpenRouter returns cost in USD in the response
        cost_usd: float | None = None
        if self.backend == "openrouter":
            cost_usd = data.get("usage", {}).get("cost")

        return GenerationResult(
            content=content,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd if cost_usd is None else float(cost_usd),
        )

    # ── Supporting methods ────────────────────────────────────────────────────

    def count_tokens(self, text: str, model: str = "") -> int:
        """Approximate token count (4 chars ≈ 1 token; no LFM tokeniser available)."""
        return len(text) // 4

    def list_models(self) -> list[str]:
        """List known Liquid AI models for the active backend."""
        if self.backend == "ollama":
            try:
                with httpx.Client(timeout=5) as client:
                    response = client.get(f"{self.base_url}/api/tags")
                    response.raise_for_status()
                    all_models = [m["name"] for m in response.json().get("models", [])]
                    lfm = [m for m in all_models if "lfm" in m.lower()]
                    if lfm:
                        return sorted(lfm)
            except Exception:
                pass
            return list(_OLLAMA_MODELS)
        else:
            return list(_OPENROUTER_MODELS)

    async def close(self) -> None:
        await self._client.aclose()

    def __repr__(self) -> str:
        return f"LiquidAdapter(backend={self.backend!r}, model={self.model!r})"
