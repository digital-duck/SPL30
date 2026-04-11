"""
cookbook/tools/image_tools.py — Image conversion and utility tools.

Dependencies: Pillow (pip install Pillow)
"""

from __future__ import annotations

import pathlib
import datetime

from spl.tools import spl_tool

_SUPPORTED_FORMATS = {"jpeg", "jpg", "png", "webp", "bmp", "gif", "tiff"}


@spl_tool
def convert_image(
    image_path: str,
    target_format: str,
    quality: str = "85",
    output_dir: str = ".",
) -> str:
    """CONVERT_IMAGE(image_path, target_format [, quality, output_dir])

    Convert an image file to a different format using Pillow.

    Args:
        image_path    : Source image file path.
        target_format : Target format — jpeg, png, webp, bmp, gif, tiff.
        quality       : JPEG/WebP quality 1–95 (default 85, ignored for lossless formats).
        output_dir    : Directory to write the converted file (created if missing).

    Returns the path of the converted image file.
    Raises UnsupportedFormat if target_format is not recognised.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required: pip install Pillow") from exc

    fmt = str(target_format).strip().lower().lstrip(".")
    if fmt not in _SUPPORTED_FORMATS:
        raise ValueError(f"UnsupportedFormat: '{fmt}'. Supported: {sorted(_SUPPORTED_FORMATS)}")

    src = pathlib.Path(str(image_path).strip())
    out_dir = pathlib.Path(str(output_dir).strip())
    out_dir.mkdir(parents=True, exist_ok=True)

    pil_fmt = "JPEG" if fmt == "jpg" else fmt.upper()
    suffix = ".jpg" if fmt == "jpg" else f".{fmt}"
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"{src.stem}_{ts}{suffix}"

    q = int(str(quality).strip() or "85")
    img = Image.open(src)
    if pil_fmt == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    save_kwargs: dict = {}
    if pil_fmt in ("JPEG", "WEBP"):
        save_kwargs["quality"] = q
    img.save(dst, format=pil_fmt, **save_kwargs)
    return str(dst.resolve())


@spl_tool
def resize_image(
    image_path: str,
    width: str,
    height: str = "0",
    output_dir: str = ".",
) -> str:
    """RESIZE_IMAGE(image_path, width [, height, output_dir])

    Resize an image. If height is 0 or omitted, aspect ratio is preserved.
    Returns the path of the resized image.
    """
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required: pip install Pillow") from exc

    src = pathlib.Path(str(image_path).strip())
    out_dir = pathlib.Path(str(output_dir).strip())
    out_dir.mkdir(parents=True, exist_ok=True)

    w = int(str(width).strip())
    h = int(str(height).strip() or "0")

    img = Image.open(src)
    if h == 0:
        ratio = w / img.width
        h = int(img.height * ratio)
    img_resized = img.resize((w, h))

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"{src.stem}_resized_{ts}{src.suffix}"
    img_resized.save(dst)
    return str(dst.resolve())


@spl_tool
def image_info(image_path: str) -> str:
    """IMAGE_INFO(image_path) — return JSON with width, height, mode, format."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillow is required: pip install Pillow") from exc

    import json

    src = pathlib.Path(str(image_path).strip())
    img = Image.open(src)
    return json.dumps({
        "width": img.width,
        "height": img.height,
        "mode": img.mode,
        "format": img.format or src.suffix.lstrip(".").upper(),
        "file": str(src.resolve()),
    })
