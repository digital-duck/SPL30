"""
cookbook/tools/registry.py — Aggregated tool registry for cookbook recipes.

Usage:
    python run.py --tools cookbook/tools/registry.py ...

This module imports all cookbook tool modules so their @spl_tool-decorated
functions are registered in the global SPL tool registry.  Pass this file
via --tools to make convert_image, extract_audio, extract_frame, etc.
available inside SPL CALL statements.

Available tools after loading
------------------------------
Image   : convert_image, resize_image, image_info
Audio   : convert_audio, trim_audio, get_audio_duration
Video   : extract_audio, extract_frame, get_video_duration, video_info
"""

from __future__ import annotations

# Importing each module triggers @spl_tool registration as a side effect.
from cookbook.tools import image_tools as _img   # noqa: F401
from cookbook.tools import audio_tools as _aud   # noqa: F401
from cookbook.tools import video_tools as _vid   # noqa: F401


def get_cookbook_tools() -> list[str]:
    """Return a sorted list of tool names registered by this registry."""
    from spl.tools import _GLOBAL_TOOLS  # type: ignore[attr-defined]
    return sorted(_GLOBAL_TOOLS.keys())
