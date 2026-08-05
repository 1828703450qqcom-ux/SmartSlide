"""
Mock ai_service_manager_core module.
"""
import logging

logger = logging.getLogger(__name__)


class AIServiceManager:
    """Singleton manager for AI service."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def get_service(self):
        from protected.ai_service_core import ai_service
        return ai_service


manager = AIServiceManager()


def get_ai_service():
    """Get the AI service instance."""
    return manager.get_service()
