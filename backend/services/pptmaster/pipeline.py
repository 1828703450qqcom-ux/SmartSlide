"""
PptMaster Pipeline - orchestrates the full SVG→PPTX generation flow.

Flow:
  1. Strategist: AI generates design_spec + spec_lock from user content
  2. Executor: AI generates SVG per page following spec_lock
  3. Finalize: Post-process SVGs (embed icons, images, flatten text, fix rects)
  4. Convert: SVG → native DrawingML PPTX
"""

import os
import re
import sys
import json
import uuid
import shutil
import logging
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List, Tuple

from protected.pptmaster_pipeline_core import (
    build_page_svg_prompts,
    build_strategist_prompts,
    create_minimal_spec,
    get_executor_reference_name,
)

logger = logging.getLogger(__name__)

_WINDOWS_RESERVED_FILENAMES = {
    'CON', 'PRN', 'AUX', 'NUL',
    'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
    'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9',
}


def _safe_filename_stem(value: Optional[str], fallback: str = 'presentation', max_length: int = 80) -> str:
    """Return a Windows-safe filename stem while preserving readable Chinese text."""
    raw = str(value or '').strip()
    raw = re.sub(r'[\r\n\t]+', ' ', raw)
    raw = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', raw)
    raw = re.sub(r'\s+', ' ', raw).strip(' ._')
    if not raw:
        raw = fallback
    if raw.lower().endswith('.pptx'):
        raw = raw[:-5].strip(' ._') or fallback

    raw = raw[:max_length].strip(' ._') or fallback
    if raw.split('.', 1)[0].upper() in _WINDOWS_RESERVED_FILENAMES:
        raw = f'{fallback}_{raw}'
    return raw


def _unique_pptx_path(exports_dir: Path, title: Optional[str], project_id: str) -> Tuple[Path, str]:
    """Build a safe, non-conflicting PPTX output path for generated decks."""
    fallback = f'presentation_{project_id[:8]}' if project_id else 'presentation'
    stem = _safe_filename_stem(title, fallback=fallback)
    filename = f'{stem}.pptx'
    output_path = exports_dir / filename
    if not output_path.exists():
        return output_path, filename

    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    filename = f'{stem}_{timestamp}.pptx'
    return exports_dir / filename, filename


# Add pptmaster package root to sys.path so sub-packages resolve correctly
_PPTMASTER_DIR = Path(__file__).parent
if str(_PPTMASTER_DIR) not in sys.path:
    sys.path.insert(0, str(_PPTMASTER_DIR))


def _get_references_dir() -> Path:
    """Return the path to the references directory."""
    return _PPTMASTER_DIR / 'references'


def _read_reference(name: str) -> str:
    """Read a reference prompt file."""
    try:
        from protected.pptmaster_references import get_reference
        protected_content = get_reference(name)
        if protected_content:
            return protected_content
    except Exception:
        pass

    ref_path = _get_references_dir() / name
    if ref_path.exists():
        return ref_path.read_text(encoding='utf-8')
    logger.warning(f"Reference file not found: {ref_path}")
    return ''


def _get_text_provider():
    """Get the configured text AI provider."""
    from services.ai_providers import get_text_provider
    from config import get_config
    try:
        from flask import current_app, has_app_context
        if has_app_context():
            model = current_app.config.get('TEXT_MODEL', get_config().TEXT_MODEL)
            return get_text_provider(model=model)
    except (ImportError, RuntimeError):
        pass
    return get_text_provider(model=get_config().TEXT_MODEL)


def _call_ai(prompt: str, system_prompt: str = '') -> str:
    """Call the text AI provider and return the response text.

    The provider exposes ``generate_text(prompt)`` which only accepts a single
    string.  To preserve system-level instructions we try two strategies:

    1. If the provider wraps an OpenAI-compatible client (``provider.client``),
       use ``chat.completions.create`` directly so we can pass system + user
       messages separately — this gives the best results.
    2. Otherwise, concatenate the system prompt and user prompt into one string
       and call ``provider.generate_text()``.
    """
    provider = _get_text_provider()

    # Strategy 1: use the underlying OpenAI client for proper system messages
    client = getattr(provider, 'client', None)
    model = getattr(provider, 'model', None)
    if client and model:
        try:
            messages = []
            if system_prompt:
                messages.append({'role': 'system', 'content': system_prompt})
            messages.append({'role': 'user', 'content': prompt})
            response = client.chat.completions.create(model=model, messages=messages)
            text = response.choices[0].message.content or ''
            # Strip <think> tags that some models emit
            from services.ai_providers.text.base import strip_think_tags
            return strip_think_tags(text)
        except Exception as e:
            logger.warning(f"Direct client call failed, falling back to generate_text: {e}")

    # Strategy 2: concatenate into a single prompt string
    combined = prompt
    if system_prompt:
        combined = f"{system_prompt}\n\n---\n\n{prompt}"

    return provider.generate_text(combined, thinking_budget=0)


# ============================================================
# Phase 1: Strategist
# ============================================================

def run_strategist(project_id: str, content: str, canvas_format: str = 'ppt169',
                   style_type: str = 'general', language: str = 'zh') -> Dict:
    """
    Run the strategist phase: generate design_spec and spec_lock from content.

    Args:
        project_id: Project ID
        content: User's input content/topic
        canvas_format: Canvas format key (ppt169, ppt43, etc.)
        style_type: Style type (general, consulting, consultant-top)
        language: Output language

    Returns:
        dict with 'design_spec', 'spec_lock', 'page_count', 'pages' (outline)
    """
    from .config import CANVAS_FORMATS

    strategist_ref = _read_reference('strategist.md')
    canvas_ref = _read_reference('canvas-formats.md')
    shared_standards = _read_reference('shared-standards.md')

    canvas_info = CANVAS_FORMATS.get(canvas_format, CANVAS_FORMATS['ppt169'])
    user_prompt, system_prompt = build_strategist_prompts(
        content=content,
        canvas_format=canvas_format,
        canvas_info=canvas_info,
        style_type=style_type,
        language=language,
        strategist_ref=strategist_ref,
        canvas_ref=canvas_ref,
        shared_standards=shared_standards,
    )

    raw = _call_ai(user_prompt, system_prompt)

    # Parse JSON from response
    result = _parse_json_response(raw)

    if not result or 'design_spec' not in result:
        # Fallback: create a minimal spec
        logger.warning("Strategist returned invalid JSON, creating minimal spec")
        result = create_minimal_spec(content, canvas_format, canvas_info, style_type)

    return result


def _parse_json_response(text: str) -> Optional[Dict]:
    """Extract and parse JSON from AI response text."""
    import re

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    match = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try finding first { to last }
    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass

    return None


# ============================================================
# Phase 2: Executor (per-page SVG generation)
# ============================================================

def generate_page_svg(page_index: int, page_info: Dict, spec_lock: Dict,
                      design_spec: Dict, style_type: str = 'general',
                      language: str = 'zh') -> str:
    """
    Generate SVG for a single page using AI.

    Args:
        page_index: 1-based page index
        page_info: Page info dict with 'title', 'brief', 'type', 'rhythm'
        spec_lock: The spec_lock configuration
        design_spec: The full design spec
        style_type: Style type for executor selection
        language: Output language

    Returns:
        SVG content string
    """
    executor_base = _read_reference('executor-base.md')
    shared_standards = _read_reference('shared-standards.md')

    style_ref_name = get_executor_reference_name(style_type)
    style_ref = _read_reference(style_ref_name)
    prompt_bundle = build_page_svg_prompts(
        page_index=page_index,
        page_info=page_info,
        spec_lock=spec_lock,
        design_spec=design_spec,
        language=language,
        executor_base=executor_base,
        style_ref=style_ref,
        shared_standards=shared_standards,
    )

    raw = _call_ai(prompt_bundle['user_prompt'], prompt_bundle['system_prompt'])

    # Extract SVG from response
    svg = _extract_svg(raw)
    if not svg:
        logger.error(f"Failed to extract SVG for page {page_index}")
        svg = _create_fallback_svg(
            page_info,
            prompt_bundle['canvas'],
            prompt_bundle['colors'],
            prompt_bundle['typography'],
        )

    return svg


def _extract_svg(text: str) -> Optional[str]:
    """Extract SVG content from AI response."""
    import re

    # Try to find <svg ... </svg>
    match = re.search(r'(<svg[\s\S]*?</svg>)', text, re.DOTALL)
    if match:
        return match.group(1)

    # Try extracting from code block
    match = re.search(r'```(?:xml|svg|html)?\s*\n(.*?)\n```', text, re.DOTALL)
    if match:
        inner = match.group(1).strip()
        if inner.startswith('<svg'):
            return inner

    # If the response itself starts with <svg
    text = text.strip()
    if text.startswith('<svg') and text.endswith('</svg>'):
        return text

    return None


def _create_fallback_svg(page_info: Dict, canvas: Dict, colors: Dict, typography: Dict) -> str:
    """Create a minimal fallback SVG."""
    w = canvas.get('width', 1280)
    h = canvas.get('height', 720)
    vb = canvas.get('viewBox', f'0 0 {w} {h}')
    bg = colors.get('background', '#FFFFFF')
    primary = colors.get('primary', '#2196F3')
    text_dark = colors.get('text_dark', '#2C3E50')
    font = typography.get('font_family', "system-ui, sans-serif")
    title = page_info.get('title', 'Untitled')

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="{vb}" width="{w}" height="{h}">
  <rect width="{w}" height="{h}" fill="{bg}"/>
  <rect x="0" y="0" width="{w}" height="4" fill="{primary}"/>
  <text x="{w//2}" y="{h//2}" text-anchor="middle" dominant-baseline="middle" font-family="{font}" font-size="36" fill="{text_dark}">{title}</text>
</svg>'''


# ============================================================
# Phase 3: Finalize SVGs
# ============================================================

def finalize_svgs(project_dir: Path) -> bool:
    """
    Run SVG post-processing on all SVGs in project_dir/svg_output/.
    Outputs to project_dir/svg_final/.

    Args:
        project_dir: Project directory containing svg_output/

    Returns:
        True if successful
    """
    try:
        from .finalize_svg import finalize_project

        options = {
            'embed_icons': True,
            'crop_images': True,
            'fix_aspect': True,
            'embed_images': True,
            'flatten_text': True,
            'fix_rounded': True,
        }

        return finalize_project(project_dir, options, quiet=True)
    except Exception as e:
        logger.error(f"SVG finalization failed: {e}", exc_info=True)
        return False


# ============================================================
# Phase 4: SVG → PPTX conversion
# ============================================================

def convert_to_pptx(project_dir: Path, canvas_format: str = 'ppt169',
                    output_path: Optional[Path] = None) -> Optional[Path]:
    """
    Convert finalized SVGs to a native DrawingML PPTX file.

    Args:
        project_dir: Project directory containing svg_final/
        canvas_format: Canvas format key
        output_path: Optional output path. If None, saves to project_dir/output.pptx

    Returns:
        Path to the generated PPTX file, or None on failure
    """
    try:
        from .svg_to_pptx import main as svg_to_pptx_main
        from .svg_to_pptx.pptx_builder import create_pptx_with_native_svg
        from .svg_to_pptx.pptx_discovery import find_svg_files, find_notes_files

        svg_dir = project_dir / 'svg_final'
        if not svg_dir.exists():
            svg_dir = project_dir / 'svg_output'

        if not svg_dir.exists():
            logger.error(f"No SVG directory found in {project_dir}")
            return None

        # find_svg_files returns (list[Path], dir_name) tuple
        svg_files_result = find_svg_files(svg_dir)
        svg_files = svg_files_result[0] if isinstance(svg_files_result, tuple) else svg_files_result
        if not svg_files:
            logger.error(f"No SVG files found in {svg_dir}")
            return None

        if output_path is None:
            output_path = project_dir / 'output.pptx'

        # Find notes
        notes_dir = project_dir / 'notes'
        notes = find_notes_files(notes_dir) if notes_dir.exists() else {}

        success = create_pptx_with_native_svg(
            svg_files=svg_files,
            output_path=output_path,
            canvas_format=canvas_format,
            verbose=False,
            transition='fade',
            transition_duration=0.5,
            use_native_shapes=True,
            notes=notes,
            enable_notes=True,
            animation='mixed',
            animation_duration=0.4,
        )

        if success:
            logger.info(f"PPTX created successfully: {output_path}")
            return output_path
        else:
            logger.error("PPTX creation reported failure")
            return None

    except Exception as e:
        logger.error(f"PPTX conversion failed: {e}", exc_info=True)
        return None


# ============================================================
# Full Pipeline (background task entry point)
# ============================================================

def run_full_pipeline(task_id: str, project_id: str, app=None):
    """
    Background task: run the complete pptmaster pipeline.

    1. Load project from DB
    2. Run strategist if needed
    3. Generate SVG per page
    4. Finalize SVGs
    5. Convert to PPTX
    6. Store result
    """
    if app is None:
        raise ValueError("Flask app instance must be provided")

    with app.app_context():
        from models import db, Task
        from models.pptmaster_project import PptMasterProject, PptMasterPage

        try:
            project = PptMasterProject.query.get(project_id)
            if not project:
                raise ValueError(f"PptMaster project {project_id} not found")

            task = Task.query.get(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            # Update status
            task.status = 'PROCESSING'
            project.status = 'PROCESSING'
            db.session.commit()

            design_spec = project.get_design_spec()
            spec_lock = project.get_spec_lock()
            pages_info = design_spec.get('pages', [])
            total_pages = len(pages_info)

            if total_pages == 0:
                raise ValueError("No pages defined in design spec")

            # Create temp project directory
            upload_folder = _get_upload_folder()
            project_dir = Path(upload_folder) / project_id / 'pptmaster'
            svg_output_dir = project_dir / 'svg_output'
            svg_output_dir.mkdir(parents=True, exist_ok=True)

            # Phase: Generate SVG per page
            task.set_progress({
                'total': total_pages,
                'completed': 0,
                'failed': 0,
                'phase': 'generating_svg'
            })
            db.session.commit()

            completed = 0
            failed = 0

            for i, page_info in enumerate(pages_info):
                page_index = i + 1
                page_name = f"{page_index:02d}_{page_info.get('type', 'content')}"

                try:
                    logger.info(f"Generating SVG for page {page_index}/{total_pages}: {page_info.get('title', '')}")

                    svg_content = generate_page_svg(
                        page_index=page_index,
                        page_info=page_info,
                        spec_lock=spec_lock,
                        design_spec=design_spec,
                        style_type=project.style_type,
                        language=project.language or 'zh',
                    )

                    # Save SVG to file
                    svg_path = svg_output_dir / f"{page_name}.svg"
                    svg_path.write_text(svg_content, encoding='utf-8')

                    # Create or update page record
                    page = PptMasterPage.query.filter_by(
                        project_id=project_id, order_index=page_index
                    ).first()

                    if not page:
                        page = PptMasterPage(
                            project_id=project_id,
                            order_index=page_index,
                            page_name=page_name,
                            page_title=page_info.get('title', ''),
                            page_brief=page_info.get('brief', ''),
                        )
                        db.session.add(page)

                    page.svg_content = svg_content
                    page.status = 'SVG_GENERATED'
                    completed += 1

                except Exception as e:
                    logger.error(f"Failed to generate page {page_index}: {e}", exc_info=True)
                    failed += 1

                task.set_progress({
                    'total': total_pages,
                    'completed': completed,
                    'failed': failed,
                    'phase': 'generating_svg',
                    'current_page': page_index,
                })
                db.session.commit()

            if completed == 0:
                raise ValueError("All pages failed to generate")

            # Phase: Finalize SVGs
            task.set_progress({
                'total': total_pages,
                'completed': completed,
                'failed': failed,
                'phase': 'finalizing_svg',
            })
            db.session.commit()

            finalize_success = finalize_svgs(project_dir)
            if not finalize_success:
                logger.warning("SVG finalization had issues, continuing with raw SVGs")

            # Phase: Convert to PPTX
            task.set_progress({
                'total': total_pages,
                'completed': completed,
                'failed': failed,
                'phase': 'converting_pptx',
            })
            db.session.commit()

            # Determine output path
            exports_dir = Path(upload_folder) / project_id / 'exports'
            exports_dir.mkdir(parents=True, exist_ok=True)
            output_path, filename = _unique_pptx_path(exports_dir, project.title, project_id)
            logger.info("PptMaster output path: %s", output_path)

            pptx_path = convert_to_pptx(
                project_dir=project_dir,
                canvas_format=project.canvas_format,
                output_path=output_path,
            )

            if pptx_path and pptx_path.exists():
                # Store the download URL
                download_url = f"/files/{project_id}/exports/{filename}"
                project.output_path = str(pptx_path)
                project.status = 'COMPLETED'

                task.status = 'COMPLETED'
                task.completed_at = datetime.utcnow()
                task.set_progress({
                    'total': total_pages,
                    'completed': completed,
                    'failed': failed,
                    'phase': 'done',
                    'output_file': download_url,
                })
            else:
                project.status = 'FAILED'
                task.status = 'FAILED'
                task.error_message = 'PPTX conversion failed'
                task.completed_at = datetime.utcnow()

            db.session.commit()
            logger.info(f"PptMaster pipeline completed for project {project_id}: {project.status}")

        except Exception as e:
            logger.error(f"PptMaster pipeline failed: {e}", exc_info=True)
            try:
                task = Task.query.get(task_id)
                if task:
                    task.status = 'FAILED'
                    task.error_message = str(e)
                    task.completed_at = datetime.utcnow()
                project = PptMasterProject.query.get(project_id)
                if project:
                    project.status = 'FAILED'
                db.session.commit()
            except Exception:
                pass


def run_full_pipeline_with_strategist(task_id: str, project_id: str, app=None):
    """
    Background task: run strategist first, then the full pipeline.
    Used by the quick-generate endpoint.
    """
    if app is None:
        raise ValueError("Flask app instance must be provided")

    with app.app_context():
        from models import db, Task
        from models.pptmaster_project import PptMasterProject, PptMasterPage

        try:
            project = PptMasterProject.query.get(project_id)
            if not project:
                raise ValueError(f"PptMaster project {project_id} not found")

            task = Task.query.get(task_id)
            if not task:
                raise ValueError(f"Task {task_id} not found")

            task.status = 'PROCESSING'
            task.set_progress({'total': 0, 'completed': 0, 'failed': 0, 'phase': 'strategist'})
            db.session.commit()

            # Phase 1: Strategist
            logger.info(f"Running strategist for project {project_id}")
            result = run_strategist(
                project_id=project_id,
                content=project.content,
                canvas_format=project.canvas_format,
                style_type=project.style_type,
                language=project.language or 'zh',
            )

            design_spec = result.get('design_spec', {})
            spec_lock = result.get('spec_lock', {})
            page_count = result.get('page_count', len(design_spec.get('pages', [])))

            project.set_design_spec(design_spec)
            project.set_spec_lock(spec_lock)
            project.page_count = page_count
            project.status = 'SPEC_READY'

            # Create page records
            PptMasterPage.query.filter_by(project_id=project_id).delete()
            for i, page_info in enumerate(design_spec.get('pages', [])):
                page = PptMasterPage(
                    project_id=project_id,
                    order_index=i + 1,
                    page_name=f"{i+1:02d}_{page_info.get('type', 'content')}",
                    page_title=page_info.get('title', ''),
                    page_brief=page_info.get('brief', ''),
                    status='PENDING',
                )
                db.session.add(page)
            db.session.commit()

            logger.info(f"Strategist completed: {page_count} pages planned")

        except Exception as e:
            logger.error(f"Strategist phase failed: {e}", exc_info=True)
            try:
                task = Task.query.get(task_id)
                if task:
                    task.status = 'FAILED'
                    task.error_message = f'Strategist failed: {str(e)}'
                    task.completed_at = datetime.utcnow()
                project = PptMasterProject.query.get(project_id)
                if project:
                    project.status = 'FAILED'
                db.session.commit()
            except Exception:
                pass
            return

    # Phase 2+: Run the rest of the pipeline
    run_full_pipeline(task_id, project_id, app=app)


def _get_upload_folder() -> str:
    """Get the upload folder path."""
    try:
        from flask import current_app
        folder = current_app.config.get('UPLOAD_FOLDER')
        if folder:
            return folder
    except RuntimeError:
        pass
    return os.getenv('SLIDEAI_UPLOAD_FOLDER') or os.getenv('UPLOAD_FOLDER', 'uploads')
