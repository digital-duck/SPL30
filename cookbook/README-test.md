# SPL 3.0 Cookbook — Testing Guide

Recipes 50–55 validate SPL 3.0 multi-modal support end-to-end.
Each recipe has a `.spl` logical view and a `run.py` physical runner.

---

## Prerequisites

### Environment setup

```bash
cd ~/projects/digital-duck/SPL30
conda activate spl2          # or whichever env has spl installed
pip install -e ../SPL20      # SPL20 base adapters
pip install -e .             # SPL30 (LiquidAdapter, codecs, etc.)
```

### Ollama (Tier 1 recipes — no API key needed)

```bash
ollama serve                 # start if not running
ollama pull gemma4:e4b       # vision model — recipes 50, 54, 55
ollama list                  # verify
```

### API keys

```bash
export OPENAI_API_KEY=sk-...          # recipes 52, 53, 54, 55 TTS
export OPENROUTER_API_KEY=sk-or-...   # recipes 51, 55 ASR
```

> **Note:** `OPENAI_API_KEY` must point to actual OpenAI (`api.openai.com`),
> not an OpenRouter proxy. DALL-E 3 and OpenAI TTS are not available on OpenRouter.

### Sample media files

```bash
# Generate test image (Pillow, no download needed)
python -c "
from PIL import Image, ImageDraw
import pathlib
img = Image.new('RGB', (800, 600), (70, 130, 180))
draw = ImageDraw.Draw(img)
draw.polygon([(0,600),(200,250),(400,600)], fill=(90,90,90))
draw.polygon([(150,600),(380,200),(600,600)], fill=(110,110,110))
draw.ellipse([600,50,720,170], fill=(255,220,50))
draw.ellipse([150,490,650,590], fill=(100,160,210))
img.save('cookbook/50_image_caption/sample/photo.jpg', 'JPEG')
import shutil; shutil.copy('cookbook/50_image_caption/sample/photo.jpg',
                            'cookbook/54_image_restyle/sample/photo.jpg')
print('test image created')
"

# Generate test audio question (requires OPENAI_API_KEY or espeak)
# Option A — OpenAI TTS (mp3)
python -c "
import asyncio, os, pathlib
from openai import AsyncOpenAI
async def gen():
    client = AsyncOpenAI()
    out = pathlib.Path('cookbook/55_voice_dialogue/sample/question.mp3')
    async with client.audio.speech.with_streaming_response.create(
        model='tts-1', voice='alloy',
        input='What are the main features of SPL version 3 multimodal support?'
    ) as r:
        out.write_bytes(await r.read())
    import shutil; shutil.copy(out, 'cookbook/51_audio_summary/sample/clip.mp3')
    print(f'audio saved: {out}')
asyncio.run(gen())
"

# Option B — espeak (Linux, no API key)
# espeak "What are the main features of SPL 3.0?" \
#     -w cookbook/55_voice_dialogue/sample/question.wav
# cp cookbook/55_voice_dialogue/sample/question.wav \
#    cookbook/51_audio_summary/sample/clip.wav
```

---

## Tier Overview

| Tier | Recipes | Requires | `is_active` default |
|------|---------|----------|---------------------|
| 1 | 50 `image_caption` | `ollama:gemma4` | `true` |
| 2 | 52 `text_to_image`, 53 `text_to_speech` | `OPENAI_API_KEY` | `false` |
| 3 | 51 `audio_summary` | `OPENROUTER_API_KEY` | `false` |
| 4 | 54 `image_restyle`, 55 `voice_dialogue` | `OPENAI_API_KEY` + `OPENROUTER_API_KEY` + Ollama | `false` |

---

## Tier 1 — Ollama only (no API key)

### Recipe 50: Image Caption (IMAGE → TEXT)

```bash
# Default caption mode
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg

# Detailed description
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg --mode detailed

# OCR — extract any text in the image
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg --mode ocr

# Custom question
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --question "What colors are dominant in this scene?"

# Larger model (more accurate)
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --model gemma4:e2b
```

Expected output:
```
[image_caption] encoded image/jpeg ~25 KB (12 ms)
[image_caption] → ollama/gemma4:e4b (mode=caption) ...
[image_caption] ✓ 1024 in / 87 out (1843 ms)

── Result ───────────────────────────────────────────────────────────
The image shows a mountain landscape with snow-capped peaks reflected
in a calm lake at golden hour. The sky is steel blue with a bright sun
visible in the upper right. Text "SPL 3.0 Multimodal Test Image" appears
in the upper left corner.
─────────────────────────────────────────────────────────────────────
```

---

## Tier 2 — OpenAI key

### Recipe 52: Text to Image (TEXT → IMAGE)

```bash
export OPENAI_API_KEY=sk-...

# Basic
python cookbook/52_text_to_image/run.py \
    --prompt "A duck writing code at sunrise"

# Landscape HD with vivid style
python cookbook/52_text_to_image/run.py \
    --prompt "Tokyo skyline at night" \
    --aspect landscape --quality hd --dalle-style vivid

# With Gemma4 prompt enhancement (Ollama + OpenAI combined)
python cookbook/52_text_to_image/run.py \
    --prompt "A fox in a forest" \
    --enhance --style "oil painting, impressionist"
```

Expected output:
```
[text_to_image] → DALL-E dall-e-3 (1024x1024, quality=standard) ...
[text_to_image] ✓ saved generated_1744000000.png (892 KB, 8432 ms)

── Output ───────────────────────────────────────────────────────────
Image saved: cookbook/52_text_to_image/outputs/generated_1744000000.png
─────────────────────────────────────────────────────────────────────
```

### Recipe 53: Text to Speech (TEXT → AUDIO)

```bash
export OPENAI_API_KEY=sk-...

# Basic TTS
python cookbook/53_text_to_speech/run.py \
    --text "SPL 3.0 multimodal support is ready for testing."

# Different voice and HD quality
python cookbook/53_text_to_speech/run.py \
    --text "Welcome to the future of agentic workflows." \
    --voice nova --model tts-1-hd

# Read from file (e.g. a generated recipe readme)
python cookbook/53_text_to_speech/run.py \
    --file cookbook/50_image_caption/readme.md \
    --prep --tone "professional"

# No API key — system TTS (macOS say / Linux espeak)
python cookbook/53_text_to_speech/run.py \
    --text "Hello from SPL 3.0." --backend system
```

Expected output:
```
[text_to_speech] → OpenAI tts-1 voice=alloy (47 chars) ...
[text_to_speech] ✓ saved speech_1744000000.mp3 (28 KB, 631 ms)

── Output ───────────────────────────────────────────────────────────
Audio saved: cookbook/53_text_to_speech/outputs/speech_1744000000.mp3
─────────────────────────────────────────────────────────────────────
```

---

## Tier 3 — OpenRouter key

### Recipe 51: Audio Summary (AUDIO → TEXT)

```bash
export OPENROUTER_API_KEY=sk-or-...

# Summarise
python cookbook/51_audio_summary/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3

# Transcribe only
python cookbook/51_audio_summary/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --mode transcribe

# Key points (meeting notes style)
python cookbook/51_audio_summary/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --mode key_points

# Custom style
python cookbook/51_audio_summary/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --style "three bullet points"
```

---

## Tier 4 — OpenAI + OpenRouter + Ollama

### Recipe 54: Image Restyle (IMAGE+TEXT → TEXT+IMAGE)

```bash
export OPENAI_API_KEY=sk-...

# Default style (watercolor)
python cookbook/54_image_restyle/run.py \
    --image cookbook/54_image_restyle/sample/photo.jpg

# Studio Ghibli anime
python cookbook/54_image_restyle/run.py \
    --image cookbook/54_image_restyle/sample/photo.jpg \
    --style "Studio Ghibli anime, soft illustration, warm colors"

# Oil painting, landscape HD
python cookbook/54_image_restyle/run.py \
    --image cookbook/54_image_restyle/sample/photo.jpg \
    --style "oil painting, impressionist, thick brushstrokes" \
    --aspect landscape --quality hd

# Cyberpunk neon, vivid mode
python cookbook/54_image_restyle/run.py \
    --image cookbook/54_image_restyle/sample/photo.jpg \
    --style "cyberpunk neon city" --dalle-style vivid
```

Expected output:
```
[image_restyle] encoded image/jpeg ~25 KB (11 ms)
[image_restyle] → Gemma4 vision analysis (gemma4:e4b) ...
[image_restyle] vision ✓ (2103 ms)
[image_restyle] → DALL-E 3 (1024x1024, quality=standard, style=natural) ...
[image_restyle] ✓ saved restyled_1744000000.png (1024 KB, 9831 ms)

── Text output (vision analysis) ────────────────────────────────────
Description:   A dramatic mountain landscape with a calm reflective lake ...
DALL-E prompt: A serene mountain lake reflecting snow-capped peaks in
               watercolor style with soft pastel blues and greens ...
── Image output ─────────────────────────────────────────────────────
Restyled image: cookbook/54_image_restyle/outputs/restyled_1744000000.png
─────────────────────────────────────────────────────────────────────
```

### Recipe 55: Voice Dialogue (AUDIO+TEXT → TEXT+AUDIO)

```bash
export OPENROUTER_API_KEY=sk-or-...
export OPENAI_API_KEY=sk-...           # for TTS step; use --tts-backend system to skip

# Minimal
python cookbook/55_voice_dialogue/run.py \
    --audio cookbook/55_voice_dialogue/sample/question.mp3

# Custom persona + context
python cookbook/55_voice_dialogue/run.py \
    --audio cookbook/55_voice_dialogue/sample/question.mp3 \
    --persona "a cheerful science teacher" \
    --context "SPL 3.0 is a multimodal agentic workflow language."

# HD voice response
python cookbook/55_voice_dialogue/run.py \
    --audio cookbook/55_voice_dialogue/sample/question.mp3 \
    --tts-voice nova --tts-model tts-1-hd

# Skip OpenAI TTS — use system say/espeak instead
python cookbook/55_voice_dialogue/run.py \
    --audio cookbook/55_voice_dialogue/sample/question.mp3 \
    --tts-backend system
```

Expected output:
```
[voice_dialogue] encoded audio/mp3 ~12 KB
[voice_dialogue] step 1: transcribing via openrouter/liquid/lfm-2.5-... ...
[voice_dialogue] transcript (2341 ms): "What are the main features of SPL version 3 multimodal support?"
[voice_dialogue] step 2: generating response via gemma4:e4b ...
[voice_dialogue] response (1876 ms, 312 chars)
[voice_dialogue] step 3: TTS via OpenAI tts-1 voice=alloy ...
[voice_dialogue] ✓ speech saved response_1744000000.mp3 (47 KB, 892 ms)

── Transcript ───────────────────────────────────────────────────────
What are the main features of SPL version 3 multimodal support?
── Text response ────────────────────────────────────────────────────
SPL 3.0 introduces native IMAGE, AUDIO, and VIDEO type annotations ...
── Audio response ───────────────────────────────────────────────────
Saved: cookbook/55_voice_dialogue/outputs/response_1744000000.mp3
─────────────────────────────────────────────────────────────────────
```

---

## Automated Testing with run_all.py

`run_all.py` reads `cookbook_catalog.json` and runs recipes as subprocesses.
Mirrors SPL 2.0's `run_all.py` pattern.

```bash
cd ~/projects/digital-duck/SPL30

# Check prerequisites before running
python cookbook/run_all.py check           # all active recipes
python cookbook/run_all.py check --tier 2  # tier-2 prerequisites only

# List recipes
python cookbook/run_all.py list
python cookbook/run_all.py list --tier 1
python cookbook/run_all.py catalog

# Run active (tier-1) recipes — default
python cookbook/run_all.py

# Run by tier
python cookbook/run_all.py --tier 1          # Ollama only (no API key)
python cookbook/run_all.py --tier 2          # OpenAI key recipes
python cookbook/run_all.py --tier 3          # OpenRouter key recipes
python cookbook/run_all.py --tier 1,2        # tier 1 AND tier 2 together

# Run specific IDs
python cookbook/run_all.py --ids 50,54
python cookbook/run_all.py --ids 50-55       # all multimodal recipes

# Full test pass (all tiers, all recipes)
python cookbook/run_all.py --all

# Save output to log
python cookbook/run_all.py --tier 1 \
    2>&1 | tee cookbook/logs/run_$(date +%Y%m%d_%H%M%S).md

# Parallel (run multiple recipes simultaneously)
python cookbook/run_all.py --all --workers 3
```

### Enabling a recipe in the catalog

Recipes with `"is_active": false` are skipped by `run_all.py` by default.
To activate a recipe once you have the required API key:

```bash
# Edit cookbook/cookbook_catalog.json and set:
#   "is_active": true   for the recipe you want to enable

# Or use --ids / --all / --tier to run inactive recipes explicitly:
python cookbook/run_all.py --ids 52,53   # runs them regardless of is_active
```

### Updating approval_status

After verifying a recipe runs correctly, update `cookbook_catalog.json`:

```json
{
  "id": "50",
  "approval_status": "approved",
  "is_active": true
}
```

Status values: `new` → `wip` → `approved` (or `disabled` / `rejected`).

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ConnectError: Cannot connect to Ollama` | Ollama not running | `ollama serve` |
| `gemma4:e4b not found` | Model not pulled | `ollama pull gemma4:e4b` |
| `OPENAI_API_KEY not set` | Missing env var | `export OPENAI_API_KEY=sk-...` |
| `OPENROUTER_API_KEY not set` | Missing env var | `export OPENROUTER_API_KEY=sk-or-...` |
| OpenAI returns 404 HTML | Key pointing to OpenRouter proxy | Use actual OpenAI key for recipes 52, 53 |
| Image encode fails | Pillow not installed | `pip install Pillow` |
| Audio convert fails | pydub / ffmpeg missing | `pip install pydub && sudo apt install ffmpeg` |
| `spl.codecs not found` | SPL30 not installed | `pip install -e .` from SPL30 root |
| Vision model returns non-JSON (recipe 54) | Gemma4 didn't follow JSON schema | Re-run; the runner falls back to raw output as the DALL-E prompt |

---

## Recipe Summary

| id | Name | Input | Output | Tier | Key model(s) |
|---|---|---|---|---|---|
| 50 | `image_caption` | IMAGE | TEXT | 1 | gemma4:e4b (Ollama) |
| 51 | `audio_summary` | AUDIO | TEXT | 3 | LFM-2.5 (OpenRouter) |
| 52 | `text_to_image` | TEXT | IMAGE | 2 | DALL-E 3 (OpenAI) |
| 53 | `text_to_speech` | TEXT | AUDIO | 2 | OpenAI TTS or system |
| 54 | `image_restyle` | IMAGE + TEXT | TEXT + IMAGE | 4 | gemma4:e4b + DALL-E 3 |
| 55 | `voice_dialogue` | AUDIO + TEXT | TEXT + AUDIO | 4 | LFM-2.5 + gemma4:e4b + OpenAI TTS |
