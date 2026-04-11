#!/usr/bin/env python3
"""
run.py — physical runner for Recipe 57: Image Format Conversion.

Converts an image file between formats using Pillow.
No LLM is required — this is a deterministic codec operation.

Usage
-----
  # PNG → JPEG (default quality 85)
  python cookbook/57_image_convert/run.py \\
      --image cookbook/50_image_caption/sample/photo.jpg \\
      --target-format png

  # JPEG → WebP (quality 90)
  python cookbook/57_image_convert/run.py \\
      --image cookbook/50_image_caption/sample/photo.jpg \\
      --target-format webp --quality 90

  # JPEG → BMP (lossless)
  python cookbook/57_image_convert/run.py \\
      --image cookbook/50_image_caption/sample/photo.jpg \\
      --target-format bmp

  # Custom output directory
  python cookbook/57_image_convert/run.py \\
      --image cookbook/50_image_caption/sample/photo.jpg \\
      --target-format webp --output-dir /tmp/converted
"""

from __future__ import annotations

import datetime
import sys
from pathlib import Path

import click

# ── Path setup (run from repo root or recipe directory) ───────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

_SUPPORTED_FORMATS = {"jpeg", "jpg", "png", "webp", "bmp", "gif", "tiff"}


def convert_image(
    image_path: str,
    target_format: str,
    quality: int,
    output_dir: str,
) -> Path:
    try:
        from PIL import Image
    except ImportError:
        print("[image_convert] ERROR: Pillow not installed. Run: pip install Pillow")
        sys.exit(1)

    fmt = target_format.strip().lower().lstrip(".")
    if fmt not in _SUPPORTED_FORMATS:
        print(f"[image_convert] ERROR: Unsupported format '{fmt}'.")
        print(f"  Supported: {sorted(_SUPPORTED_FORMATS)}")
        sys.exit(1)

    src = Path(image_path.strip())
    if not src.exists():
        print(f"[image_convert] ERROR: Source file not found: {src}")
        sys.exit(1)

    out_dir = Path(output_dir.strip())
    out_dir.mkdir(parents=True, exist_ok=True)

    pil_fmt = "JPEG" if fmt == "jpg" else fmt.upper()
    suffix = ".jpg" if fmt == "jpg" else f".{fmt}"
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"{src.stem}_{ts}{suffix}"

    print(f"[image_convert] {src.name}  →  {dst.name}  (quality={quality})")

    img = Image.open(src)
    if pil_fmt == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    save_kwargs: dict = {}
    if pil_fmt in ("JPEG", "WEBP"):
        save_kwargs["quality"] = quality

    img.save(dst, format=pil_fmt, **save_kwargs)
    print(f"[image_convert] saved → {dst.resolve()}")
    return dst


@click.command()
@click.option("--image",         required=True, help="Source image file path")
@click.option("--target-format", default="jpeg", show_default=True,
              type=click.Choice(["jpeg", "jpg", "png", "webp", "bmp", "gif", "tiff"]))
@click.option("--quality",       default=85, show_default=True, type=int,
              help="Compression quality for JPEG/WebP (1–95)")
@click.option("--output-dir",    default="cookbook/57_image_convert/outputs", show_default=True)
def main(image, target_format, quality, output_dir) -> None:
    """Recipe 57 — Image Format Conversion (SPL 3.0)."""
    dst = convert_image(
        image_path=image,
        target_format=target_format,
        quality=quality,
        output_dir=output_dir,
    )

    click.echo()
    click.echo("── Result ───────────────────────────────────────────────────────────")
    click.echo(f"Converted image: {dst}")
    click.echo("─────────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
