"""Audio codec — encode audio files as base64 AudioPart dicts.

Accepts WAV, MP3, OGG, or FLAC file paths (or raw bytes) and returns an
``AudioPart`` dict ready to pass to ``adapter.generate_multimodal()``.

No heavy dependencies required for WAV files — the standard library ``wave``
module handles WAV inspection.  For MP3/OGG/FLAC, the ``pydub`` library is
used when available; otherwise raw bytes are encoded as-is.

Examples::

    from spl3.codecs.audio_codec import encode_audio

    part = encode_audio("clip.wav")
    part = encode_audio("speech.mp3")
    part = encode_audio(raw_wav_bytes, media_type="audio/wav")
"""

from __future__ import annotations

import base64
import io
import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spl3.adapters.base_multimodal import AudioPart

_MIME_MAP: dict[str, str] = {
    "audio/wav":  "audio/wav",
    "audio/x-wav": "audio/wav",
    "audio/mpeg": "audio/mp3",
    "audio/mp3":  "audio/mp3",
    "audio/ogg":  "audio/ogg",
    "audio/flac": "audio/flac",
}
_DEFAULT_MEDIA_TYPE = "audio/wav"

# Max duration hint — LLM APIs typically cap at 25 MB or ~5 minutes of audio.
# This codec does NOT enforce this; callers should chunk long audio themselves.


def encode_audio(
    source: "str | Path | bytes",
    *,
    media_type: str | None = None,
    to_wav: bool = False,
) -> "AudioPart":
    """Encode an audio clip as a base64 ``AudioPart`` dict.

    Args:
        source:      File path (str/Path) or raw bytes.
        media_type:  Override the inferred MIME type.  If omitted, inferred
                     from the file extension.  For raw bytes, defaults to
                     ``"audio/wav"``.
        to_wav:      Convert to WAV before encoding (requires ``pydub``).
                     Useful to normalise MP3/OGG for APIs that only accept WAV.

    Returns:
        An ``AudioPart`` dict with ``source="base64"``.
    """
    if isinstance(source, (str, Path)):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
        inferred_mt = _infer_mime(path) or _DEFAULT_MEDIA_TYPE
        mt = media_type or inferred_mt

        if to_wav and mt != "audio/wav":
            data = _convert_to_wav(path)
            mt = "audio/wav"
        else:
            data = path.read_bytes()

        return _make_part(data, mt)

    if isinstance(source, (bytes, bytearray)):
        mt = media_type or _DEFAULT_MEDIA_TYPE
        if to_wav and mt != "audio/wav":
            data = _convert_to_wav_bytes(bytes(source), mt)
            mt = "audio/wav"
        else:
            data = bytes(source)
        return _make_part(data, mt)

    raise TypeError(
        f"encode_audio: unsupported source type {type(source).__name__}. "
        "Expected file path or bytes."
    )


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_part(data: bytes, media_type: str) -> "AudioPart":
    return {
        "type":       "audio",
        "source":     "base64",
        "media_type": media_type,
        "data":       base64.b64encode(data).decode("ascii"),
    }


def _infer_mime(path: Path) -> str | None:
    mt, _ = mimetypes.guess_type(str(path))
    return _MIME_MAP.get(mt or "", None)


def _convert_to_wav(path: Path) -> bytes:
    """Convert audio file to WAV bytes using pydub (if available)."""
    try:
        from pydub import AudioSegment  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "pydub is required for audio format conversion. "
            "Install it with: pip install pydub\n"
            "Also requires ffmpeg: https://ffmpeg.org/download.html"
        )
    audio = AudioSegment.from_file(str(path))
    buf = io.BytesIO()
    audio.export(buf, format="wav")
    return buf.getvalue()


def _convert_to_wav_bytes(data: bytes, source_media_type: str) -> bytes:
    """Convert raw audio bytes to WAV bytes using pydub."""
    try:
        from pydub import AudioSegment  # type: ignore[import]
    except ImportError:
        raise ImportError(
            "pydub is required for audio format conversion. "
            "Install it with: pip install pydub"
        )
    fmt = source_media_type.split("/")[-1]  # "mp3", "ogg", etc.
    audio = AudioSegment.from_file(io.BytesIO(data), format=fmt)
    buf = io.BytesIO()
    audio.export(buf, format="wav")
    return buf.getvalue()
