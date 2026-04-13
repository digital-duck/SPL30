"""SPL 3.0 extension of the SPL 2.0 DDLLMBridge.

Adds ``generate_multimodal()`` support for vision-capable providers that
expose an OpenAI-compatible messages API (Ollama, OpenAI, OpenRouter, …).

The multimodal content array (SPL 3.0 ImagePart / TextPart format) is
converted to OpenAI-compatible message content blocks and forwarded via the
existing dd-llm ``call(messages=…)`` path — no new provider code needed.
"""

from __future__ import annotations

import asyncio
import logging

from spl.adapters.dd_llm_bridge import DDLLMBridge
from spl.adapters.base import GenerationResult

_log = logging.getLogger("spl.adapters.bridge")


def _to_wav_base64(b64_data: str, src_fmt: str) -> tuple[str, str]:
    """Convert base64-encoded compressed audio to base64 WAV.

    Ollama only accepts WAV in its input_audio content blocks.  This helper
    decodes the base64 payload, converts via pydub, and re-encodes as base64.

    Returns (wav_b64_data, "wav").  Raises ImportError if pydub is not installed.
    """
    import base64
    import io
    try:
        from pydub import AudioSegment  # type: ignore[import]
    except ImportError:
        raise ImportError(
            f"Ollama requires WAV audio but received {src_fmt!r}. "
            "Install pydub to auto-convert: pip install pydub\n"
            "Also requires ffmpeg: sudo apt install ffmpeg"
        )
    raw = base64.b64decode(b64_data)
    audio = AudioSegment.from_file(io.BytesIO(raw), format=src_fmt)
    buf = io.BytesIO()
    audio.export(buf, format="wav")
    wav_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    _log.debug("_to_wav_base64: converted %s → wav (%d bytes)", src_fmt, len(buf.getvalue()))
    return wav_b64, "wav"


class MultiModalDDLLMBridge(DDLLMBridge):
    """DDLLMBridge extended with generate_multimodal() for IMAGE/video input.

    Converts SPL 3.0 ContentPart dicts to the OpenAI content-array format
    and calls the underlying dd-llm adapter's ``call(messages=…)`` path.

    Supported content part types:
      - ``{"type": "text",  "text": "..."}``
      - ``{"type": "image", "source": "base64", "media_type": "…", "data": "…"}``
      - ``{"type": "image", "source": "url",    "url": "https://…"}``
    """

    async def generate_multimodal(
        self,
        content: list[dict],
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system: str | None = None,
    ) -> GenerationResult:
        """Generate from a structured content array (text + image parts).

        Builds an OpenAI-compatible ``messages`` list and forwards it to the
        dd-llm adapter's synchronous ``call()`` method.
        """
        user_content: list[dict] = []
        for part in content:
            ptype = part.get("type")
            if ptype == "text":
                user_content.append({"type": "text", "text": part.get("text", "")})
            elif ptype == "image":
                if part.get("source") == "base64":
                    mt = part.get("media_type", "image/jpeg")
                    data = part.get("data", "")
                    data_uri = f"data:{mt};base64,{data}"
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": data_uri},
                    })
                elif part.get("source") == "url":
                    user_content.append({
                        "type": "image_url",
                        "image_url": {"url": part.get("url", "")},
                    })
            elif ptype == "audio":
                # OpenAI input_audio format (used by OpenRouter LFM-2.5 and Ollama).
                # Ollama only accepts WAV — convert compressed formats on the fly.
                mt = part.get("media_type", "audio/wav")
                fmt = mt.split("/")[-1]   # "wav", "mp3", "ogg"
                data = part.get("data", "")
                if self._provider_name == "ollama" and fmt != "wav":
                    data, fmt = _to_wav_base64(data, fmt)
                user_content.append({
                    "type": "input_audio",
                    "input_audio": {"data": data, "format": fmt},
                })
            else:
                _log.debug("generate_multimodal: skipping unsupported part type %r", ptype)

        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user_content})

        result = await asyncio.to_thread(
            self._impl.call,
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        if not result.success:
            last_err = (
                result.error_history[-1].get("error", "unknown")
                if result.error_history
                else "unknown"
            )
            raise RuntimeError(
                f"dd-llm [{self._provider_name}] multimodal failed: {last_err}"
            )
        return GenerationResult(
            content=result.content,
            model=result.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            total_tokens=result.input_tokens + result.output_tokens,
            latency_ms=result.latency_ms,
            cost_usd=result.cost_usd,
        )
