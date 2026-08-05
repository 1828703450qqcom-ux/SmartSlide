"""Services package.

The public names are loaded lazily so protected extension modules can import
``services.*`` submodules without triggering a circular import through
``services.ai_service``.
"""

__all__ = ['AIService', 'ProjectContext', 'FileService', 'ExportService']


def __getattr__(name):
    if name in ('AIService', 'ProjectContext'):
        from .ai_service import AIService, ProjectContext
        return {'AIService': AIService, 'ProjectContext': ProjectContext}[name]
    if name == 'FileService':
        from .file_service import FileService
        return FileService
    if name == 'ExportService':
        from .export_service import ExportService
        return ExportService
    raise AttributeError(f"module 'services' has no attribute {name!r}")
