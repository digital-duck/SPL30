# Recipe 53: Text to Speech

**Category:** multimodal  
**SPL types:** TEXT → AUDIO  
**Primary:** OpenAI TTS via `openai` library (requires `OPENAI_API_KEY`)  
**Fallback:** system TTS (`say` on macOS, `espeak` on Linux) — zero dependencies

Convert any text to natural speech. Optional script prep via Gemma4 cleans
markdown, expands abbreviations, and adds natural pause punctuation.

## Pipeline

```
[text / file]
      │
      ▼  Gemma4 / Ollama (--prep)           optional: clean for speech
[clean script]
      │
      ▼  OpenAI TTS  or  system TTS
[MP3 / WAV file]  →  outputs/speech_TIMESTAMP.mp3
```

## Usage

```bash
export OPENAI_API_KEY=sk-...

# Minimal
python cookbook/53_text_to_speech/run.py \
    --text "Hello from SPL 3.0 multimodal support."

# Read from file, prep script, HD quality
python cookbook/53_text_to_speech/run.py \
    --file article.md --prep --model tts-1-hd --voice nova

# Expressive TTS with acting instructions (gpt-4o-mini-tts)
python cookbook/53_text_to_speech/run.py \
    --text "Breaking news: SPL 3.0 ships!" \
    --model gpt-4o-mini-tts --voice coral \
    --instructions "Speak like an excited news anchor."

# No API key needed — system TTS
python cookbook/53_text_to_speech/run.py \
    --text "Hello world." --backend system
```

## Parameters

| Flag | Default | Description |
|---|---|---|
| `--text` | *(required\*)* | Text to speak |
| `--file` | *(required\*)* | Read text from file (mutually exclusive with --text) |
| `--voice` | `alloy` | `alloy echo fable onyx nova shimmer` |
| `--model` | `tts-1` | `tts-1` \| `tts-1-hd` \| `gpt-4o-mini-tts` |
| `--instructions` | — | Speaking instructions (gpt-4o-mini-tts only) |
| `--prep` | off | Clean script via Gemma4 before TTS |
| `--tone` | `neutral` | Tone hint for script prep |
| `--backend` | `openai` | `openai` \| `system` (say/espeak) |
