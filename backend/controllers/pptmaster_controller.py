"""
PptMaster Controller - API endpoints for editable PPTX generation.

Routes:
  POST /api/pptmaster/projects          - Create project
  GET  /api/pptmaster/projects/:id      - Get project details
  POST /api/pptmaster/projects/:id/strategist  - Run strategist (AI design spec)
  PUT  /api/pptmaster/projects/:id/strategist  - Update design spec
  POST /api/pptmaster/projects/:id/generate    - Start full generation pipeline
  GET  /api/pptmaster/projects/:id/status      - Get task status
  GET  /api/pptmaster/projects/:id/download    - Download PPTX
  GET  /api/pptmaster/projects          - List projects
  DELETE /api/pptmaster/projects/:id    - Delete project
"""

import os
import logging
from pathlib import Path
from datetime import datetime
from flask import Blueprint, request, jsonify, send_file, current_app
from models import db, Task
from models.pptmaster_project import PptMasterProject, PptMasterPage

logger = logging.getLogger(__name__)

pptmaster_bp = Blueprint('pptmaster', __name__, url_prefix='/api/pptmaster')

# Shared task manager instance (lazy init)
_task_manager = None


def _get_task_manager():
    global _task_manager
    if _task_manager is None:
        from services.task_manager import TaskManager
        _task_manager = TaskManager(max_workers=2)
    return _task_manager


# ============================================================
# Project CRUD
# ============================================================

@pptmaster_bp.route('/projects', methods=['POST'])
def create_project():
    """Create a new PptMaster project."""
    data = request.get_json() or {}

    title = data.get('title', '').strip()
    content = data.get('content', '').strip()
    canvas_format = data.get('canvas_format', 'ppt169')
    style_type = data.get('style_type', 'general')
    language = data.get('language', 'zh')

    if not content:
        return jsonify({'error': {'message': 'Content is required'}}), 400

    project = PptMasterProject(
        title=title or content[:80],
        content=content,
        canvas_format=canvas_format,
        style_type=style_type,
        language=language,
        status='DRAFT',
    )
    db.session.add(project)
    db.session.commit()

    logger.info(f"Created PptMaster project {project.id}: {project.title[:50]}")
    return jsonify({'data': project.to_dict()}), 201


@pptmaster_bp.route('/projects', methods=['GET'])
def list_projects():
    """List all PptMaster projects."""
    projects = PptMasterProject.query.order_by(
        PptMasterProject.updated_at.desc()
    ).all()
    return jsonify({'data': [p.to_dict() for p in projects]})


@pptmaster_bp.route('/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get project details including pages."""
    project = PptMasterProject.query.get(project_id)
    if not project:
        return jsonify({'error': {'message': 'Project not found'}}), 404
    return jsonify({'data': project.to_dict(include_pages=True)})


@pptmaster_bp.route('/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete a project and all its pages."""
    project = PptMasterProject.query.get(project_id)
    if not project:
        return jsonify({'error': {'message': 'Project not found'}}), 404

    db.session.delete(project)
    db.session.commit()

    logger.info(f"Deleted PptMaster project {project_id}")
    return jsonify({'data': {'message': 'Project deleted'}})


# ============================================================
# Strategist Phase
# ============================================================

@pptmaster_bp.route('/projects/<project_id>/strategist', methods=['POST'])
def run_strategist(project_id):
    """Run AI strategist to generate design spec."""
    project = PptMasterProject.query.get(project_id)
    if not project:
        return jsonify({'error': {'message': 'Project not found'}}), 404

    data = request.get_json() or {}
    style_type = data.get('style_type', project.style_type or 'general')
    canvas_format = data.get('canvas_format', project.canvas_format or 'ppt169')

    # Update project settings
    project.style_type = style_type
    project.canvas_format = canvas_format

    try:
        from services.pptmaster.pipeline import run_strategist as pipeline_strategist

        result = pipeline_strategist(
            project_id=project_id,
            content=project.content,
            canvas_format=canvas_format,
            style_type=style_type,
            language=project.language or 'zh',
        )

        design_spec = result.get('design_spec', {})
        spec_lock = result.get('spec_lock', {})
        page_count = result.get('page_count', len(design_spec.get('pages', [])))

        project.set_design_spec(design_spec)
        project.set_spec_lock(spec_lock)
        project.page_count = page_count
        project.status = 'SPEC_READY'

        # Create page records from outline
        pages_info = design_spec.get('pages', [])
        # Remove existing pages
        PptMasterPage.query.filter_by(project_id=project_id).delete()

        for i, page_info in enumerate(pages_info):
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

        return jsonify({'data': {
            'design_spec': design_spec,
            'spec_lock': spec_lock,
            'page_count': page_count,
        }})

    except Exception as e:
        logger.error(f"Strategist failed for project {project_id}: {e}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': {'message': f'Strategist failed: {str(e)}'}}), 500


@pptmaster_bp.route('/projects/<project_id>/strategist', methods=['PUT'])
def update_strategist(project_id):
    """Update design spec (user adjustments)."""
    project = PptMasterProject.query.get(project_id)
    if not project:
        return jsonify({'error': {'message': 'Project not found'}}), 404

    data = request.get_json() or {}

    if 'design_spec' in data:
        project.set_design_spec(data['design_spec'])
    if 'spec_lock' in data:
        project.set_spec_lock(data['spec_lock'])
    if 'page_count' in data:
        project.page_count = data['page_count']

    db.session.commit()
    return jsonify({'data': project.to_dict()})


# ============================================================
# Generation Phase
# ============================================================

@pptmaster_bp.route('/projects/<project_id>/generate', methods=['POST'])
def start_generation(project_id):
    """Start the full generation pipeline (background task)."""
    project = PptMasterProject.query.get(project_id)
    if not project:
        return jsonify({'error': {'message': 'Project not found'}}), 404

    if not project.design_spec:
        return jsonify({'error': {'message': 'Run strategist first'}}), 400

    # Create task record
    task = Task(
        project_id=project_id,
        task_type='PPTMASTER_GENERATE',
        status='PENDING',
    )
    task.set_progress({'total': project.page_count or 0, 'completed': 0, 'failed': 0, 'phase': 'queued'})
    db.session.add(task)
    db.session.commit()

    # Submit background task
    from services.pptmaster.pipeline import run_full_pipeline

    tm = _get_task_manager()
    tm.submit_task(
        task.id,
        run_full_pipeline,
        project_id=project_id,
        app=current_app._get_current_object(),
    )

    logger.info(f"Started PptMaster generation task {task.id} for project {project_id}")
    return jsonify({'data': {'task_id': task.id}}), 202


@pptmaster_bp.route('/projects/<project_id>/status', methods=['GET'])
def get_status(project_id):
    """Get the latest task status for a project."""
    # Find latest task for this project
    task = Task.query.filter_by(
        project_id=project_id,
        task_type='PPTMASTER_GENERATE'
    ).order_by(Task.created_at.desc()).first()

    if not task:
        project = PptMasterProject.query.get(project_id)
        if not project:
            return jsonify({'error': {'message': 'Project not found'}}), 404
        return jsonify({'data': {'status': project.status, 'task': None}})

    return jsonify({'data': {
        'status': task.status,
        'task': task.to_dict(),
    }})


# ============================================================
# Download
# ============================================================

@pptmaster_bp.route('/projects/<project_id>/download', methods=['GET'])
def download_pptx(project_id):
    """Download the generated PPTX file."""
    project = PptMasterProject.query.get(project_id)
    if not project:
        return jsonify({'error': {'message': 'Project not found'}}), 404

    if not project.output_path:
        return jsonify({'error': {'message': 'No PPTX file available. Run generation first.'}}), 404

    output_path = Path(project.output_path)
    if not output_path.exists():
        return jsonify({'error': {'message': 'PPTX file not found on disk'}}), 404

    return send_file(
        str(output_path),
        as_attachment=True,
        download_name=output_path.name,
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
    )


# ============================================================
# Quick Generate (strategist + generate in one step)
# ============================================================

@pptmaster_bp.route('/projects/<project_id>/quick-generate', methods=['POST'])
def quick_generate(project_id):
    """Run strategist and immediately start generation."""
    project = PptMasterProject.query.get(project_id)
    if not project:
        return jsonify({'error': {'message': 'Project not found'}}), 404

    data = request.get_json() or {}
    style_type = data.get('style_type', project.style_type or 'general')
    canvas_format = data.get('canvas_format', project.canvas_format or 'ppt169')

    project.style_type = style_type
    project.canvas_format = canvas_format
    db.session.commit()

    # Create task for the full pipeline (strategist included)
    task = Task(
        project_id=project_id,
        task_type='PPTMASTER_GENERATE',
        status='PENDING',
    )
    task.set_progress({'total': 0, 'completed': 0, 'failed': 0, 'phase': 'strategist'})
    db.session.add(task)
    db.session.commit()

    from services.pptmaster.pipeline import run_full_pipeline_with_strategist

    tm = _get_task_manager()
    tm.submit_task(
        task.id,
        run_full_pipeline_with_strategist,
        project_id=project_id,
        app=current_app._get_current_object(),
    )

    logger.info(f"Started PptMaster quick-generate task {task.id} for project {project_id}")
    return jsonify({'data': {'task_id': task.id}}), 202


# ============================================================
# Canvas formats / config endpoints
# ============================================================

@pptmaster_bp.route('/config/canvas-formats', methods=['GET'])
def get_canvas_formats():
    """Get available canvas formats."""
    from services.pptmaster.config import CANVAS_FORMATS
    return jsonify({'data': CANVAS_FORMATS})


@pptmaster_bp.route('/config/color-schemes', methods=['GET'])
def get_color_schemes():
    """Get available design color schemes."""
    from services.pptmaster.config import DESIGN_COLORS
    return jsonify({'data': DESIGN_COLORS})


@pptmaster_bp.route('/config/style-types', methods=['GET'])
def get_style_types():
    """Get available style types."""
    return jsonify({'data': {
        'general': {'name': 'General Versatile', 'description': 'Visual impact first, public/clients'},
        'consulting': {'name': 'General Consulting', 'description': 'Data clarity first, teams/management'},
        'consultant-top': {'name': 'Top Consulting', 'description': 'Logical persuasion first, executives/board'},
    }})
