"""
Mock pptmaster_references module.
"""
import logging

logger = logging.getLogger(__name__)


def get_reference(name: str) -> dict:
    """Get reference data by name."""
    logger.info("Getting reference: %s", name)
    return {
        'name': name,
        'data': None,
        'message': 'Reference not available in mock'
    }
