"""Image codec — encode images as base64 ImagePart dicts.

Accepts PIL Images, file paths, raw bytes, or public URLs and returns an
``ImagePart`` dict ready to pass to ``adapter.generate_multimodal()``.

Dependencies
------------
- **Pillow** (optional but recommended): enables format conversion, auto
  JPEG compression for large images, and resizing.  If not installed, raw
  file bytes are base64-encoded as-is (works for JPEG/PNG files on disk).
- No dependency needed for URL-based image parts.

Examples::

    from spl3.codecs.image_codec import encode_image

    # From file path
    part = encode_image("photo.jpg")

    # From PIL Image
    from PIL import Image
    img = Image.open("photo.png").convert("RGB")
    part = encode_image(img, max_dim=1024)

    # URL pass-through (no encoding needed)
    part = encode_image("https://example.com/photo.jpg")
"""

from __future__ import annotations

import base64
import io
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spl3.adapters.base_multimodal import ImagePart

# MIME type → media_type string understood by LLM APIs
_MIME_MAP: dict[str, str] = {
    "image/jpeg": "image/jpeg",
    "image/png":  "image/png",
    "image/webp": "image/webp",
    "image/gif":  "image/gif",
}
_DEFAULT_MEDIA_TYPE = "image/jpeg"
_MAX_DIM_DEFAULT = 1568   # Anthropic recommends ≤1568 on longest side
_JPEG_QUALITY = 85


def encode_image(
    source: "str | Path | bytes | object",
    *,
    max_dim: int | None = _MAX_DIM_DEFAULT,
    quality: int = _JPEG_QUALITY,
    media_type: str | None = None,
) -> "ImagePart":
    """Encode an image as a base64 ``ImagePart`` dict.

    Args:
        source:      File path (str/Path), PIL Image object, raw bytes, or
                     a public HTTPS URL.  URLs are returned as ``source="url"``
                     parts — no downloading or encoding is performed.
        max_dim:     Resize so the longest edge is at most this many pixels.
                     Set to ``None`` to skip resizing.  Applies only when
                     Pillow is available.
        quality:     JPEG quality (1–95) used when saving with Pillow.
        media_type:  Override the inferred MIME type (e.g. ``"image/png"``).

    Returns:
        An ``ImagePart`` dict with ``source="base64"`` (or ``source="url"``
        for HTTP/HTTPS strings).
    """
    # ── URL pass-through ───────────────────────────────────────────────────
    if isinstance(source, str) and source.startswith(("http://", "https://")):
        part: ImagePart = {
            "type":       "image",
            "source":     "url",
            "url":        source,
            "media_type": media_type or _DEFAULT_MEDIA_TYPE,
        }
        return part

    # ── PIL Image ──────────────────────────────────────────────────────────
    try:
        from PIL import Image as _PILImage  # type: ignore[import]
        _PIL_AVAILABLE = True
    except ImportError:
        _PILImage = None
        _PIL_AVAILABLE = False

    if _PIL_AVAILABLE and _PILImage and isinstance(source, _PILImage.Image):
        return _encode_pil(source, max_dim=max_dim, quality=quality,
                           media_type=media_type or _DEFAULT_MEDIA_TYPE)

    # ── File path ──────────────────────────────────────────────────────────
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Image file not found: {path}")
        inferred_mt = _infer_mime(path) or _DEFAULT_MEDIA_TYPE
        mt = media_type or inferred_mt

        if _PIL_AVAILABLE and _PILImage:
            img = _PILImage.open(path).convert("RGB")
            return _encode_pil(img, max_dim=max_dim, quality=quality, media_type=mt)

        # Pillow not available — encode raw bytes
        data = path.read_bytes()
        return _make_part(data, mt)

    # ── Raw bytes ──────────────────────────────────────────────────────────
    if isinstance(source, (bytes, bytearray)):
        mt = media_type or _DEFAULT_MEDIA_TYPE
        if _PIL_AVAILABLE and _PILImage and max_dim is not None:
            img = _PILImage.open(io.BytesIO(bytes(source))).convert("RGB")
            return _encode_pil(img, max_dim=max_dim, quality=quality, media_type=mt)
        return _make_part(bytes(source), mt)

    raise TypeError(
        f"encode_image: unsupported source type {type(source).__name__}. "
        "Expected file path, PIL Image, bytes, or URL string."
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _encode_pil(img: object, *, max_dim: int | None, quality: int, media_type: str) -> "ImagePart":
    from PIL import Image as _PILImage  # type: ignore[import]
    assert isinstance(img, _PILImage.Image)

    if max_dim is not None:
        w, h = img.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            resample = getattr(_PILImage, "LANCZOS", getattr(_PILImage, "ANTIALIAS", None))
            img = img.resize((int(w * ratio), int(h * ratio)), resample)

    buf = io.BytesIO()
    fmt = "JPEG" if media_type in ("image/jpeg", "image/webp") else "PNG"
    img.save(buf, format=fmt, quality=quality if fmt == "JPEG" else None)
    return _make_part(buf.getvalue(), media_type)


def _make_part(data: bytes, media_type: str) -> "ImagePart":
    return {
        "type":       "image",
        "source":     "base64",
        "media_type": media_type,
        "data":       base64.b64encode(data).decode("ascii"),
    }


def _infer_mime(path: Path) -> str | None:
    mt, _ = mimetypes.guess_type(str(path))
    return _MIME_MAP.get(mt or "", None)
