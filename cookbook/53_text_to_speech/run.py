#!/usr/bin/env python3
"""
run.py — physical runner for Recipe 53: Text to Speech.

Pipeline
--------
  1. (optional) Script prep via Gemma4 / Ollama — clean text for natural TTS
  2. Synthesise speech via:
       a. OpenAI TTS  (tts-1, tts-1-hd, gpt-4o-mini-tts)  — cloud, requires OPENAI_API_KEY
       b. system TTS  (`say` on macOS, `espeak` on Linux)  — local, zero dependencies
  3. Save MP3/WAV to outputs/

OpenAI voices (tts-1 / tts-1-hd)
  alloy echo fable onyx nova shimmer

gpt-4o-mini-tts voices (expressive, instruction-driven)
  alloy ash ballad coral echo fable onyx nova sage shimmer verse

Usage
-----
  # Minimal — OpenAI TTS, alloy voice
  python cookbook/53_text_to_speech/run.py \\
      --text "Hello from SPL 3.0 multimodal support."

  # High-definition audio
  python cookbook/53_text_to_speech/run.py \\
      --text "This is a detailed narration." --model tts-1-hd --voice nova

  # Read from a text file
  python cookbook/53_text_to_speech/run.py --file path/to/article.txt

  # Clean/prep script before TTS (remove markdown, expand abbreviations)
  python cookbook/53_text_to_speech/run.py \\
      --file article.md --prep --tone "professional"

  # Expressive TTS with instruction (gpt-4o-mini-tts)
  python cookbook/53_text_to_speech/run.py \\
      --text "Breaking news: SPL 3.0 ships multimodal support!" \\
      --model gpt-4o-mini-tts --voice coral \\
      --instructions "Speak like an excited news anchor."

  # Local system TTS (no API key needed)
  python cookbook/53_text_to_speech/run.py \\
      --text "Hello world." --backend system
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

import click

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from spl.adapters.liquid import LiquidAdapter   # noqa: E402

try:
    from openai import AsyncOpenAI as _AsyncOpenAI
    _OPENAI_OK = True
except ImportError:
    _AsyncOpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_OK = False

_PREP_SYSTEM = "You are a script editor. Output only the cleaned script, no explanation."
_PREP_PROMPT = """\
Clean this text for natural text-to-speech narration.
Tone: {tone}

Rules: expand abbreviations, remove markdown symbols (**, #, `-`), replace URLs
with brief descriptions, add natural pause punctuation.

Text:
{text}"""


# ── Script prep via Ollama ────────────────────────────────────────────────────

async def prep_script(text: str, tone: str, llm_model: str) -> str:
    adapter = LiquidAdapter(backend="ollama", model=llm_model)
    try:
        result = await adapter.generate(
            _PREP_PROMPT.format(tone=tone, text=text),
            system=_PREP_SYSTEM,
            max_tokens=2048,
        )
        cleaned = result.content.strip()
        print(f"[text_to_speech] script prep: {len(text)} → {len(cleaned)} chars")
        return cleaned
    finally:
        await adapter.close()


# ── OpenAI TTS ────────────────────────────────────────────────────────────────

async def synthesise_openai(
    text: str,
    model: str,
    voice: str,
    instructions: str | None,
    output_dir: Path,
) -> Path:
    if not _OPENAI_OK or _AsyncOpenAI is None:
        raise ImportError("openai library not found. Install: pip install openai")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set.")

    client = _AsyncOpenAI(api_key=api_key)
    ext = "mp3"
    ts = int(time.time())
    out_path = output_dir / f"speech_{ts}.{ext}"

    kwargs: dict = dict(model=model, voice=voice, input=text)
    if instructions and model == "gpt-4o-mini-tts":
        kwargs["instructions"] = instructions

    print(f"[text_to_speech] → OpenAI {model} voice={voice} ({len(text)} chars) ...")
    t0 = time.perf_counter()
    response = await client.audio.speech.create(**kwargs)
    latency_ms = (time.perf_counter() - t0) * 1000

    response.stream_to_file(str(out_path))
    size_kb = out_path.stat().st_size // 1024
    print(f"[text_to_speech] ✓ saved {out_path.name} ({size_kb} KB, {latency_ms:.0f} ms)")
    return out_path


# ── System TTS (macOS say / Linux espeak) ─────────────────────────────────────

def synthesise_system(text: str, output_dir: Path) -> Path:
    ts = int(time.time())
    import platform
    sys_name = platform.system()

    if sys_name == "Darwin":
        # macOS: say → AIFF → convert to WAV if ffmpeg available
        aiff_path = output_dir / f"speech_{ts}.aiff"
        wav_path  = output_dir / f"speech_{ts}.wav"
        print(f"[text_to_speech] → macOS say ...")
        subprocess.run(["say", "-o", str(aiff_path), text], check=True)
        # Try ffmpeg conversion to WAV
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(aiff_path), str(wav_path)],
                check=True, capture_output=True,
            )
            aiff_path.unlink(missing_ok=True)
            out_path = wav_path
        except (FileNotFoundError, subprocess.CalledProcessError):
            out_path = aiff_path   # keep AIFF if ffmpeg not available
    elif sys_name == "Linux":
        wav_path = output_dir / f"speech_{ts}.wav"
        print(f"[text_to_speech] → espeak ...")
        try:
            subprocess.run(["espeak", text, "-w", str(wav_path)], check=True)
        except FileNotFoundError:
            raise RuntimeError(
                "espeak not found. Install: sudo apt install espeak\n"
                "Or use --backend openai with OPENAI_API_KEY set."
            )
        out_path = wav_path
    else:
        raise RuntimeError(f"System TTS not supported on {sys_name}. Use --backend openai.")

    size_kb = out_path.stat().st_size // 1024
    print(f"[text_to_speech] ✓ saved {out_path.name} ({size_kb} KB)")
    return out_path


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run(
    text: str,
    voice: str,
    tone: str,
    model: str,
    instructions: str | None,
    prep: bool,
    backend: str,
    llm_model: str,
    output_dir: Path,
) -> Path:
    script = text
    if prep:
        print("[text_to_speech] prepping script via Ollama ...")
        script = await prep_script(text, tone, llm_model)

    if backend == "openai":
        return await synthesise_openai(script, model, voice, instructions, output_dir)
    else:
        return synthesise_system(script, output_dir)


@click.command()
@click.option("--text",         default=None, help="Text to speak (mutually exclusive with --file)")
@click.option("--file",         default=None, type=click.Path(exists=True),
              help="Read text from file (mutually exclusive with --text)")
@click.option("--voice",        default="alloy", show_default=True,
              help="Voice: alloy echo fable onyx nova shimmer")
@click.option("--tone",         default="neutral", show_default=True,
              help="Tone for script prep")
@click.option("--model",        default="tts-1", show_default=True,
              type=click.Choice(["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]))
@click.option("--instructions", default=None,
              help="Speaking instructions for gpt-4o-mini-tts")
@click.option("--prep",         is_flag=True, help="Clean/prep script via Gemma4/Ollama first")
@click.option("--backend",      default="openai", show_default=True,
              type=click.Choice(["openai", "system"]),
              help="openai | system (say/espeak, no API key)")
@click.option("--llm-model",    default="gemma4:e4b", show_default=True,
              help="Ollama model for script prep")
@click.option("--output-dir",   default="cookbook/53_text_to_speech/outputs", show_default=True)
def main(text, file, voice, tone, model, instructions, prep, backend, llm_model, output_dir) -> None:
    """Recipe 53 — Text to Speech (SPL 3.0 multimodal output)."""
    if not text and not file:
        raise click.UsageError("Provide either --text or --file.")
    if text and file:
        raise click.UsageError("--text and --file are mutually exclusive.")

    content = text if text else Path(file).read_text(encoding="utf-8")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path = asyncio.run(run(
        text=content,
        voice=voice,
        tone=tone,
        model=model,
        instructions=instructions,
        prep=prep,
        backend=backend,
        llm_model=llm_model,
        output_dir=out_dir,
    ))

    click.echo()
    click.echo("── Output ───────────────────────────────────────────────────────────")
    click.echo(f"Audio saved: {out_path}")
    click.echo("─────────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
