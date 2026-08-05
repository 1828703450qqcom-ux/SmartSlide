"""
Mock image_lazyllm_provider_core module - LazyLLM image provider for ALL Chinese AI vendors.
"""
import os
import logging
from typing import Optional, List
from PIL import Image
import io
import base64

logger = logging.getLogger(__name__)

# Image-capable vendors configuration
IMAGE_VENDOR_CONFIG = {
    'doubao': {
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'default_model': 'doubao-seedream-3-0',
    },
    'qwen': {
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'default_model': 'wanx-v1',
    },
    'siliconflow': {
        'base_url': 'https://api.siliconflow.cn/v1',
        'default_model': 'black-forest-labs/FLUX.1-schnell',
    },
    'glm': {
        'base_url': 'https://open.bigmodel.cn/api/paas/v4',
        'default_model': 'cogview-3-plus',
    },
    'sensenova': {
        'base_url': 'https://api.sensenova.cn/v1',
        'default_model': 'sana-1.0',
    },
    'minimax': {
        'base_url': 'https://api.minimax.chat/v1',
        'default_model': 'image-01',
    },
    'kimi': {
        'base_url': 'https://api.moonshot.cn/v1',
        'default_model': 'moonshot-v1-8k-vision-preview',
    },
    'deepseek': {
        'base_url': 'https://api.deepseek.com/v1',
        'default_model': 'deepseek-chat',
    },
}


class LazyLLMImageProvider:
    """LazyLLM image provider - supports Chinese AI vendors via OpenAI-compatible API."""

    def __init__(self, source: str = 'doubao', model: str = None):
        self.source = source
        vendor_cfg = IMAGE_VENDOR_CONFIG.get(source, IMAGE_VENDOR_CONFIG['doubao'])
        self.model = model or vendor_cfg['default_model']
        self.base_url = vendor_cfg['base_url']
        logger.info("LazyLLMImageProvider: source=%s, model=%s, base_url=%s",
                     source, self.model, self.base_url)

    def _get_client(self):
        api_key_env = f"{self.source.upper()}_API_KEY"
        api_key = os.getenv(api_key_env, '')
        if not api_key:
            raise ValueError(
                f"未找到 {self.source} 的 API Key。\n"
                f"请在 .env 文件中设置: {api_key_env}=你的密钥"
            )
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=self.base_url)

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
            # Try using images.generate API
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
            logger.warning("Image generation failed with %s: %s", self.source, e)
            raise

        return None

    def generate(self, prompt: str, **kwargs) -> Optional[Image.Image]:
        return self.generate_image(prompt, **kwargs)
