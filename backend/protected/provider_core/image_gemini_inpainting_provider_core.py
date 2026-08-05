"""
Mock image_gemini_inpainting_provider_core module.
"""
import os
import logging

logger = logging.getLogger(__name__)


class GeminiInpaintingProvider:
    """Gemini inpainting provider."""

    def __init__(self, api_key: str = None, api_base: str = None, model: str = None):
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY', '')
        self.api_base = api_base or os.getenv('GOOGLE_API_BASE', '')
        self.model = model or 'gemini-pro'
        logger.info("GeminiInpaintingProvider initialized")

    def inpaint(self, image_path: str, mask_path: str = None, prompt: str = None):
        """Perform inpainting."""
        logger.info("Inpainting with Gemini")
        raise NotImplementedError("Gemini inpainting not implemented in mock")
