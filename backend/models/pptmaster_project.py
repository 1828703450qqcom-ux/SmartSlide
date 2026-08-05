"""
PptMaster Project and Page models
"""
import uuid
import json
from datetime import datetime
from . import db


class PptMasterProject(db.Model):
    """PptMaster project - independent editable PPTX creation"""
    __tablename__ = 'pptmaster_projects'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title = db.Column(db.Text, nullable=True)
    content = db.Column(db.Text, nullable=True)
    design_spec = db.Column(db.Text, nullable=True)  # JSON: AI-generated design spec
    spec_lock = db.Column(db.Text, nullable=True)  # JSON: execution lock parameters
    canvas_format = db.Column(db.String(20), nullable=False, default='ppt169')
    color_scheme = db.Column(db.String(50), nullable=True)
    style_type = db.Column(db.String(20), nullable=False, default='general')
    page_count = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='DRAFT')
    output_path = db.Column(db.Text, nullable=True)
    language = db.Column(db.String(10), nullable=True, default='zh')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    pages = db.relationship('PptMasterPage', back_populates='project', lazy='select',
                           cascade='all, delete-orphan', order_by='PptMasterPage.order_index')
    # Note: Tasks use project_id but the FK references the original 'projects' table.
    # We query tasks manually instead of using a relationship to avoid FK conflicts.

    def get_design_spec(self):
        if self.design_spec:
            try:
                return json.loads(self.design_spec)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_design_spec(self, data):
        self.design_spec = json.dumps(data, ensure_ascii=False) if data else None

    def get_spec_lock(self):
        if self.spec_lock:
            try:
                return json.loads(self.spec_lock)
            except json.JSONDecodeError:
                return {}
        return {}

    def set_spec_lock(self, data):
        self.spec_lock = json.dumps(data, ensure_ascii=False) if data else None

    def to_dict(self, include_pages=False):
        data = {
            'project_id': self.id,
            'title': self.title,
            'content': self.content,
            'design_spec': self.get_design_spec(),
            'spec_lock': self.get_spec_lock(),
            'canvas_format': self.canvas_format,
            'color_scheme': self.color_scheme,
            'style_type': self.style_type,
            'page_count': self.page_count,
            'status': self.status,
            'output_path': self.output_path,
            'language': self.language,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
            'updated_at': self.updated_at.isoformat() + 'Z' if self.updated_at else None,
        }
        if include_pages:
            data['pages'] = [p.to_dict() for p in self.pages]
        return data


class PptMasterPage(db.Model):
    """PptMaster page - individual slide in a project"""
    __tablename__ = 'pptmaster_pages'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = db.Column(db.String(36), db.ForeignKey('pptmaster_projects.id'), nullable=False)
    order_index = db.Column(db.Integer, nullable=False)
    page_name = db.Column(db.String(100), nullable=True)
    page_title = db.Column(db.Text, nullable=True)
    page_brief = db.Column(db.Text, nullable=True)
    svg_content = db.Column(db.Text, nullable=True)
    svg_final_content = db.Column(db.Text, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(50), nullable=False, default='PENDING')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    project = db.relationship('PptMasterProject', back_populates='pages')

    def to_dict(self):
        return {
            'id': self.id,
            'project_id': self.project_id,
            'order_index': self.order_index,
            'page_name': self.page_name,
            'page_title': self.page_title,
            'page_brief': self.page_brief,
            'svg_content': self.svg_content is not None,  # Don't send full SVG to frontend
            'svg_final_content': self.svg_final_content is not None,
            'notes': self.notes,
            'status': self.status,
            'created_at': self.created_at.isoformat() + 'Z' if self.created_at else None,
        }
