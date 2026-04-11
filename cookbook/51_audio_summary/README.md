# Recipe 51: Audio Summary

**Category:** multimodal  
**SPL version:** 3.0  
**Type:** AUDIO → TEXT  
**LLM required:** Yes — Liquid AI LFM-2.5 via OpenRouter  
**Demonstrates:** `AUDIO` as a first-class SPL input type, multi-mode `EVALUATE`, speech-capable model dispatch

---

## What it does

Transcribes, summarises, or extracts key points from an audio clip using
Liquid AI's LFM-2.5 model — a sparse recurrent architecture with native
audio understanding, accessed via OpenRouter.

| Mode | What it produces |
|------|-----------------|
| `summary` | Concise prose summary of the audio content |
| `transcribe` | Verbatim transcript with speaker changes on new lines |
| `key_points` | Structured Markdown: topic, key points, decisions, action items |

The AUDIO input is encoded by `spl/codecs/audio_codec.py` before being passed
to `generate_multimodal()` as `AudioPart` dicts.

---

## Files

| File | Role |
|------|------|
| `audio_summary.spl` | SPL logical view — 3 prompt functions, 1 workflow |
| `run.py` | Physical runner — audio codec + OpenRouter LFM-2.5 call |
| `sample/` | Place test audio files here (`.wav` / `.mp3`) |

---

## Prerequisites

```bash
export OPENROUTER_API_KEY=sk-or-...
pip install openai           # OpenRouter uses the OpenAI-compatible API
```

> **Note:** LFM-2.5 is accessed via OpenRouter (`liquid/lfm-2.5-1.2b-instruct:free`).
> This is not available on Ollama — an OpenRouter API key is required.

### Generate test audio (requires `OPENAI_API_KEY` or espeak)

```bash
# Option A — OpenAI TTS
python -c "
import pathlib
from openai import OpenAI
client = OpenAI()
out = pathlib.Path('cookbook/51_audio_summary/sample/clip.mp3')
out.parent.mkdir(parents=True, exist_ok=True)
response = client.audio.speech.create(
    model='tts-1', voice='alloy',
    input='What are the main features of SPL version 3 multimodal support?'
)
out.write_bytes(response.content)
print(f'audio saved: {out}')
"

# Option B — espeak (Linux, no API key)
espeak "What are the main features of SPL 3.0?" \
    -w cookbook/51_audio_summary/sample/clip.wav
```

---

## Running

```bash
export OPENROUTER_API_KEY=sk-or-...

# Default — summary mode
python cookbook/51_audio_summary/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3

# Verbatim transcript
python cookbook/51_audio_summary/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --mode transcribe

# Key points (meeting notes style)
python cookbook/51_audio_summary/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --mode key_points

# Custom summary style
python cookbook/51_audio_summary/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --style "three bullet points, executive summary"

# Larger output budget for long recordings
python cookbook/51_audio_summary/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --mode transcribe --output-budget 4096
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@clip` | AUDIO | `cookbook/51_audio_summary/sample/clip.wav` | Source audio file path |
| `@mode` | TEXT | `summary` | Output mode: `summary`, `transcribe`, `key_points` |
| `@style` | TEXT | `concise paragraph` | Prose style for `summary` mode |
| `@model` | TEXT | `liquid/lfm-2.5-1.2b-instruct:free` | Speech-capable model (OpenRouter) |
| `@output_budget` | INT | `2048` | Max output tokens |
| `@log_dir` | TEXT | `cookbook/51_audio_summary/logs-spl` | Directory for log output |

---

## Output

`@result TEXT` — transcript, summary, or key points in the format matching `@mode`.

---

## Composability

```sql
-- Extract audio from video, then summarise
CALL video_to_audio(@video, 'mp3', '192k', 44100, @output_dir) INTO @audio
CALL audio_summary(@audio, 'summary', 'concise paragraph', @model, 2048) INTO @summary

-- Convert format first if needed
CALL audio_convert(@raw_audio, 'mp3', '192k', 44100, @output_dir) INTO @audio
CALL audio_summary(@audio, 'transcribe', '', @model, 4096) INTO @transcript
```

---

## Error handling

| Exception | Cause | Behaviour |
|-----------|-------|-----------|
| `ModelUnavailable` | `OPENROUTER_API_KEY` not set or LFM-2.5 unavailable | Returns error string with `status = 'failed'` |
