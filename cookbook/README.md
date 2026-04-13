# SPL 3.0 Cookbook

SPL 3.0 extends SPL 2.0 with multimodal types (`IMAGE`, `AUDIO`, `VIDEO`),
sub-workflow `CALL` composition, and `CALL PARALLEL` concurrency.
Recipe 05 is the entry point; recipes 50–64 cover the full SPL 3.0 capability set.

Each recipe has its own `README.md` with full details, parameters, and examples.

---

## Recipe Index

| # | Recipe | Flow | Group | Tier | Model(s) |
|---|--------|------|-------|------|----------|
| [05](05_self_refine/) | self_refine | TEXT → TEXT | entry | 1 | gemma3 + llama3.2 (Ollama) |
| [50](50_code_pipeline/) | code_pipeline | TEXT → TEXT | text / code | 1 | gemma4 (Ollama) |
| [51](51_image_caption/) | image_caption | IMAGE → TEXT | → text | 1 | gemma4:e4b (Ollama) |
| [52](52_audio_summary/) | audio_summary | AUDIO → TEXT | → text | 1 | gemma4:e4b (Ollama) |
| [53](53_video_summary/) | video_summary | VIDEO → TEXT | → text | 1 | gemma4 (Ollama) |
| [54](54_text_to_image/) | text_to_image | TEXT → IMAGE | text → | 2 | DALL-E 3 (OpenAI) |
| [55](55_text_to_speech/) | text_to_speech | TEXT → AUDIO | text → | 2 | OpenAI TTS or system |
| [56](56_text_to_video/) | text_to_video | TEXT → VIDEO | text → | 2 | Veo 2 / RunwayML |
| [57](57_image_convert/) | image_convert | IMAGE → IMAGE | image | 1 | codec only |
| [58](58_image_restyle/) | image_restyle | IMAGE → IMAGE | image | 2 | gemma4:e4b + DALL-E 3 |
| [59](59_audio_convert/) | audio_convert | AUDIO → AUDIO | audio | 1 | codec only |
| [60](60_voice_dialogue/) | voice_dialogue | AUDIO → AUDIO | audio | 4 | LFM-2.5 + gemma4 + OpenAI TTS |
| [61](61_video_to_audio/) | video_to_audio | VIDEO → AUDIO | video | 1 | codec only |
| [62](62_video_to_image/) | video_to_image | VIDEO → IMAGE | video | 1 | gemma4 optional |
| [63](63_parallel_code_review/) | parallel_code_review | TEXT → TEXT | advanced | 1 | gemma4 (Ollama) |
| [64](64_parallel_news_digest/) | parallel_news_digest | TEXT → TEXT | advanced | 1 | gemma4 (Ollama) |

**Tier key:** 1 = Ollama only (no API key) · 2 = OpenAI key · 3 = OpenRouter key · 4 = OpenAI + OpenRouter + Ollama

---

## Setup

```bash
conda activate spl3
pip install spl-llm>=2.0.0
pip install -e ~/projects/digital-duck/SPL30

# Tier 1 models (Ollama)
ollama serve
ollama pull gemma4:e4b
ollama pull gemma3
ollama pull llama3.2

# Codec tools (recipes 57–62)
pip install Pillow pydub
sudo apt install ffmpeg        # Ubuntu/Debian

# API keys (tier 2+)
export OPENAI_API_KEY=sk-...
export OPENROUTER_API_KEY=sk-or-...
```

---

## Running recipes

```bash
# SPL workflows (recipes 05, 50, 63, 64)
spl3 run cookbook/05_self_refine/self_refine.spl --adapter ollama

# Multimodal — native spl3 run (recipes 51–53)
spl3 run cookbook/51_image_caption/image_caption.spl \
    --adapter ollama \
    --param photo="cookbook/51_image_caption/sample/photo.jpg" \
    --param model="gemma4:e4b"

spl3 run cookbook/52_audio_summary/audio_summary.spl \
    --adapter ollama \
    --param clip="cookbook/52_audio_summary/sample/clip.wav" \
    --param model="gemma4:e4b"

# Physical runners (run.py) for recipes with extra options
python cookbook/51_image_caption/run.py --image path/to/photo.jpg
python cookbook/52_audio_summary/run.py --audio path/to/clip.wav

# Batch run (reads cookbook_catalog.json)
python cookbook/run_all.py              # tier-1 active recipes
python cookbook/run_all.py --tier 1     # Ollama only
python cookbook/run_all.py --ids 51,52  # specific recipes
python cookbook/run_all.py --all        # everything
```

---

## Groups

### Entry
**05 self_refine** — The first SPL 3.0 recipe. Demonstrates `CALL` sub-workflow
dispatch: `critique_workflow` is called from the orchestrator, with a retry
loop that stops on `[APPROVED]`. Start here.

### Text / Code (50)
**50 code_pipeline** — NDD closure: `generate → review → improve → test →
document → extract_spec → spec_judge`. Seven sub-workflows composed via `CALL`.
The reference implementation of the closure principle.

### Multimodal → Text (51–53)
Recipes that take a media file and produce a text description, transcript, or summary.
- **51 image_caption** — describe / OCR an image (IMAGE → TEXT)
- **52 audio_summary** — transcribe / summarise audio (AUDIO → TEXT)
- **53 video_summary** — summarise / transcribe a video (VIDEO → TEXT)

### Text → Multimodal (54–56)
Recipes that take a text prompt and produce a media file.
- **54 text_to_image** — DALL-E 3 image generation (TEXT → IMAGE)
- **55 text_to_speech** — TTS audio file (TEXT → AUDIO)
- **56 text_to_video** — Veo 2 / RunwayML video clip (TEXT → VIDEO)

### Image (57–58)
- **57 image_convert** — format conversion: PNG ↔ JPEG ↔ WebP ↔ BMP (codec only)
- **58 image_restyle** — vision analysis + DALL-E 3 restyle (IMAGE → IMAGE)

### Audio (59–60)
- **59 audio_convert** — format conversion: WAV ↔ MP3 ↔ OGG ↔ FLAC (codec only)
- **60 voice_dialogue** — full voice assistant: transcribe → respond → speak

### Video → (61–62)
- **61 video_to_audio** — extract audio track: .mp4 → .mp3 / .wav / .flac (codec only)
- **62 video_to_image** — extract frame(s); optional gemma4 caption

### Advanced Parallel (63–64)
- **63 parallel_code_review** — style + security + test reviews via `CALL PARALLEL`
- **64 parallel_news_digest** — three topics summarised concurrently, merged into a briefing
