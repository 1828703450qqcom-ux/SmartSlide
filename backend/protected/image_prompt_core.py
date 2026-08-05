"""
Mock image_prompt_core module - handles image prompt generation.
"""
import logging

logger = logging.getLogger(__name__)


def generate_image_prompt(description: str, style: str = 'professional') -> str:
    """Generate image prompt from page description."""
    logger.info("Generating image prompt for description")

    prompt = f"""Create a professional presentation slide image based on:

Content: {description}
Style: {style}

Requirements:
- Clean, modern design
- Appropriate for business presentation
- High quality visual elements
- Professional color scheme"""

    return prompt
