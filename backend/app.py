"""
Simplified Flask Application Entry Point
"""
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import event
from sqlalchemy.engine import Engine
import sqlite3
from sqlalchemy.exc import SQLAlchemyError
from flask_migrate import Migrate

# Load environment variables from the packaged user config when provided,
# otherwise use the project root .env file for local development.
_project_root = Path(__file__).parent.parent
_env_file = Path(os.getenv('SLIDEAI_ENV_FILE')) if os.getenv('SLIDEAI_ENV_FILE') else _project_root / '.env'
load_dotenv(dotenv_path=_env_file, override=True)

# Auto-detect frontend directory for local development
if not os.getenv('SLIDEAI_FRONTEND_DIR'):
    _frontend_dir = _project_root / 'frontend'
    if _frontend_dir.exists():
        os.environ['SLIDEAI_FRONTEND_DIR'] = str(_frontend_dir)
if not os.getenv('SLIDEAI_ASSETS_DIR'):
    _assets_dir = _project_root / 'assets'
    if _assets_dir.exists():
        os.environ['SLIDEAI_ASSETS_DIR'] = str(_assets_dir)

from flask import Flask, send_from_directory, send_file, Response
from flask_cors import CORS
from models import db
from config import Config
from controllers.material_controller import material_bp, material_global_bp
from controllers.reference_file_controller import reference_file_bp
from controllers.settings_controller import LOCKED_API_BASE_URL, settings_bp
from controllers import project_bp, page_bp, template_bp, user_template_bp, export_bp, file_bp, style_bp
from controllers.pptmaster_controller import pptmaster_bp


# Enable SQLite WAL mode for all connections
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_conn, connection_record):
    """
    Enable WAL mode and related PRAGMAs for each SQLite connection.
    Registered once at import time to avoid duplicate handlers when
    create_app() is called multiple times.
    """
    # Only apply to SQLite connections
    if not isinstance(dbapi_conn, sqlite3.Connection):
        return

    cursor = dbapi_conn.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds timeout
    finally:
        cursor.close()


def create_app():
    """Application factory"""
    app = Flask(__name__)

    # Auto-detect frontend directory for local development (inside create_app)
    if not os.getenv('SLIDEAI_FRONTEND_DIR'):
        _local_frontend = Path(__file__).parent.parent / 'frontend'
        if _local_frontend.exists():
            os.environ['SLIDEAI_FRONTEND_DIR'] = str(_local_frontend)
    if not os.getenv('SLIDEAI_ASSETS_DIR'):
        _local_assets = Path(__file__).parent.parent / 'assets'
        if _local_assets.exists():
            os.environ['SLIDEAI_ASSETS_DIR'] = str(_local_assets)

    # Load configuration from Config class
    app.config.from_object(Config)
    
    # Override with environment-specific paths (use absolute path).
    # Electron builds pass SLIDEAI_DATA_DIR so each user gets an isolated DB/key store.
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.getenv('SLIDEAI_DATA_DIR')
    if data_dir:
        instance_dir = os.path.join(data_dir, 'backend', 'instance')
    else:
        instance_dir = os.path.join(backend_dir, 'instance')
    os.makedirs(instance_dir, exist_ok=True)
    
    db_path = os.path.join(instance_dir, 'database.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    
    # Ensure upload folder exists
    project_root = os.path.dirname(backend_dir)
    upload_folder = os.getenv('SLIDEAI_UPLOAD_FOLDER')
    if not upload_folder:
        upload_folder = os.path.join(data_dir, 'uploads') if data_dir else os.path.join(project_root, 'uploads')
    os.makedirs(upload_folder, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = upload_folder
    app.config['ASSETS_DIR'] = os.getenv('SLIDEAI_ASSETS_DIR') or os.path.join(project_root, 'assets')
    
    # CORS configuration (parse from environment)
    raw_cors = os.getenv('CORS_ORIGINS', 'http://localhost:3000')
    if raw_cors.strip() == '*':
        cors_origins = '*'
    else:
        cors_origins = [o.strip() for o in raw_cors.split(',') if o.strip()]
    app.config['CORS_ORIGINS'] = cors_origins
    
    # Initialize logging (log to stdout so Docker can capture it)
    log_level = getattr(logging, app.config['LOG_LEVEL'], logging.INFO)
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    
    # 设置第三方库的日志级别，避免过多的DEBUG日志
    logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('werkzeug').setLevel(logging.INFO)  # Flask开发服务器日志保持INFO
    logging.getLogger('volcenginesdkarkruntime').setLevel(logging.WARNING)

    # Initialize extensions
    db.init_app(app)
    CORS(app, origins=cors_origins)
    # Database migrations (Alembic via Flask-Migrate)
    Migrate(app, db)
    
    # Register blueprints
    app.register_blueprint(project_bp)
    app.register_blueprint(page_bp)
    app.register_blueprint(template_bp)
    app.register_blueprint(user_template_bp)
    app.register_blueprint(export_bp)
    app.register_blueprint(file_bp)
    app.register_blueprint(material_bp)
    app.register_blueprint(material_global_bp)
    app.register_blueprint(reference_file_bp, url_prefix='/api/reference-files')
    app.register_blueprint(settings_bp)
    app.register_blueprint(style_bp)
    app.register_blueprint(pptmaster_bp)

    with app.app_context():
        # Fresh portable installs start without database.db; create the current schema on first boot.
        db.create_all()
        # Auto-migrate: add missing columns to existing tables so upgrades don't break
        _auto_add_missing_columns(app, db)
        # Electron upgrades should clear stale keys/model overrides once per app version.
        _clear_sensitive_settings_on_version_change(app)
        # Load settings from database and sync to app.config
        _load_settings_to_config(app)

    # Activation-code enforcement on all /api/ routes
    @app.before_request
    def _enforce_access_code():
        from flask import request, jsonify
        from protected.license_guard import is_activation_enabled, validate_activation_code

        if not is_activation_enabled():
            return
        if not request.path.startswith('/api/'):
            return  # non-API routes (health, static, etc.)
        if request.path.startswith('/api/access-code/'):
            return  # allow check/verify endpoints
        code = request.headers.get('X-Access-Code', '')
        if validate_activation_code(code):
            return
        return jsonify({'error': 'Access code required'}), 403

    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'ok', 'message': 'SlideAI API is running'}

    # Access code verification
    @app.route('/api/access-code/check', methods=['GET'])
    def check_access_code():
        """Check if access code protection is enabled"""
        from protected.license_guard import is_activation_enabled
        enabled = is_activation_enabled()
        return {'data': {'enabled': enabled}}

    @app.route('/api/access-code/verify', methods=['POST'])
    def verify_access_code():
        """Verify the provided access code"""
        from flask import request, jsonify
        from protected.license_guard import is_activation_enabled, validate_activation_code

        if not is_activation_enabled():
            return {'data': {'valid': True}}
        code = (request.json or {}).get('code', '')
        if validate_activation_code(code):
            return {'data': {'valid': True}}
        return jsonify({'error': 'Invalid access code'}), 403
    
    # Output language endpoint
    @app.route('/api/output-language', methods=['GET'])
    def get_output_language():
        """
        获取用户的输出语言偏好（从数据库 Settings 读取）
        返回: zh, ja, en, auto
        """
        from models import Settings
        try:
            settings = Settings.get_settings()
            return {'data': {'language': settings.output_language or Config.OUTPUT_LANGUAGE}}
        except SQLAlchemyError as db_error:
            logging.warning(f"Failed to load output language from settings: {db_error}")
            return {'data': {'language': Config.OUTPUT_LANGUAGE}}  # 默认中文

    frontend_dir = os.getenv('SLIDEAI_FRONTEND_DIR', '').strip()
    if not frontend_dir:
        _auto_frontend = Path(__file__).resolve().parent.parent / 'frontend'
        if _auto_frontend.exists():
            frontend_dir = str(_auto_frontend)
    logging.info(f"Frontend dir: {frontend_dir}")

    _frontend_path = Path(frontend_dir) if frontend_dir else None

    def _serve_file(rel_path: str):
        """Read and serve a file from the frontend directory.
        Uses direct file read to avoid Flask/Werkzeug issues with non-ASCII paths."""
        if not _frontend_path:
            return None
        target = (_frontend_path / rel_path).resolve()
        if not target.exists() or not target.is_file():
            return None
        if not str(target).startswith(str(_frontend_path.resolve())):
            return None
        try:
            data = target.read_bytes()
            mime = 'text/html; charset=utf-8' if rel_path.endswith('.html') else None
            if mime is None:
                import mimetypes
                mime, _ = mimetypes.guess_type(rel_path)
                mime = mime or 'application/octet-stream'
            return Response(data, mimetype=mime)
        except Exception:
            return None

    # Root endpoint
    @app.route('/')
    def index():
        result = _serve_file('index.html')
        if result:
            return result
        return {
            'name': 'SlideAI API',
            'version': '1.0.0',
            'description': 'AI-powered PPT generation service',
            'endpoints': {
                'health': '/health',
                'api_docs': '/api',
                'projects': '/api/projects'
            }
        }

    if _frontend_path:
        @app.route('/<path:path>')
        def serve_frontend(path):
            if path.startswith('api/') or path == 'health':
                return {'error': 'Not found'}, 404
            result = _serve_file(path)
            if result:
                return result
            result = _serve_file('index.html')
            if result:
                return result
            return {'error': 'Not found'}, 404
    
    return app


def _auto_add_missing_columns(app, db):
    """Auto-migrate: inspect all models and add any missing columns to existing tables.
    This ensures upgrades don't break when new columns are added to models."""
    from sqlalchemy import inspect as sa_inspect, text
    try:
        inspector = sa_inspect(db.engine)
        existing_tables = inspector.get_table_names()

        for table_name, table_obj in db.metadata.tables.items():
            if table_name not in existing_tables:
                continue
            existing_cols = {col['name'] for col in inspector.get_columns(table_name)}
            for column in table_obj.columns:
                if column.name not in existing_cols:
                    col_type = column.type.compile(db.engine.dialect)
                    nullable = "NULL" if column.nullable else "NOT NULL"
                    default = ""
                    if column.default is not None:
                        default = f" DEFAULT {column.default.arg!r}"
                    sql = f"ALTER TABLE {table_name} ADD COLUMN {column.name} {col_type} {nullable}{default}"
                    logging.info(f"Auto-migrate: adding column {table_name}.{column.name} ({col_type})")
                    db.session.execute(text(sql))
        db.session.commit()
    except Exception as e:
        logging.warning(f"Auto-migrate check failed (non-fatal): {e}")
        db.session.rollback()


def _clear_sensitive_settings_on_version_change(app):
    """Clear saved keys and per-model overrides once after an Electron upgrade."""
    data_dir = os.getenv('SLIDEAI_DATA_DIR')
    app_version = os.getenv('SLIDEAI_APP_VERSION', '').strip()
    if not data_dir or not app_version:
        return

    marker_path = Path(data_dir) / '.slideai_settings_version'
    previous_version = ''
    try:
        if marker_path.exists():
            previous_version = marker_path.read_text(encoding='utf-8').strip()
    except OSError as e:
        logging.warning(f"Could not read settings version marker: {e}")

    if previous_version == app_version:
        return

    from models import Settings
    try:
        settings = Settings.get_settings()
        for attr in (
            'api_key',
            'text_api_key',
            'image_api_key',
            'image_caption_api_key',
            'mineru_token',
            'baidu_api_key',
            'lazyllm_api_keys',
            'ai_provider_format',
            'text_model',
            'image_model',
            'image_caption_model',
            'text_model_source',
            'image_model_source',
            'image_caption_model_source',
        ):
            setattr(settings, attr, None)

        for attr in ('api_base_url', 'text_api_base_url', 'image_api_base_url', 'image_caption_api_base_url'):
            setattr(settings, attr, LOCKED_API_BASE_URL)

        db.session.commit()
        marker_path.parent.mkdir(parents=True, exist_ok=True)
        marker_path.write_text(app_version, encoding='utf-8')
        logging.info(f"Cleared sensitive settings after app upgrade: {previous_version or 'none'} -> {app_version}")
    except Exception as e:
        db.session.rollback()
        logging.warning(f"Could not clear sensitive settings after app upgrade: {e}")


def _load_settings_to_config(app):
    """Load settings from database and apply to app.config on startup"""
    from models import Settings
    try:
        settings = Settings.get_settings()
        
        # Load AI provider format (always sync, has default value)
        if settings.ai_provider_format:
            app.config['AI_PROVIDER_FORMAT'] = settings.ai_provider_format
            logging.info(f"Loaded AI_PROVIDER_FORMAT from settings: {settings.ai_provider_format}")
        
        # Load API configuration, locked to MHcoding regardless of env/database value.
        app.config['GOOGLE_API_BASE'] = LOCKED_API_BASE_URL
        app.config['OPENAI_API_BASE'] = LOCKED_API_BASE_URL
        logging.info(f"Loaded API_BASE from locked setting: {LOCKED_API_BASE_URL}")

        if settings.api_key is not None:
            # 同步到两个提供商的 key，数据库优先于环境变量
            app.config['GOOGLE_API_KEY'] = settings.api_key
            app.config['OPENAI_API_KEY'] = settings.api_key
            if settings.api_key:
                logging.info("Loaded API key from settings")
            else:
                logging.info("API key is empty in settings, using env var or default")

        # Load image generation settings (fall back to .env/Config when NULL)
        resolution = settings.image_resolution or Config.DEFAULT_RESOLUTION
        aspect_ratio = settings.image_aspect_ratio or Config.DEFAULT_ASPECT_RATIO
        app.config['DEFAULT_RESOLUTION'] = resolution
        app.config['DEFAULT_ASPECT_RATIO'] = aspect_ratio
        logging.info(f"Loaded image settings: {resolution}, {aspect_ratio}")

        # Load worker settings (fall back to .env/Config when NULL)
        desc_workers = settings.max_description_workers or Config.MAX_DESCRIPTION_WORKERS
        img_workers = settings.max_image_workers or Config.MAX_IMAGE_WORKERS
        app.config['MAX_DESCRIPTION_WORKERS'] = desc_workers
        app.config['MAX_IMAGE_WORKERS'] = img_workers
        logging.info(f"Loaded worker settings: desc={desc_workers}, img={img_workers}")

        # Load model settings (FIX for Issue #136: these were missing before)
        if settings.text_model:
            app.config['TEXT_MODEL'] = settings.text_model
            logging.info(f"Loaded TEXT_MODEL from settings: {settings.text_model}")
        
        if settings.image_model:
            app.config['IMAGE_MODEL'] = settings.image_model
            logging.info(f"Loaded IMAGE_MODEL from settings: {settings.image_model}")
        
        # Load MinerU settings
        if settings.mineru_api_base:
            app.config['MINERU_API_BASE'] = settings.mineru_api_base
            logging.info(f"Loaded MINERU_API_BASE from settings: {settings.mineru_api_base}")
        
        if settings.mineru_token:
            app.config['MINERU_TOKEN'] = settings.mineru_token
            logging.info("Loaded MINERU_TOKEN from settings")
        
        # Load image caption model
        if settings.image_caption_model:
            app.config['IMAGE_CAPTION_MODEL'] = settings.image_caption_model
            logging.info(f"Loaded IMAGE_CAPTION_MODEL from settings: {settings.image_caption_model}")
        
        # Load output language
        if settings.output_language:
            app.config['OUTPUT_LANGUAGE'] = settings.output_language
            logging.info(f"Loaded OUTPUT_LANGUAGE from settings: {settings.output_language}")
        
        # Load reasoning mode settings (separate for text and image)
        app.config['ENABLE_TEXT_REASONING'] = settings.enable_text_reasoning
        app.config['TEXT_THINKING_BUDGET'] = settings.text_thinking_budget
        app.config['ENABLE_IMAGE_REASONING'] = settings.enable_image_reasoning
        app.config['IMAGE_THINKING_BUDGET'] = settings.image_thinking_budget
        logging.info(f"Loaded reasoning config: text={settings.enable_text_reasoning}(budget={settings.text_thinking_budget}), image={settings.enable_image_reasoning}(budget={settings.image_thinking_budget})")
        
        # Load Baidu API settings
        if settings.baidu_api_key:
            app.config['BAIDU_API_KEY'] = settings.baidu_api_key
            logging.info("Loaded BAIDU_API_KEY from settings")

        # Load LazyLLM source settings
        if settings.text_model_source:
            app.config['TEXT_MODEL_SOURCE'] = settings.text_model_source
            logging.info(f"Loaded TEXT_MODEL_SOURCE from settings: {settings.text_model_source}")
        if settings.image_model_source:
            app.config['IMAGE_MODEL_SOURCE'] = settings.image_model_source
            logging.info(f"Loaded IMAGE_MODEL_SOURCE from settings: {settings.image_model_source}")
        if settings.image_caption_model_source:
            app.config['IMAGE_CAPTION_MODEL_SOURCE'] = settings.image_caption_model_source
            logging.info(f"Loaded IMAGE_CAPTION_MODEL_SOURCE from settings: {settings.image_caption_model_source}")

        # Load per-model API credentials (for gemini/openai per-model overrides)
        for model_type in ('text', 'image', 'image_caption'):
            prefix = model_type.upper()
            for suffix, setting_suffix in [('_API_KEY', '_api_key'), ('_API_BASE', '_api_base_url')]:
                config_key = f'{prefix}{suffix}'
                val = LOCKED_API_BASE_URL if suffix == '_API_BASE' else getattr(settings, f'{model_type}{setting_suffix}', None)
                if val:
                    app.config[config_key] = val
                    if suffix == '_API_BASE':
                        logging.info(f"Loaded {config_key} from settings: {val}")
                    else:
                        logging.info(f"Loaded {config_key} from settings")

        # Sync LazyLLM vendor API keys to environment variables
        # Only allow known vendor names to prevent environment variable injection
        from services.ai_providers.lazyllm_env import ALLOWED_LAZYLLM_VENDORS
        if settings.lazyllm_api_keys:
            import json
            try:
                keys = json.loads(settings.lazyllm_api_keys)
                for vendor, key in keys.items():
                    if key and vendor.lower() in ALLOWED_LAZYLLM_VENDORS:
                        os.environ[f"{vendor.upper()}_API_KEY"] = key
                    elif key:
                        logging.warning(f"Ignoring unknown lazyllm vendor: {vendor}")
                logging.info(f"Loaded LazyLLM API keys for vendors: {[v for v, k in keys.items() if k and v.lower() in ALLOWED_LAZYLLM_VENDORS]}")
            except (json.JSONDecodeError, TypeError):
                logging.warning("Failed to parse lazyllm_api_keys from settings")

    except Exception as e:
        if isinstance(e, SQLAlchemyError) and "no such table: settings" in str(e):
            logging.debug(f"Settings table not yet created (expected on first boot): {e}")
        else:
            logging.warning(f"Could not load settings from database: {e}")


# Create app instance
app = create_app()


def _compute_worktree_port(base_port: int) -> int:
    """Compute a deterministic port from the worktree directory name.

    Uses MD5 of the project root basename so each worktree gets a unique,
    stable port pair (backend 5xxx, frontend 3xxx) without manual config.
    """
    import hashlib
    basename = _project_root.name
    offset = int(hashlib.md5(basename.encode()).hexdigest()[:8], 16) % 500
    return base_port + offset


if __name__ == '__main__':
    # Run development server
    if os.getenv("IN_DOCKER", "0") == "1":
        port = 5000  # Docker 容器内部固定使用 5000 端口
    elif os.getenv('SLIDEAI_BACKEND_PORT'):
        port = int(os.getenv('SLIDEAI_BACKEND_PORT'))
    elif os.getenv('BACKEND_PORT'):
        port = int(os.getenv('BACKEND_PORT'))
    else:
        port = _compute_worktree_port(5000)
    debug = os.getenv('FLASK_ENV', 'development') == 'development'
    
    logging.info(
        "\n"
        "╔══════════════════════════════════════╗\n"
        "║          SlideAI API Server          ║\n"
        "╚══════════════════════════════════════╝\n"
        f"Server starting on: http://localhost:{port}\n"
        f"Output Language: {Config.OUTPUT_LANGUAGE}\n"
        f"Environment: {os.getenv('FLASK_ENV', 'development')}\n"
        f"Debug mode: {debug}\n"
        f"API Base URL: http://localhost:{port}/api\n"
        f"Database: {app.config['SQLALCHEMY_DATABASE_URI']}\n"
        f"Uploads: {app.config['UPLOAD_FOLDER']}"
    )
    
    # Using absolute paths for database, so WSL path issues should not occur
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=debug)
