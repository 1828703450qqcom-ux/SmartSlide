# SlideAI 本地版 - AI PPT 生成工具

> 基于多厂商大模型的智能 PPT 自动生成工具，支持 Web 界面和命令行两种模式。

输入主题或文档，AI 自动生成结构化大纲、逐页内容、配图描述，并输出可编辑的 `.pptx` 文件。

---

## 功能特性

- **多厂商 AI 支持**：DeepSeek / 通义千问 / 豆包 / 智谱GLM / SiliconFlow / 商汤 / MiniMax / Kimi
- **Web 界面**：Flask + 前端页面，可视化操作
- **命令行模式**：`python 生成PPT.py` 直接生成
- **文档导入**：支持 PDF / Word / PPT / Excel / Markdown 解析
- **多语言输出**：中文 / 英文 / 日文
- **多种设计风格**：科技 / 商务 / 学术 / 创意
- **图片生成**：可选 AI 配图（豆包 Seedream）
- **Docker 部署**：一键启动

---

## 项目结构

```
PPT生成本地版/
├── web_app.py              # Web 服务主程序
├── 生成PPT.py              # 命令行生成工具
├── .env                    # API 密钥配置（不提交）
├── .env.example            # 配置模板
├── backend/                # 后端服务（Flask）
│   ├── app.py              # Flask 应用
│   ├── config.py           # 配置管理
│   ├── controllers/        # API 控制器
│   ├── services/           # 业务逻辑
│   ├── models/             # 数据模型
│   ├── utils/              # 工具函数
│   ├── protected/          # 核心服务模块
│   └── Dockerfile
├── frontend/               # 前端页面
│   ├── index.html          # 主页面
│   ├── assets/             # 静态资源
│   └── templates/          # HTML 模板
└── 启动.bat                # Windows 快捷启动
```

---

## 快速开始

### 方式一：命令行生成

```bash
# 1. 安装依赖
pip install openai python-pptx

# 2. 配置 API 密钥
cp .env.example .env
# 编辑 .env 填入至少一个厂商的 API Key

# 3. 生成 PPT
python 生成PPT.py
```

### 方式二：Web 界面

```bash
# 1. 安装依赖
pip install flask flask-cors openai python-pptx

# 2. 配置 API 密钥
cp .env.example .env

# 3. 启动服务
python web_app.py
# 或双击 启动.bat

# 4. 访问 http://127.0.0.1:5000
```

### 方式三：Docker 部署

```bash
docker-compose up -d
```

---

## API 密钥配置

在 `.env` 文件中填入至少一个厂商的密钥：

| 厂商 | 注册地址 | 环境变量 |
|------|---------|---------|
| DeepSeek | https://platform.deepseek.com/ | `DEEPSEEK_API_KEY` |
| 通义千问 | https://dashscope.console.aliyun.com/ | `QWEN_API_KEY` |
| 豆包 | https://console.volcengine.com/ark | `DOUBAO_API_KEY` |
| 智谱GLM | https://open.bigmodel.cn/ | `GLM_API_KEY` |
| SiliconFlow | https://cloud.siliconflow.cn/ | `SILICONFLOW_API_KEY` |
| 商汤 | https://platform.sensenova.cn/ | `SENSENOVA_API_KEY` |
| MiniMax | https://platform.minimaxi.com/ | `MINIMAX_API_KEY` |
| Kimi | https://platform.moonshot.cn/ | `KIMI_API_KEY` |

然后在 `.env` 中设置文本模型来源：

```bash
TEXT_MODEL_SOURCE=minimax    # 使用 MiniMax
TEXT_MODEL=MiniMax-Text-01
```

---

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | Flask + Python |
| 前端 | HTML + CSS + JavaScript |
| AI 接口 | OpenAI 兼容格式（支持 8 家国内厂商） |
| PPT 生成 | python-pptx |
| 文档解析 | PyMuPDF / pdfplumber / python-docx |
| 部署 | Docker |

---

## License

MIT License
