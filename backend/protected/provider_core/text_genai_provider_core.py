"""
Mock text_genai_provider_core module - Google GenAI text provider.
"""
import os
import logging

logger = logging.getLogger(__name__)


class GenAITextProvider:
    """Google GenAI text provider."""

    def __init__(self, api_key: str = None, api_base: str = None, model: str = None,
                 vertexai: bool = False, project_id: str = None, location: str = None):
        self.api_key = api_key or os.getenv('GOOGLE_API_KEY', '')
        self.api_base = api_base or os.getenv('GOOGLE_API_BASE', '')
        self.model = model or os.getenv('TEXT_MODEL', 'gemini-pro')
        self.vertexai = vertexai
        self.project_id = project_id
        self.location = location
        logger.info("GenAITextProvider initialized: model=%s", self.model)

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using Google GenAI."""
        logger.info("Generating text with GenAI model: %s", self.model)
        # Placeholder - actual implementation would use google.genai SDK
        raise NotImplementedError("GenAI provider not implemented in mock - use OpenAI format instead")
