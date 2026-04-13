#!/usr/bin/env python3
"""
run.py — physical runner for Recipe 58: Audio Format Conversion.

Converts an audio file between formats using ffmpeg (via subprocess).
No LLM is required — this is a deterministic codec operation.

Usage
-----
  # MP3 → WAV
  python cookbook/59_audio_convert/run.py \\
      --audio cookbook/59_audio_convert/sample/clip.mp3 \\
      --target-format wav

  # MP3 → OGG (128k bitrate)
  python cookbook/59_audio_convert/run.py \\
      --audio cookbook/59_audio_convert/sample/clip.mp3 \\
      --target-format ogg --bitrate 128k

  # MP3 → FLAC (lossless)
  python cookbook/59_audio_convert/run.py \\
      --audio cookbook/59_audio_convert/sample/clip.mp3 \\
      --target-format flac

  # WAV → MP3 with high quality
  python cookbook/59_audio_convert/run.py \\
      --audio cookbook/59_audio_convert/sample/clip.wav \\
      --target-format mp3 --bitrate 320k --sample-rate 48000

  # Custom output directory
  python cookbook/59_audio_convert/run.py \\
      --audio cookbook/59_audio_convert/sample/clip.mp3 \\
      --target-format wav --output-dir /tmp/converted
"""

from __future__ import annotations

import datetime
import shutil
import subprocess
import sys
from pathlib import Path

import click

# ── Path setup (run from repo root or recipe directory) ───────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

_SUPPORTED_FORMATS = {"mp3", "wav", "ogg", "flac", "aac", "m4a", "opus"}
_LOSSLESS_FORMATS = {"wav", "flac"}


def _check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        print("[audio_convert] ERROR: ffmpeg not found.")
        print("  Ubuntu/Debian: sudo apt install ffmpeg")
        print("  macOS:         brew install ffmpeg")
        sys.exit(1)


def convert_audio(
    audio_path: str,
    target_format: str,
    bitrate: str,
    sample_rate: int,
    output_dir: str,
) -> Path:
    _check_ffmpeg()

    fmt = target_format.strip().lower().lstrip(".")
    if fmt not in _SUPPORTED_FORMATS:
        print(f"[audio_convert] ERROR: Unsupported format '{fmt}'.")
        print(f"  Supported: {sorted(_SUPPORTED_FORMATS)}")
        sys.exit(1)

    src = Path(audio_path.strip())
    if not src.exists():
        print(f"[audio_convert] ERROR: Source file not found: {src}")
        sys.exit(1)

    out_dir = Path(output_dir.strip())
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = out_dir / f"{src.stem}_{ts}.{fmt}"

    print(f"[audio_convert] {src.name}  →  {dst.name}  "
          f"(bitrate={bitrate}, sample_rate={sample_rate})")

    cmd = ["ffmpeg", "-y", "-i", str(src), "-ar", str(sample_rate)]
    if fmt not in _LOSSLESS_FORMATS:
        cmd += ["-b:a", bitrate]
    cmd.append(str(dst))

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[audio_convert] ERROR: ffmpeg failed:\n{result.stderr}")
        sys.exit(1)

    print(f"[audio_convert] saved → {dst.resolve()}")
    return dst


@click.command()
@click.option("--audio",         required=True, help="Source audio file path")
@click.option("--target-format", default="mp3", show_default=True,
              type=click.Choice(sorted(_SUPPORTED_FORMATS)))
@click.option("--bitrate",       default="192k", show_default=True,
              help="Bitrate for lossy formats, e.g. 128k, 192k, 320k")
@click.option("--sample-rate",   default=44100, show_default=True, type=int,
              help="Output sample rate in Hz")
@click.option("--output-dir",    default="cookbook/59_audio_convert/outputs", show_default=True)
def main(audio, target_format, bitrate, sample_rate, output_dir) -> None:
    """Recipe 58 — Audio Format Conversion (SPL 3.0)."""
    dst = convert_audio(
        audio_path=audio,
        target_format=target_format,
        bitrate=bitrate,
        sample_rate=sample_rate,
        output_dir=output_dir,
    )

    click.echo()
    click.echo("── Result ───────────────────────────────────────────────────────────")
    click.echo(f"Converted audio: {dst}")
    click.echo("─────────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
