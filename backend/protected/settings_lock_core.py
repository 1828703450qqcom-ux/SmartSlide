"""
Mock settings_lock_core module - allows custom API endpoints.
"""
import os
import logging

logger = logging.getLogger(__name__)

# Get API base URL from environment, default to DeepSeek
_DEFAULT_API_BASE_URL = os.getenv('OPENAI_API_BASE', 'https://api.deepseek.com/v1')


def get_locked_api_base_url() -> str:
    """Return API base URL (no longer locked)."""
    return _DEFAULT_API_BASE_URL


def force_locked_api_base_url(url: str) -> str:
    """No-op - just return the URL."""
    return url


def is_gateway_enabled() -> bool:
    """Check if gateway is enabled."""
    return os.getenv('SLIDEAI_GATEWAY_ENABLED', 'false').lower() == 'true'


def get_gateway_base_url() -> str:
    """Get gateway base URL."""
    return os.getenv('SLIDEAI_GATEWAY_BASE_URL', '')


def get_locked_api_base_fields() -> dict:
    """Get fields that should use the locked API base URL."""
    return {
        'api_base_url': _DEFAULT_API_BASE_URL,
        'text_api_base_url': _DEFAULT_API_BASE_URL,
        'image_api_base_url': _DEFAULT_API_BASE_URL,
        'image_caption_api_base_url': _DEFAULT_API_BASE_URL,
    }
