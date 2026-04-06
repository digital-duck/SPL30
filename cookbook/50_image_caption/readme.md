# Recipe 50: Image Caption

**Category:** multimodal  
**SPL type:** `IMAGE`  
**Primary model:** Gemma 4 via Ollama (native image+text)  
**splc targets:** `python/liquid`, `go` + Ollama

Describe, analyse, or extract text from any image using a vision-capable model.
Demonstrates SPL 3.0's `IMAGE` type annotation and the `spl.codecs` layer.

## Pattern

```
[image file / URL]
       │
       ▼  spl.codecs.encode_image()
[ImagePart (base64)]
       │
       ▼  LiquidAdapter.generate_multimodal()
[caption / description / OCR text]
```

## Modes

| Mode | Prompt strategy | Best for |
|---|---|---|
| `caption` | Q&A — answer a specific question | Targeted queries |
| `detailed` | Full description | Scene understanding, accessibility |
| `ocr` | Extract all visible text | Screenshots, documents, signs |

## Prerequisites

```bash
# Pull Gemma 4 (vision-capable)
ollama pull gemma4

# Or LLaVA as fallback
ollama pull llava:13b
```

Pillow for auto-resize (strongly recommended):
```bash
pip install Pillow
```

## Usage

### Minimal — caption a local image

```bash
python cookbook/50_image_caption/run.py --image path/to/photo.jpg
```

### Ask a specific question

```bash
python cookbook/50_image_caption/run.py \
    --image path/to/photo.jpg \
    --question "How many people are in this image?"
```

### Full detailed description

```bash
python cookbook/50_image_caption/run.py \
    --image path/to/photo.jpg --mode detailed
```

### OCR — extract text from a screenshot

```bash
python cookbook/50_image_caption/run.py \
    --image path/to/screenshot.png --mode ocr
```

### Caption a public URL (no local encoding)

```bash
python cookbook/50_image_caption/run.py \
    --image "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"
```

### Via OpenRouter (LFM-2.5 multimodal, no local GPU needed)

```bash
export OPENROUTER_API_KEY=sk-...
python cookbook/50_image_caption/run.py \
    --image path/to/photo.jpg \
    --backend openrouter \
    --model liquid/lfm-2.5-1.2b-instruct:free
```

### Larger Gemma 4 for higher accuracy

```bash
python cookbook/50_image_caption/run.py \
    --image path/to/photo.jpg \
    --model gemma4:27b --max-dim 1568
```

## Parameters

| Flag | Default | Description |
|---|---|---|
| `--image` | *(required)* | Local file path or public HTTPS URL |
| `--question` | `"What is in this image?"` | Question for caption mode |
| `--mode` | `caption` | `caption` \| `detailed` \| `ocr` |
| `--model` | `gemma4` | Any vision-capable Ollama model |
| `--backend` | `ollama` | `ollama` (local) or `openrouter` (cloud) |
| `--max-dim` | `1024` | Resize longest edge to N pixels before encoding |
| `--max-tokens` | `1024` | Max output tokens |

## SPL Logical View

`image_caption.spl` is the DODA invariant — it declares the workflow with an
`IMAGE`-typed input param.  The runtime encodes the image via `spl/codecs/`
and passes a `ContentPart` dict to `generate_multimodal()`.

```sql
WORKFLOW image_caption
    INPUT:
        @photo    IMAGE  DEFAULT 'cookbook/50_image_caption/sample/photo.jpg',
        @question TEXT   DEFAULT 'What is in this image?',
        @mode     TEXT   DEFAULT 'caption',
        @model    TEXT   DEFAULT 'gemma4'
    OUTPUT: @result TEXT
```

## Supported Models

| Model | Pull command | Notes |
|---|---|---|
| `gemma4` | `ollama pull gemma4` | Recommended — native multimodal |
| `gemma4:27b` | `ollama pull gemma4:27b` | Higher accuracy, needs ~20 GB RAM |
| `llava:13b` | `ollama pull llava:13b` | Fallback if Gemma 4 not available |
| `llava-phi3` | `ollama pull llava-phi3` | Lightweight fallback |
| `liquid/lfm-2.5-1.2b-instruct:free` | OpenRouter | No local GPU needed |
