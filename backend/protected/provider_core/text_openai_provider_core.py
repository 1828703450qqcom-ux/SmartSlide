"""
Mock text_openai_provider_core module - OpenAI-compatible text provider.
Works with any OpenAI-compatible API (DeepSeek, Qwen, etc.)
"""
import os
import re
import logging
from typing import Optional, Generator

logger = logging.getLogger(__name__)


class OpenAITextProvider:
    """OpenAI-compatible text provider - works with any OpenAI-compatible endpoint."""

    def __init__(self, api_key: str = None, api_base: str = None, model: str = None):
        self.api_key = api_key or os.getenv('OPENAI_API_KEY', '')
        self.api_base = api_base or os.getenv('OPENAI_API_BASE', 'https://api.deepseek.com/v1')
        self.model = model or os.getenv('TEXT_MODEL', 'deepseek-chat')
        logger.info("OpenAITextProvider: model=%s, api_base=%s", self.model, self.api_base)

    def _get_client(self):
        if not self.api_key:
            raise ValueError(
                "OPENAI_API_KEY is required.\n"
                "Please set it in .env file."
            )
        from openai import OpenAI
        return OpenAI(api_key=self.api_key, base_url=self.api_base)

    def generate_text(self, prompt: str, thinking_budget: int = 0) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content or ''
        return re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()

    def generate(self, prompt: str, **kwargs) -> str:
        return self.generate_text(prompt)

    def generate_text_stream(self, prompt: str, thinking_budget: int = 0) -> Generator[str, None, None]:
        client = self._get_client()
        stream = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            stream=True,
        )
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
