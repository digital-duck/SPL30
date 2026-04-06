# Recipe 55: Voice Dialogue

**Category:** multimodal  
**SPL types:** AUDIO + TEXT → TEXT + AUDIO  
**ASR:** Liquid LFM-2.5 via OpenRouter (requires `OPENROUTER_API_KEY`)  
**LLM:** Gemma4 via Ollama (already available: `gemma4:e4b`)  
**TTS:** OpenAI TTS (requires `OPENAI_API_KEY`) or system `say`/`espeak`

Full voice assistant pipeline: ask a question by voice, get a spoken answer.
The first complete AUDIO-in / AUDIO-out recipe in SPL 3.0.

## Pipeline

```
[voice question WAV]  +  [optional text context]
          │
          ▼  LFM-2.5 / OpenRouter  generate_multimodal()     AUDIO → TEXT
   [transcript]
          │
          ▼  Gemma4:e4b / Ollama   generate()                TEXT → TEXT
   [text response]
          │
          ▼  OpenAI TTS  or  system say/espeak               TEXT → AUDIO
   [spoken response]  →  outputs/response_TIMESTAMP.mp3
```

## Prerequisites

```bash
export OPENROUTER_API_KEY=sk-or-...   # for ASR (LFM-2.5)
export OPENAI_API_KEY=sk-...          # for TTS (optional — use --tts-backend system)

# Gemma4 already on Ollama (gemma4:e4b)
```

## Generate a test question WAV

```bash
# macOS
say -o cookbook/55_voice_dialogue/sample/question.aiff "What is SPL 3.0 and why does it matter?"
ffmpeg -i sample/question.aiff sample/question.wav

# Linux
espeak "What is SPL 3.0 and why does it matter?" \
    -w cookbook/55_voice_dialogue/sample/question.wav
```

## Usage

```bash
# Minimal
python cookbook/55_voice_dialogue/run.py --audio question.wav

# With context (background document or system info)
python cookbook/55_voice_dialogue/run.py \
    --audio question.wav \
    --context "SPL 3.0 is a multimodal agentic workflow language."

# Custom persona
python cookbook/55_voice_dialogue/run.py \
    --audio question.wav \
    --persona "a cheerful science teacher explaining to a 10-year-old"

# HD voice, Nova
python cookbook/55_voice_dialogue/run.py \
    --audio question.wav --tts-voice nova --tts-model tts-1-hd

# No OpenAI TTS — use system espeak/say instead
python cookbook/55_voice_dialogue/run.py \
    --audio question.wav --tts-backend system

# Different response model
python cookbook/55_voice_dialogue/run.py \
    --audio question.wav --llm-model phi4:latest
```

## Parameters

| Flag | Default | Description |
|---|---|---|
| `--audio` | *(required)* | Voice question WAV/MP3 file |
| `--context` | `""` | Text context to include in response |
| `--persona` | `"a helpful assistant"` | LLM response persona |
| `--asr-model` | `liquid/lfm-2.5-1.2b-instruct:free` | Transcription model |
| `--asr-backend` | `openrouter` | `openrouter` \| `ollama` |
| `--llm-model` | `gemma4:e4b` | Response LLM (Ollama) |
| `--tts-voice` | `alloy` | OpenAI TTS voice |
| `--tts-model` | `tts-1` | `tts-1` \| `tts-1-hd` \| `gpt-4o-mini-tts` |
| `--tts-backend` | `openai` | `openai` \| `system` (say/espeak) |

## Output

Both TEXT and AUDIO are produced:
- **Transcript:** what the voice question said
- **Text response:** LLM's written answer
- **Audio response:** `outputs/response_TIMESTAMP.mp3`
