# Recipe 54: Image Restyle

**Category:** multimodal  
**SPL types:** IMAGE + TEXT → TEXT + IMAGE  
**Vision model:** Gemma4 via Ollama (already available: `gemma4:e4b`)  
**Image gen:** DALL-E 3 via OpenAI API (requires `OPENAI_API_KEY`)

Analyse a source image and generate a restyled version. Gemma4 describes
the image and creates a DALL-E prompt; DALL-E 3 generates the new image.

## Pipeline

```
[source image]  +  [style instruction]
        │
        ▼  Gemma4:e4b (Ollama)  generate_multimodal()
[JSON: {description, dalle_prompt}]
        │
        ▼  DALL-E 3 (OpenAI)
[restyled PNG]  →  outputs/restyled_TIMESTAMP.png
```

## Prerequisites

```bash
# Gemma4 already on Ollama (gemma4:e4b)
export OPENAI_API_KEY=sk-...
```

## Usage

```bash
# Default style (watercolor)
python cookbook/58_image_restyle/run.py --image path/to/photo.jpg

# Anime / Studio Ghibli
python cookbook/58_image_restyle/run.py \
    --image photo.jpg \
    --style "Studio Ghibli anime, soft illustration, warm colors"

# Oil painting, landscape HD
python cookbook/58_image_restyle/run.py \
    --image photo.jpg \
    --style "oil painting, impressionist, thick brushstrokes" \
    --aspect landscape --quality hd

# Cyberpunk neon, vivid DALL-E style
python cookbook/58_image_restyle/run.py \
    --image photo.jpg \
    --style "cyberpunk neon city, rain-slicked streets" \
    --dalle-style vivid
```

## Parameters

| Flag | Default | Description |
|---|---|---|
| `--image` | *(required)* | Source image path |
| `--style` | `watercolor painting, soft edges, pastel tones` | Style to apply |
| `--preserve` | `composition, main subject, mood` | Elements to keep |
| `--aspect` | `square` | `square` \| `landscape` \| `portrait` |
| `--quality` | `standard` | `standard` \| `hd` |
| `--dalle-style` | `natural` | `natural` \| `vivid` |
| `--vision-model` | `gemma4:e4b` | Ollama vision model |

## Output

Both TEXT and IMAGE are produced:
- **Text:** Gemma4's description + the DALL-E prompt used
- **Image:** `outputs/restyled_TIMESTAMP.png`
