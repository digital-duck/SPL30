#!/usr/bin/env python3
"""
run.py — physical runner for Recipe 54: Image Restyle.

IMAGE + TEXT  →  TEXT + IMAGE

Pipeline
--------
  1. Encode source image via spl.codecs.encode_image
  2. Call Gemma4 (Ollama) via generate_multimodal():
       image + style instruction → JSON {description, dalle_prompt}
  3. Call DALL-E 3 with the generated prompt → new image file
  4. Output: description text  +  restyled image file

Both the original analysis (TEXT) and the new image (IMAGE) are produced.

Usage
-----
  # Default style (watercolor)
  python cookbook/58_image_restyle/run.py --image path/to/photo.jpg

  # Custom style
  python cookbook/58_image_restyle/run.py \\
      --image photo.jpg \\
      --style "Studio Ghibli anime, soft illustration, warm colors"

  # Oil painting, preserve composition
  python cookbook/58_image_restyle/run.py \\
      --image photo.jpg \\
      --style "oil painting, impressionist, thick brushstrokes" \\
      --preserve "composition, lighting, main subject"

  # Landscape HD
  python cookbook/58_image_restyle/run.py \\
      --image photo.jpg --style "cyberpunk neon" \\
      --aspect landscape --quality hd
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path

import click

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from spl.codecs import encode_image              # noqa: E402
from spl.adapters.liquid import LiquidAdapter   # noqa: E402

try:
    from openai import AsyncOpenAI as _AsyncOpenAI
    _OPENAI_OK = True
except ImportError:
    _AsyncOpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_OK = False

_DALL_E_3_SIZES = {
    "square":    "1024x1024",
    "landscape": "1792x1024",
    "portrait":  "1024x1792",
}

_ANALYSE_SYSTEM = (
    "You are a visual artist and prompt engineer. "
    "Respond with valid JSON only — no markdown, no explanation."
)
_ANALYSE_PROMPT = """\
Analyse this image and create a DALL-E 3 prompt to recreate it in a new style.

Style to apply: {style}
Elements to preserve: {preserve}

Return a JSON object with exactly these two fields:
{{
  "description": "<1-2 sentence description of the original image>",
  "dalle_prompt": "<detailed DALL-E 3 prompt under 150 words>"
}}"""


# ── Step 1: Vision analysis via Gemma4 ────────────────────────────────────────

async def analyse_image(
    image: str,
    style: str,
    preserve: str,
    vision_model: str,
    max_dim: int,
) -> tuple[str, str]:
    """Returns (description, dalle_prompt)."""
    adapter = LiquidAdapter(backend="ollama", model=vision_model)
    try:
        t0 = time.perf_counter()
        image_part = encode_image(image, max_dim=max_dim)
        encode_ms  = (time.perf_counter() - t0) * 1000
        media_type = image_part.get("media_type", "image/jpeg")
        b64_kb     = len(image_part.get("data", "")) * 3 // 4 // 1024
        print(f"[image_restyle] encoded {media_type} ~{b64_kb} KB ({encode_ms:.0f} ms)")

        content = [
            {"type": "text", "text": _ANALYSE_PROMPT.format(style=style, preserve=preserve)},
            image_part,
        ]

        print(f"[image_restyle] → Gemma4 vision analysis ({vision_model}) ...")
        t1 = time.perf_counter()
        result = await adapter.generate_multimodal(
            content,
            system=_ANALYSE_SYSTEM,
            max_tokens=512,
        )
        latency_ms = (time.perf_counter() - t1) * 1000
        print(f"[image_restyle] vision ✓ ({latency_ms:.0f} ms)")

        # Parse JSON response
        raw = result.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw)
        return data.get("description", ""), data.get("dalle_prompt", raw)

    except json.JSONDecodeError:
        # Fallback: treat full response as the dalle_prompt
        print("[image_restyle] WARNING: vision model did not return valid JSON — using raw output as prompt")
        return "", result.content.strip()
    finally:
        await adapter.close()


# ── Step 2: Image generation via DALL-E 3 ────────────────────────────────────

async def generate_image(
    prompt: str,
    aspect: str,
    quality: str,
    dalle_style: str,
    output_dir: Path,
) -> Path:
    if not _OPENAI_OK or _AsyncOpenAI is None:
        raise ImportError("openai library required. Install: pip install openai")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    client = _AsyncOpenAI(api_key=api_key)
    size = _DALL_E_3_SIZES.get(aspect, "1024x1024")
    ts   = int(time.time())
    out  = output_dir / f"restyled_{ts}.png"

    print(f"[image_restyle] → DALL-E 3 ({size}, quality={quality}, style={dalle_style}) ...")
    t0 = time.perf_counter()
    response = await client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size=size,
        quality=quality,
        style=dalle_style,
        response_format="b64_json",
    )
    latency_ms = (time.perf_counter() - t0) * 1000

    revised = getattr(response.data[0], "revised_prompt", None)
    if revised:
        print(f"[image_restyle] DALL-E revised: {revised[:80]}...")

    img_bytes = base64.b64decode(response.data[0].b64_json)
    out.write_bytes(img_bytes)
    size_kb = len(img_bytes) // 1024
    print(f"[image_restyle] ✓ saved {out.name} ({size_kb} KB, {latency_ms:.0f} ms)")
    return out


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run(
    image: str,
    style: str,
    preserve: str,
    aspect: str,
    quality: str,
    dalle_style: str,
    vision_model: str,
    max_dim: int,
    output_dir: Path,
) -> tuple[str, str, Path]:
    description, dalle_prompt = await analyse_image(
        image=image,
        style=style,
        preserve=preserve,
        vision_model=vision_model,
        max_dim=max_dim,
    )
    out_path = await generate_image(
        prompt=dalle_prompt,
        aspect=aspect,
        quality=quality,
        dalle_style=dalle_style,
        output_dir=output_dir,
    )
    return description, dalle_prompt, out_path


@click.command()
@click.option("--image",        required=True, help="Source image path")
@click.option("--style",        default="watercolor painting, soft edges, pastel tones",
              show_default=True, help="Style transformation to apply")
@click.option("--preserve",     default="composition, main subject, mood",
              show_default=True, help="Elements to preserve from the original")
@click.option("--aspect",       default="square", show_default=True,
              type=click.Choice(["square", "landscape", "portrait"]))
@click.option("--quality",      default="standard", show_default=True,
              type=click.Choice(["standard", "hd"]))
@click.option("--dalle-style",  default="natural", show_default=True,
              type=click.Choice(["natural", "vivid"]))
@click.option("--vision-model", default="gemma4:e4b", show_default=True,
              help="Ollama vision model for image analysis")
@click.option("--max-dim",      default=1024, show_default=True, type=int)
@click.option("--output-dir",   default="cookbook/58_image_restyle/outputs", show_default=True)
def main(image, style, preserve, aspect, quality, dalle_style, vision_model, max_dim, output_dir) -> None:
    """Recipe 54 — Image Restyle (IMAGE+TEXT → TEXT+IMAGE)."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    description, dalle_prompt, out_path = asyncio.run(run(
        image=image,
        style=style,
        preserve=preserve,
        aspect=aspect,
        quality=quality,
        dalle_style=dalle_style,
        vision_model=vision_model,
        max_dim=max_dim,
        output_dir=out_dir,
    ))

    click.echo()
    click.echo("── Text output (vision analysis) ────────────────────────────────────")
    if description:
        click.echo(f"Description:   {description}")
    click.echo(f"DALL-E prompt: {dalle_prompt}")
    click.echo()
    click.echo("── Image output ─────────────────────────────────────────────────────")
    click.echo(f"Restyled image: {out_path}")
    click.echo("─────────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
