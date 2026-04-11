#!/usr/bin/env python3
"""
run.py — physical runner for Recipe 55: Voice Dialogue.

AUDIO + TEXT  →  TEXT + AUDIO

Pipeline
--------
  1. Encode audio question via spl.codecs.encode_audio
  2. Transcribe via LFM-2.5 (OpenRouter) — AUDIO → TEXT
  3. Generate response via Gemma4 (Ollama) — TEXT → TEXT
  4. Synthesise spoken response via OpenAI TTS or system TTS — TEXT → AUDIO
  5. Output: response text  +  spoken response audio file

This is the SPL 3.0 voice assistant recipe — the first full
AUDIO-in / AUDIO-out multi-modal pipeline.

Usage
-----
  # Minimal — transcribe + respond + speak
  python cookbook/55_voice_dialogue/run.py --audio question.wav

  # With context (e.g. feed a document as background knowledge)
  python cookbook/55_voice_dialogue/run.py \\
      --audio question.wav \\
      --context "We are discussing SPL 3.0 multimodal capabilities."

  # Custom persona
  python cookbook/55_voice_dialogue/run.py \\
      --audio question.wav \\
      --persona "a cheerful science teacher explaining to a 10-year-old"

  # Use a different response model
  python cookbook/55_voice_dialogue/run.py \\
      --audio question.wav --llm-model phi4:latest

  # Nova voice, HD TTS
  python cookbook/55_voice_dialogue/run.py \\
      --audio question.wav --tts-voice nova --tts-model tts-1-hd

  # System TTS (no OpenAI key needed for TTS step)
  python cookbook/55_voice_dialogue/run.py \\
      --audio question.wav --tts-backend system
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
import platform
from pathlib import Path

import click

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT))

from spl.codecs import encode_audio              # noqa: E402
from spl.adapters.liquid import LiquidAdapter   # noqa: E402

try:
    from openai import AsyncOpenAI as _AsyncOpenAI
    _OPENAI_OK = True
except ImportError:
    _AsyncOpenAI = None  # type: ignore[assignment,misc]
    _OPENAI_OK = False

_TRANSCRIBE_PROMPT = (
    "Transcribe the audio accurately. "
    "Return only the verbatim transcript. "
    "If unclear, mark uncertain words with [?]."
)
_TRANSCRIBE_SYSTEM = "You are an accurate speech transcription engine. Output only the transcript."

_RESPOND_SYSTEM = "You are {persona}. Write in natural spoken language — no bullet points or markdown."
_RESPOND_PROMPT = """\
{context_block}User said: {transcript}

Respond helpfully and concisely."""


# ── Step 1: Transcription via LFM-2.5 ────────────────────────────────────────

async def transcribe(
    audio: str,
    asr_model: str,
    asr_backend: str,
    to_wav: bool,
) -> str:
    adapter = LiquidAdapter(backend=asr_backend, model=asr_model)
    try:
        audio_part = encode_audio(audio, to_wav=to_wav)
        media_type = audio_part.get("media_type", "audio/wav")
        size_kb    = len(audio_part.get("data", "")) * 3 // 4 // 1024
        print(f"[voice_dialogue] encoded {media_type} ~{size_kb} KB")

        content = [
            {"type": "text", "text": _TRANSCRIBE_PROMPT},
            audio_part,
        ]
        print(f"[voice_dialogue] step 1: transcribing via {asr_backend}/{asr_model} ...")
        t0 = time.perf_counter()
        result = await adapter.generate_multimodal(
            content, system=_TRANSCRIBE_SYSTEM, max_tokens=512
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        transcript = result.content.strip()
        print(f"[voice_dialogue] transcript ({latency_ms:.0f} ms): \"{transcript}\"")
        return transcript
    finally:
        await adapter.close()


# ── Step 2: LLM response via Ollama ──────────────────────────────────────────

async def respond(
    transcript: str,
    context: str,
    persona: str,
    llm_model: str,
) -> str:
    adapter = LiquidAdapter(backend="ollama", model=llm_model)
    try:
        context_block = f"Context: {context}\n\n" if context.strip() else ""
        prompt = _RESPOND_PROMPT.format(context_block=context_block, transcript=transcript)
        system = _RESPOND_SYSTEM.format(persona=persona)

        print(f"[voice_dialogue] step 2: generating response via {llm_model} ...")
        t0 = time.perf_counter()
        result = await adapter.generate(
            prompt, system=system, max_tokens=512
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        response   = result.content.strip()
        print(f"[voice_dialogue] response ({latency_ms:.0f} ms, {len(response)} chars)")
        return response
    finally:
        await adapter.close()


# ── Step 3: TTS ───────────────────────────────────────────────────────────────

async def speak_openai(
    text: str,
    voice: str,
    model: str,
    output_dir: Path,
) -> Path:
    if not _OPENAI_OK or _AsyncOpenAI is None:
        raise ImportError("openai library required. Install: pip install openai")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set. Use --tts-backend system as fallback.")

    client = _AsyncOpenAI(api_key=api_key)
    ts  = int(time.time())
    out = output_dir / f"response_{ts}.mp3"

    print(f"[voice_dialogue] step 3: TTS via OpenAI {model} voice={voice} ...")
    t0 = time.perf_counter()
    async with client.audio.speech.with_streaming_response.create(
        model=model, voice=voice, input=text  # type: ignore[arg-type]
    ) as stream:
        out.write_bytes(await stream.read())
    latency_ms = (time.perf_counter() - t0) * 1000
    size_kb    = out.stat().st_size // 1024
    print(f"[voice_dialogue] ✓ speech saved {out.name} ({size_kb} KB, {latency_ms:.0f} ms)")
    return out


def speak_system(text: str, output_dir: Path) -> Path:
    ts  = int(time.time())
    sys_name = platform.system()
    print(f"[voice_dialogue] step 3: system TTS ({sys_name}) ...")

    if sys_name == "Darwin":
        aiff_path = output_dir / f"response_{ts}.aiff"
        wav_path  = output_dir / f"response_{ts}.wav"
        subprocess.run(["say", "-o", str(aiff_path), text], check=True)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(aiff_path), str(wav_path)],
                check=True, capture_output=True,
            )
            aiff_path.unlink(missing_ok=True)
            out = wav_path
        except (FileNotFoundError, subprocess.CalledProcessError):
            out = aiff_path
    elif sys_name == "Linux":
        out = output_dir / f"response_{ts}.wav"
        try:
            subprocess.run(["espeak", text, "-w", str(out)], check=True)
        except FileNotFoundError:
            raise RuntimeError("espeak not found. Install: sudo apt install espeak")
    else:
        raise RuntimeError(f"System TTS not supported on {sys_name}. Use --tts-backend openai.")

    print(f"[voice_dialogue] ✓ speech saved {out.name}")
    return out


# ── Main pipeline ─────────────────────────────────────────────────────────────

async def run(
    audio: str,
    context: str,
    persona: str,
    asr_model: str,
    asr_backend: str,
    llm_model: str,
    tts_voice: str,
    tts_model: str,
    tts_backend: str,
    to_wav: bool,
    output_dir: Path,
) -> tuple[str, str, Path]:
    transcript = await transcribe(audio, asr_model, asr_backend, to_wav)
    response   = await respond(transcript, context, persona, llm_model)

    if tts_backend == "openai":
        audio_out = await speak_openai(response, tts_voice, tts_model, output_dir)
    else:
        audio_out = speak_system(response, output_dir)

    return transcript, response, audio_out


@click.command()
@click.option("--audio",       required=True, help="Path to audio question (WAV/MP3)")
@click.option("--context",     default="", help="Optional text context for the response")
@click.option("--persona",     default="a helpful assistant", show_default=True,
              help="LLM persona description")
@click.option("--asr-model",   default="liquid/lfm-2.5-1.2b-instruct:free", show_default=True,
              help="Transcription model")
@click.option("--asr-backend", default="openrouter", show_default=True,
              type=click.Choice(["openrouter", "ollama"]))
@click.option("--llm-model",   default="gemma4:e4b", show_default=True,
              help="Response LLM via Ollama")
@click.option("--tts-voice",   default="alloy", show_default=True, help="TTS voice")
@click.option("--tts-model",   default="tts-1", show_default=True,
              type=click.Choice(["tts-1", "tts-1-hd", "gpt-4o-mini-tts"]))
@click.option("--tts-backend", default="openai", show_default=True,
              type=click.Choice(["openai", "system"]))
@click.option("--to-wav",      is_flag=True, help="Convert audio to WAV before ASR (requires ffmpeg)")
@click.option("--output-dir",  default="cookbook/55_voice_dialogue/outputs", show_default=True)
def main(audio, context, persona, asr_model, asr_backend, llm_model,
         tts_voice, tts_model, tts_backend, to_wav, output_dir) -> None:
    """Recipe 55 — Voice Dialogue (AUDIO+TEXT → TEXT+AUDIO)."""
    if asr_backend == "openrouter" and not os.environ.get("OPENROUTER_API_KEY"):
        raise click.UsageError(
            "OPENROUTER_API_KEY not set.\n"
            "  export OPENROUTER_API_KEY=sk-or-...\n"
            "  Or use --asr-backend ollama --asr-model lfm-2.5"
        )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    transcript, response, audio_out = asyncio.run(run(
        audio=audio,
        context=context,
        persona=persona,
        asr_model=asr_model,
        asr_backend=asr_backend,
        llm_model=llm_model,
        tts_voice=tts_voice,
        tts_model=tts_model,
        tts_backend=tts_backend,
        to_wav=to_wav,
        output_dir=out_dir,
    ))

    click.echo()
    click.echo("── Transcript ───────────────────────────────────────────────────────")
    click.echo(transcript)
    click.echo()
    click.echo("── Text response ────────────────────────────────────────────────────")
    click.echo(response)
    click.echo()
    click.echo("── Audio response ───────────────────────────────────────────────────")
    click.echo(f"Saved: {audio_out}")
    click.echo("─────────────────────────────────────────────────────────────────────")


if __name__ == "__main__":
    main()
