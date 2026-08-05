"""
Mock image_openai_provider_core module - OpenAI-compatible image provider.
Works with any OpenAI-compatible endpoint.
"""
import os
import io
import base64
import logging
from typing import Optional, List
from PIL import Image

logger = logging.getLogger(__name__)


class OpenAIImageProvider:
    """OpenAI-compatible image provider."""

    def __init__(self, api_key: str = None, api_base: str = None, model: str = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', '')
        self.api_base = api_base or os.getenv('OPENAI_API_BASE', 'https://api.deepseek.com/v1')
        self.model = model or os.getenv('IMAGE_MODEL', 'gpt-image-1')
        logger.info("OpenAIImageProvider: model=%s, api_base=%s", self.model, self.api_base)

    def _get_client(self):
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required.")
        from openai import OpenAI
        return OpenAI(api_key=self.api_key, base_url=self.api_base)

    def generate_image(
        self,
        prompt: str,
        ref_images: Optional[List[Image.Image]] = None,
        aspect_ratio: str = "16:9",
        resolution: str = "2K",
        enable_thinking: bool = False,
        thinking_budget: int = 0
    ) -> Optional[Image.Image]:
        """Generate image using OpenAI-compatible image API."""
        client = self._get_client()

        try:
            response = client.images.generate(
                model=self.model,
                prompt=prompt,
                n=1,
                size="1024x1024",
            )

            if response.data and response.data[0].url:
                import requests
                img_response = requests.get(response.data[0].url, timeout=120)
                return Image.open(io.BytesIO(img_response.content))
            elif response.data and response.data[0].b64_json:
                img_data = base64.b64decode(response.data[0].b64_json)
                return Image.open(io.BytesIO(img_data))
        except Exception as e:
            logger.error("Image generation failed: %s", e)
            raise

        return None

    def generate(self, prompt: str, **kwargs) -> Optional[Image.Image]:
        return self.generate_image(prompt, **kwargs)
