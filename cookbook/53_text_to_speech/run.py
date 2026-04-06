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

import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

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


def main() -> None:
    p = argparse.ArgumentParser(
        description="Recipe 53 — Text to Speech (SPL 3.0 multimodal output)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="Text to speak")
    src.add_argument("--file", help="Read text from file")

    p.add_argument("--voice",  default="alloy",
                   help="Voice name (default: alloy). OpenAI: alloy echo fable onyx nova shimmer")
    p.add_argument("--tone",   default="neutral",
                   help='Tone for script prep (default: "neutral")')
    p.add_argument("--model",  default="tts-1",
                   choices=["tts-1", "tts-1-hd", "gpt-4o-mini-tts"],
                   help="TTS model (default: tts-1)")
    p.add_argument("--instructions", default=None,
                   help="Speaking instructions for gpt-4o-mini-tts (e.g. 'Speak like a news anchor')")
    p.add_argument("--prep",   action="store_true",
                   help="Clean/prep script before TTS via Gemma4/Ollama")
    p.add_argument("--backend", default="openai", choices=["openai", "system"],
                   help="openai (default) or system (say/espeak, no API key)")
    p.add_argument("--llm-model", default="gemma4:e4b", dest="llm_model",
                   help="Ollama model for script prep (default: gemma4:e4b)")
    p.add_argument("--output-dir", default="cookbook/53_text_to_speech/outputs",
                   dest="output_dir")
    args = p.parse_args()

    text = args.text
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8")
    assert text

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    out_path = asyncio.run(run(
        text=text,
        voice=args.voice,
        tone=args.tone,
        model=args.model,
        instructions=args.instructions,
        prep=args.prep,
        backend=args.backend,
        llm_model=args.llm_model,
        output_dir=output_dir,
    ))

    print()
    print("── Output ───────────────────────────────────────────────────────────")
    print(f"Audio saved: {out_path}")
    print("─────────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
