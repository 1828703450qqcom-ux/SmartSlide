"""
Mock image_errors_core module - handles image error detection.
"""
import logging

logger = logging.getLogger(__name__)


class ImageError:
    """Image error information."""
    def __init__(self, error_type: str, message: str, details: dict = None):
        self.error_type = error_type
        self.message = message
        self.details = details or {}


def detect_image_errors(image_path: str) -> list:
    """Detect errors in generated image."""
    logger.info("Checking image for errors: %s", image_path)
    # Placeholder - return no errors
    return []
