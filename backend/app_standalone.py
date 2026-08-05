"""
Standalone Flask Application for Windows EXE Distribution
This version serves both API and frontend static files
"""
import os
import sys
from pathlib import Path
from flask import send_from_directory, send_file

# 获取可执行文件的目录
if getattr(sys, 'frozen', False):
    # 运行在 PyInstaller 打包的 exe 中
    application_path = Path(sys._MEIPASS)
    project_root = Path(sys.executable).parent.parent
else:
    # 运行在开发环境
    application_path = Path(__file__).parent
    project_root = Path(__file__).parent.parent

# 设置工作目录
os.chdir(project_root)

# 导入原始的 app
from app import create_app

app = create_app()

# 配置静态文件目录
STATIC_FOLDER = project_root / 'backend' / 'static'

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """服务前端静态文件"""
    # API 路由已经在原始 app 中注册，这里只处理前端文件
    if path.startswith('api/') or path == 'health':
        # 让 Flask 的其他路由处理
        return app.send_static_file('index.html')
    
    # 尝试返回请求的文件
    if path and (STATIC_FOLDER / path).exists():
        return send_from_directory(STATIC_FOLDER, path)
    
    # 对于所有其他路由，返回 index.html（支持前端路由）
    index_path = STATIC_FOLDER / 'index.html'
    if index_path.exists():
        return send_file(index_path)
    
    return {'error': 'Frontend not found'}, 404

if __name__ == '__main__':
    port = int(os.getenv('BACKEND_PORT', 5000))
    debug = False  # 生产环境不使用 debug 模式
    
    print("\n" + "=" * 60)
    print("   SlideAI 智演 - AI PPT 生成器")
    print("=" * 60)
    print(f"服务地址: http://localhost:{port}")
    print(f"数据库: {app.config.get('SQLALCHEMY_DATABASE_URI', 'N/A')}")
    print("=" * 60 + "\n")
    
    app.run(host='0.0.0.0', port=port, debug=debug, use_reloader=False)
