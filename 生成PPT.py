"""
SlideAI 本地版 - 独立PPT生成工具
用法: python 生成PPT.py
"""
import os
import sys
import json
import re
import shutil
import tempfile
import time
from pathlib import Path

# 设置工作目录为脚本所在目录
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
# 1. AI 文本提供商 (国内8厂商)
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

def get_text_provider():
    """根据环境变量创建文本AI提供商"""
    source = os.getenv('TEXT_MODEL_SOURCE', 'deepseek')
    model = os.getenv('TEXT_MODEL', '')
    api_key = os.getenv(f'{source.upper()}_API_KEY', '')

    if not api_key:
        print(f"[错误] 未找到 {source.upper()}_API_KEY，请在 .env 文件中配置")
        sys.exit(1)

    config = VENDOR_CONFIG.get(source, VENDOR_CONFIG['deepseek'])
    if not model:
        model = config['default_model']

    try:
        from openai import OpenAI
    except ImportError:
        print("[错误] 未安装 openai 库，正在安装...")
        os.system(f'"{SCRIPT_DIR / "python" / "python.exe"}" -m pip install openai -q')
        from openai import OpenAI

    client = OpenAI(api_key=api_key, base_url=config['base_url'])

    def generate(prompt, system_prompt=''):
        messages = []
        if system_prompt:
            messages.append({'role': 'system', 'content': system_prompt})
        messages.append({'role': 'user', 'content': prompt})
        resp = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.7,
            max_tokens=8192,
        )
        text = resp.choices[0].message.content or ''
        # 去掉 <think> 标签
        text = re.sub(r'<think>.*?</think>\s*', '', text, flags=re.DOTALL).strip()
        return text

    return generate


# ============================================================
# 2. 设计配置
# ============================================================
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


# ============================================================
# 3. 提示词模板
# ============================================================

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

STRATEGIST_USER_PROMPT = """请为以下主题设计PPT：

主题：{topic}

画布格式：{canvas_format} ({width}x{height})

语言：{language}

请严格按照JSON格式返回设计规划。"""

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

EXECUTOR_USER_PROMPT = """请生成第 {page_index} 页的SVG幻灯片：

页面标题：{title}
页面类型：{page_type}
页面描述：{brief}

设计规范：
- 画布尺寸：{width}x{height}，viewBox: {viewbox}
- 主色：{primary}
- 辅色：{secondary}
- 强调色：{accent}
- 深色文字：{text_dark}
- 浅色文字：{text_light}
- 背景色：{background}
- 标题字号：{title_size}px
- 正文字号：{body_size}px
- 标题字体：{title_font}
- 正文字体：{body_font}

请生成完整的SVG代码。"""


# ============================================================
# 4. 核心流程函数
# ============================================================

def parse_json_response(text):
    """从AI回复中提取JSON"""
    # 尝试直接解析
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 尝试从代码块提取
    m = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # 尝试从花括号提取
    start = text.find('{')
    end = text.rfind('}')
    if start != -1 and end > start:
        try:
            return json.loads(text[start:end+1])
        except json.JSONDecodeError:
            pass
    return None


def extract_svg(text):
    """从AI回复中提取SVG"""
    # 尝试正则匹配
    m = re.search(r'(<svg[\s\S]*?</svg>)', text)
    if m:
        return m.group(1)
    # 尝试代码块
    m = re.search(r'```(?:svg|xml)?\s*\n(.*?)\n```', text, re.DOTALL)
    if m:
        content = m.group(1).strip()
        if content.startswith('<svg'):
            return content
    # 尝试从<svg开始
    idx = text.find('<svg')
    if idx != -1:
        return text[idx:]
    return None


def run_strategist(generate_text, topic, canvas_format='ppt169', style='general', language='zh'):
    """Phase 1: 设计师 - 生成设计规划"""
    canvas = CANVAS_FORMATS.get(canvas_format, CANVAS_FORMATS['ppt169'])
    colors = DESIGN_COLORS.get(style, DESIGN_COLORS['general'])

    user_prompt = STRATEGIST_USER_PROMPT.format(
        topic=topic,
        canvas_format=canvas_format,
        width=canvas['width'],
        height=canvas['height'],
        language='中文' if language == 'zh' else 'English',
    )

    print("[1/4] 正在生成设计规划...")
    raw = generate_text(user_prompt, STRATEGIST_SYSTEM_PROMPT)
    spec = parse_json_response(raw)

    if not spec or 'design_spec' not in spec:
        print("[警告] AI返回格式不正确，使用默认设计")
        spec = create_default_spec(topic, canvas, colors)

    design_spec = spec['design_spec']

    # 确保颜色完整
    if 'colors' not in design_spec or not design_spec['colors']:
        design_spec['colors'] = colors
    else:
        for k, v in colors.items():
            if k not in design_spec['colors'] or not design_spec['colors'][k]:
                design_spec['colors'][k] = v

    # 确保canvas完整
    if 'canvas' not in design_spec or not design_spec['canvas']:
        design_spec['canvas'] = canvas

    # 确保typography完整
    if 'typography' not in design_spec or not design_spec['typography']:
        design_spec['typography'] = {
            'title_font': 'Microsoft YaHei',
            'body_font': 'Microsoft YaHei',
            'title_size': FONT_SIZES['title'],
            'heading_size': FONT_SIZES['heading'],
            'body_size': FONT_SIZES['body'],
        }

    pages = design_spec.get('pages', [])
    print(f"  -> 生成了 {len(pages)} 个页面的设计规划")
    for p in pages:
        print(f"     [{p.get('type', '?')}] {p.get('title', '无标题')}")

    return design_spec


def create_default_spec(topic, canvas, colors):
    """创建默认设计规划（AI失败时的后备）"""
    return {
        'design_spec': {
            'pages': [
                {'index': 0, 'type': 'cover', 'title': topic, 'brief': f'{topic} 演示文稿封面', 'layout': 'cover'},
                {'index': 1, 'type': 'toc', 'title': '目录', 'brief': '演示文稿内容概览', 'layout': 'toc'},
                {'index': 2, 'type': 'content', 'title': '核心内容', 'brief': f'{topic}的核心要点介绍', 'layout': 'content'},
                {'index': 3, 'type': 'content', 'title': '详细分析', 'brief': f'{topic}的深入分析', 'layout': 'content'},
                {'index': 4, 'type': 'summary', 'title': '总结', 'brief': '关键要点回顾与展望', 'layout': 'summary'},
            ],
            'colors': colors,
            'typography': {
                'title_font': 'Microsoft YaHei',
                'body_font': 'Microsoft YaHei',
                'title_size': 36,
                'heading_size': 24,
                'body_size': 18,
            },
            'canvas': canvas,
            'style_notes': '专业简洁的设计风格',
        }
    }


def generate_page_svg(generate_text, page_info, design_spec, page_index):
    """Phase 2: 执行师 - 为每个页面生成SVG"""
    canvas = design_spec.get('canvas', CANVAS_FORMATS['ppt169'])
    colors = design_spec.get('colors', DESIGN_COLORS['general'])
    typography = design_spec.get('typography', {})

    user_prompt = EXECUTOR_USER_PROMPT.format(
        page_index=page_index + 1,
        title=page_info.get('title', '未命名'),
        page_type=page_info.get('type', 'content'),
        brief=page_info.get('brief', ''),
        width=canvas.get('width', 1280),
        height=canvas.get('height', 720),
        viewbox=canvas.get('viewbox', '0 0 1280 720'),
        primary=colors.get('primary', '#2563EB'),
        secondary=colors.get('secondary', '#7C3AED'),
        accent=colors.get('accent', '#F59E0B'),
        text_dark=colors.get('text_dark', '#1F2937'),
        text_light=colors.get('text_light', '#6B7280'),
        background=colors.get('background', '#FFFFFF'),
        title_size=typography.get('title_size', 36),
        body_size=typography.get('body_size', 18),
        title_font=typography.get('title_font', 'Microsoft YaHei'),
        body_font=typography.get('body_font', 'Microsoft YaHei'),
    )

    system_prompt = EXECUTOR_SYSTEM_PROMPT.format(
        svg_constraints=SVG_CONSTRAINTS,
        viewbox=canvas.get('viewbox', '0 0 1280 720'),
    )

    raw = generate_text(user_prompt, system_prompt)
    svg = extract_svg(raw)

    if not svg:
        print(f"  [警告] 第{page_index+1}页SVG提取失败，使用后备方案")
        svg = create_fallback_svg(page_info, canvas, colors, typography)

    return svg


def create_fallback_svg(page_info, canvas, colors, typography):
    """后备SVG生成"""
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


def finalize_svgs(project_dir):
    """Phase 3: SVG后处理"""
    print("[3/4] 正在处理SVG...")
    svg_output = project_dir / 'svg_output'
    svg_final = project_dir / 'svg_final'

    if not svg_output.exists():
        print("[错误] svg_output目录不存在")
        return False

    # 删除旧的svg_final
    if svg_final.exists():
        shutil.rmtree(svg_final)

    # 复制svg_output到svg_final
    shutil.copytree(svg_output, svg_final)

    # 尝试导入并运行finalize
    try:
        sys.path.insert(0, str(SCRIPT_DIR / 'backend'))
        from services.pptmaster.finalize_svg import finalize_project
        options = {
            'embed_icons': True, 'crop_images': True, 'fix_aspect': True,
            'embed_images': True, 'flatten_text': True, 'fix_rounded': True,
        }
        result = finalize_project(project_dir, options, quiet=True)
        print(f"  -> SVG后处理{'成功' if result else '部分完成'}")
        return True
    except Exception as e:
        print(f"  [警告] finalize处理出错: {e}")
        print("  -> 使用原始SVG继续")
        return True


def convert_to_pptx(project_dir, canvas_format='ppt169', output_path=None):
    """Phase 4: SVG转PPTX"""
    print("[4/4] 正在生成PPTX...")
    svg_dir = project_dir / 'svg_final'
    if not svg_dir.exists():
        svg_dir = project_dir / 'svg_output'

    svg_files = sorted(svg_dir.glob('*.svg'))
    if not svg_files:
        print("[错误] 没有找到SVG文件")
        return None

    print(f"  -> 找到 {len(svg_files)} 个SVG文件")

    if not output_path:
        output_path = project_dir / 'output.pptx'

    try:
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
            size_kb = output_path.stat().st_size / 1024
            print(f"  -> PPTX生成成功: {output_path}")
            print(f"  -> 文件大小: {size_kb:.1f} KB")
            return output_path
        else:
            print("[错误] PPTX生成失败")
            return None
    except Exception as e:
        print(f"[错误] PPTX转换出错: {e}")
        import traceback
        traceback.print_exc()
        return None


# ============================================================
# 5. 主流程
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description='SlideAI 本地版 - PPT生成工具')
    parser.add_argument('topic', nargs='?', help='PPT主题')
    parser.add_argument('--style', default='tech', choices=['general', 'tech', 'consulting', 'academic'], help='设计风格')
    parser.add_argument('--canvas', default='ppt169', choices=['ppt169', 'ppt43'], help='画布格式')
    parser.add_argument('--lang', default='zh', choices=['zh', 'en'], help='语言')
    args, _ = parser.parse_known_args()

    print("=" * 50)
    print("  SlideAI 本地版 - PPT生成工具")
    print("=" * 50)
    print()

    # 获取主题
    topic = args.topic
    if not topic:
        try:
            topic = input("请输入PPT主题: ").strip()
        except EOFError:
            print("请通过命令行参数指定主题: python 生成PPT.py '主题'")
            return
    if not topic:
        print("主题不能为空")
        return

    canvas_format = args.canvas
    style = args.style
    language = args.lang

    print(f"主题: {topic}")
    print(f"画布: {canvas_format}")
    print(f"风格: {style}")
    print(f"语言: {language}")

    print()
    print("-" * 50)

    # 创建AI提供商
    generate_text = get_text_provider()

    # 创建项目目录
    timestamp = int(time.time())
    project_dir = Path.home() / 'Desktop' / f'PPT_{timestamp}'
    svg_output = project_dir / 'svg_output'
    svg_output.mkdir(parents=True, exist_ok=True)

    # Phase 1: 设计师
    design_spec = run_strategist(generate_text, topic, canvas_format, style, language)
    pages = design_spec.get('pages', [])

    if not pages:
        print("[错误] 没有生成任何页面")
        return

    # Phase 2: 执行师 - 逐页生成SVG
    print(f"\n[2/4] 正在生成 {len(pages)} 页SVG...")
    for i, page in enumerate(pages):
        print(f"  -> 第{i+1}/{len(pages)}页: {page.get('title', '未命名')}")
        svg = generate_page_svg(generate_text, page, design_spec, i)

        # 保存SVG
        page_type = page.get('type', 'content')
        filename = f"{i+1:02d}_{page_type}.svg"
        (svg_output / filename).write_text(svg, encoding='utf-8')
        print(f"     保存: {filename}")

    # Phase 3: SVG后处理
    print()
    finalize_svgs(project_dir)

    # Phase 4: 转PPTX
    print()
    output_path = convert_to_pptx(project_dir, canvas_format)

    print()
    print("=" * 50)
    if output_path:
        print(f"  完成! PPT已保存到:")
        print(f"  {output_path}")
    else:
        print("  生成过程完成，但PPTX转换失败")
        print(f"  SVG文件保存在: {svg_output}")
    print("=" * 50)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n已取消")
    except Exception as e:
        print(f"\n[错误] {e}")
        import traceback
        traceback.print_exc()
