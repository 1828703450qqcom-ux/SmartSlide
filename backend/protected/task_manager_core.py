"""
Mock task_manager_core module - handles async task management.
"""
import logging
import threading
import uuid
from typing import Callable, Any, Optional

logger = logging.getLogger(__name__)


class TaskManager:
    """Simple task manager for async operations."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.tasks = {}
        return cls._instance

    def create_task(self, task_id: str, func: Callable, *args, **kwargs) -> str:
        """Create and run an async task."""
        logger.info("Creating task: %s", task_id)

        def run_task():
            try:
                result = func(*args, **kwargs)
                self.tasks[task_id] = {'status': 'completed', 'result': result}
            except Exception as e:
                self.tasks[task_id] = {'status': 'failed', 'error': str(e)}
                logger.error("Task %s failed: %s", task_id, e)

        thread = threading.Thread(target=run_task)
        thread.daemon = True
        thread.start()

        self.tasks[task_id] = {'status': 'running'}
        return task_id

    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get task status."""
        return self.tasks.get(task_id)


# Global instance
task_manager = TaskManager()
TaskManagerClass = TaskManager


def generate_descriptions_task(project_id: str, pages: list, requirements: str = None, style: str = None):
    """Generate descriptions for pages."""
    logger.info("Generating descriptions task for project: %s", project_id)
    return {'status': 'completed', 'message': 'Descriptions generated (mock)'}


def generate_images_task(project_id: str, pages: list):
    """Generate images for pages."""
    logger.info("Generating images task for project: %s", project_id)
    return {'status': 'completed', 'message': 'Images generated (mock)'}


def generate_editable_pptx_task(project_id: str, project_data: dict):
    """Generate editable PPTX."""
    logger.info("Generating editable PPTX task for project: %s", project_id)
    return {'status': 'completed', 'message': 'PPTX generated (mock)'}


def export_editable_pptx_with_recursive_analysis_task(project_id: str, project_data: dict):
    """Export editable PPTX with recursive analysis."""
    logger.info("Exporting editable PPTX with analysis for project: %s", project_id)
    return {'status': 'completed', 'message': 'PPTX exported (mock)'}


def generate_single_page_image_task(project_id: str, page_id: str):
    """Generate image for a single page."""
    logger.info("Generating image for page: %s", page_id)
    return {'status': 'completed', 'message': 'Page image generated (mock)'}


def edit_page_image_task(project_id: str, page_id: str, prompt: str):
    """Edit page image."""
    logger.info("Editing image for page: %s", page_id)
    return {'status': 'completed', 'message': 'Page image edited (mock)'}


def generate_material_image_task(project_id: str, prompt: str):
    """Generate material image."""
    logger.info("Generating material image for project: %s", project_id)
    return {'status': 'completed', 'message': 'Material image generated (mock)'}


def save_image_with_version(page_id: str, image_path: str):
    """Save image with version control."""
    logger.info("Saving image version for page: %s", page_id)
    return {'status': 'completed', 'message': 'Image version saved (mock)'}


def process_ppt_renovation_task(project_id: str, file_path: str):
    """Process PPT renovation task."""
    logger.info("Processing PPT renovation for project: %s", project_id)
    return {'status': 'completed', 'message': 'PPT renovation processed (mock)'}


def create_task(task_id: str, func: Callable, *args, **kwargs) -> str:
    """Create and run an async task (module-level function)."""
    return task_manager.create_task(task_id, func, *args, **kwargs)


def get_task_status(task_id: str) -> Optional[dict]:
    """Get task status (module-level function)."""
    return task_manager.get_task_status(task_id)
