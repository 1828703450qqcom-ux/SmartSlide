"""
Mock gateway_provider_core module - provides gateway providers that use custom API endpoints.
When gateway is disabled, these act as pass-through to OpenAI-compatible endpoints.
"""
import os
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class GatewayTextProvider:
    """Gateway text provider - routes to OpenAI-compatible API."""

    def __init__(self, api_key: str = '', model: str = 'claude-opus-4-6', kind: str = 'text'):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', '')
        self.model = model or os.getenv('TEXT_MODEL', 'deepseek-chat')
        self.kind = kind
        self.api_base = os.getenv('OPENAI_API_BASE', 'https://api.deepseek.com/v1')
        logger.info("GatewayTextProvider initialized: model=%s, api_base=%s", self.model, self.api_base)

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate text using OpenAI-compatible API."""
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.api_base)
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            **kwargs
        )
        return response.choices[0].message.content

    def generate_stream(self, prompt: str, **kwargs):
        """Generate text stream using OpenAI-compatible API."""
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.api_base)
        stream = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
            **kwargs
        )
        for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class GatewayImageProvider:
    """Gateway image provider - routes to OpenAI-compatible API."""

    def __init__(self, api_key: str = '', model: str = 'gpt-image-2'):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', '')
        self.model = model or os.getenv('IMAGE_MODEL', 'deepseek-chat')
        self.api_base = os.getenv('OPENAI_API_BASE', 'https://api.deepseek.com/v1')
        logger.info("GatewayImageProvider initialized: model=%s, api_base=%s", self.model, self.api_base)

    def generate(self, prompt: str, **kwargs) -> Any:
        """Generate image using OpenAI-compatible API."""
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key, base_url=self.api_base)
        response = client.images.generate(
            model=self.model,
            prompt=prompt,
            **kwargs
        )
        return response.data[0].url if response.data else None
