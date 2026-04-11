# Recipe 54: Image Restyle

**Category:** multimodal / generative  
**SPL version:** 3.0  
**Type:** IMAGE + TEXT → TEXT + IMAGE  
**LLM required:** Yes — gemma4 vision (Ollama) + DALL-E 3 (OpenAI)  
**Demonstrates:** IMAGE as both input and output type, two-model pipeline (local vision → cloud generation), JSON-structured intermediate

---

## What it does

Analyses a source image with gemma4 vision, generates a DALL-E 3 prompt that
preserves the original composition while applying a new style, then generates
a restyled image.

```
[source image] + [style instruction]
      │
      ▼  gemma4 vision via Ollama  (IMAGE → TEXT)
[JSON: {description, dalle_prompt}]
      │
      ▼  DALL-E 3 via OpenAI       (TEXT → IMAGE)
[restyled image file]
```

The intermediate step produces a JSON object with two fields:
- `description` — what gemma4 sees in the original
- `dalle_prompt` — the DALL-E 3 prompt to recreate the scene in the new style

This two-model handoff is the core pattern of the recipe: a local vision model
understands the image; a cloud generation model produces the new one.

---

## Files

| File | Role |
|------|------|
| `image_restyle.spl` | SPL logical view — 1 prompt function, 1 workflow |
| `run.py` | Physical runner — gemma4 vision + DALL-E 3 generation |
| `sample/` | Place source images here |
| `outputs/` | Restyled images written here |

---

## Prerequisites

```bash
# Vision analysis (local)
ollama serve
ollama pull gemma4:e4b

# Image generation (cloud)
export OPENAI_API_KEY=sk-...   # must point to api.openai.com
pip install Pillow
```

---

## Running

```bash
export OPENAI_API_KEY=sk-...

# Default — watercolor style
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
    --quality hd

# Cyberpunk neon, vivid mode
python cookbook/54_image_restyle/run.py \
    --image cookbook/54_image_restyle/sample/photo.jpg \
    --style "cyberpunk neon city" --dalle-style vivid

# Preserve specific elements explicitly
python cookbook/54_image_restyle/run.py \
    --image cookbook/54_image_restyle/sample/photo.jpg \
    --style "pencil sketch, black and white" \
    --preserve "main subject, facial expression, proportions"
```

### Generate a test image

```bash
cp cookbook/50_image_caption/sample/photo.jpg \
   cookbook/54_image_restyle/sample/photo.jpg
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@photo` | IMAGE | `cookbook/54_image_restyle/sample/photo.jpg` | Source image file path |
| `@style` | TEXT | `watercolor painting, soft edges, pastel tones` | Style transformation to apply |
| `@preserve` | TEXT | `composition, main subject, mood` | Elements to preserve from the original |
| `@quality` | TEXT | `hd` | DALL-E 3 quality: `standard` or `hd` |
| `@dalle_style` | TEXT | `natural` | DALL-E 3 rendering style: `natural` or `vivid` |
| `@vision_model` | TEXT | `gemma4:e4b` | Local vision model for image analysis |
| `@output_dir` | TEXT | `cookbook/54_image_restyle/outputs` | Directory to write restyled image |
| `@log_dir` | TEXT | `cookbook/54_image_restyle/logs-spl` | Directory for log output |

---

## Output

`@result TEXT` — the JSON intermediate (`{description, dalle_prompt}`) returned
by the vision step. The restyled image file is a side effect written to `@output_dir`
by `run.py`.

Filename pattern: `restyled_<timestamp>.png`

---

## Known behaviour

If gemma4 does not return valid JSON (rare), `run.py` falls back to using the
raw vision output as the DALL-E prompt — the image is still generated, though
the prompt may be less precise.

---

## Composability

```sql
-- Convert format first, then restyle
CALL image_convert(@raw_image, 'jpeg', 85, @output_dir) INTO @image
CALL image_restyle(@image, @style, @preserve, ...) INTO @result

-- Restyle a frame extracted from video
CALL video_to_image(@video, 'middle', ...) INTO @frame
CALL image_restyle(@frame, 'watercolor painting', ...) INTO @restyled
```

---

## Error handling

| Exception | Cause | Behaviour |
|-----------|-------|-----------|
| `ModelUnavailable` | Ollama not running or `OPENAI_API_KEY` missing | Returns error string with `status = 'failed'` |
