"""
Mock ai_service_core module - provides AI service functionality.
"""
import os
import logging
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class ProjectContext:
    """Context for a project with reference files."""

    def __init__(self, project, reference_files_content: str = None):
        self.project = project
        self.reference_files_content = reference_files_content or ''

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        if hasattr(self.project, 'to_dict'):
            return self.project.to_dict()
        return self.project if isinstance(self.project, dict) else {'project': str(self.project)}


class AIService:
    """AI Service for generating outlines, descriptions, and images."""

    def __init__(self):
        self.initialized = False

    def generate_outline(self, idea: str, requirements: str = None, style: str = None) -> str:
        """Generate outline from idea."""
        logger.info("Generating outline for idea: %s", idea[:50])
        return ""

    def generate_descriptions(self, outline: str, requirements: str = None, style: str = None) -> List[Dict]:
        """Generate page descriptions from outline."""
        logger.info("Generating descriptions from outline")
        return []

    def generate_image_prompt(self, description: str, style: str = None) -> str:
        """Generate image prompt from description."""
        logger.info("Generating image prompt")
        return ""


# Global instance
ai_service = AIService()
