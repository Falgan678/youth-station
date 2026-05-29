# -*- coding: utf-8 -*-
"""数据库模型"""
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()


class Admin(UserMixin, db.Model):
    """后台管理员"""
    __tablename__ = "admin"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, raw: str):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw: str) -> bool:
        return check_password_hash(self.password_hash, raw)


class Station(db.Model):
    """青年驿站"""
    __tablename__ = "station"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, index=True)
    province = db.Column(db.String(32), index=True, default="广东省")
    city = db.Column(db.String(32), index=True)        # 例：佛山市
    district = db.Column(db.String(32), index=True)    # 例：禅城区
    address = db.Column(db.String(400))
    lng = db.Column(db.Float)  # 高德经度
    lat = db.Column(db.Float)  # 高德纬度
    # 申请入住指导 - 富文本 HTML（支持图片/链接/文件嵌入）
    guide_html = db.Column(db.Text)
    # 备注（特殊要求）
    remark = db.Column(db.Text)
    # 附件 JSON：[{name, url, type}]
    attachments = db.Column(db.Text, default="[]")
    # 来源文件夹（如"佛山青年人才驿站"）
    folder = db.Column(db.String(120))
    location_code = db.Column(db.String(64))  # 兼容工作地图位置编码

    # ===== 一键申请直达：结构化字段 =====
    contact_name = db.Column(db.String(64))           # 联系人姓名
    contact_phone = db.Column(db.String(32))          # 联系电话
    apply_url = db.Column(db.String(500))             # 申请链接（小程序/H5）
    wechat_qr = db.Column(db.String(500))             # 微信公众号二维码图片 URL
    requirements = db.Column(db.Text, default="[]")   # 申请条件 JSON 数组：["应届毕业生","本科及以上"]
    materials = db.Column(db.Text, default="[]")      # 所需材料 JSON 数组：["身份证","毕业证","录用证明"]
    free_days = db.Column(db.Integer)                 # 免费入住天数

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        import json
        try:
            atts = json.loads(self.attachments or "[]")
        except Exception:
            atts = []
        try:
            reqs = json.loads(self.requirements or "[]")
        except Exception:
            reqs = []
        try:
            mats = json.loads(self.materials or "[]")
        except Exception:
            mats = []
        return {
            "id": self.id,
            "name": self.name,
            "province": self.province,
            "city": self.city,
            "district": self.district,
            "address": self.address,
            "lng": self.lng,
            "lat": self.lat,
            "guide_html": self.guide_html or "",
            "remark": self.remark or "",
            "attachments": atts,
            "folder": self.folder,
            "location_code": self.location_code,
            "contact_name": self.contact_name or "",
            "contact_phone": self.contact_phone or "",
            "apply_url": self.apply_url or "",
            "wechat_qr": self.wechat_qr or "",
            "requirements": reqs,
            "materials": mats,
            "free_days": self.free_days,
        }


class AccessCode(db.Model):
    """毕业生驿站码"""
    __tablename__ = "access_code"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(32), unique=True, nullable=False, index=True)
    remark = db.Column(db.String(200))           # 分发对象备注（学校/姓名）
    enabled = db.Column(db.Boolean, default=True)
    expire_at = db.Column(db.DateTime)           # 可空 = 永久
    used_count = db.Column(db.Integer, default=0)
    last_used_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self) -> bool:
        if not self.enabled:
            return False
        if self.expire_at and datetime.utcnow() > self.expire_at:
            return False
        return True


class AccessLog(db.Model):
    """访问统计 - 按日聚合"""
    __tablename__ = "access_log"
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.String(10), index=True)   # YYYY-MM-DD
    ip = db.Column(db.String(64), index=True)
    code_id = db.Column(db.Integer, db.ForeignKey("access_code.id"), nullable=True)
    user_agent = db.Column(db.String(300))
    # 行为埋点：page_view / detail_view / apply_click / policy_view
    event = db.Column(db.String(32), index=True, default="page_view")
    station_id = db.Column(db.Integer, db.ForeignKey("station.id"), nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CityPolicy(db.Model):
    """各城市的政策入口（人才补贴、租房补贴、落户等）"""
    __tablename__ = "city_policy"
    id = db.Column(db.Integer, primary_key=True)
    city = db.Column(db.String(32), index=True, nullable=False)   # 例：广州市
    category = db.Column(db.String(32), index=True)                # 例：人才认定/生活补贴/租房补贴/落户/创业扶持
    title = db.Column(db.String(200), nullable=False)              # 例：广州市青年人才认定申报入口
    description = db.Column(db.String(500))                        # 简短说明（可空）
    url = db.Column(db.String(500), nullable=False)                # 跳转链接
    icon = db.Column(db.String(16))                                # emoji 图标
    sort = db.Column(db.Integer, default=0)                        # 显示顺序，越小越前
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "city": self.city,
            "category": self.category or "",
            "title": self.title,
            "description": self.description or "",
            "url": self.url,
            "icon": self.icon or "📋",
            "sort": self.sort,
        }


class AIProvider(db.Model):
    """AI 模型服务配置（支持多服务商切换）"""
    __tablename__ = "ai_provider"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)        # 显示名 "DeepSeek-V3"
    provider_type = db.Column(db.String(32), default="openai")  # openai / tencent_adp / hunyuan
    base_url = db.Column(db.String(300))                   # OpenAI 兼容协议的 base url
    api_key = db.Column(db.String(300))                    # API Key
    model = db.Column(db.String(64))                       # 模型名 deepseek-chat
    extra_config = db.Column(db.Text)                      # JSON 额外字段（如 ADP 的 bot_app_key、agent_id 等）
    web_search = db.Column(db.Boolean, default=False)      # 是否启用联网（模型自带 / 服务端搜索注入）
    sort = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict_public(self):
        """暴露给前端的公开信息（不含 Key）"""
        return {
            "id": self.id,
            "name": self.name,
            "provider_type": self.provider_type,
            "model": self.model or "",
            "web_search": self.web_search,
            "is_default": self.is_default,
        }


class KnowledgeEntry(db.Model):
    """通用知识库（FAQ / 入住须知 / 常见问题）"""
    __tablename__ = "knowledge_entry"
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(64), index=True)        # 申请流程 / 入住须知 / 政策解读 / 注意事项
    question = db.Column(db.String(500), nullable=False)
    answer = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.String(300))                   # 用空格/逗号分隔，便于检索
    sort = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ============================================================
#  ⑩ 多模态知识库（升级版）
# ============================================================
class KnowledgeDoc(db.Model):
    """知识库主表：一份原始资料（FAQ/PDF/Word/TXT/MD/URL/笔记/图片/音频）"""
    __tablename__ = "knowledge_doc"
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    doc_type = db.Column(db.String(20), index=True, default="note")
    # faq / doc / url / note / image / audio
    category = db.Column(db.String(64), index=True)        # 申请流程/入住须知/政策...
    source_url = db.Column(db.String(800))                 # 当 doc_type=url 时
    file_path = db.Column(db.String(500))                  # 文件相对路径（uploads/kb/xxx.pdf）
    file_name = db.Column(db.String(300))                  # 原始文件名
    mime = db.Column(db.String(80))
    size = db.Column(db.Integer)
    summary = db.Column(db.Text)                           # 自动摘要（用于前台引文卡片显示）
    status = db.Column(db.String(20), default="pending")   # pending/parsing/ready/failed
    error_msg = db.Column(db.String(500))
    chunk_count = db.Column(db.Integer, default=0)
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks = db.relationship("KnowledgeChunk", backref="doc", lazy="dynamic",
                              cascade="all, delete-orphan")

    TYPE_LABEL = {
        "faq": "常见问答",
        "doc": "文档",
        "url": "网页",
        "note": "笔记",
        "image": "图片",
        "audio": "音频",
    }
    TYPE_ICON = {
        "faq": "💬", "doc": "📄", "url": "🔗",
        "note": "📝", "image": "🖼️", "audio": "🎵",
    }

    def type_label(self):
        return self.TYPE_LABEL.get(self.doc_type, "资料")

    def type_icon(self):
        return self.TYPE_ICON.get(self.doc_type, "📚")


class KnowledgeChunk(db.Model):
    """切块表：检索的最小粒度"""
    __tablename__ = "knowledge_chunk"
    id = db.Column(db.Integer, primary_key=True)
    doc_id = db.Column(db.Integer, db.ForeignKey("knowledge_doc.id"), index=True, nullable=False)
    chunk_index = db.Column(db.Integer, default=0)         # 在原 doc 中的位置序号
    content = db.Column(db.Text, nullable=False)           # 切块文本（用于检索 + 上下文）
    tokens = db.Column(db.Text)                            # 预切好的分词字符串（空格分隔），加速 BM25
    page_no = db.Column(db.Integer)                        # PDF 页码
    section = db.Column(db.String(200))                    # 段落小标题（Word 等）
    enabled = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CitationLog(db.Model):
    """回答引用记录（审计/溯源）"""
    __tablename__ = "citation_log"
    id = db.Column(db.Integer, primary_key=True)
    code_id = db.Column(db.Integer, db.ForeignKey("access_code.id"), nullable=True)
    question = db.Column(db.Text)
    answer = db.Column(db.Text)
    citations = db.Column(db.Text)                          # JSON: [{doc_id, chunk_id, score, snippet}]
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)


# ============================================================
#  ⑪ 多会话管理
# ============================================================
class ChatSession(db.Model):
    """前台 AI 助手的会话（一个驿站码可有多个）"""
    __tablename__ = "chat_session"
    id = db.Column(db.Integer, primary_key=True)
    code_id = db.Column(db.Integer, db.ForeignKey("access_code.id"), index=True, nullable=True)
    visitor_token = db.Column(db.String(64), index=True)   # 未登录情况下的设备标识（保留扩展性）
    title = db.Column(db.String(120), default="新对话")
    last_message = db.Column(db.String(200))                # 最后一条消息预览
    msg_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    messages = db.relationship("ChatMessage", backref="session", lazy="dynamic",
                                cascade="all, delete-orphan",
                                order_by="ChatMessage.id")


class ChatMessage(db.Model):
    """单条消息（user / assistant）"""
    __tablename__ = "chat_message"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("chat_session.id"), index=True, nullable=False)
    role = db.Column(db.String(16))                         # user / assistant
    content = db.Column(db.Text)
    citations = db.Column(db.Text)                          # assistant 消息用：JSON
    provider_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
