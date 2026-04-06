"""SPL 3.0 multi-modal adapter extension.

Extends the SPL 2.0 LLMAdapter base class with a `generate_multimodal` method
that accepts structured content blocks (text, image, audio, video) matching
the OpenAI / Anthropic content-array format.

Design principles
-----------------
- Backwards compatible: all SPL 2.0 adapters continue to work unchanged.
  `generate_multimodal` has a default implementation that extracts the text
  parts and falls back to the existing `generate()` method.
- Codec-agnostic: this layer handles *LLM API* formatting only.
  Raw data conversions (PIL Image → base64, audio WAV → bytes, video → frames)
  belong in `spl/codecs/` — not here.
- Type-safe: `ContentPart` is a typed dict so SPL type-checker can validate
  content blocks at workflow parse time.

Content part format (mirrors OpenAI / Anthropic)
-------------------------------------------------
  Text:
      {"type": "text",  "text": "Describe this image."}

  Image (base64):
      {"type": "image", "source": "base64",
       "media_type": "image/jpeg", "data": "<b64-string>"}

  Image (URL):
      {"type": "image", "source": "url", "url": "https://…"}

  Audio (base64):
      {"type": "audio", "source": "base64",
       "media_type": "audio/wav", "data": "<b64-string>"}

  Video (frame list):
      {"type": "video", "frames": [<image-part>, …], "fps": 1}

Adapters that support multi-modal input should override
`generate_multimodal`.  Adapters that only support text will use the default
fallback (text parts concatenated → `generate()`).
"""

from __future__ import annotations

from typing import TypedDict, Literal, Any

from spl.adapters.base import LLMAdapter, GenerationResult  # noqa: F401 re-export


# ── Content part types ────────────────────────────────────────────────────────

class TextPart(TypedDict):
    type: Literal["text"]
    text: str


class ImagePart(TypedDict, total=False):
    type: Literal["image"]
    source: Literal["base64", "url"]
    media_type: str          # "image/jpeg" | "image/png" | "image/webp" | "image/gif"
    data: str                # base64-encoded bytes (when source="base64")
    url: str                 # public URL (when source="url")


class AudioPart(TypedDict, total=False):
    type: Literal["audio"]
    source: Literal["base64"]
    media_type: str          # "audio/wav" | "audio/mp3" | "audio/ogg"
    data: str                # base64-encoded bytes


class VideoPart(TypedDict, total=False):
    type: Literal["video"]
    frames: list[ImagePart]  # extracted frames as image parts
    fps: float               # frames per second used for extraction


ContentPart = TextPart | ImagePart | AudioPart | VideoPart


# ── Multi-modal adapter mixin ─────────────────────────────────────────────────

class MultiModalMixin:
    """Mixin that adds `generate_multimodal` to any LLMAdapter subclass.

    Adapters that natively support multi-modal input (Anthropic Claude 3+,
    GPT-4o, Gemini, LFM-2.5, …) should override `generate_multimodal`.

    Adapters that only support text will use the default fallback, which
    concatenates all text parts and calls the existing `generate()`.
    """

    async def generate_multimodal(
        self,
        content: list[ContentPart],
        model: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.7,
        system: str | None = None,
    ) -> GenerationResult:
        """Generate from a list of structured content parts.

        Default implementation: extract text parts, join, call generate().
        Override in adapters that support native multi-modal input.
        """
        text_parts = [
            p["text"] for p in content
            if p.get("type") == "text" and p.get("text")
        ]
        non_text = [p for p in content if p.get("type") != "text"]
        if non_text:
            import logging
            logging.getLogger(__name__).warning(
                "%s does not implement native multi-modal generation; "
                "%d non-text part(s) will be ignored.",
                self.__class__.__name__, len(non_text),
            )
        prompt = "\n".join(text_parts)
        return await self.generate(  # type: ignore[attr-defined]
            prompt=prompt,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
        )

    @property
    def supports_multimodal(self) -> bool:
        """True if this adapter has a native multi-modal implementation."""
        return type(self).generate_multimodal is not MultiModalMixin.generate_multimodal


# ── Convenience type alias ────────────────────────────────────────────────────

class MultiModalAdapter(MultiModalMixin, LLMAdapter):
    """Base class for SPL 3.0 adapters that support multi-modal input.

    Subclass this (instead of LLMAdapter) when implementing a new adapter
    that natively handles image / audio / video input.

    Example::

        class MyVisionAdapter(MultiModalAdapter):
            async def generate(self, prompt, ...): ...
            async def generate_multimodal(self, content, ...): ...
            def count_tokens(self, text, model=""): ...
            def list_models(self): ...
    """
    pass
