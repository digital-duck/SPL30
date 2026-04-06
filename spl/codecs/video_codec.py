"""Video codec — extract frames from video files as ImagePart lists.

Accepts a video file path and returns a list of ``ImagePart`` dicts (one per
sampled frame) ready to pass to ``adapter.generate_multimodal()``.

Dependencies
------------
- **OpenCV** (``cv2``): primary frame extractor.  Install: ``pip install opencv-python-headless``
- **Pillow** fallback: if cv2 is not available, GIF files can be extracted
  frame-by-frame using Pillow.  Other video formats require cv2.

Examples::

    from spl.codecs.video_codec import encode_video

    frames = encode_video("demo.mp4", fps=1, max_frames=8)
    # → list of up to 8 ImagePart dicts sampled at 1 frame per second

    content = [{"type": "text", "text": "Describe this video."}, *frames]
    result = await adapter.generate_multimodal(content)
"""

from __future__ import annotations

import io
import base64
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spl.adapters.base_multimodal import ImagePart

_DEFAULT_FPS = 1
_DEFAULT_MAX_FRAMES = 16
_JPEG_QUALITY = 80


def encode_video(
    source: "str | Path",
    *,
    fps: float = _DEFAULT_FPS,
    max_frames: int = _DEFAULT_MAX_FRAMES,
    max_dim: int | None = 1024,
    quality: int = _JPEG_QUALITY,
) -> "list[ImagePart]":
    """Extract frames from a video file as a list of base64 ``ImagePart`` dicts.

    Args:
        source:     Path to the video file (MP4, AVI, MOV, GIF, …).
        fps:        Sample rate in frames per second.  ``1`` = one frame per
                    second, ``0.5`` = one frame every two seconds.
        max_frames: Hard cap on the number of frames returned.  Frames are
                    sampled evenly from the video duration if the raw count
                    exceeds this limit.
        max_dim:    Resize frames so the longest edge is at most this many
                    pixels.  ``None`` to skip resizing.
        quality:    JPEG quality (1–95) for the encoded frames.

    Returns:
        A list of ``ImagePart`` dicts (``source="base64"``, ``media_type="image/jpeg"``).

    Raises:
        FileNotFoundError: if the video file does not exist.
        ImportError:       if neither cv2 nor Pillow (for GIF) is available.
        RuntimeError:      if the video file cannot be opened.
    """
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Video file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".gif":
        return _extract_gif(path, fps=fps, max_frames=max_frames,
                            max_dim=max_dim, quality=quality)
    return _extract_cv2(path, fps=fps, max_frames=max_frames,
                        max_dim=max_dim, quality=quality)


# ── cv2 extractor (primary) ────────────────────────────────────────────────────

def _extract_cv2(
    path: Path,
    fps: float,
    max_frames: int,
    max_dim: int | None,
    quality: int,
) -> "list[ImagePart]":
    try:
        import cv2  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "opencv-python-headless is required for video frame extraction. "
            "Install it with: pip install opencv-python-headless"
        )

    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video file: {path}")

    video_fps: float = cap.get(cv2.CAP_PROP_FPS) or 24.0
    total_frames: int = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Frame indices to sample
    step = max(1, int(round(video_fps / fps)))
    indices = list(range(0, total_frames, step))

    # Apply max_frames cap via even sub-sampling
    if len(indices) > max_frames:
        every = len(indices) / max_frames
        indices = [indices[int(i * every)] for i in range(max_frames)]

    parts: list[ImagePart] = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        # cv2 uses BGR; convert to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        parts.append(_encode_ndarray(frame_rgb, max_dim=max_dim, quality=quality))

    cap.release()
    return parts


def _encode_ndarray(arr: object, max_dim: int | None, quality: int) -> "ImagePart":
    """Encode a numpy HxWx3 RGB array as a JPEG ImagePart."""
    from PIL import Image as _PILImage  # type: ignore[import]
    img = _PILImage.fromarray(arr)  # type: ignore[arg-type]
    return _resize_and_encode(img, max_dim=max_dim, quality=quality)


# ── GIF extractor (Pillow fallback) ───────────────────────────────────────────

def _extract_gif(
    path: Path,
    fps: float,
    max_frames: int,
    max_dim: int | None,
    quality: int,
) -> "list[ImagePart]":
    try:
        from PIL import Image as _PILImage  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "Pillow is required for GIF frame extraction. "
            "Install it with: pip install Pillow"
        )

    parts: list[ImagePart] = []
    img = _PILImage.open(path)
    n_frames = getattr(img, "n_frames", 1)
    duration_ms = img.info.get("duration", 100)  # ms per frame

    # Sample at requested fps
    step = max(1, int(round(1000 / (duration_ms * fps))))
    indices = list(range(0, n_frames, step))
    if len(indices) > max_frames:
        every = len(indices) / max_frames
        indices = [indices[int(i * every)] for i in range(max_frames)]

    for idx in indices:
        img.seek(idx)
        frame = img.convert("RGB")
        parts.append(_resize_and_encode(frame, max_dim=max_dim, quality=quality))

    return parts


# ── Shared encode helper ───────────────────────────────────────────────────────

def _resize_and_encode(img: object, max_dim: int | None, quality: int) -> "ImagePart":
    from PIL import Image as _PILImage  # type: ignore[import]
    assert isinstance(img, _PILImage.Image)

    if max_dim is not None:
        w, h = img.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            img = img.resize(
                (int(w * ratio), int(h * ratio)),
                getattr(_PILImage, "LANCZOS", _PILImage.BICUBIC),
            )

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality)
    return {
        "type":       "image",
        "source":     "base64",
        "media_type": "image/jpeg",
        "data":       base64.b64encode(buf.getvalue()).decode("ascii"),
    }
