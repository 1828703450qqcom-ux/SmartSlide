#!/usr/bin/env python3
"""
PPT Master - Project Utilities Module

Provides common functions for project information parsing and validation,
reusable by other tools.
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Canvas format definitions (unified source)
try:
    from config import CANVAS_FORMATS
except ImportError:
    # Fallback: maintain minimal usable configuration to avoid runtime crashes
    CANVAS_FORMATS = {
        'ppt169': {
            'name': 'PPT 16:9',
            'dimensions': '1280×720',
            'viewbox': '0 0 1280 720',
            'aspect_ratio': '16:9'
        },
        'ppt43': {
            'name': 'PPT 4:3',
            'dimensions': '1024×768',
            'viewbox': '0 0 1024 768',
            'aspect_ratio': '4:3'
        },
    }

CANVAS_FORMAT_ALIASES = {
    'xhs': 'xiaohongshu',
    'wechat_moment': 'moments',
    'wechat-moment': 'moments',
}


def normalize_canvas_format(format_key: str) -> str:
    """Normalize canvas format key name (supports common aliases)."""
    if not format_key:
        return ''
    key = format_key.strip().lower()
    return CANVAS_FORMAT_ALIASES.get(key, key)


def parse_project_name(dir_name: str) -> Dict[str, str]:
    """
    Parse project information from the project directory name.

    Args:
        dir_name: Project directory name

    Returns:
        Dictionary containing name, format, date
    """
    result = {
        'name': dir_name,
        'format': 'unknown',
        'format_name': 'Unknown format',
        'date': 'unknown',
        'date_formatted': 'Unknown date'
    }

    dir_name_lower = dir_name.lower()

    # Extract date (format: _YYYYMMDD)
    date_match = re.search(r'_(\d{8})$', dir_name)
    if date_match:
        date_str = date_match.group(1)
        result['date'] = date_str
        try:
            date_obj = datetime.strptime(date_str, '%Y%m%d')
            result['date_formatted'] = date_obj.strftime('%Y-%m-%d')
        except ValueError:
            pass

    # Prefer parsing standard format: name_format_YYYYMMDD
    full_match = re.match(r'^(?P<name>.+)_(?P<format>[a-z0-9_-]+)_(?P<date>\d{8})$', dir_name_lower)
    if full_match:
        raw_format = full_match.group('format')
        normalized_format = normalize_canvas_format(raw_format)
        if normalized_format in CANVAS_FORMATS:
            result['format'] = normalized_format
            result['format_name'] = CANVAS_FORMATS[normalized_format]['name']
            result['name'] = dir_name[:len(full_match.group('name'))]
            return result

    # Fallback: only match trailing `_format` to avoid deleting parts of the project name
    sorted_formats = sorted(CANVAS_FORMATS.keys(), key=len, reverse=True)
    for fmt_key in sorted_formats:
        if re.search(rf'_{re.escape(fmt_key)}(?:_\d{{8}})?$', dir_name_lower):
            result['format'] = fmt_key
            result['format_name'] = CANVAS_FORMATS[fmt_key]['name']
            break

    # Extract project name (only remove trailing date and format suffix)
    name = re.sub(r'_\d{8}$', '', dir_name)
    if result['format'] != 'unknown':
        name = re.sub(rf'_{re.escape(result["format"])}$', '', name, flags=re.IGNORECASE)
    result['name'] = name

    return result


def get_project_info(project_path: str) -> Dict:
    """
    Get detailed project information.

    Args:
        project_path: Project directory path

    Returns:
        Project information dictionary
    """
    project_path = Path(project_path)

    # Parse directory name
    parsed = parse_project_name(project_path.name)

    info = {
        'path': str(project_path),
        'dir_name': project_path.name,
        'name': parsed['name'],
        'format': parsed['format'],
        'format_name': parsed['format_name'],
        'date': parsed['date'],
        'date_formatted': parsed['date_formatted'],
        'exists': project_path.exists(),
        'svg_count': 0,
        'has_spec': False,
        'has_readme': False,
        'svg_files': []
    }

    if not project_path.exists():
        return info

    # Check README.md
    info['has_readme'] = (project_path / 'README.md').exists()

    # Check design specification files
    spec_files = ['design_spec.md', 'design_specification.md']
    for spec_file in spec_files:
        if (project_path / spec_file).exists():
            info['has_spec'] = True
            break

    # Count SVG files
    svg_output = project_path / 'svg_output'
    if svg_output.exists():
        svg_files = sorted(svg_output.glob('*.svg'))
        info['svg_count'] = len(svg_files)
        info['svg_files'] = [f.name for f in svg_files]

    # Get canvas format details
    if info['format'] in CANVAS_FORMATS:
        info['canvas_info'] = CANVAS_FORMATS[info['format']]

    return info


def find_all_projects(base_dir: str) -> List[Path]:
    """
    Find all projects under the specified directory.

    Args:
        base_dir: Base directory path

    Returns:
        List of project directories
    """
    base_path = Path(base_dir)
    if not base_path.exists():
        return []

    projects = []
    for item in base_path.iterdir():
        if item.is_dir() and not item.name.startswith('.'):
            # Check if it's a valid project directory (contains svg_output or design spec)
            has_svg_output = (item / 'svg_output').exists()
            has_spec = any((item / f).exists() for f in ['design_spec.md', 'design_specification.md'])

            if has_svg_output or has_spec:
                projects.append(item)

    return sorted(projects)


if __name__ == '__main__':
    # Test code
    import sys

    if len(sys.argv) > 1:
        project_path = sys.argv[1]
        info = get_project_info(project_path)

        print(f"\nProject Info: {info['dir_name']}")
        print("=" * 60)
        print(f"Project Name: {info['name']}")
        print(f"Canvas Format: {info['format_name']} ({info['format']})")
        print(f"Created: {info['date_formatted']}")
        print(f"SVG Files: {info['svg_count']}")
        print(f"README: {'Yes' if info['has_readme'] else 'No'}")
        print(f"Design Spec: {'Yes' if info['has_spec'] else 'No'}")
    else:
        print("Usage: python3 project_utils.py <project_path>")
