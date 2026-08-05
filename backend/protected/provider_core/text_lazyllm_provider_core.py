"""
Mock text_lazyllm_provider_core module - LazyLLM text provider for ALL Chinese AI vendors.
"""
import os
import logging
import json
from typing import Optional, Generator

logger = logging.getLogger(__name__)

# Complete vendor configuration: base URL + default model
VENDOR_CONFIG = {
    'deepseek': {
        'base_url': 'https://api.deepseek.com/v1',
        'default_model': 'deepseek-chat',
    },
    'qwen': {
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'default_model': 'qwen-turbo',
    },
    'doubao': {
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'default_model': 'doubao-pro-256k',
    },
    'glm': {
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'default_model': 'glm-4-flash',
    },
    'siliconflow': {
        'base_url': 'https://api.siliconflow.cn/v1',
        'default_model': 'deepseek-ai/DeepSeek-V3',
    },
    'sensenova': {
        'base_url': 'https://api.sensenova.cn/v1',
        'default_model': 'nova-ptc-xl-v1',
    },
    'minimax': {
        'base_url': 'https://api.minimax.chat/v1',
        'default_model': 'MiniMax-Text-01',
    },
    'kimi': {
        'base_url': 'https://api.moonshot.cn/v1',
        'default_model': 'moonshot-v1-8k',
    },
}


class LazyLLMTextProvider:
    """LazyLLM text provider - supports all Chinese AI vendors via OpenAI-compatible API."""

    def __init__(self, source: str = 'deepseek', model: str = None):
        self.source = source
        vendor_cfg = VENDOR_CONFIG.get(source, VENDOR_CONFIG['deepseek'])
        self.model = model or vendor_cfg['default_model']
        self.base_url = vendor_cfg['base_url']
        logger.info("LazyLLMTextProvider: source=%s, model=%s, base_url=%s",
                     source, self.model, self.base_url)

    def _get_client(self):
        api_key_env = f"{self.source.upper()}_API_KEY"
        api_key = os.getenv(api_key_env, '')
        if not api_key:
            raise ValueError(
                f"未找到 {self.source} 的 API Key。\n"
                f"请在 .env 文件中设置: {api_key_env}=你的密钥\n"
                f"注册地址: {_get_register_url(self.source)}"
            )
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=self.base_url)

    def generate_text(self, prompt: str, thinking_budget: int = 0) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.choices[0].message.content or ''
        import re
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


def _get_register_url(source: str) -> str:
    urls = {
        'deepseek': 'https://platform.deepseek.com/',
        'qwen': 'https://dashscope.console.aliyun.com/',
        'doubao': 'https://console.volcengine.com/ark',
        'glm': 'https://open.bigmodel.cn/',
        'siliconflow': 'https://cloud.siliconflow.cn/',
        'sensenova': 'https://platform.sensenova.cn/',
        'minimax': 'https://platform.minimaxi.com/',
        'kimi': 'https://platform.moonshot.cn/',
    }
    return urls.get(source, '')
