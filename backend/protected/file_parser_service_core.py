"""
Mock file_parser_service_core module - handles PDF/document parsing.
"""
import os
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class FileParserService:
    """File parser service for PDF/document parsing."""

    def __init__(self):
        pass

    def parse_pdf(self, file_path: str, output_dir: str = None) -> Dict[str, Any]:
        """Parse PDF file and extract content."""
        logger.info("Parsing PDF: %s", file_path)

        if not os.path.exists(file_path):
            return {'success': False, 'error': 'File not found'}

        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(file_path)
            content = []

            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                content.append({
                    'page': i + 1,
                    'text': text or ''
                })

            return {
                'success': True,
                'file_path': file_path,
                'pages': len(reader.pages),
                'content': content
            }
        except Exception as e:
            logger.error("PDF parsing failed: %s", e)
            return {
                'success': False,
                'error': str(e)
            }

    def parse_file(self, file_path: str) -> Dict[str, Any]:
        """Parse any supported file format."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == '.pdf':
            return self.parse_pdf(file_path)
        else:
            return {'success': False, 'error': f'Unsupported file format: {ext}'}


def parse_pdf(file_path: str, output_dir: str = None) -> Dict[str, Any]:
    """Parse PDF file (standalone function)."""
    service = FileParserService()
    return service.parse_pdf(file_path, output_dir)


def parse_file(file_path: str) -> Dict[str, Any]:
    """Parse any supported file format (standalone function)."""
    service = FileParserService()
    return service.parse_file(file_path)
