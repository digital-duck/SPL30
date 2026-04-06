# Recipe 52: Text to Image

**Category:** multimodal  
**SPL types:** TEXT → IMAGE  
**Model:** DALL-E 3 via OpenAI API (requires `OPENAI_API_KEY`)  
**Optional:** Gemma4 via Ollama for prompt enhancement

Generate an image from a text prompt. Optionally enhance the prompt using
Gemma4 before sending to DALL-E 3.

## Pipeline

```
[text prompt]  (+ optional style hint)
      │
      ▼  Gemma4 / Ollama (--enhance)        optional prompt enhancement
[enhanced prompt]
      │
      ▼  DALL-E 3 (OpenAI)
[PNG image file]  →  outputs/generated_TIMESTAMP.png
```

## Prerequisites

```bash
export OPENAI_API_KEY=sk-...

# Optional: Gemma4 for prompt enhancement
# Already available: ollama pull gemma4:e4b (check with: ollama list)
```

## Usage

```bash
# Minimal
python cookbook/52_text_to_image/run.py \
    --prompt "A fox in a moonlit forest"

# With prompt enhancement via Gemma4
python cookbook/52_text_to_image/run.py \
    --prompt "A fox in a forest" --enhance --style "oil painting"

# HD landscape
python cookbook/52_text_to_image/run.py \
    --prompt "Tokyo skyline at night" \
    --aspect landscape --quality hd

# Vivid (dramatic) style
python cookbook/52_text_to_image/run.py \
    --prompt "Dragon over a medieval castle" --dalle-style vivid
```

## Parameters

| Flag | Default | Description |
|---|---|---|
| `--prompt` | *(required)* | Text description of the image |
| `--style` | `photorealistic` | Style hint for prompt enhancement |
| `--aspect` | `square` | `square` \| `landscape` \| `portrait` |
| `--quality` | `standard` | `standard` \| `hd` (costs ~2× more) |
| `--dalle-style` | `natural` | `natural` (realistic) \| `vivid` (dramatic) |
| `--enhance` | off | Run prompt through Gemma4 before DALL-E |
| `--model` | `dall-e-3` | `dall-e-3` \| `dall-e-2` |
| `--llm-model` | `gemma4:e4b` | Ollama model for enhancement |
