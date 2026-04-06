#!/usr/bin/env python3
"""
run.py — physical runner for Recipe 52: Text to Image.

Pipeline
--------
  1. (optional) Enhance prompt via Gemma4 / Ollama  ← LiquidAdapter.generate()
  2. Generate image via DALL-E 3 (openai)
  3. Save PNG to outputs/

Backends
--------
  dall-e-3   OpenAI DALL-E 3 (default, requires OPENAI_API_KEY)
  dall-e-2   OpenAI DALL-E 2 (cheaper, lower quality)

Usage
-----
  # Minimal — DALL-E 3 with default prompt
  python cookbook/52_text_to_image/run.py --prompt "A fox in a moonlit forest"

  # With prompt enhancement via Gemma4
  python cookbook/52_text_to_image/run.py \\
      --prompt "A fox in a forest" --enhance --style "oil painting"

  # Landscape aspect, HD quality
  python cookbook/52_text_to_image/run.py \\
      --prompt "Tokyo skyline at night" \\
      --aspect landscape --quality hd

  # Vivid style (DALL-E 3 only)
  python cookbook/52_text_to_image/run.py \\
      --prompt "Dragon over a medieval castle" \\
      --dalle-style vivid
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import os
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from spl.adapters.liquid import LiquidAdapter   # noqa: E402

try:
    from openai import AsyncOpenAI
    _OPENAI_OK = True
except ImportError:
    _OPENAI_OK = False

# ── Size map for DALL-E aspect ratios ─────────────────────────────────────────
_DALL_E_3_SIZES = {
    "square":    "1024x1024",
    "landscape": "1792x1024",
    "portrait":  "1024x1792",
}
_DALL_E_2_SIZES = {
    "square":    "1024x1024",
    "landscape": "1024x1024",   # DALL-E 2 only supports square
    "portrait":  "1024x1024",
}

_ENHANCE_SYSTEM = "You are a professional prompt engineer. Output only the enhanced prompt."
_ENHANCE_PROMPT = """\
Enhance this image prompt to be more vivid and effective for DALL-E 3.
Style: {style}  |  Aspect: {aspect}

Original: {prompt}

Return ONLY the enhanced prompt (under 200 words), no explanation."""


# ── Prompt enhancement via Ollama Gemma4 ─────────────────────────────────────

async def enhance_prompt(prompt: str, style: str, aspect: str, llm_model: str) -> str:
    adapter = LiquidAdapter(backend="ollama", model=llm_model)
    try:
        result = await adapter.generate(
            _ENHANCE_PROMPT.format(prompt=prompt, style=style, aspect=aspect),
            system=_ENHANCE_SYSTEM,
            max_tokens=256,
        )
        enhanced = result.content.strip()
        print(f"[text_to_image] enhanced prompt ({len(enhanced)} chars)")
        return enhanced
    finally:
        await adapter.close()


# ── Image generation via OpenAI DALL-E ────────────────────────────────────────

async def generate_image_dalle(
    prompt: str,
    model: str,
    aspect: str,
    quality: str,
    dalle_style: str,
    output_dir: Path,
) -> Path:
    if not _OPENAI_OK:
        raise ImportError("openai library not found. Install: pip install openai")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    client = AsyncOpenAI(api_key=api_key)
    sizes = _DALL_E_3_SIZES if model == "dall-e-3" else _DALL_E_2_SIZES
    size = sizes.get(aspect, "1024x1024")

    kwargs: dict = dict(
        model=model,
        prompt=prompt,
        n=1,
        size=size,
        response_format="b64_json",
    )
    if model == "dall-e-3":
        kwargs["quality"] = quality          # "standard" | "hd"
        kwargs["style"]   = dalle_style      # "natural" | "vivid"

    print(f"[text_to_image] → DALL-E {model} ({size}, quality={quality}) ...")
    t0 = time.perf_counter()
    response = await client.images.generate(**kwargs)
    latency_ms = (time.perf_counter() - t0) * 1000

    b64 = response.data[0].b64_json
    revised = getattr(response.data[0], "revised_prompt", None)
    if revised:
        print(f"[text_to_image] DALL-E revised prompt: {revised[:80]}...")

    img_bytes = base64.b64decode(b64)
    ts = int(time.time())
    out_path = output_dir / f"generated_{ts}.png"
    out_path.write_bytes(img_bytes)

    size_kb = len(img_bytes) // 1024
    print(f"[text_to_image] ✓ saved {out_path.name} ({size_kb} KB, {latency_ms:.0f} ms)")
    return out_path


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run(
    prompt: str,
    style: str,
    aspect: str,
    quality: str,
    dalle_style: str,
    enhance: bool,
    model: str,
    llm_model: str,
    output_dir: Path,
) -> Path:
    final_prompt = prompt
    if enhance:
        print("[text_to_image] enhancing prompt via Ollama ...")
        final_prompt = await enhance_prompt(prompt, style, aspect, llm_model)

    return await generate_image_dalle(
        prompt=final_prompt,
        model=model,
        aspect=aspect,
        quality=quality,
        dalle_style=dalle_style,
        output_dir=output_dir,
    )


def main() -> None:
    p = argparse.ArgumentParser(
        description="Recipe 52 — Text to Image (SPL 3.0 multimodal output)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--prompt",  required=True, help="Text prompt to generate image from")
    p.add_argument("--style",   default="photorealistic",
                   help='Visual style hint for prompt enhancer (default: "photorealistic")')
    p.add_argument("--aspect",  default="square", choices=["square", "landscape", "portrait"])
    p.add_argument("--quality", default="standard", choices=["standard", "hd"],
                   help="DALL-E 3 quality (default: standard; hd costs more)")
    p.add_argument("--dalle-style", default="natural", choices=["natural", "vivid"],
                   dest="dalle_style",
                   help="DALL-E 3 style: natural (realistic) or vivid (dramatic)")
    p.add_argument("--enhance", action="store_true",
                   help="Enhance prompt via Gemma4 / Ollama before generating")
    p.add_argument("--model",   default="dall-e-3", choices=["dall-e-3", "dall-e-2"])
    p.add_argument("--llm-model", default="gemma4:e4b", dest="llm_model",
                   help="Ollama model for prompt enhancement (default: gemma4:e4b)")
    p.add_argument("--output-dir", default="cookbook/52_text_to_image/outputs",
                   dest="output_dir")
    args = p.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = asyncio.run(run(
        prompt=args.prompt,
        style=args.style,
        aspect=args.aspect,
        quality=args.quality,
        dalle_style=args.dalle_style,
        enhance=args.enhance,
        model=args.model,
        llm_model=args.llm_model,
        output_dir=output_dir,
    ))

    print()
    print("── Output ───────────────────────────────────────────────────────────")
    print(f"Image saved: {out_path}")
    print("─────────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
