# SPL 3.0 Cookbook — Testing Guide

Recipes 05, 50–62 validate SPL 3.0 capabilities end-to-end.
Recipes 50–55 each have a `.spl` logical view and a `run.py` physical runner.
Recipes 05 and 56 run via the `spl` CLI and demonstrate native workflow composition (`CALL`).

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
ollama pull gemma4:e4b       # vision + video model — recipes 50, 54, 55, 56, 60, 62
ollama pull gemma3           # writer model — recipe 05 self_refine
ollama pull llama3.2         # critic model — recipe 05 self_refine
ollama list                  # verify
```

### Codec tools (recipes 57, 58, 61, 62)

```bash
# Pillow — image format conversion (recipe 57)
pip install Pillow

# pydub + ffmpeg — audio/video codec operations (recipes 58, 61, 62)
pip install pydub
sudo apt install ffmpeg      # Ubuntu/Debian
# brew install ffmpeg        # macOS

ffmpeg -version              # verify
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
| 1 | 05 `self_refine`, 50 `image_caption`, 56 `code_pipeline`, 57 `image_convert`, 58 `audio_convert`, 61 `video_to_audio`, 60 `video_summary`, 62 `video_to_image` | Ollama / ffmpeg / Pillow | `true` (codec); `false` (video) |
| 2 | 52 `text_to_image`, 53 `text_to_speech`, 59 `text_to_video` | `OPENAI_API_KEY` / `GOOGLE_API_KEY` | `false` |
| 3 | 51 `audio_summary` | `OPENROUTER_API_KEY` | `false` |
| 4 | 54 `image_restyle`, 55 `voice_dialogue` | `OPENAI_API_KEY` + `OPENROUTER_API_KEY` + Ollama | `false` |

---

## Tier 1 — Ollama only (no API key)

### Recipe 05: Self-Refine (TEXT → TEXT, CALL workflow demo)

The first SPL 3.0 recipe to demonstrate `CALL` sub-workflow dispatch.
`critique_workflow` is a self-contained `WORKFLOW` called from the orchestrator.

```bash
# Default task (meditation), gemma3 writer + llama3.2 critic, max 5 iterations
spl run cookbook/05_self_refine/self_refine.spl

# Custom task
spl run cookbook/05_self_refine/self_refine.spl \
    --param task="Explain the closure principle in NDD"

# Fewer iterations, same models
spl run cookbook/05_self_refine/self_refine.spl \
    --param task="What is the DODA paradigm?" \
    --param max_iterations=3

# Same model for writer and critic
spl run cookbook/05_self_refine/self_refine.spl \
    --param task="Write a haiku about distributed computing" \
    --param writer_model=gemma3 \
    --param critic_model=gemma3
```

Expected output:
```
[self_refine] Self-refine started | max_iterations=5 for task: ...
[self_refine] Initial draft ready
[self_refine] Iteration 0 | critiquing ...
[self_refine] Approved at iteration 2
```

**What to verify:**
- [ ] `critique_workflow` is dispatched via `CALL` (not inline `GENERATE`)
- [ ] `[APPROVED]` sentinel stops the loop early (does not always run to max)
- [ ] Log files appear in `cookbook/05_self_refine/logs-spl/` (draft_0.md, feedback_0.md, final.md)
- [ ] `RETURN @current WITH status = 'complete', iterations = @iteration` surfaces correctly

---

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

---

## Recipe 56: Code Pipeline — NDD Closure (TEXT → TEXT, Tier 1)

The reference implementation of **Natural-language Driven Development (NDD)**
and the closure principle. Runs entirely on Ollama (no API key needed).

Lifecycle: `generate → review → improve → test` (retry loop) → `document → extract_spec → spec_judge`

See `cookbook/56_code_pipeline/README.md` for full parameter reference.

```bash
# Minimal — binary search, closure check enabled by default
spl run cookbook/56_code_pipeline/code_pipeline.spl \
    --param spec="Write a binary search function that returns the index or -1"

# More complex spec — tests the retry loop
spl run cookbook/56_code_pipeline/code_pipeline.spl \
    --param spec="Write a function to flatten a nested list to any depth"

# Increase retry budget for harder specs
spl run cookbook/56_code_pipeline/code_pipeline.spl \
    --param spec="Write a function to parse ISO 8601 date strings" \
    --param max_cycles=5

# Skip closure check (faster, steps 3b and 3c omitted)
spl run cookbook/56_code_pipeline/code_pipeline.spl \
    --param spec="Write a function to count word frequencies in a string" \
    --param check_closure=FALSE

# Custom model
spl run cookbook/56_code_pipeline/code_pipeline.spl \
    --param spec="Write a LRU cache with get and put methods" \
    --param model=llama3.2 \
    --param max_cycles=3
```

Expected log output:
```
[code_pipeline] started | spec="..." max_cycles=3 check_closure=True
[code_pipeline] cycle=1 | step 1: generate
[generate_code] started | spec="..."
[generate_code] done | output_len=...
[code_pipeline] cycle=1 | step 1: review
[code_pipeline] cycle=1 | step 1: improve
[code_pipeline] cycle=1 | step 2: test
[test_code] done | result=[PASSED]...
[code_pipeline] tests passed at cycle=1
[code_pipeline] step 3: document
[code_pipeline] step 3: extract spec from implementation
[code_pipeline] step 3: closure check — spec vs derived spec
[spec_judge] verdict: CLOSED — implementation matches intent
[code_pipeline] done | cycles=1 test_passed=True check_closure=True
```

**What to verify — step by step:**

- [ ] **CALL dispatch works** — each sub-workflow (`generate_code`, `review_code`, etc.) is called via `CALL`, not inlined; verify Hub registry resolves the names
- [ ] **Sentinel format** — `[PASSED]` / `[FAILED]` in `test_code` output; `[CLOSED]` / `[DIVERGED]` in `spec_judge` output; if the LLM outputs these tokens inside prose rather than on the first line, `EVALUATE contains(...)` still matches correctly
- [ ] **Retry loop triggers** — run with a deliberately tricky spec and confirm `cycle=2` or `cycle=3` appears in the log when tests fail
- [ ] **Closure report in final output** — the `@docs` return value should end with a `## Closure Report` section containing the original spec, derived spec, and judge verdict
- [ ] **String concatenation** — the `@docs := @docs || '...' || @closure_report` assignment in the orchestrator; verify the SPL runtime supports `||` in variable assignment context (not just in `LOGGING`)
- [ ] **`@out_spec` quality** — read the derived spec in the closure report and check how much semantic content `extract_spec` preserved vs. paraphrased away; this is the most revealing signal of model comprehension
- [ ] **`check_closure=FALSE` path** — confirm step 3b and 3c are skipped cleanly and `@docs` is returned without the closure section
- [ ] **`@log_dir` param** — present in all sub-workflow signatures; no `write_file` calls yet in recipes 50–56 (except 05); file logging is a planned follow-up

**Known watch items for this weekend:**

| Item | Risk | What to check |
|------|------|---------------|
| `[PASSED]` / `[CLOSED]` token placement | Medium — model may embed token in prose | `EVALUATE contains(...)` handles this; verify no false positives |
| `\|\|` in assignment context | Medium — runtime may not support | If `@docs` is truncated or empty, this is the cause; workaround: return `@closure_report` as a separate output |
| `CALL` registry resolution | High — first live test of sub-workflow dispatch | Check Hub logs for `workflow not found` errors; ensure all 7 `.spl` files are registered |
| LLM refusal on `generate_code` | Low | `EXCEPTION WHEN RefusalToAnswer` should catch; verify `status = 'refused'` surfaces |

---

## Media Conversion Recipes (Tier 1, no API key)

### Recipe 57: Image Format Conversion (IMAGE → IMAGE)

```bash
# PNG → JPEG (default, quality 85)
python cookbook/57_image_convert/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --target-format png

# JPEG → WebP (high quality)
python cookbook/57_image_convert/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --target-format webp --quality 90

# PNG → BMP
python cookbook/57_image_convert/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --target-format bmp
```

**What to verify:**
- [ ] Output file appears in `cookbook/57_image_convert/outputs/`
- [ ] Format is correct (open with image viewer or `file <output>`)
- [ ] Quality param affects JPEG/WebP file size meaningfully
- [ ] `FileNotFound` and `UnsupportedFormat` exceptions surface correctly

---

### Recipe 58: Audio Format Conversion (AUDIO → AUDIO)

```bash
# WAV → MP3 (default 192k)
python cookbook/58_audio_convert/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --target-format wav

# MP3 → OGG
python cookbook/58_audio_convert/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --target-format ogg --bitrate 128k

# WAV → FLAC (lossless)
python cookbook/58_audio_convert/run.py \
    --audio cookbook/51_audio_summary/sample/clip.mp3 \
    --target-format flac
```

**What to verify:**
- [ ] Output file appears in `cookbook/58_audio_convert/outputs/`
- [ ] Audio is playable and format is correct (`ffprobe <output>`)
- [ ] `CodecError` surfaces cleanly if ffmpeg is missing

---

## Video Recipes

### Prerequisites for video recipes

```bash
# Use any short MP4 clip as sample input (10–30 seconds recommended)
# Place it at the expected sample path for each recipe, e.g.:
cp /path/to/your/clip.mp4 cookbook/60_video_summary/sample/clip.mp4
cp /path/to/your/clip.mp4 cookbook/61_video_to_audio/sample/clip.mp4
cp /path/to/your/clip.mp4 cookbook/62_video_to_image/sample/clip.mp4
```

---

### Recipe 59: Text to Video (TEXT → VIDEO, Tier 2)

Requires `GOOGLE_API_KEY` (Veo 2) or a RunwayML API key.

```bash
export GOOGLE_API_KEY=...

# Default — forest at dawn, 5 seconds, cinematic
python cookbook/59_text_to_video/run.py \
    --prompt "A duck walking through a quiet forest at dawn, soft morning light"

# With gemma4 prompt enhancement
python cookbook/59_text_to_video/run.py \
    --prompt "A mountain lake at sunset" \
    --style "cinematic, drone shot" --enhance

# No enhancement, portrait aspect, 8 seconds
python cookbook/59_text_to_video/run.py \
    --prompt "A candle flickering in the wind" \
    --aspect portrait --duration 8 --enhance false
```

**What to verify:**
- [ ] Prompt enhancement produces a more detailed, cinematic prompt
- [ ] Video file appears in `cookbook/59_text_to_video/outputs/`
- [ ] `ModelUnavailable` surfaces cleanly if API key is missing or quota exceeded

---

### Recipe 60: Video Summary (VIDEO → TEXT, Tier 1)

```bash
# Default — summary mode
python cookbook/60_video_summary/run.py \
    --video cookbook/60_video_summary/sample/clip.mp4

# Transcript with timestamps
python cookbook/60_video_summary/run.py \
    --video cookbook/60_video_summary/sample/clip.mp4 --mode transcript

# Key moments list
python cookbook/60_video_summary/run.py \
    --video cookbook/60_video_summary/sample/clip.mp4 --mode key_moments

# Chapter breakdown
python cookbook/60_video_summary/run.py \
    --video cookbook/60_video_summary/sample/clip.mp4 --mode chapters

# Custom summary style
python cookbook/60_video_summary/run.py \
    --video cookbook/60_video_summary/sample/clip.mp4 \
    --mode summary --style "three bullet points, executive style"
```

**What to verify:**
- [ ] gemma4 correctly processes the VIDEO type (frames + audio)
- [ ] `[NO SPEECH]` output in transcript mode for silent videos
- [ ] All 4 modes produce structurally distinct output formats
- [ ] `FileNotFound` exception surfaces for missing video

---

### Recipe 61: Video to Audio (.mp4 → .mp3, Tier 1)

```bash
# Default — MP3 at 192k
python cookbook/61_video_to_audio/run.py \
    --video cookbook/61_video_to_audio/sample/clip.mp4

# WAV at high sample rate
python cookbook/61_video_to_audio/run.py \
    --video cookbook/61_video_to_audio/sample/clip.mp4 \
    --target-format wav --sample-rate 48000

# FLAC lossless
python cookbook/61_video_to_audio/run.py \
    --video cookbook/61_video_to_audio/sample/clip.mp4 \
    --target-format flac

# Pipe output directly into recipe 51 (audio_summary)
# (demonstrates composability — video_to_audio → audio_summary)
python cookbook/61_video_to_audio/run.py \
    --video cookbook/61_video_to_audio/sample/clip.mp4 \
    --output-dir /tmp/extracted && \
python cookbook/51_audio_summary/run.py \
    --audio /tmp/extracted/clip.mp3
```

**What to verify:**
- [ ] Audio track extracted correctly and is playable
- [ ] `NoAudioTrack` exception for silent/video-only files
- [ ] Composability: output feeds into recipe 51 without modification

---

### Recipe 62: Video to Image (VIDEO → IMAGE, Tier 1)

```bash
# Extract middle frame (default)
python cookbook/62_video_to_image/run.py \
    --video cookbook/62_video_to_image/sample/clip.mp4

# Extract at specific timestamp
python cookbook/62_video_to_image/run.py \
    --video cookbook/62_video_to_image/sample/clip.mp4 \
    --mode timestamp --timestamp 00:00:03

# First frame
python cookbook/62_video_to_image/run.py \
    --video cookbook/62_video_to_image/sample/clip.mp4 --mode first

# Last frame
python cookbook/62_video_to_image/run.py \
    --video cookbook/62_video_to_image/sample/clip.mp4 --mode last

# Extract frame + caption with gemma4 vision
python cookbook/62_video_to_image/run.py \
    --video cookbook/62_video_to_image/sample/clip.mp4 \
    --caption --context "This is a wildlife documentary clip"

# Pipe output into recipe 50 (image_caption) for full captioning
# (demonstrates composability — video_to_image → image_caption)
python cookbook/62_video_to_image/run.py \
    --video cookbook/62_video_to_image/sample/clip.mp4 \
    --output-dir /tmp/frames && \
python cookbook/50_image_caption/run.py \
    --image /tmp/frames/frame_middle.jpg --mode detailed
```

**What to verify:**
- [ ] Frame extracted at correct position (verify visually)
- [ ] `InvalidTimestamp` exception for out-of-range timestamps
- [ ] Caption mode calls gemma4 vision and returns meaningful description
- [ ] `ModelUnavailable` in caption mode returns frame with `status = 'partial'` (not a crash)
- [ ] Composability: output feeds into recipe 50 without modification

---

## Recipe Summary

| id | Name | Input | Output | Tier | Key model(s) | Notes |
|---|---|---|---|---|---|---|
| 05 | `self_refine` | TEXT | TEXT | 1 | gemma3 + llama3.2 (Ollama) | First `CALL` workflow demo |
| 50 | `image_caption` | IMAGE | TEXT | 1 | gemma4:e4b (Ollama) | |
| 51 | `audio_summary` | AUDIO | TEXT | 3 | LFM-2.5 (OpenRouter) | |
| 52 | `text_to_image` | TEXT | IMAGE | 2 | DALL-E 3 (OpenAI) | |
| 53 | `text_to_speech` | TEXT | AUDIO | 2 | OpenAI TTS or system | |
| 54 | `image_restyle` | IMAGE + TEXT | TEXT + IMAGE | 4 | gemma4:e4b + DALL-E 3 | |
| 55 | `voice_dialogue` | AUDIO + TEXT | TEXT + AUDIO | 4 | LFM-2.5 + gemma4:e4b + OpenAI TTS | |
| 56 | `code_pipeline` | TEXT (spec) | TEXT (docs + closure) | 1 | gemma4 (Ollama) | NDD closure; 7 sub-workflows |
| 57 | `image_convert` | IMAGE | IMAGE | 1 | — (codec only) | PNG ↔ JPEG ↔ WebP ↔ BMP |
| 58 | `audio_convert` | AUDIO | AUDIO | 1 | — (codec only) | WAV ↔ MP3 ↔ OGG ↔ FLAC |
| 59 | `text_to_video` | TEXT | VIDEO | 2 | Veo 2 / RunwayML + gemma4 | First VIDEO output recipe |
| 60 | `video_summary` | VIDEO | TEXT | 1 | gemma4 (Ollama) | 4 modes; first VIDEO input recipe |
| 61 | `video_to_audio` | VIDEO | AUDIO | 1 | — (codec only) | .mp4 → .mp3 / .wav / .flac |
| 62 | `video_to_image` | VIDEO | IMAGE | 1 | gemma4 optional | Frame extraction + optional caption |

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
| `workflow not found` error (recipe 56) | Hub registry missing sub-workflow | Ensure all 7 `.spl` files in `56_code_pipeline/` are registered; check IMPORT resolution |
| `@docs` empty or truncated (recipe 56) | `\|\|` assignment not supported by runtime | Return `@closure_report` separately; workaround pending runtime fix |
| `[PASSED]` / `[CLOSED]` never matched | LLM embedded token in prose | `EVALUATE contains(...)` should still match; if not, check SPL `contains()` implementation |
| `llama3.2 not found` (recipe 05) | Model not pulled | `ollama pull llama3.2` |
| `gemma3 not found` (recipe 05) | Model not pulled | `ollama pull gemma3` |

