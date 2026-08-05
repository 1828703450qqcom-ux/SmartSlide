"""
Mock image_genai_provider_core module - Google GenAI image provider.
"""
import os
import logging

logger = logging.getLogger(__name__)


class GenAIImageProvider:
    """Google GenAI image provider."""

    def __init__(self, api_key: str = None, api_base: str = None, model: str = None,
                 vertexai: bool = False, project_id: str = None, location: str = None):
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY', '')
        self.api_base = api_base or os.getenv('GOOGLE_API_BASE', '')
        self.model = model or os.getenv('IMAGE_MODEL', 'gemini-pro')
        self.vertexai = vertexai
        self.project_id = project_id
        self.location = location
        logger.info("GenAIImageProvider initialized: model=%s", self.model)

    def generate(self, prompt: str, **kwargs):
        """Generate image using Google GenAI."""
        logger.info("Generating image with GenAI model: %s", self.model)
        raise NotImplementedError("GenAI image provider not implemented in mock - use OpenAI format instead")
