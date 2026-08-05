"""
Mock prompts_core module - provides prompt templates.
"""
import logging

logger = logging.getLogger(__name__)

# Default prompt templates
OUTLINE_PROMPT_TEMPLATE = """你是一个专业的PPT大纲生成助手。根据以下主题生成PPT大纲：

主题：{topic}
{requirements}

请生成一个包含以下部分的大纲：
1. 封面页
2. 目录页
3. 主要内容页（3-7页）
4. 总结页

每个页面请提供标题和简要内容描述。"""

DESCRIPTION_PROMPT_TEMPLATE = """你是一个专业的PPT页面描述生成助手。根据以下大纲生成每页的详细描述：

大纲：
{outline}

要求：
{requirements}

请为每个页面生成详细的描述，包括：
- 页面标题
- 主要内容要点
- 视觉元素建议
- 配色建议"""

IMAGE_PROMPT_TEMPLATE = """根据以下PPT页面描述生成适合的图片：

页面描述：{description}
风格：{style}

请生成一个简洁、专业的图片，适合用于PPT演示。"""


def get_outline_prompt(topic: str, requirements: str = '') -> str:
    return OUTLINE_PROMPT_TEMPLATE.format(topic=topic, requirements=requirements)


def get_description_prompt(outline: str, requirements: str = '') -> str:
    return DESCRIPTION_PROMPT_TEMPLATE.format(outline=outline, requirements=requirements)


def get_image_prompt(description: str, style: str = 'professional') -> str:
    return IMAGE_PROMPT_TEMPLATE.format(description=description, style=style)
