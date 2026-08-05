"""
SlideAI 本地版 - Web前端服务
双击启动后访问 http://127.0.0.1:5000
"""
import os
import sys
import json
import re
import shutil
import time
import threading
from pathlib import Path
from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS

# 设置工作目录
SCRIPT_DIR = Path(__file__).resolve().parent
os.chdir(SCRIPT_DIR)

# 加载 .env
def load_env():
    env_file = SCRIPT_DIR / '.env'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8').splitlines():
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip()
                if key and key not in os.environ:
                    os.environ[key] = value

load_env()

# ============================================================
# 复用生成PPT.py的核心逻辑
# ============================================================
VENDOR_CONFIG = {
    'deepseek':    {'base_url': 'https://api.deepseek.com/v1',                'default_model': 'deepseek-chat'},
    'qwen':        {'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'default_model': 'qwen-turbo'},
    'doubao':      {'base_url': 'https://ark.cn-beijing.volces.com/api/v3',   'default_model': 'doubao-pro-256k'},
    'glm':         {'base_url': 'https://open.bigmodel.cn/api/paas/v4',       'default_model': 'glm-4-flash'},
    'siliconflow': {'base_url': 'https://api.siliconflow.cn/v1',              'default_model': 'deepseek-ai/DeepSeek-V3'},
    'sensenova':   {'base_url': 'https://api.sensenova.cn/v1',                'default_model': 'nova-ptc-xl-v1'},
    'minimax':     {'base_url': 'https://api.minimax.chat/v1',                'default_model': 'MiniMax-Text-01'},
    'kimi':        {'base_url': 'https://api.moonshot.cn/v1',                 'default_model': 'moonshot-v1-8k'},
}

CANVAS_FORMATS = {
    'ppt169': {'width': 1280, 'height': 720, 'viewbox': '0 0 1280 720'},
    'ppt43':  {'width': 1024, 'height': 768, 'viewbox': '0 0 1024 768'},
}

DESIGN_COLORS = {
    'tech': {
        'primary': '#00D4FF', 'secondary': '#7B61FF', 'accent': '#FF6B35',
        'text_dark': '#E8ECF1', 'text_light': '#8899AA',
        'background': '#0A0E17', 'background_alt': '#111827',
    },
    'general': {
        'primary': '#2563EB', 'secondary': '#7C3AED', 'accent': '#F59E0B',
        'text_dark': '#1F2937', 'text_light': '#6B7280',
        'background': '#FFFFFF', 'background_alt': '#F3F4F6',
    },
    'consulting': {
        'primary': '#1E40AF', 'secondary': '#0369A1', 'accent': '#DC2626',
        'text_dark': '#111827', 'text_light': '#4B5563',
        'background': '#FFFFFF', 'background_alt': '#EFF6FF',
    },
    'academic': {
        'primary': '#1D4ED8', 'secondary': '#4338CA', 'accent': '#059669',
        'text_dark': '#1E293B', 'text_light': '#64748B',
        'background': '#FFFFFF', 'background_alt': '#F8FAFC',
    },
}

FONT_SIZES = {
    'title_large': 48, 'title': 36, 'title_small': 28,
    'heading': 24, 'subheading': 20, 'body': 18,
    'body_small': 16, 'caption': 14, 'footnote': 12,
}

SVG_CONSTRAINTS = """
SVG技术约束（必须严格遵守）:
- 禁止元素: mask, style, foreignObject, textPath, animate*, script, iframe
- 禁止属性: class, id, onclick等事件处理器
- 禁止模式: @font-face, rgba(), 外部CSS, @import
- 允许的元素: rect, circle, ellipse, line, polyline, polygon, path, text, tspan, image, g, defs, linearGradient, radialGradient
- 字体使用系统字体: Segoe UI, Microsoft YaHei, SimHei
- 所有颜色使用十六进制(#RRGGBB)，不要用rgba
- opacity只用在具体元素上，不要用在<g>组上
"""

STRATEGIST_SYSTEM_PROMPT = """你是一个专业的PPT设计总监。你的任务是根据用户提供的主题，设计一套完整的PPT页面规划。

你需要返回一个JSON对象，包含以下字段：

{{
  "design_spec": {{
    "pages": [
      {{
        "index": 0,
        "type": "cover",
        "title": "封面标题",
        "brief": "封面的简要描述，包括副标题和视觉风格",
        "layout": "cover"
      }},
      {{
        "index": 1,
        "type": "toc",
        "title": "目录",
        "brief": "目录页的内容描述",
        "layout": "toc"
      }},
      {{
        "index": 2,
        "type": "content",
        "title": "章节标题",
        "brief": "该页面要展示的核心内容、要点和视觉元素",
        "layout": "content"
      }}
    ],
    "colors": {{
      "primary": "#主色",
      "secondary": "#辅色",
      "accent": "#强调色",
      "text_dark": "#深色文字",
      "text_light": "#浅色文字",
      "background": "#背景色",
      "background_alt": "#辅助背景色"
    }},
    "typography": {{
      "title_font": "字体名称",
      "body_font": "字体名称",
      "title_size": 36,
      "heading_size": 24,
      "body_size": 18
    }},
    "canvas": {{
      "width": 1280,
      "height": 720,
      "viewbox": "0 0 1280 720"
    }},
    "style_notes": "整体设计风格描述"
  }}
}}

设计要求:
1. 封面页(cover)必须有
2. 目录页(toc)必须有
3. 内容页(content) 3-7页，每页有明确的主题和要点
4. 总结页(summary)可选
5. 每个页面的brief要足够详细，让后续SVG生成有足够信息
6. 颜色搭配要专业、协调
7. 只返回JSON，不要其他文字"""

EXECUTOR_SYSTEM_PROMPT = """你是一个专业的SVG幻灯片设计师。你的任务是根据页面设计规范，生成一个完整的SVG文件作为PPT幻灯片。

{svg_constraints}

SVG设计要求:
1. viewBox必须是 "{viewbox}"
2. 使用<rect>作为背景
3. 使用<text>元素显示文字，不要用<tspan>做换行（每行一个<text>）
4. 颜色使用指定的配色方案
5. 布局要美观、专业、有层次感
6. 每个SVG都是一个完整的幻灯片页面
7. 不要使用任何禁止的元素和属性
8. 文字要有足够的大小和对比度
9. 使用装饰性元素(线条、圆形、矩形)增强视觉效果

只返回SVG代码，不要其他文字。SVG标签以<svg开头，以</svg>结尾。"""

def get_text_provider():
    source = os.getenv('TEXT_MODEL_SOURCE', 'deepseek')
    model = os.getenv('TEXT_MODEL', '')
    api_key = os.getenv(f'{source.upper()}_API_KEY', '')
    if not api_key:
        raise ValueError(f"未找到 {source.upper()}_API_KEY，请在 .env 文件中配置")
    config = VENDOR_CONFIG.get(source, VENDOR_CONFIG['deepseek'])
    if not model:
        model = config['default_model']
    from openai import OpenAI
    client = OpenAI(api_key=api_key, base_url=config['base_url'])

    def generate(prompt, system_prompt=''):
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        resp = client.chat.completions.create(model=model, messages=messages, temperature=0.7, max_tokens=8192)
        text = resp.choices[0].message.content or ''
        text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()
        return text
    return generate

def parse_json_response(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    m = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
    return None

def extract_svg(text):
    m = re.search(r'(<svg[\s\S]*?</svg>)', text)
    if m:
        return m.group(1)
    m = re.search(r'```(?:svg|xml)?\s*\n(.*?)\n```', text, re.DOTALL)
    if m:
        content = m.group(1).strip()
        if content.startswith('<svg'):
            return content
    idx = text.find('<svg')
    if idx != -1:
        return text[idx:]
    return None

def create_fallback_svg(page_info, canvas, colors, typography):
    w = canvas.get('width', 1280)
    h = canvas.get('height', 720)
    bg = colors.get('background', '#FFFFFF')
    primary = colors.get('primary', '#2563EB')
    text_dark = colors.get('text_dark', '#1F2937')
    title = page_info.get('title', '未命名')
    brief = page_info.get('brief', '')
    title_size = typography.get('title_size', 36)
    body_size = typography.get('body_size', 18)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">
  <rect width="{w}" height="{h}" fill="{bg}"/>
  <rect x="0" y="0" width="8" height="{h}" fill="{primary}"/>
  <text x="{w//2}" y="{h//2 - 30}" text-anchor="middle" font-family="Microsoft YaHei" font-size="{title_size}" font-weight="bold" fill="{text_dark}">{title}</text>
  <text x="{w//2}" y="{h//2 + 20}" text-anchor="middle" font-family="Microsoft YaHei" font-size="{body_size}" fill="{text_dark}">{brief[:60]}</text>
</svg>'''

# ============================================================
# 任务管理
# ============================================================
tasks = {}  # task_id -> {status, progress, message, output_path, logs}

def run_generation(task_id, topic, canvas_format, style, language):
    """后台生成PPT"""
    task = tasks[task_id]
    try:
        generate_text = get_text_provider()

        # 创建项目目录
        timestamp = int(time.time())
        project_dir = Path.home() / 'Desktop' / f'PPT_{timestamp}'
        svg_output = project_dir / 'svg_output'
        svg_output.mkdir(parents=True, exist_ok=True)

        # Phase 1: 设计师
        task['message'] = '正在生成设计规划...'
        task['progress'] = 10
        canvas = CANVAS_FORMATS.get(canvas_format, CANVAS_FORMATS['ppt169'])
        colors = DESIGN_COLORS.get(style, DESIGN_COLORS['general'])

        user_prompt = f"请为以下主题设计PPT：\n\n主题：{topic}\n\n画布格式：{canvas_format} ({canvas['width']}x{canvas['height']})\n\n语言：{'中文' if language == 'zh' else 'English'}\n\n请严格按照JSON格式返回设计规划。"
        raw = generate_text(user_prompt, STRATEGIST_SYSTEM_PROMPT)
        spec = parse_json_response(raw)

        if not spec or 'design_spec' not in spec:
            spec = {
                'design_spec': {
                    'pages': [
                        {'index': 0, 'type': 'cover', 'title': topic, 'brief': f'{topic} 演示文稿封面', 'layout': 'cover'},
                        {'index': 1, 'type': 'toc', 'title': '目录', 'brief': '演示文稿内容概览', 'layout': 'toc'},
                        {'index': 2, 'type': 'content', 'title': '核心内容', 'brief': f'{topic}的核心要点', 'layout': 'content'},
                        {'index': 3, 'type': 'content', 'title': '详细分析', 'brief': f'{topic}的深入分析', 'layout': 'content'},
                        {'index': 4, 'type': 'summary', 'title': '总结', 'brief': '关键要点回顾', 'layout': 'summary'},
                    ],
                    'colors': colors,
                    'typography': {'title_font': 'Microsoft YaHei', 'body_font': 'Microsoft YaHei', 'title_size': 36, 'heading_size': 24, 'body_size': 18},
                    'canvas': canvas,
                }
            }

        design_spec = spec['design_spec']
        if 'colors' not in design_spec or not design_spec['colors']:
            design_spec['colors'] = colors
        else:
            for k, v in colors.items():
                if k not in design_spec['colors'] or not design_spec['colors'][k]:
                    design_spec['colors'][k] = v
        if 'canvas' not in design_spec or not design_spec['canvas']:
            design_spec['canvas'] = canvas
        if 'typography' not in design_spec or not design_spec['typography']:
            design_spec['typography'] = {'title_font': 'Microsoft YaHei', 'body_font': 'Microsoft YaHei', 'title_size': 36, 'heading_size': 24, 'body_size': 18}

        pages = design_spec.get('pages', [])
        task['logs'].append(f"设计规划完成: {len(pages)} 个页面")
        task['progress'] = 20

        # Phase 2: 执行师
        for i, page in enumerate(pages):
            task['message'] = f'正在生成第 {i+1}/{len(pages)} 页: {page.get("title", "")}'
            task['progress'] = 20 + int(50 * (i / len(pages)))

            typography = design_spec.get('typography', {})
            canvas_info = design_spec.get('canvas', canvas)
            colors_info = design_spec.get('colors', colors)

            exec_user = f"""请生成第 {i+1} 页的SVG幻灯片：

页面标题：{page.get('title', '未命名')}
页面类型：{page.get('type', 'content')}
页面描述：{page.get('brief', '')}

设计规范：
- 画布尺寸：{canvas_info.get('width', 1280)}x{canvas_info.get('height', 720)}，viewBox: {canvas_info.get('viewbox', '0 0 1280 720')}
- 主色：{colors_info.get('primary', '#2563EB')}
- 辅色：{colors_info.get('secondary', '#7C3AED')}
- 强调色：{colors_info.get('accent', '#F59E0B')}
- 深色文字：{colors_info.get('text_dark', '#1F2937')}
- 浅色文字：{colors_info.get('text_light', '#6B7280')}
- 背景色：{colors_info.get('background', '#FFFFFF')}
- 标题字号：{typography.get('title_size', 36)}px
- 正文字号：{typography.get('body_size', 18)}px
- 标题字体：{typography.get('title_font', 'Microsoft YaHei')}
- 正文字体：{typography.get('body_font', 'Microsoft YaHei')}

请生成完整的SVG代码。"""

            exec_sys = EXECUTOR_SYSTEM_PROMPT.format(
                svg_constraints=SVG_CONSTRAINTS,
                viewbox=canvas_info.get('viewbox', '0 0 1280 720'),
            )

            raw = generate_text(exec_user, exec_sys)
            svg = extract_svg(raw)
            if not svg:
                svg = create_fallback_svg(page, canvas_info, colors_info, typography)

            filename = f"{i+1:02d}_{page.get('type', 'content')}.svg"
            (svg_output / filename).write_text(svg, encoding='utf-8')
            task['logs'].append(f"生成: {filename}")

        task['progress'] = 70
        task['message'] = '正在处理SVG...'

        # Phase 3: SVG后处理
        svg_final = project_dir / 'svg_final'
        if svg_final.exists():
            shutil.rmtree(svg_final)
        shutil.copytree(svg_output, svg_final)

        try:
            sys.path.insert(0, str(SCRIPT_DIR / 'backend'))
            from services.pptmaster.finalize_svg import finalize_project
            options = {'embed_icons': True, 'crop_images': True, 'fix_aspect': True, 'embed_images': True, 'flatten_text': True, 'fix_rounded': True}
            finalize_project(project_dir, options, quiet=True)
            task['logs'].append("SVG后处理完成")
        except Exception as e:
            task['logs'].append(f"SVG后处理跳过: {e}")

        task['progress'] = 85
        task['message'] = '正在生成PPTX...'

        # Phase 4: 转PPTX
        svg_dir = project_dir / 'svg_final'
        svg_files = sorted(svg_dir.glob('*.svg'))
        output_path = project_dir / 'output.pptx'

        sys.path.insert(0, str(SCRIPT_DIR / 'backend' / 'services'))
        from pptmaster.svg_to_pptx.pptx_builder import create_pptx_with_native_svg
        success = create_pptx_with_native_svg(
            svg_files=svg_files,
            output_path=output_path,
            canvas_format=canvas_format,
            verbose=False,
            transition='fade',
            transition_duration=0.5,
            use_native_shapes=True,
        )

        if success and output_path.exists():
            task['status'] = 'done'
            task['message'] = '生成完成!'
            task['progress'] = 100
            task['output_path'] = str(output_path)
            task['logs'].append(f"PPTX生成成功: {output_path.name}")
        else:
            task['status'] = 'error'
            task['message'] = 'PPTX生成失败'

    except Exception as e:
        task['status'] = 'error'
        task['message'] = f'错误: {str(e)}'
        task['logs'].append(f"错误: {e}")

# ============================================================
# Flask 应用
# ============================================================
app = Flask(__name__)
CORS(app)

@app.route('/')
def index():
    return send_from_directory(str(SCRIPT_DIR / 'frontend'), 'index.html')

@app.route('/<path:path>')
def static_files(path):
    file_path = SCRIPT_DIR / 'frontend' / path
    if file_path.exists() and file_path.is_file():
        return send_from_directory(str(SCRIPT_DIR / 'frontend'), path)
    return send_from_directory(str(SCRIPT_DIR / 'frontend'), 'index.html')

@app.route('/api/generate', methods=['POST'])
def api_generate():
    data = request.json or {}
    topic = data.get('topic', '').strip()
    if not topic:
        return jsonify({'error': '请输入主题'}), 400

    canvas_format = data.get('canvas', 'ppt169')
    style = data.get('style', 'tech')
    language = data.get('lang', 'zh')

    task_id = f"task_{int(time.time() * 1000)}"
    tasks[task_id] = {
        'status': 'running',
        'progress': 0,
        'message': '正在启动...',
        'output_path': None,
        'logs': [],
        'topic': topic,
    }

    thread = threading.Thread(target=run_generation, args=(task_id, topic, canvas_format, style, language), daemon=True)
    thread.start()

    return jsonify({'task_id': task_id})

@app.route('/api/task/<task_id>')
def api_task_status(task_id):
    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': '任务不存在'}), 404
    return jsonify({
        'status': task['status'],
        'progress': task['progress'],
        'message': task['message'],
        'logs': task['logs'],
        'output_path': task['output_path'],
    })

@app.route('/api/download/<task_id>')
def api_download(task_id):
    task = tasks.get(task_id)
    if not task or task['status'] != 'done' or not task['output_path']:
        return jsonify({'error': '文件不可用'}), 404
    return send_file(task['output_path'], as_attachment=True, download_name='presentation.pptx')

@app.route('/api/vendors')
def api_vendors():
    return jsonify({
        'vendors': list(VENDOR_CONFIG.keys()),
        'current': os.getenv('TEXT_MODEL_SOURCE', 'deepseek'),
        'has_key': bool(os.getenv(f"{os.getenv('TEXT_MODEL_SOURCE', 'deepseek').upper()}_API_KEY")),
    })

if __name__ == '__main__':
    frontend_dir = SCRIPT_DIR / 'frontend'
    frontend_dir.mkdir(exist_ok=True)

    print("=" * 50)
    print("  SlideAI 本地版 - Web服务")
    print("  访问 http://127.0.0.1:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False)
