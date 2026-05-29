# -*- coding: utf-8 -*-
"""项目配置 - 部署时按需修改"""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 启动时若存在 .env 则读取（生产环境用，零依赖实现）
_env_path = os.path.join(BASE_DIR, ".env")
if os.path.exists(_env_path):
    with open(_env_path, "r", encoding="utf-8") as _f:
        for _line in _f:
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip().strip('"').strip("'")
            os.environ.setdefault(_k, _v)


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "youth-station-secret-change-me-please")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.join(BASE_DIR, "data", "app.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024  # 32MB
    ALLOWED_UPLOAD_EXT = {"png", "jpg", "jpeg", "gif", "webp", "pdf", "doc", "docx", "xlsx", "xls", "txt", "zip"}

    # ===== 高德地图 Key =====
    # 请在 .env 文件中配置，避免提交到代码仓库
    AMAP_JS_KEY = os.environ.get("AMAP_JS_KEY", "")
    AMAP_JS_SECRET = os.environ.get("AMAP_JS_SECRET", "")
    AMAP_WEB_KEY = os.environ.get("AMAP_WEB_KEY", "")

    # 默认管理员（首次启动会自动创建，请尽快修改密码）
    DEFAULT_ADMIN_USER = os.environ.get("DEFAULT_ADMIN_USER", "admin")
    DEFAULT_ADMIN_PASS = os.environ.get("DEFAULT_ADMIN_PASS", "admin123")

    # ===== ⑨ AI 驿站助手 =====
    # 推荐 DeepSeek（极便宜，国内稳定）：https://platform.deepseek.com
    # 兼容 OpenAI / Qwen / Moonshot / 智谱 GLM 等 OpenAI 协议的服务
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.deepseek.com/v1")
    AI_MODEL = os.environ.get("AI_MODEL", "deepseek-chat")
