#!/usr/bin/env python3
"""
run.py — physical runner for Recipe 50: Image Caption.

Bridge between the SPL logical view (image_caption.spl) and the current
physical implementation.  The SPL executor will handle IMAGE-typed params
natively once multimodal param pass-through lands in spl/executor.py.

Supported models (vision-capable, via Ollama):
  gemma4          — Google Gemma 4 (default; native image+text)
  gemma4:27b      — larger Gemma 4 variant
  llava:13b       — LLaVA (fallback if Gemma 4 not pulled)
  llava-phi3      — lightweight LLaVA

Via OpenRouter:
  liquid/lfm-2.5-1.2b-instruct:free  — Liquid AI LFM-2.5 (multimodal)
  google/gemma-3-27b-it:free          — Gemma 3 27B

Usage
-----
  # Minimal — caption a local image (Gemma 4 via Ollama)
  python cookbook/50_image_caption/run.py --image path/to/photo.jpg

  # Custom question
  python cookbook/50_image_caption/run.py \\
      --image path/to/photo.jpg \\
      --question "What text is visible in this image?"

  # OCR mode
  python cookbook/50_image_caption/run.py \\
      --image path/to/screenshot.png --mode ocr

  # Detailed description
  python cookbook/50_image_caption/run.py \\
      --image path/to/photo.jpg --mode detailed

  # Public URL (no encoding needed)
  python cookbook/50_image_caption/run.py \\
      --image "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"

  # Via OpenRouter (LFM-2.5)
  python cookbook/50_image_caption/run.py \\
      --image path/to/photo.jpg \\
      --backend openrouter \\
      --model liquid/lfm-2.5-1.2b-instruct:free
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

# ── Path setup (run from repo root or directly) ───────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from spl.codecs import encode_image                     # noqa: E402
from spl.adapters.liquid import LiquidAdapter           # noqa: E402

# ── Prompt templates (mirror image_caption.spl CREATE FUNCTIONs) ─────────────

_PROMPTS = {
    "caption": (
        "You are a precise visual analyst.\n\n"
        "Look at the image and answer the following question concisely and accurately.\n\n"
        "Question: {question}"
    ),
    "detailed": (
        "You are a detailed visual analyst. Describe this image comprehensively.\n\n"
        "Cover:\n"
        "- Main subject(s) and their key characteristics\n"
        "- Setting, background, environment\n"
        "- Colors, lighting, and overall mood\n"
        "- Any visible text, signs, or notable details"
    ),
    "ocr": (
        "You are an OCR engine. Extract all visible text from this image exactly as it appears.\n"
        "If no text is present, reply with: [NO TEXT FOUND]"
    ),
}

_SYSTEM = "You are a helpful visual assistant. Answer based only on what you observe in the image."


async def run(
    image: str,
    question: str,
    mode: str,
    model: str,
    backend: str,
    max_dim: int,
    max_tokens: int,
) -> str:
    adapter = LiquidAdapter(backend=backend, model=model)
    try:
        # 1. Encode image via codec layer
        t0 = time.perf_counter()
        image_part = encode_image(image, max_dim=max_dim)
        encode_ms = (time.perf_counter() - t0) * 1000

        src = image_part.get("source")
        if src == "base64":
            b64_len = len(image_part.get("data", ""))
            size_kb = b64_len * 3 // 4 // 1024
            print(f"[image_caption] encoded {image_part['media_type']} "
                  f"~{size_kb} KB ({encode_ms:.0f} ms)")
        else:
            print(f"[image_caption] URL pass-through: {image}")

        # 2. Build prompt
        prompt_text = _PROMPTS.get(mode, _PROMPTS["caption"])
        if mode == "caption":
            prompt_text = prompt_text.format(question=question)

        # 3. Call generate_multimodal
        content = [
            {"type": "text", "text": prompt_text},
            image_part,
        ]
        print(f"[image_caption] → {backend}/{model} (mode={mode}) ...")
        t1 = time.perf_counter()
        result = await adapter.generate_multimodal(
            content,
            system=_SYSTEM,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - t1) * 1000
        print(f"[image_caption] ✓ {result.input_tokens} in / {result.output_tokens} out "
              f"({latency_ms:.0f} ms)")
        return result.content

    finally:
        await adapter.close()


def main() -> None:
    p = argparse.ArgumentParser(
        description="Recipe 50 — Image Caption (SPL 3.0 multimodal)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--image",    required=True,
                   help="Local file path or public HTTPS URL")
    p.add_argument("--question", default="What is in this image? Describe it in detail.",
                   help="Question to ask about the image (caption mode only)")
    p.add_argument("--mode",     default="caption",
                   choices=["caption", "detailed", "ocr"],
                   help="caption (Q&A) | detailed (full description) | ocr (text extraction)")
    p.add_argument("--model",    default="gemma4",
                   help="Model name (default: gemma4)")
    p.add_argument("--backend",  default="ollama",
                   choices=["ollama", "openrouter"],
                   help="Backend: ollama (local) or openrouter (cloud)")
    p.add_argument("--max-dim",  type=int, default=1024, dest="max_dim",
                   help="Resize longest edge to N pixels before encoding (default 1024)")
    p.add_argument("--max-tokens", type=int, default=1024, dest="max_tokens",
                   help="Max output tokens (default 1024)")
    args = p.parse_args()

    caption = asyncio.run(run(
        image=args.image,
        question=args.question,
        mode=args.mode,
        model=args.model,
        backend=args.backend,
        max_dim=args.max_dim,
        max_tokens=args.max_tokens,
    ))

    print()
    print("── Result ───────────────────────────────────────────────────────────")
    print(caption)
    print("─────────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
