#!/usr/bin/env python3
"""
run.py — physical runner for Recipe 51: Audio Summary.

Bridge between the SPL logical view (audio_summary.spl) and the current
physical implementation.  Uses spl.codecs.encode_audio to encode the audio
clip and LiquidAdapter.generate_multimodal() to send it to the model.

Audio backend notes
-------------------
- **OpenRouter + LFM-2.5** (default): confirmed multi-modal audio support.
  Requires OPENROUTER_API_KEY environment variable.
- **Ollama + LFM-2.5**: experimental — Ollama's audio passthrough for LFM
  is not yet confirmed upstream.  A warning is logged if you try this.
- **WAV recommended**: use --to-wav to convert MP3/OGG to WAV first if the
  API rejects the format.

Usage
-----
  # Summarise a WAV file via OpenRouter (default)
  python cookbook/52_audio_summary/run.py --audio path/to/clip.wav

  # Transcribe only
  python cookbook/52_audio_summary/run.py --audio clip.wav --mode transcribe

  # Extract key points (meeting notes style)
  python cookbook/52_audio_summary/run.py --audio meeting.wav --mode key_points

  # Custom summary style
  python cookbook/52_audio_summary/run.py \\
      --audio clip.wav --style "three bullet points"

  # Convert MP3 to WAV before sending (requires pydub + ffmpeg)
  python cookbook/52_audio_summary/run.py \\
      --audio clip.mp3 --to-wav

  # Via Ollama (experimental — audio support not yet confirmed)
  python cookbook/52_audio_summary/run.py \\
      --audio clip.wav --backend ollama --model lfm-2.5
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path

import click

# ── Path setup ────────────────────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from spl.codecs import encode_audio                     # noqa: E402
from spl.adapters.liquid import LiquidAdapter           # noqa: E402

# ── Prompt templates (mirror audio_summary.spl CREATE FUNCTIONs) ─────────────

_PROMPTS = {
    "transcribe": (
        "You are an accurate speech transcription engine.\n\n"
        "Listen to the audio and produce a verbatim transcript.\n"
        "Format: plain text, with speaker changes on new lines if distinguishable.\n"
        "If the audio is unclear, mark uncertain words with [?]."
    ),
    "summary": (
        "You are a concise summariser. Listen to the audio and produce a summary.\n\n"
        "Style: {style}\n\n"
        "Guidelines:\n"
        "- Capture the main topic, key points, and any conclusions.\n"
        "- Preserve names, dates, figures, and decisions exactly.\n"
        "- Omit filler words and off-topic remarks."
    ),
    "key_points": (
        "You are a meeting analyst. Listen to the audio and extract:\n\n"
        "1. Main topic / agenda item\n"
        "2. Key points discussed (bullet list)\n"
        "3. Decisions made (if any)\n"
        "4. Action items with owners (if mentioned)\n\n"
        "Format as structured Markdown."
    ),
}

_SYSTEM = "You are a helpful audio analysis assistant. Base your answer only on the provided audio."

# Default model: OpenRouter LFM-2.5 (confirmed audio support)
_DEFAULT_MODEL_OPENROUTER = "liquid/lfm-2.5-1.2b-instruct:free"
_DEFAULT_MODEL_OLLAMA      = "lfm-2.5"


async def run(
    audio: str,
    mode: str,
    style: str,
    model: str,
    backend: str,
    to_wav: bool,
    max_tokens: int,
) -> str:
    adapter = LiquidAdapter(backend=backend, model=model)
    try:
        # 1. Encode audio via codec layer
        t0 = time.perf_counter()
        audio_part = encode_audio(audio, to_wav=to_wav)
        encode_ms = (time.perf_counter() - t0) * 1000

        b64_len = len(audio_part.get("data", ""))
        size_kb = b64_len * 3 // 4 // 1024
        print(f"[audio_summary] encoded {audio_part['media_type']} "
              f"~{size_kb} KB ({encode_ms:.0f} ms)")

        # 2. Build prompt
        prompt_text = _PROMPTS.get(mode, _PROMPTS["summary"])
        if mode == "summary":
            prompt_text = prompt_text.format(style=style)

        # 3. Build content array — text instruction first, then audio
        content = [
            {"type": "text", "text": prompt_text},
            audio_part,
        ]

        print(f"[audio_summary] → {backend}/{model} (mode={mode}) ...")
        t1 = time.perf_counter()
        result = await adapter.generate_multimodal(
            content,
            system=_SYSTEM,
            max_tokens=max_tokens,
        )
        latency_ms = (time.perf_counter() - t1) * 1000
        print(f"[audio_summary] ✓ {result.input_tokens} in / {result.output_tokens} out "
              f"({latency_ms:.0f} ms)")
        return result.content

    finally:
        await adapter.close()


@click.command()
@click.option("--audio",      required=True, help="Path to audio file (WAV, MP3, OGG, FLAC)")
@click.option("--mode",       default="summary", show_default=True,
              type=click.Choice(["summary", "transcribe", "key_points"]))
@click.option("--style",      default="concise paragraph", show_default=True,
              help="Summary style hint")
@click.option("--backend",    default="openrouter", show_default=True,
              type=click.Choice(["openrouter", "ollama"]),
              help="openrouter (confirmed audio) | ollama (experimental)")
@click.option("--model",      default="", help="Override model (default auto-selected per backend)")
@click.option("--to-wav",     is_flag=True, help="Convert audio to WAV first (requires ffmpeg)")
@click.option("--max-tokens", default=2048, show_default=True, type=int)
def main(audio, mode, style, backend, model, to_wav, max_tokens) -> None:
    """Recipe 51 — Audio Summary (SPL 3.0 multimodal)."""
    if not model:
        model = _DEFAULT_MODEL_OPENROUTER if backend == "openrouter" else _DEFAULT_MODEL_OLLAMA

    if backend == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        raise click.UsageError(
            "OPENROUTER_API_KEY not set.\n"
            "  export OPENROUTER_API_KEY=sk-or-..."
        )

    result = asyncio.run(run(
        audio=audio,
        mode=mode,
        style=style,
        model=model,
        backend=backend,
        to_wav=to_wav,
        max_tokens=max_tokens,
    ))

    click.echo()
    click.echo("── Result ───────────────────────────────────────────────────────────")
    click.echo(result)
    click.echo("─────────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
