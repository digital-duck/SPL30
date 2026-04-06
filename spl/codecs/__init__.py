"""SPL 3.0 codec layer — raw media → ContentPart dicts for LLM adapters.

Codecs sit between user code (file paths, PIL images, raw bytes) and the
LLM adapter layer (structured ContentPart dicts).  Adapters never handle
raw files; they receive pre-encoded ContentPart dicts from this layer.

Usage::

    from spl.codecs import encode_image, encode_audio, encode_video

    image_part  = encode_image("photo.jpg")               # → ImagePart
    audio_part  = encode_audio("clip.wav")                 # → AudioPart
    frame_parts = encode_video("demo.mp4", fps=1)          # → list[ImagePart]

    content = [
        {"type": "text", "text": "What is in this image?"},
        image_part,
    ]
    result = await adapter.generate_multimodal(content)
"""

from __future__ import annotations

from spl.codecs.image_codec import encode_image
from spl.codecs.audio_codec import encode_audio
from spl.codecs.video_codec import encode_video

__all__ = ["encode_image", "encode_audio", "encode_video"]
