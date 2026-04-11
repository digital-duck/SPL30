# Recipe 50: Image Caption

**Category:** multimodal  
**SPL version:** 3.0  
**Type:** IMAGE → TEXT  
**LLM required:** Yes — gemma4 (native vision) via Ollama  
**Demonstrates:** `IMAGE` as a first-class SPL input type, multi-mode `EVALUATE`, vision model dispatch

---

## What it does

Describes, analyses, or OCRs an image using gemma4's native vision capability.
Three modes cover the most common image understanding tasks:

| Mode | What it produces |
|------|-----------------|
| `caption` | Answers a specific question about the image |
| `detailed` | Comprehensive description: subjects, setting, colours, text, mood |
| `ocr` | Extracts all visible text exactly as it appears |

The IMAGE input is encoded by `spl/codecs/image_codec.py` before being passed
to `generate_multimodal()` — the `.spl` logical view is hardware-agnostic.

---

## Files

| File | Role |
|------|------|
| `image_caption.spl` | SPL logical view — 3 prompt functions, 1 workflow |
| `run.py` | Physical runner — image codec + Ollama multimodal call |
| `sample/` | Place test images here (`.jpg` / `.png` recommended) |
| `outputs/` | (no file output — result is returned as TEXT) |

---

## Prerequisites

```bash
ollama serve
ollama pull gemma4:e4b       # vision model
pip install Pillow           # image encoding
```

---

## Running

```bash
# Default — caption mode, answers default question
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg

# Detailed description
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --mode detailed

# OCR — extract visible text
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --mode ocr

# Custom question
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --question "What colours are dominant in this scene?"

# Larger model for higher accuracy
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --model gemma4:e2b

# Larger output budget
python cookbook/50_image_caption/run.py \
    --image cookbook/50_image_caption/sample/photo.jpg \
    --mode detailed --output-budget 2048
```

### Generate a test image (no download needed)

```bash
python -c "
from PIL import Image, ImageDraw
import pathlib
pathlib.Path('cookbook/50_image_caption/sample').mkdir(parents=True, exist_ok=True)
img = Image.new('RGB', (800, 600), (70, 130, 180))
draw = ImageDraw.Draw(img)
draw.polygon([(0,600),(200,250),(400,600)], fill=(90,90,90))
draw.polygon([(150,600),(380,200),(600,600)], fill=(110,110,110))
draw.ellipse([600,50,720,170], fill=(255,220,50))
img.save('cookbook/50_image_caption/sample/photo.jpg', 'JPEG')
print('test image created')
"
```

---

## Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `@photo` | IMAGE | `cookbook/50_image_caption/sample/photo.jpg` | Source image file path |
| `@question` | TEXT | `What is in this image? Describe it in detail.` | Question for `caption` mode |
| `@mode` | TEXT | `caption` | Output mode: `caption`, `detailed`, `ocr` |
| `@model` | TEXT | `gemma4` | Vision model (Ollama) |
| `@output_budget` | INT | `1024` | Max output tokens |
| `@log_dir` | TEXT | `cookbook/50_image_caption/logs-spl` | Directory for log output |

---

## Output

`@result TEXT` — the image description, answer, or OCR text.

---

## Composability

```sql
-- Convert format first, then caption
CALL image_convert(@raw_image, 'jpeg', 85, @output_dir) INTO @image
CALL image_caption(@image, @question, 'caption', @model, @output_budget) INTO @caption

-- Extract video frame, then caption
CALL video_to_image(@video, 'middle', ...) INTO @frame
CALL image_caption(@frame, '', 'detailed', @model, 2048) INTO @description
```

---

## Error handling

| Exception | Cause | Behaviour |
|-----------|-------|-----------|
| `ModelUnavailable` | Ollama not running or gemma4 not pulled | Returns error string with `status = 'failed'` |
