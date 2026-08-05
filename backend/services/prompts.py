"""Compatibility wrapper for protected prompt helpers.

The core prompt and generation rules live in ``backend/protected`` so release
builds can ship them as compiled ``.pyd`` modules while keeping existing imports
stable for the rest of the application.
"""
from protected.prompts_core import *  # noqa: F401,F403

