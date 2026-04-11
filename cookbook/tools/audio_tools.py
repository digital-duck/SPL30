"""
cookbook/tools/audio_tools.py — Audio conversion and utility tools.

Dependencies: ffmpeg (system), pydub (pip install pydub)
"""

from __future__ import annotations

import datetime
import json
import pathlib
import subprocess

from spl.tools import spl_tool

_SUPPORTED_FORMATS = {"mp3", "wav", "ogg", "flac", "aac", "m4a", "opus"}


def _ffmpeg(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-y", *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


@spl_tool
def convert_audio(
    audio_path: str,
    target_format: str,
    bitrate: str = "192k",
    sample_rate: str = "44100",
    output_dir: str = ".",
) -> str:
    """CONVERT_AUDIO(audio_path, target_format [, bitrate, sample_rate, output_dir])

    Convert an audio file to a different format via ffmpeg.

    Args:
        audio_path    : Source audio file path.
        target_format : Target format — mp3, wav, ogg, flac, aac, m4a, opus.
        bitrate       : Output bitrate (default '192k', ignored for lossless formats).
        sample_rate   : Sample rate in Hz (default 44100).
        output_dir    : Directory to write the converted file (created if missing).

    Returns the path of the converted audio file.
    Raises UnsupportedFormat if target_format is not recognised.
    """
    fmt = str(target_format).strip().lower().lstrip(".")
    if fmt not in _SUPPORTED_FORMATS:
        raise ValueError(f"UnsupportedFormat: '{fmt}'. Supported: {sorted(_SUPPORTED_FORMATS)}")

    src = pathlib.Path(str(audio_path).strip())
    out_dir = pathlib.Path(str(output_dir).strip())
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"{src.stem}_{ts}.{fmt}"

    br = str(bitrate).strip() or "192k"
    sr = str(sample_rate).strip() or "44100"

    ffmpeg_args = ["-i", str(src), "-ar", sr]
    if fmt not in ("wav", "flac"):
        ffmpeg_args += ["-b:a", br]
    ffmpeg_args.append(str(dst))

    result = _ffmpeg(*ffmpeg_args, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"CodecError: ffmpeg failed:\n{result.stderr}")
    return str(dst.resolve())


@spl_tool
def trim_audio(
    audio_path: str,
    start_sec: str,
    end_sec: str,
    output_dir: str = ".",
) -> str:
    """TRIM_AUDIO(audio_path, start_sec, end_sec [, output_dir])

    Trim an audio file to a time range [start_sec, end_sec].
    Returns the path of the trimmed file (same format as source).
    """
    src = pathlib.Path(str(audio_path).strip())
    out_dir = pathlib.Path(str(output_dir).strip())
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"{src.stem}_trim_{ts}{src.suffix}"

    t_start = str(start_sec).strip()
    t_end = str(end_sec).strip()
    result = _ffmpeg("-i", str(src), "-ss", t_start, "-to", t_end, "-c", "copy", str(dst), check=False)
    if result.returncode != 0:
        raise RuntimeError(f"CodecError: ffmpeg trim failed:\n{result.stderr}")
    return str(dst.resolve())


@spl_tool
def get_audio_duration(audio_path: str) -> str:
    """GET_AUDIO_DURATION(audio_path) — return duration in seconds as a string.

    Uses ffprobe; returns '0' if duration cannot be determined.
    """
    src = pathlib.Path(str(audio_path).strip())
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", str(src),
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return "0"
    data = json.loads(result.stdout)
    return str(data.get("format", {}).get("duration", "0"))
