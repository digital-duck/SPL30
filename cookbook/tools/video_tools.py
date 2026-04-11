"""
cookbook/tools/video_tools.py — Video extraction and utility tools.

Dependencies: ffmpeg + ffprobe (system install)
"""

from __future__ import annotations

import datetime
import json
import pathlib
import subprocess

from spl.tools import spl_tool

_AUDIO_FORMATS = {"mp3", "wav", "ogg", "flac", "aac", "m4a", "opus"}
_IMAGE_FORMATS = {"jpg", "jpeg", "png", "webp"}


def _ffmpeg(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    cmd = ["ffmpeg", "-y", *args]
    return subprocess.run(cmd, capture_output=True, text=True, check=check)


def _ffprobe(video_path: str) -> dict:
    result = subprocess.run(
        [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_streams", "-show_format", video_path,
        ],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        return {}
    return json.loads(result.stdout)


@spl_tool
def extract_audio(
    video_path: str,
    target_format: str = "mp3",
    bitrate: str = "192k",
    sample_rate: str = "44100",
    output_dir: str = ".",
) -> str:
    """EXTRACT_AUDIO(video_path [, target_format, bitrate, sample_rate, output_dir])

    Extract the audio track from a video file via ffmpeg.

    Args:
        video_path    : Source video file path.
        target_format : Audio format for output — mp3, wav, ogg, flac, aac, m4a (default mp3).
        bitrate       : Output bitrate (default '192k').
        sample_rate   : Sample rate in Hz (default 44100).
        output_dir    : Directory to write the audio file (created if missing).

    Returns the path of the extracted audio file.
    Raises NoAudioTrack if the video has no audio stream.
    Raises UnsupportedFormat if target_format is not recognised.
    """
    fmt = str(target_format).strip().lower().lstrip(".")
    if fmt not in _AUDIO_FORMATS:
        raise ValueError(f"UnsupportedFormat: '{fmt}'. Supported: {sorted(_AUDIO_FORMATS)}")

    src = pathlib.Path(str(video_path).strip())
    probe = _ffprobe(str(src))
    streams = probe.get("streams", [])
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if not has_audio:
        raise RuntimeError("NoAudioTrack: video file has no audio stream")

    out_dir = pathlib.Path(str(output_dir).strip())
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"{src.stem}_audio_{ts}.{fmt}"

    br = str(bitrate).strip() or "192k"
    sr = str(sample_rate).strip() or "44100"
    ffmpeg_args = ["-i", str(src), "-vn", "-ar", sr]
    if fmt not in ("wav", "flac"):
        ffmpeg_args += ["-b:a", br]
    ffmpeg_args.append(str(dst))

    result = _ffmpeg(*ffmpeg_args, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"CodecError: ffmpeg audio extraction failed:\n{result.stderr}")
    return str(dst.resolve())


@spl_tool
def extract_frame(
    video_path: str,
    mode: str = "middle",
    timestamp: str = "0",
    output_dir: str = ".",
    image_format: str = "jpg",
) -> str:
    """EXTRACT_FRAME(video_path [, mode, timestamp, output_dir, image_format])

    Extract a single frame from a video file.

    Args:
        video_path   : Source video file path.
        mode         : 'first', 'middle', 'last', 'timestamp' (default 'middle').
        timestamp    : Seconds from start — used only when mode='timestamp'.
        output_dir   : Directory to write the frame image (created if missing).
        image_format : Output image format — jpg, png, webp (default jpg).

    Returns the path of the extracted frame image.
    Raises InvalidTimestamp if mode='timestamp' and timestamp is out of range.
    """
    fmt = str(image_format).strip().lower().lstrip(".")
    if fmt not in _IMAGE_FORMATS:
        fmt = "jpg"

    src = pathlib.Path(str(video_path).strip())
    probe = _ffprobe(str(src))
    duration = float(probe.get("format", {}).get("duration", "0") or "0")

    m = str(mode).strip().lower()
    if m == "first":
        t = 0.0
    elif m == "last":
        t = max(0.0, duration - 0.1)
    elif m == "timestamp":
        t = float(str(timestamp).strip() or "0")
        if duration > 0 and (t < 0 or t > duration):
            raise ValueError(
                f"InvalidTimestamp: {t}s is outside video duration {duration:.1f}s"
            )
    else:  # middle (default)
        t = duration / 2.0

    out_dir = pathlib.Path(str(output_dir).strip())
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"{src.stem}_frame_{ts}.{fmt}"

    result = _ffmpeg(
        "-ss", str(t), "-i", str(src),
        "-frames:v", "1", "-q:v", "2",
        str(dst), check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"CodecError: ffmpeg frame extraction failed:\n{result.stderr}")
    return str(dst.resolve())


@spl_tool
def get_video_duration(video_path: str) -> str:
    """GET_VIDEO_DURATION(video_path) — return duration in seconds as a string.

    Returns '0' if duration cannot be determined.
    """
    probe = _ffprobe(str(video_path).strip())
    return str(probe.get("format", {}).get("duration", "0"))


@spl_tool
def video_info(video_path: str) -> str:
    """VIDEO_INFO(video_path) — return JSON with duration, width, height, codec, fps."""
    probe = _ffprobe(str(video_path).strip())
    fmt = probe.get("format", {})
    video_stream = next(
        (s for s in probe.get("streams", []) if s.get("codec_type") == "video"),
        {},
    )
    audio_stream = next(
        (s for s in probe.get("streams", []) if s.get("codec_type") == "audio"),
        {},
    )

    # Parse fps fraction e.g. "30000/1001"
    fps_raw = video_stream.get("r_frame_rate", "0/1")
    try:
        num, den = fps_raw.split("/")
        fps = round(int(num) / int(den), 3)
    except Exception:
        fps = 0.0

    return json.dumps({
        "duration": float(fmt.get("duration", 0) or 0),
        "size_bytes": int(fmt.get("size", 0) or 0),
        "width": video_stream.get("width", 0),
        "height": video_stream.get("height", 0),
        "video_codec": video_stream.get("codec_name", ""),
        "fps": fps,
        "audio_codec": audio_stream.get("codec_name", ""),
        "audio_channels": audio_stream.get("channels", 0),
        "file": str(pathlib.Path(str(video_path).strip()).resolve()),
    })
