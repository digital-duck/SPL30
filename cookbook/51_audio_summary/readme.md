# Recipe 51: Audio Summary

**Category:** multimodal  
**SPL type:** `AUDIO`  
**Primary model:** Liquid AI LFM-2.5 via OpenRouter (confirmed audio support)  
**Experimental:** LFM-2.5 via Ollama (audio passthrough not yet confirmed upstream)  
**splc target:** `python/liquid` (edge audio on ARM / laptop)

Transcribe, summarise, or extract key points from an audio clip.
Demonstrates SPL 3.0's `AUDIO` type annotation and the `spl.codecs` layer.

## Pattern

```
[audio file (WAV / MP3 / OGG)]
         │
         ▼  spl.codecs.encode_audio()         optional: --to-wav (pydub)
[AudioPart (base64, media_type)]
         │
         ▼  LiquidAdapter.generate_multimodal()  (input_audio content type)
[transcript / summary / key points]
```

## Modes

| Mode | What it does | Best for |
|---|---|---|
| `summary` | Concise summary in chosen style | Meetings, lectures, podcasts |
| `transcribe` | Verbatim transcript | Documentation, searchable archives |
| `key_points` | Structured Markdown: topic + bullets + decisions + actions | Meeting notes |

## Prerequisites

### OpenRouter (default — confirmed audio)

```bash
export OPENROUTER_API_KEY=sk-or-...
```

LFM-2.5 on OpenRouter is free-tier: `liquid/lfm-2.5-1.2b-instruct:free`.

### Ollama (experimental)

```bash
ollama pull lfm-2.5
```

> **Note:** Ollama's audio passthrough for LFM-2.5 is not yet confirmed in
> upstream Ollama releases.  A warning is logged when `--backend ollama` is
> used with audio input.  Use OpenRouter for reliable audio processing.

### Optional: pydub + ffmpeg (for MP3/OGG → WAV conversion)

```bash
pip install pydub
# macOS
brew install ffmpeg
# Ubuntu / Debian
sudo apt install ffmpeg
```

## Usage

### Summarise a WAV clip (OpenRouter, default)

```bash
export OPENROUTER_API_KEY=sk-or-...
python cookbook/51_audio_summary/run.py --audio path/to/clip.wav
```

### Transcribe only

```bash
python cookbook/51_audio_summary/run.py --audio clip.wav --mode transcribe
```

### Key points (meeting notes style)

```bash
python cookbook/51_audio_summary/run.py --audio meeting.wav --mode key_points
```

### Custom summary style

```bash
python cookbook/51_audio_summary/run.py \
    --audio clip.wav --style "three bullet points"

python cookbook/51_audio_summary/run.py \
    --audio clip.wav --style "executive summary in one sentence"
```

### Convert MP3 to WAV before sending

```bash
python cookbook/51_audio_summary/run.py \
    --audio podcast.mp3 --to-wav
```

### Ollama backend (experimental)

```bash
python cookbook/51_audio_summary/run.py \
    --audio clip.wav --backend ollama --model lfm-2.5
```

## Parameters

| Flag | Default | Description |
|---|---|---|
| `--audio` | *(required)* | Path to audio file (WAV, MP3, OGG, FLAC) |
| `--mode` | `summary` | `summary` \| `transcribe` \| `key_points` |
| `--style` | `"concise paragraph"` | Style hint for summary mode |
| `--backend` | `openrouter` | `openrouter` (confirmed) or `ollama` (experimental) |
| `--model` | *(per backend)* | Override model name |
| `--to-wav` | off | Convert to WAV via pydub before encoding |
| `--max-tokens` | `2048` | Max output tokens |

## SPL Logical View

`audio_summary.spl` is the DODA invariant — declares the workflow with an
`AUDIO`-typed input param.  The runtime encodes via `spl/codecs/audio_codec.py`
and passes an `AudioPart` dict to `generate_multimodal()`.

```sql
WORKFLOW audio_summary
    INPUT:
        @clip   AUDIO  DEFAULT 'cookbook/51_audio_summary/sample/clip.wav',
        @mode   TEXT   DEFAULT 'summary',
        @style  TEXT   DEFAULT 'concise paragraph',
        @model  TEXT   DEFAULT 'liquid/lfm-2.5-1.2b-instruct:free'
    OUTPUT: @result TEXT
```

## Generating a test clip

If you don't have a WAV file handy, generate one with `say` (macOS) or `espeak` (Linux):

```bash
# macOS
say -o sample/clip.aiff "Welcome to the SPL 3.0 multimodal demo. Today we will test audio summarisation using Liquid AI LFM."
ffmpeg -i sample/clip.aiff sample/clip.wav

# Linux
espeak "Welcome to the SPL 3.0 multimodal demo." -w sample/clip.wav
```

## Audio format notes

| Format | Encode as-is | Requires pydub |
|---|---|---|
| `.wav` | yes | no |
| `.mp3` | yes (send as audio/mp3) | only for `--to-wav` |
| `.ogg` | yes (send as audio/ogg) | only for `--to-wav` |
| `.flac` | yes (send as audio/flac) | only for `--to-wav` |

Most APIs accept WAV natively.  If you get format errors, add `--to-wav`.
