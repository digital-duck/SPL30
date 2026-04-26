"""SPL adapters — SPL30 extends SPL20's adapter registry with new providers.

SPL30 adds:
  - liquid  — Liquid AI LFM models (Ollama local or OpenRouter cloud)

All SPL20 adapters (claude_cli, anthropic, openai, ollama, openrouter, google,
deepseek, qwen, bedrock, vertex, azure_openai, echo) are re-registered here
unchanged.  This file shadows SPL20's spl/adapters/__init__.py, so it must
replicate the bootstrap logic in full.
"""

from __future__ import annotations

import importlib as _importlib
import inspect as _inspect
import logging as _logging
from pathlib import Path as _Path

# ── Extend __path__ to include SPL20's adapters/ ──────────────────────────────
# Keeps `from spl3.adapters.claude_cli import …` etc. resolvable via SPL20's files.
_spl20_adapters = _Path(__file__).parent.parent.parent.parent / "SPL20" / "spl" / "adapters"
if _spl20_adapters.exists():
    __path__ = list(__path__) + [str(_spl20_adapters)]

# ── Re-export base types ───────────────────────────────────────────────────────
from spl3.adapters.base import LLMAdapter, GenerationResult  # noqa: F401

_log = _logging.getLogger("spl.adapters")
_ADAPTER_REGISTRY: dict[str, type] = {}

# Providers handled natively by dd-llm bridge
_DD_LLM_PROVIDERS: dict[str, str] = {
    "anthropic":  "anthropic",
    "openai":     "openai",
    "ollama":     "ollama",
    "openrouter": "openrouter",
    "claude_cli": "claude_cli",
    "gemini_cli": "gemini_cli",
    "google":     "gemini",
}


# ── Public registry API (mirrors SPL20) ───────────────────────────────────────

def register_adapter(name: str, adapter_cls) -> None:
    """Register an LLM adapter by name (class or factory callable)."""
    _ADAPTER_REGISTRY[name] = adapter_cls


def get_adapter(name: str, **kwargs) -> LLMAdapter:
    """Get an LLM adapter instance by name."""
    if name not in _ADAPTER_REGISTRY:
        available = ", ".join(sorted(_ADAPTER_REGISTRY.keys())) or "(none)"
        raise ValueError(f"Unknown adapter '{name}'. Available: {available}")
    entry = _ADAPTER_REGISTRY[name]
    if _inspect.isclass(entry):
        sig = _inspect.signature(entry.__init__)
        supported = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return entry(**supported)
    return entry(**kwargs)


def list_adapters() -> list[str]:
    """List registered adapter names (sorted)."""
    return sorted(_ADAPTER_REGISTRY.keys())


# ── Bootstrap ─────────────────────────────────────────────────────────────────

def _bootstrap() -> None:
    # 1. dd-llm bridge (preferred for standard cloud providers)
    #    Use SPL30's MultiModalDDLLMBridge so generate_multimodal() works.
    _dd_ok = False
    try:
        from spl3.adapters.dd_llm_bridge import MultiModalDDLLMBridge
        for _spl_name, _dd_name in _DD_LLM_PROVIDERS.items():
            register_adapter(_spl_name, lambda p=_dd_name, **kw: MultiModalDDLLMBridge(p, **kw))
        _log.debug("dd-llm multimodal bridge registered: %s", ", ".join(_DD_LLM_PROVIDERS))
        _dd_ok = True
    except ImportError:
        _log.debug("dd-llm not found; falling back to bespoke adapters")

    # 2. Bespoke fallback adapters (when dd-llm not installed)
    if not _dd_ok:
        for _name, _mod, _cls in [
            ("claude_cli", "spl.adapters.claude_cli", "ClaudeCLIAdapter"),
            ("gemini_cli", "spl3.adapters.gemini_cli", "GeminiCLIAdapter"),
            ("openrouter", "spl.adapters.openrouter", "OpenRouterAdapter"),
            ("ollama",     "spl.adapters.ollama",     "OllamaAdapter"),
            ("anthropic",  "spl.adapters.anthropic",  "AnthropicAdapter"),
            ("openai",     "spl.adapters.openai",     "OpenAIAdapter"),
            ("google",     "spl.adapters.google",     "GoogleAdapter"),
        ]:
            try:
                register_adapter(_name, getattr(_importlib.import_module(_mod), _cls))
            except (ImportError, AttributeError):
                pass

    # 3. Always-available SPL20 adapters
    for _name, _mod, _cls in [
        ("echo",         "spl.adapters.echo",         "EchoAdapter"),
        ("deepseek",     "spl.adapters.deepseek",     "DeepSeekAdapter"),
        ("qwen",         "spl.adapters.qwen",         "QwenAdapter"),
        ("bedrock",      "spl.adapters.bedrock",      "BedrockAdapter"),
        ("vertex",       "spl.adapters.vertex",       "VertexAdapter"),
        ("azure_openai", "spl.adapters.azure_openai", "AzureOpenAIAdapter"),
    ]:
        try:
            register_adapter(_name, getattr(_importlib.import_module(_mod), _cls))
        except (ImportError, AttributeError):
            pass

    # 4. SPL30 new adapters
    for _name, _mod, _cls in [
        ("liquid",     "spl3.adapters.liquid",     "LiquidAdapter"),
        ("snap",       "spl3.adapters.snap",       "SnapAdapter"),    # placeholder — Ubuntu 26.04
        ("gemini_cli", "spl3.adapters.gemini_cli", "GeminiCLIAdapter"),
    ]:
        try:
            register_adapter(_name, getattr(_importlib.import_module(_mod), _cls))
        except (ImportError, AttributeError):
            _log.debug("SPL30 adapter '%s' not available", _name)


_bootstrap()
