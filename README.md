# 🐬 全国青年人才驿站聚合查询平台

> 应届毕业生免费驿站 · 大湾区政策速查 · AI 智能助手「湾湾鲸」

[![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-3.0+-lightgrey.svg)](https://flask.palletsprojects.com/)
[![License](https://img.shields.io/badge/license-Private-red.svg)]()
[![Status](https://img.shields.io/badge/status-Production_Ready-green.svg)]()

一个面向应届毕业生的青年人才驿站聚合查询网站，覆盖**珠三角 7 城市 180+ 驿站**。前端蓝色科技风（昼/夜双主题），驿站码登录鉴权，集成高德地图、政策速查、数据看板和**多模型多模态 AI 智能助手**。

---

## 🚀 在线预览

### 🌐 直接访问（无需任何配置）

| 环境 | 地址 | 说明 |
|------|------|------|
| **生产站点** | [**https://yuexinys.cn**](https://yuexinys.cn) | 正式上线，HTTPS 加密，ICP 已备案 |
| **开发预览** | [*Cloud Studio 临时链接*] | 每次启动工作区会变，详见下方 |

> 💡 **普通用户**：直接点击上方「生产站点」链接即可使用，无需安装任何东西。

---

### 🛠️ 开发者：一键打开云端 IDE

[![Open in Cloud Studio](https://cs-res.codehub.cn/common/assets/icon-badge.svg)](https://cloudstudio.net/?gitUrl=https%3A%2F%2Fgithub.com%2FFalgan678%2Fyouth-station.git)
[![Open in Gitpod](https://img.shields.io/badge/Gitpod-Ready--to--Code-908a85?logo=gitpod)](https://gitpod.io/#https://github.com/Falgan678/youth-station)
[![Open in GitHub Codespaces](https://img.shields.io/badge/Codespaces-Open-blue?logo=github)](https://codespaces.new/Falgan678/youth-station)

> **🎯 推荐 Cloud Studio**（腾讯云出品，国内访问快，免费）：
> 点击上方按钮 → 登录腾讯云 → 选择「Python」基础模板 → 自动 clone 仓库 → 配置 `.env`（填 AI Key）→ 终端跑 `cd web && pip install -r requirements.txt && python app.py` → 点右侧"端口转发"打开 5000 预览
>
> 如果仍 404，可手动操作：访问 [cloudstudio.net](https://cloudstudio.net) → 工作空间 → 新建 → 选 **「从 Git 仓库导入」** → 粘贴 `https://github.com/Falgan678/youth-station.git`



---

## ✨ 核心功能

### 🏠 驿站查询
- **180+ 真实驿站**：广州/深圳/东莞/佛山/珠海/中山/惠州
- **高德地图一键定位**（兼容 WebGL 与 Canvas，1.4 版本稳定渲染）
- **多维筛选**：城市 / 区域 / 关键词
- **驿站详情页**：富文本入住指引、申请条件、所需材料、联系电话、申请链接

### 🎫 驿站码鉴权
- 后台批量生成驿站码
- 学校/机构分发，应届生凭码登录
- 支持过期时间、使用次数限制、启用/停用
- 完整访问日志（IP / UA / 行为埋点）

### 📋 政策速查
- 各市人才认定 / 生活补贴 / 租房补贴 / 落户 / 创业扶持
- 一键直达官方申报入口

### 📊 多维数据看板
- 总览：PV / UV / 驿站数 / 驿站码使用率
- **转化漏斗**：访问 → 详情 → 申请点击
- **城市健康度**：各市驿站完整度评分
- **Top 10 热门驿站**

### 🤖 AI 助手「湾湾鲸」
- **🎨 自定义吉祥物**：粤港澳大湾区粉色海豚 SVG，3 状态动画（呼吸/思考/说话）
- **💬 多会话管理**：左侧抽屉显示历史对话，可新建/切换/重命名/删除/清空
- **🔄 多模型切换**：内置 26 个主流大模型预设
  - 国内：DeepSeek / 腾讯混元 / 字节豆包 / 通义千问 / Kimi / GLM / 文心 / 星火 …
  - 国外：GPT-5 / GPT-4o / Claude Opus / Gemini Pro …
  - 智能体：腾讯 ADP / 百度灵境 / 豆包智能体
- **🌊 流式输出**：SSE 协议打字机效果
- **🌐 联网搜索**：DuckDuckGo + 模型自带联网（如混元 Turbo S）
- **📚 多模态知识库 RAG**：
  - 支持 PDF / Word / TXT / Markdown / **图片** / **网页 URL** / 文本笔记
  - jieba 中文分词 + BM25 检索
  - 自动切块（500 字 + 80 字重叠）
- **🖼️ 图片视觉理解**：
  - 用户在浮窗**拖拽 / 粘贴 / 上传**图片提问
  - 调智谱 **GLM-4V-Flash**（免费）OCR + 内容理解
  - AI 看图后结合知识库精准回答（"这份录用通知能用来申请深圳驿站吗？"）
- **📖 引文溯源**：
  - 答案中带 `[1] [2]` 角标，hover 显示资料卡片
  - **前台脱敏**：仅显示标题 + 类型 + 120 字预览，不能查看原文
  - **后台完整**：管理员可查看完整切块、原文档、命中关键词
  - **审计日志**：每次问答的引文记录

### 🌗 昼/夜双主题
- 右上角悬浮按钮一键切换
- 自动跟随系统偏好
- localStorage 持久化记忆

---

## 🛠 技术栈

| 层 | 技术 |
|----|------|
| 后端 | **Python 3.10+ / Flask 3 / Flask-SQLAlchemy / Flask-Login** |
| 数据库 | SQLite（生产可平滑迁 PostgreSQL/MySQL） |
| 前端 | 原生 HTML/CSS/JS（无构建依赖） + 高德 JS API 1.4 + Quill 富文本 |
| 检索 | **jieba 分词 + BM25**（轻量服务器友好，无向量数据库） |
| 文档解析 | pypdf · python-docx · BeautifulSoup |
| 图片处理 | Pillow + GLM-4V-Flash 视觉模型 |
| 部署 | Gunicorn + Nginx + systemd |

---

## 🚀 快速开始

### 1. 克隆 & 安装依赖

```bash
git clone https://github.com/<your-username>/youth-station.git
cd youth-station/web
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate # Linux/Mac
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你自己的 Key
```

需要的 Key：
- **高德地图 Key**：https://lbs.amap.com/（必需）
- **AI Key**：DeepSeek 或任意 OpenAI 兼容服务（推荐 [DeepSeek](https://platform.deepseek.com)）

### 3. 启动

```bash
python app.py
```

打开 http://localhost:5000

### 4. 默认账号

| 入口 | 凭据 |
|------|------|
| 前台 | 驿站码 `DEMO2026`（启动后自动创建）或后台分发 |
| 后台 `/admin` | `admin` / `admin123` ⚠️ **首次登录请立即修改** |

### 5. 导入驿站数据（可选）

```bash
python seed_from_excel.py  # 导入项目根的 7 个 Excel 文件
```

或在后台 `/admin/stations` 下载模板后批量上传。

---

## 📦 项目结构

```
青年驿站/
├── README.md
├── PRD.md                    # 产品需求文档
├── .gitignore
└── web/
    ├── app.py                # Flask 主应用（路由）
    ├── config.py             # 配置（读 .env）
    ├── models.py             # 数据模型（10 张表）
    ├── utils.py              # 工具：地理编码 / Excel / AI 流式
    ├── kb_ingest.py          # 知识库解析 + BM25 检索 + 视觉模型
    ├── seed_from_excel.py    # 数据导入脚本
    ├── add_ai_provider.py    # 命令行添加 AI 服务
    ├── requirements.txt
    ├── .env.example
    ├── templates/            # Jinja2 模板（18 个）
    ├── static/css/           # portal.css + admin.css（双主题）
    ├── data/                 # SQLite 库（gitignore）
    ├── uploads/              # 用户上传文件（gitignore）
    └── deploy/               # 部署配置（nginx / systemd / 上传脚本）
```

---

## 🌐 部署到生产

详见 `web/deploy/DEPLOY.md`。简要：

```bash
# 服务器上
pip install -r requirements.txt
gunicorn -w 4 -b 127.0.0.1:5000 'app:create_app()'
```

Nginx 配置 + systemd 服务文件已准备在 `web/deploy/` 目录。

---

## 📄 许可

私有项目（Private），未经授权不得复制、分发或商用。

---

## 💖 致谢

- 全国各地人才驿站官方公开数据
- 高德开放平台
- 智谱 BigModel（GLM 系列免费 API）
- DeepSeek、腾讯混元、字节豆包等国产大模型

---

> 🐬 _湾湾鲸来啦！希望每位毕业生都能找到温暖的「驿站」。_
