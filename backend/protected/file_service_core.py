"""
Mock file_service_core module - handles file operations.
"""
import os
import shutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FileService:
    """File service for managing uploads and files."""

    def __init__(self, upload_folder: str = None):
        self.upload_folder = upload_folder or os.getenv('SLIDEAI_UPLOAD_FOLDER', 'uploads')

    def save_file(self, file, project_id: str, subfolder: str = 'uploads') -> str:
        """Save uploaded file."""
        try:
            target_dir = os.path.join(self.upload_folder, project_id, subfolder)
            os.makedirs(target_dir, exist_ok=True)

            filename = file.filename
            filepath = os.path.join(target_dir, filename)
            file.save(filepath)

            logger.info("File saved: %s", filepath)
            return filepath
        except Exception as e:
            logger.error("Failed to save file: %s", e)
            raise

    def delete_file(self, filepath: str) -> bool:
        """Delete a file."""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info("File deleted: %s", filepath)
                return True
            return False
        except Exception as e:
            logger.error("Failed to delete file: %s", e)
            return False

    def get_file_path(self, project_id: str, subfolder: str, filename: str) -> Optional[str]:
        """Get full file path."""
        filepath = os.path.join(self.upload_folder, project_id, subfolder, filename)
        if os.path.exists(filepath):
            return filepath
        return None


def save_file(file, upload_folder: str, project_id: str, subfolder: str = 'uploads') -> str:
    """Save uploaded file (standalone function)."""
    service = FileService(upload_folder)
    return service.save_file(file, project_id, subfolder)


def delete_file(filepath: str) -> bool:
    """Delete a file (standalone function)."""
    service = FileService()
    return service.delete_file(filepath)


def get_file_path(upload_folder: str, project_id: str, subfolder: str, filename: str) -> Optional[str]:
    """Get full file path (standalone function)."""
    service = FileService(upload_folder)
    return service.get_file_path(project_id, subfolder, filename)
