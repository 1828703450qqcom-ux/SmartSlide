"""
Mock license_guard module - bypasses activation code checks.
"""
import os
import logging

logger = logging.getLogger(__name__)


def is_activation_enabled() -> bool:
    """Check if activation code is enabled - always returns False (disabled)."""
    return False


def validate_activation_code(code: str) -> bool:
    """Validate activation code - always returns True."""
    return True


def get_license_info() -> dict:
    """Get license info."""
    return {
        'valid': True,
        'enabled': False,
        'message': 'License check disabled'
    }


def check_license(key: str = None):
    """Check license - always returns valid."""
    logger.info("License check: always valid (mock)")
    return type('LicenseInfo', (), {'valid': True, 'message': 'Valid'})()


def activate_license(key: str):
    """Activate license - always returns valid."""
    logger.info("License activation: always valid (mock)")
    return type('LicenseInfo', (), {'valid': True, 'message': 'Activated'})()
