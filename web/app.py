# -*- coding: utf-8 -*-
"""主应用入口"""
import io
import json
import os
from datetime import datetime, timedelta
from functools import wraps

from flask import (Flask, Response, abort, flash, jsonify, redirect, render_template,
                   request, send_file, send_from_directory, session, url_for)
from flask_login import (LoginManager, current_user, login_required, login_user,
                         logout_user)
from werkzeug.utils import secure_filename

from config import Config
from models import AccessCode, AccessLog, Admin, AIPersona, AIProvider, CityPolicy, KnowledgeEntry, Station, db
from utils import (amap_geocode, build_import_template, export_stations_to_excel,
                   generate_code, parse_city_district, read_stations_from_excel,
                   safe_filename)


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(Config)

    # 确保目录存在
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"]), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), "data"), exist_ok=True)

    db.init_app(app)
    login_manager = LoginManager(app)
    login_manager.login_view = "admin_login"

    @login_manager.user_loader
    def load_user(uid):
        return Admin.query.get(int(uid))

    # ============= 前端：驿站码鉴权 =============
    def code_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            def _unauth():
                # API 请求（路径以 /api/ 开头，或显式要 JSON）：返回 401 JSON
                if request.path.startswith("/api/") or \
                   "application/json" in (request.headers.get("Accept") or ""):
                    return jsonify({"ok": False, "code": "auth_required",
                                    "msg": "请先登录或验证驿站码"}), 401
                # 页面请求：维持原行为，重定向到登录页
                return redirect(url_for("portal_login"))

            cid = session.get("code_id")
            if not cid:
                return _unauth()
            ac = AccessCode.query.get(cid)
            if not ac or not ac.is_valid():
                session.pop("code_id", None)
                return _unauth()
            return view(*args, **kwargs)
        return wrapped

    # ============= 访问统计中间件 =============
    @app.before_request
    def _track_access():
        # 只统计前端主页和详情页 PV
        if request.endpoint in ("portal_index", "portal_detail"):
            try:
                today = datetime.utcnow().strftime("%Y-%m-%d")
                ip = request.headers.get("X-Forwarded-For", request.remote_addr or "")
                ip = ip.split(",")[0].strip()
                evt = "page_view"
                sid = None
                if request.endpoint == "portal_detail":
                    evt = "detail_view"
                    sid = request.view_args.get("sid")
                log = AccessLog(
                    date=today,
                    ip=ip,
                    code_id=session.get("code_id"),
                    user_agent=(request.headers.get("User-Agent") or "")[:300],
                    event=evt,
                    station_id=sid,
                )
                db.session.add(log)
                db.session.commit()
            except Exception:
                db.session.rollback()

    # ============================================================
    # 前端门户
    # ============================================================
    @app.route("/")
    def portal_login():
        if session.get("code_id"):
            return redirect(url_for("portal_index"))
        return render_template("portal_login.html")

    @app.route("/api/portal/login", methods=["POST"])
    def api_portal_login():
        code = (request.json or {}).get("code", "").strip().upper()
        if not code:
            return jsonify({"ok": False, "msg": "请输入驿站码"}), 400
        ac = AccessCode.query.filter_by(code=code).first()
        if not ac or not ac.is_valid():
            return jsonify({"ok": False, "msg": "驿站码无效或已过期"}), 403
        ac.used_count = (ac.used_count or 0) + 1
        ac.last_used_at = datetime.utcnow()
        db.session.commit()
        session["code_id"] = ac.id
        session.permanent = True
        return jsonify({"ok": True})

    @app.route("/logout")
    def portal_logout():
        session.pop("code_id", None)
        return redirect(url_for("portal_login"))

    @app.route("/index")
    @code_required
    def portal_index():
        return render_template(
            "portal_index.html",
            amap_js_key=app.config["AMAP_JS_KEY"],
            amap_js_secret=app.config["AMAP_JS_SECRET"],
        )

    @app.route("/station/<int:sid>")
    @code_required
    def portal_detail(sid):
        s = Station.query.get_or_404(sid)
        return render_template(
            "portal_detail.html",
            station=s.to_dict(),
            amap_js_key=app.config["AMAP_JS_KEY"],
            amap_js_secret=app.config["AMAP_JS_SECRET"],
        )

    # 前端数据 API
    @app.route("/api/stations")
    @code_required
    def api_stations():
        city = request.args.get("city", "").strip()
        district = request.args.get("district", "").strip()
        kw = request.args.get("kw", "").strip()
        q = Station.query
        if city:
            q = q.filter(Station.city == city)
        if district:
            q = q.filter(Station.district == district)
        if kw:
            q = q.filter(db.or_(Station.name.like(f"%{kw}%"), Station.address.like(f"%{kw}%")))
        items = [s.to_dict() for s in q.order_by(Station.city, Station.id).all()]
        return jsonify({"ok": True, "items": items})

    @app.route("/api/cities")
    @code_required
    def api_cities():
        rows = db.session.query(Station.city, Station.district).distinct().all()
        m = {}
        for c, d in rows:
            if not c:
                continue
            m.setdefault(c, set())
            if d:
                m[c].add(d)
        return jsonify({"ok": True, "cities": [{"city": c, "districts": sorted(list(ds))} for c, ds in sorted(m.items())]})

    # 申请按钮埋点
    @app.route("/api/track/apply", methods=["POST"])
    @code_required
    def api_track_apply():
        data = request.json or {}
        sid = data.get("sid")
        channel = data.get("channel") or "unknown"
        try:
            log = AccessLog(
                date=datetime.utcnow().strftime("%Y-%m-%d"),
                ip=(request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip(),
                code_id=session.get("code_id"),
                user_agent=(request.headers.get("User-Agent") or "")[:300],
                event=f"apply_click:{channel}",
                station_id=int(sid) if sid else None,
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"ok": True})

    # ====== ⑤ 政策"傻瓜式"查询 ======
    @app.route("/policy")
    @code_required
    def portal_policy():
        return render_template("portal_policy.html")

    @app.route("/api/policies")
    @code_required
    def api_policies():
        city = request.args.get("city", "").strip()
        q = CityPolicy.query.filter_by(enabled=True)
        if city:
            q = q.filter_by(city=city)
        rows = q.order_by(CityPolicy.city, CityPolicy.sort).all()
        # 按城市分组
        grouped = {}
        for p in rows:
            grouped.setdefault(p.city, []).append(p.to_dict())
            # 顺便记录政策点击 → 这里改成 GET 不埋点；点击转跳由前端单独埋
        return jsonify({"ok": True, "data": grouped})

    @app.route("/api/policies/click", methods=["POST"])
    @code_required
    def api_policy_click():
        data = request.json or {}
        try:
            log = AccessLog(
                date=datetime.utcnow().strftime("%Y-%m-%d"),
                ip=(request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip(),
                code_id=session.get("code_id"),
                user_agent=(request.headers.get("User-Agent") or "")[:300],
                event="policy_view",
                station_id=None,
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()
        return jsonify({"ok": True})

    # ====== ⑨ AI 驿站助手 ======
    @app.route("/api/ai/providers")
    @code_required
    def api_ai_providers():
        """前端拉取可用模型列表（不含 Key）"""
        rows = AIProvider.query.filter_by(enabled=True).order_by(AIProvider.sort, AIProvider.id).all()
        return jsonify({"ok": True, "items": [p.to_dict_public() for p in rows]})

    @app.route("/api/ai/persona")
    @code_required
    def api_ai_persona():
        """前端打开浮窗时拉取湾湾鲸的开场白和示例问题（不暴露 system prompt）。"""
        p = AIPersona.query.filter_by(enabled=True).order_by(AIPersona.id).first()
        if not p:
            # 没配置过：返回内置默认值，避免前端空白
            return jsonify({
                "ok": True,
                "data": {
                    "name": "湾湾鲸",
                    "emoji": "🐬",
                    "tagline": "AI 驿站助手",
                    "greeting": "🐬 <b>湾湾鲸</b>来啦！我是粤港澳大湾区的小海豚，专门帮应届毕业生找驿站、查政策~",
                    "quick_asks": [
                        "我是 2026 届，深圳哪些驿站适合我？",
                        "广州人才补贴怎么申请？",
                        "东莞松山湖驿站联系方式？",
                        "驿站码丢了怎么办？",
                    ],
                },
            })
        return jsonify({"ok": True, "data": p.to_public_dict()})

    @app.route("/api/ai/chat", methods=["POST"])
    @code_required
    def api_ai_chat():
        """非流式（保留兼容）"""
        from utils import ai_chat
        data = request.json or {}
        question = (data.get("question") or "").strip()
        history = data.get("history") or []
        if not question:
            return jsonify({"ok": False, "msg": "请输入问题"}), 400
        try:
            answer = ai_chat(question, history, app.config)
            log = AccessLog(
                date=datetime.utcnow().strftime("%Y-%m-%d"),
                ip=(request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip(),
                code_id=session.get("code_id"),
                user_agent="ai_chat",
                event="ai_chat",
            )
            db.session.add(log)
            db.session.commit()
            return jsonify({"ok": True, "answer": answer})
        except Exception as e:
            return jsonify({"ok": False, "msg": f"AI 服务异常：{e}"}), 500

    @app.route("/api/ai/stream", methods=["POST"])
    @code_required
    def api_ai_stream():
        """流式：SSE 协议（边生成边推送，打字机效果）"""
        from utils import ai_chat_stream, get_active_provider
        from models import ChatSession, ChatMessage
        data = request.json or {}
        question = (data.get("question") or "").strip()
        history = data.get("history") or []
        provider_id = data.get("provider_id")
        use_web = bool(data.get("use_web"))
        use_knowledge = data.get("use_knowledge", True)
        session_id = data.get("session_id")

        if not question:
            return jsonify({"ok": False, "msg": "请输入问题"}), 400

        # 会话：找到/自动创建
        chat_sess = None
        if session_id:
            chat_sess = ChatSession.query.filter_by(
                id=int(session_id), code_id=session.get("code_id")
            ).first()
        if not chat_sess:
            chat_sess = ChatSession(
                code_id=session.get("code_id"),
                title=question[:30] or "新对话",
                msg_count=0,
            )
            db.session.add(chat_sess)
            db.session.commit()

        # 如果前端没传 history，则从 DB 拉最近 8 条
        if not history:
            recent = (ChatMessage.query.filter_by(session_id=chat_sess.id)
                      .order_by(ChatMessage.id.desc()).limit(8).all())
            history = [{"role": m.role, "content": m.content or ""} for m in reversed(recent)]

        # 写入用户消息
        user_msg = ChatMessage(session_id=chat_sess.id, role="user", content=question)
        db.session.add(user_msg)
        chat_sess.msg_count = (chat_sess.msg_count or 0) + 1
        chat_sess.last_message = question[:200]
        if chat_sess.msg_count == 1 and (not chat_sess.title or chat_sess.title == "新对话"):
            chat_sess.title = question[:30]
        db.session.commit()

        provider = get_active_provider(provider_id)
        # 强制 web_search 跟随服务商默认
        if provider and provider.web_search:
            use_web = True

        # 把 provider 数据先取出（避免在生成器里 ORM session 已关闭）
        provider_snap = None
        if provider:
            provider_snap = {
                "id": provider.id,
                "name": provider.name,
                "provider_type": provider.provider_type or "openai",
                "base_url": provider.base_url or "",
                "api_key": provider.api_key or "",
                "model": provider.model or "",
                "extra_config": provider.extra_config or "",
                "web_search": bool(provider.web_search),
            }

        fb_cfg = {
            "AI_API_KEY": app.config.get("AI_API_KEY", ""),
            "AI_BASE_URL": app.config.get("AI_BASE_URL", ""),
            "AI_MODEL": app.config.get("AI_MODEL", ""),
        }

        # 写入埋点
        try:
            log = AccessLog(
                date=datetime.utcnow().strftime("%Y-%m-%d"),
                ip=(request.headers.get("X-Forwarded-For", request.remote_addr or "") or "").split(",")[0].strip(),
                code_id=session.get("code_id"),
                user_agent="ai_chat_stream",
                event="ai_chat",
            )
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()

        # 在 app context 内提前构建好 messages（包含从 DB 拉的 RAG）
        from utils import _build_messages, web_search as _web_search
        kb_use_web = use_web
        # 在 request context 里完成 RAG 构建
        messages, citations = _build_messages(question, history, use_web=kb_use_web, use_knowledge=use_knowledge)

        # 把会话 ID + 引文列表预先编码
        import json as _json_cite
        sess_frame = "data: " + _json_cite.dumps({"type": "session", "session_id": chat_sess.id, "title": chat_sess.title}, ensure_ascii=False) + "\n\n"
        cite_frame = "data: " + _json_cite.dumps({"type": "citations", "items": citations}, ensure_ascii=False) + "\n\n"

        # 写入审计：保存 citation 信息
        try:
            from models import CitationLog
            cl = CitationLog(
                code_id=session.get("code_id"),
                question=question[:500],
                answer="",  # 流式完成后不回写答案，简化实现
                citations=_json_cite.dumps(citations, ensure_ascii=False) if citations else None,
            )
            db.session.add(cl)
            db.session.commit()
        except Exception:
            db.session.rollback()

        # 闭包变量：会话 + 引文，用于在生成器里写库
        _sess_id = chat_sess.id
        _cites_json = _json_cite.dumps(citations, ensure_ascii=False) if citations else None
        _provider_id_for_msg = provider.id if provider else None

        def gen():
            # 先把 session 信息推给前端（用于自动选中）
            yield sess_frame
            # 再推 citations
            yield cite_frame
            answer_buf = []
            for chunk in ai_chat_stream(
                question, history, provider_snap,
                use_web=use_web, use_knowledge=use_knowledge,
                fallback_config=fb_cfg,
                prebuilt_messages=messages,
            ):
                yield chunk
                # 解析 delta 累计 assistant 文本
                if chunk.startswith("data: "):
                    try:
                        obj = _json_cite.loads(chunk[6:].strip())
                        if obj.get("type") == "delta" and obj.get("content"):
                            answer_buf.append(obj["content"])
                    except Exception:
                        pass
            # 流结束 → 把 assistant 消息写入 DB（在新的 app context 里）
            full_answer = "".join(answer_buf).strip()
            if full_answer:
                try:
                    with app.app_context():
                        from models import ChatSession as _CS, ChatMessage as _CM
                        am = _CM(session_id=_sess_id, role="assistant",
                                 content=full_answer, citations=_cites_json,
                                 provider_id=_provider_id_for_msg)
                        db.session.add(am)
                        s = _CS.query.get(_sess_id)
                        if s:
                            s.msg_count = (s.msg_count or 0) + 1
                            s.last_message = full_answer[:200]
                        db.session.commit()
                except Exception:
                    pass

        from flask import Response
        return Response(gen(), mimetype="text/event-stream", headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        })

    # ============================================================
    # ⑪ 多会话管理 API
    # ============================================================
    @app.route("/api/chat/sessions", methods=["GET"])
    @code_required
    def api_chat_sessions():
        """列出当前驿站码的所有会话"""
        from models import ChatSession
        rows = (ChatSession.query.filter_by(code_id=session.get("code_id"))
                .order_by(ChatSession.updated_at.desc()).limit(50).all())
        return jsonify({"ok": True, "items": [
            {
                "id": s.id,
                "title": s.title or "新对话",
                "last_message": s.last_message or "",
                "msg_count": s.msg_count or 0,
                "updated_at": s.updated_at.strftime("%m-%d %H:%M") if s.updated_at else "",
            } for s in rows
        ]})

    @app.route("/api/chat/sessions", methods=["POST"])
    @code_required
    def api_chat_sessions_create():
        """新建空会话"""
        from models import ChatSession
        s = ChatSession(code_id=session.get("code_id"), title="新对话", msg_count=0)
        db.session.add(s)
        db.session.commit()
        return jsonify({"ok": True, "id": s.id, "title": s.title})

    @app.route("/api/chat/sessions/<int:sid>/messages", methods=["GET"])
    @code_required
    def api_chat_session_messages(sid):
        """拉取会话历史消息"""
        from models import ChatSession, ChatMessage
        s = ChatSession.query.filter_by(id=sid, code_id=session.get("code_id")).first()
        if not s:
            return jsonify({"ok": False, "msg": "会话不存在"}), 404
        msgs = ChatMessage.query.filter_by(session_id=sid).order_by(ChatMessage.id).all()
        items = []
        for m in msgs:
            try:
                cites = json.loads(m.citations) if m.citations else []
            except Exception:
                cites = []
            items.append({
                "role": m.role, "content": m.content or "",
                "citations": cites,
                "time": m.created_at.strftime("%H:%M") if m.created_at else "",
            })
        return jsonify({"ok": True, "title": s.title, "items": items})

    @app.route("/api/chat/sessions/<int:sid>/rename", methods=["POST"])
    @code_required
    def api_chat_session_rename(sid):
        from models import ChatSession
        s = ChatSession.query.filter_by(id=sid, code_id=session.get("code_id")).first()
        if not s:
            return jsonify({"ok": False, "msg": "会话不存在"}), 404
        title = (request.json or {}).get("title", "").strip()[:60]
        if not title:
            return jsonify({"ok": False, "msg": "标题不能为空"}), 400
        s.title = title
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/api/chat/sessions/<int:sid>", methods=["DELETE"])
    @code_required
    def api_chat_session_delete(sid):
        from models import ChatSession
        s = ChatSession.query.filter_by(id=sid, code_id=session.get("code_id")).first()
        if not s:
            return jsonify({"ok": False, "msg": "会话不存在"}), 404
        db.session.delete(s)
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/api/chat/sessions/<int:sid>/clear", methods=["POST"])
    @code_required
    def api_chat_session_clear(sid):
        """清空会话内的所有消息（保留会话本身）"""
        from models import ChatSession, ChatMessage
        s = ChatSession.query.filter_by(id=sid, code_id=session.get("code_id")).first()
        if not s:
            return jsonify({"ok": False, "msg": "会话不存在"}), 404
        ChatMessage.query.filter_by(session_id=sid).delete(synchronize_session=False)
        s.msg_count = 0
        s.last_message = ""
        s.title = "新对话"
        db.session.commit()
        return jsonify({"ok": True})

    # ============================================================
    # 后台管理
    # ============================================================
    @app.route("/admin/login", methods=["GET", "POST"])
    def admin_login():
        if request.method == "POST":
            u = request.form.get("username", "").strip()
            p = request.form.get("password", "")
            user = Admin.query.filter_by(username=u).first()
            if user and user.check_password(p):
                login_user(user, remember=True)
                return redirect(url_for("admin_dashboard"))
            flash("账号或密码错误")
        return render_template("admin_login.html")

    @app.route("/admin/logout")
    @login_required
    def admin_logout():
        logout_user()
        return redirect(url_for("admin_login"))

    @app.route("/admin")
    @login_required
    def admin_dashboard():
        from sqlalchemy import func
        today = datetime.utcnow().strftime("%Y-%m-%d")

        # ===== 基础指标 =====
        total_pv = AccessLog.query.filter(AccessLog.event.in_(["page_view", "detail_view"])).count()
        today_pv = AccessLog.query.filter_by(date=today).filter(AccessLog.event.in_(["page_view", "detail_view"])).count()
        today_uv = db.session.query(AccessLog.ip).filter_by(date=today).distinct().count()
        station_count = Station.query.count()
        code_count = AccessCode.query.count()
        active_code_count = AccessCode.query.filter_by(enabled=True).count()
        used_code_count = AccessCode.query.filter(AccessCode.used_count > 0).count()

        # ===== 转化漏斗 =====
        # PV (登录后的访问) → 详情页查看 → 申请按钮点击
        funnel_pv = AccessLog.query.filter(AccessLog.event == "page_view").count()
        funnel_detail = AccessLog.query.filter(AccessLog.event == "detail_view").count()
        funnel_apply = AccessLog.query.filter(AccessLog.event.like("apply_click:%")).count()
        funnel_policy = AccessLog.query.filter_by(event="policy_view").count()
        funnel_ai = AccessLog.query.filter_by(event="ai_chat").count()

        # 转化率
        rate_detail = round(funnel_detail / funnel_pv * 100, 1) if funnel_pv else 0
        rate_apply = round(funnel_apply / funnel_detail * 100, 1) if funnel_detail else 0

        # ===== 14 天趋势（PV/UV/申请点击） =====
        days = []
        for i in range(13, -1, -1):
            d = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
            pv = AccessLog.query.filter_by(date=d).filter(AccessLog.event.in_(["page_view", "detail_view"])).count()
            uv = db.session.query(AccessLog.ip).filter_by(date=d).distinct().count()
            ap = AccessLog.query.filter_by(date=d).filter(AccessLog.event.like("apply_click:%")).count()
            days.append({"date": d, "pv": pv, "uv": uv, "apply": ap})

        # ===== 城市健康度 =====
        city_stats = []
        city_rows = db.session.query(Station.city, func.count(Station.id)).group_by(Station.city).all()
        for city, sn in city_rows:
            if not city:
                continue
            station_ids = [s[0] for s in db.session.query(Station.id).filter_by(city=city).all()]
            views = AccessLog.query.filter(AccessLog.station_id.in_(station_ids)).filter_by(event="detail_view").count() if station_ids else 0
            applies = AccessLog.query.filter(AccessLog.station_id.in_(station_ids)).filter(AccessLog.event.like("apply_click:%")).count() if station_ids else 0
            located = Station.query.filter_by(city=city).filter(Station.lng.isnot(None)).count()
            with_apply = Station.query.filter_by(city=city).filter(
                db.or_(Station.contact_phone.isnot(None), Station.apply_url.isnot(None), Station.wechat_qr.isnot(None))
            ).count()
            city_stats.append({
                "city": city, "stations": sn, "views": views, "applies": applies,
                "located": located, "with_apply": with_apply,
                "located_pct": round(located / sn * 100) if sn else 0,
                "apply_pct": round(with_apply / sn * 100) if sn else 0,
            })
        city_stats.sort(key=lambda x: -x["views"])

        # ===== 热门驿站 Top10 =====
        hot_rows = db.session.query(
            AccessLog.station_id, func.count(AccessLog.id)
        ).filter(AccessLog.event == "detail_view").filter(AccessLog.station_id.isnot(None)).group_by(AccessLog.station_id).order_by(func.count(AccessLog.id).desc()).limit(10).all()
        hot_stations = []
        for sid, n in hot_rows:
            st = Station.query.get(sid)
            if st:
                hot_stations.append({"name": st.name, "city": st.city, "views": n, "id": st.id})

        # ===== 申请渠道分布 =====
        channel_rows = db.session.query(AccessLog.event, func.count(AccessLog.id)).filter(
            AccessLog.event.like("apply_click:%")
        ).group_by(AccessLog.event).all()
        channel_stats = {}
        for ev, n in channel_rows:
            ch = ev.split(":", 1)[1] if ":" in ev else ev
            ch_name = {"phone": "电话", "url": "在线申请", "wechat": "微信扫码", "nav": "导航"}.get(ch, ch)
            channel_stats[ch_name] = n

        # ===== 驿站健康度 =====
        located_total = Station.query.filter(Station.lng.isnot(None)).count()
        with_apply_total = Station.query.filter(
            db.or_(Station.contact_phone.isnot(None), Station.apply_url.isnot(None), Station.wechat_qr.isnot(None))
        ).count()
        with_guide_total = Station.query.filter(Station.guide_html.isnot(None), Station.guide_html != "").count()

        return render_template(
            "admin_dashboard.html",
            total_pv=total_pv, today_pv=today_pv, today_uv=today_uv,
            days=days, station_count=station_count, code_count=code_count,
            active_code_count=active_code_count, used_code_count=used_code_count,
            funnel_pv=funnel_pv, funnel_detail=funnel_detail, funnel_apply=funnel_apply,
            funnel_policy=funnel_policy, funnel_ai=funnel_ai,
            rate_detail=rate_detail, rate_apply=rate_apply,
            city_stats=city_stats, hot_stations=hot_stations,
            channel_stats=channel_stats,
            located_total=located_total, with_apply_total=with_apply_total,
            with_guide_total=with_guide_total,
        )

    # ----- 驿站管理 -----
    @app.route("/admin/stations")
    @login_required
    def admin_stations():
        city = request.args.get("city", "").strip()
        kw = request.args.get("kw", "").strip()
        q = Station.query
        if city:
            q = q.filter(Station.city == city)
        if kw:
            q = q.filter(db.or_(Station.name.like(f"%{kw}%"), Station.address.like(f"%{kw}%")))
        stations = q.order_by(Station.city, Station.id.desc()).all()
        cities = [c[0] for c in db.session.query(Station.city).distinct().all() if c[0]]
        return render_template("admin_stations.html", stations=stations, cities=sorted(cities), q_city=city, q_kw=kw)

    @app.route("/admin/station/edit", methods=["GET", "POST"])
    @app.route("/admin/station/edit/<int:sid>", methods=["GET", "POST"])
    @login_required
    def admin_station_edit(sid=None):
        s = Station.query.get(sid) if sid else Station()
        if request.method == "POST":
            s.name = request.form.get("name", "").strip()
            s.address = request.form.get("address", "").strip()
            s.city = request.form.get("city", "").strip()
            s.district = request.form.get("district", "").strip()
            s.folder = request.form.get("folder", "").strip()
            s.guide_html = request.form.get("guide_html", "")
            s.remark = request.form.get("remark", "")
            # 一键申请字段
            s.contact_name = request.form.get("contact_name", "").strip() or None
            s.contact_phone = request.form.get("contact_phone", "").strip() or None
            s.apply_url = request.form.get("apply_url", "").strip() or None
            s.wechat_qr = request.form.get("wechat_qr", "").strip() or None
            try:
                fd = request.form.get("free_days", "").strip()
                s.free_days = int(fd) if fd else None
            except Exception:
                s.free_days = None
            # 申请条件 / 所需材料：每行一条 → JSON 数组
            req_text = request.form.get("requirements_text", "")
            mat_text = request.form.get("materials_text", "")
            import json as _json
            s.requirements = _json.dumps([ln.strip() for ln in req_text.splitlines() if ln.strip()],
                                         ensure_ascii=False)
            s.materials = _json.dumps([ln.strip() for ln in mat_text.splitlines() if ln.strip()],
                                      ensure_ascii=False)
            try:
                s.lng = float(request.form.get("lng") or 0) or None
                s.lat = float(request.form.get("lat") or 0) or None
            except Exception:
                s.lng = s.lat = None
            # 自动从地址识别城市/区
            if not s.city or not s.district:
                p, c, d = parse_city_district(s.address)
                s.province = p
                s.city = s.city or c
                s.district = s.district or d
            # 自动地理编码
            if (not s.lng or not s.lat) and app.config.get("AMAP_WEB_KEY"):
                xy = amap_geocode(s.address, s.city, app.config["AMAP_WEB_KEY"], s.name)
                if xy:
                    s.lng, s.lat = xy
            if not sid:
                db.session.add(s)
            db.session.commit()
            flash("保存成功")
            return redirect(url_for("admin_stations"))
        # GET：把 JSON 字段转为多行文本传给模板
        import json as _json
        try:
            s.requirements_text = "\n".join(_json.loads(s.requirements or "[]"))
        except Exception:
            s.requirements_text = ""
        try:
            s.materials_text = "\n".join(_json.loads(s.materials or "[]"))
        except Exception:
            s.materials_text = ""
        return render_template("admin_station_edit.html", s=s)

    @app.route("/admin/station/delete/<int:sid>", methods=["POST"])
    @login_required
    def admin_station_delete(sid):
        s = Station.query.get_or_404(sid)
        db.session.delete(s)
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/admin/station/batch_delete", methods=["POST"])
    @login_required
    def admin_station_batch_delete():
        ids = request.json.get("ids", [])
        Station.query.filter(Station.id.in_(ids)).delete(synchronize_session=False)
        db.session.commit()
        return jsonify({"ok": True, "n": len(ids)})

    # ----- Excel 模板 / 导入 / 导出 -----
    @app.route("/admin/template.xlsx")
    @login_required
    def admin_template():
        data = build_import_template()
        return send_file(io.BytesIO(data), as_attachment=True, download_name="驿站导入模板.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    @app.route("/admin/station/import", methods=["POST"])
    @login_required
    def admin_station_import():
        f = request.files.get("file")
        if not f:
            return jsonify({"ok": False, "msg": "请选择 Excel 文件"}), 400
        try:
            records = read_stations_from_excel(f.stream)
        except Exception as e:
            return jsonify({"ok": False, "msg": f"解析失败：{e}"}), 400
        added, updated = 0, 0
        do_geo = bool(app.config.get("AMAP_WEB_KEY")) and request.form.get("geocode", "1") == "1"
        for r in records:
            # 自动补全城市/区
            if not r["city"] or not r["district"]:
                p, c, d = parse_city_district(r["address"])
                r["city"] = r["city"] or c
                r["district"] = r["district"] or d
            # 同名+同地址 视为已存在
            existing = Station.query.filter_by(name=r["name"], address=r["address"]).first()
            target = existing or Station()
            target.name = r["name"]
            target.address = r["address"]
            target.city = r["city"]
            target.district = r["district"]
            target.guide_html = r["guide_html"] or target.guide_html
            target.remark = r["remark"] or target.remark
            target.folder = r["folder"] or target.folder
            target.location_code = r["location_code"] or target.location_code
            if do_geo and (not target.lng or not target.lat):
                xy = amap_geocode(target.address, target.city, app.config["AMAP_WEB_KEY"])
                if xy:
                    target.lng, target.lat = xy
            if existing:
                updated += 1
            else:
                db.session.add(target)
                added += 1
        db.session.commit()
        return jsonify({"ok": True, "added": added, "updated": updated, "total": len(records)})

    @app.route("/admin/station/export")
    @login_required
    def admin_station_export():
        city = request.args.get("city", "").strip()
        q = Station.query
        if city:
            q = q.filter(Station.city == city)
        stations = q.order_by(Station.city, Station.id).all()
        data = export_stations_to_excel(stations)
        fname = f"{city or '全部'}-驿站信息-{datetime.now().strftime('%Y%m%d%H%M')}.xlsx"
        return send_file(io.BytesIO(data), as_attachment=True, download_name=fname,
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ----- 富文本图片/文件上传 -----
    @app.route("/admin/upload", methods=["POST"])
    @login_required
    def admin_upload():
        f = request.files.get("file")
        if not f:
            return jsonify({"ok": False, "msg": "无文件"}), 400
        ext = f.filename.rsplit(".", 1)[-1].lower() if "." in f.filename else ""
        if ext not in app.config["ALLOWED_UPLOAD_EXT"]:
            return jsonify({"ok": False, "msg": f"不支持的文件类型: {ext}"}), 400
        # 用时间戳+原名
        ts = datetime.now().strftime("%Y%m%d%H%M%S")
        safe = safe_filename(f.filename)
        new_name = f"{ts}_{safe}"
        path = os.path.join(app.config["UPLOAD_FOLDER"], new_name)
        f.save(path)
        url = url_for("uploaded_file", filename=new_name)
        return jsonify({"ok": True, "url": url, "name": f.filename})

    @app.route("/uploads/<path:filename>")
    def uploaded_file(filename):
        return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

    # ----- 驿站码管理 -----
    @app.route("/admin/codes")
    @login_required
    def admin_codes():
        codes = AccessCode.query.order_by(AccessCode.id.desc()).all()
        return render_template("admin_codes.html", codes=codes)

    @app.route("/admin/codes/generate", methods=["POST"])
    @login_required
    def admin_codes_generate():
        n = int(request.form.get("count", 10))
        days = request.form.get("days", "").strip()
        remark = request.form.get("remark", "").strip()
        expire_at = None
        if days and days.isdigit():
            expire_at = datetime.utcnow() + timedelta(days=int(days))
        created = []
        for _ in range(min(max(n, 1), 500)):
            code = generate_code()
            while AccessCode.query.filter_by(code=code).first():
                code = generate_code()
            ac = AccessCode(code=code, remark=remark, expire_at=expire_at)
            db.session.add(ac)
            created.append(code)
        db.session.commit()
        flash(f"成功生成 {len(created)} 个驿站码")
        return redirect(url_for("admin_codes"))

    @app.route("/admin/codes/toggle/<int:cid>", methods=["POST"])
    @login_required
    def admin_codes_toggle(cid):
        ac = AccessCode.query.get_or_404(cid)
        ac.enabled = not ac.enabled
        db.session.commit()
        return jsonify({"ok": True, "enabled": ac.enabled})

    @app.route("/admin/codes/delete/<int:cid>", methods=["POST"])
    @login_required
    def admin_codes_delete(cid):
        ac = AccessCode.query.get_or_404(cid)
        db.session.delete(ac)
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/admin/codes/export")
    @login_required
    def admin_codes_export():
        from openpyxl import Workbook as WB
        wb = WB()
        ws = wb.active
        ws.title = "驿站码"
        ws.append(["驿站码", "备注", "状态", "过期时间", "使用次数", "最后使用", "创建时间"])
        for c in AccessCode.query.order_by(AccessCode.id.desc()).all():
            ws.append([
                c.code, c.remark or "", "启用" if c.enabled else "停用",
                c.expire_at.strftime("%Y-%m-%d %H:%M") if c.expire_at else "永久",
                c.used_count or 0,
                c.last_used_at.strftime("%Y-%m-%d %H:%M") if c.last_used_at else "",
                c.created_at.strftime("%Y-%m-%d %H:%M") if c.created_at else "",
            ])
        bio = io.BytesIO()
        wb.save(bio)
        bio.seek(0)
        return send_file(bio, as_attachment=True, download_name="驿站码列表.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # ----- 高德 Key 暴露给后台前端的小端点 -----
    @app.route("/admin/api/amap_key")
    @login_required
    def admin_amap_key():
        return jsonify({"key": app.config["AMAP_JS_KEY"], "secret": app.config["AMAP_JS_SECRET"]})

    # ===== ⑤ 后台政策入口管理 =====
    @app.route("/admin/policies")
    @login_required
    def admin_policies():
        rows = CityPolicy.query.order_by(CityPolicy.city, CityPolicy.sort).all()
        cities = sorted(set(p.city for p in rows))
        return render_template("admin_policies.html", policies=rows, cities=cities)

    @app.route("/admin/policies/save", methods=["POST"])
    @login_required
    def admin_policies_save():
        pid = request.form.get("id")
        p = CityPolicy.query.get(int(pid)) if pid else CityPolicy()
        p.city = request.form.get("city", "").strip()
        p.category = request.form.get("category", "").strip()
        p.title = request.form.get("title", "").strip()
        p.description = request.form.get("description", "").strip()
        p.url = request.form.get("url", "").strip()
        p.icon = (request.form.get("icon", "").strip() or "📋")[:8]
        p.sort = int(request.form.get("sort") or 0)
        p.enabled = request.form.get("enabled") == "1"
        if not p.city or not p.title or not p.url:
            flash("城市/标题/链接不能为空")
            return redirect(url_for("admin_policies"))
        if not pid:
            db.session.add(p)
        db.session.commit()
        flash("已保存")
        return redirect(url_for("admin_policies"))

    @app.route("/admin/policies/delete/<int:pid>", methods=["POST"])
    @login_required
    def admin_policies_delete(pid):
        p = CityPolicy.query.get_or_404(pid)
        db.session.delete(p)
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/admin/policies/toggle/<int:pid>", methods=["POST"])
    @login_required
    def admin_policies_toggle(pid):
        p = CityPolicy.query.get_or_404(pid)
        p.enabled = not p.enabled
        db.session.commit()
        return jsonify({"ok": True, "enabled": p.enabled})

    # ===== ⑨ AI 模型管理 =====
    @app.route("/admin/ai")
    @login_required
    def admin_ai():
        rows = AIProvider.query.order_by(AIProvider.sort, AIProvider.id).all()
        return render_template("admin_ai.html", providers=rows)

    @app.route("/admin/ai/save", methods=["POST"])
    @login_required
    def admin_ai_save():
        pid = request.form.get("id")
        p = AIProvider.query.get(int(pid)) if pid else AIProvider()
        p.name = request.form.get("name", "").strip()
        p.provider_type = request.form.get("provider_type", "openai").strip()
        p.base_url = request.form.get("base_url", "").strip()
        p.api_key = request.form.get("api_key", "").strip()
        p.model = request.form.get("model", "").strip()
        p.extra_config = request.form.get("extra_config", "").strip() or None
        p.web_search = request.form.get("web_search") == "1"
        p.sort = int(request.form.get("sort") or 0)
        p.enabled = request.form.get("enabled") == "1"
        is_default = request.form.get("is_default") == "1"
        if not p.name:
            flash("名称必填")
            return redirect(url_for("admin_ai"))
        if is_default:
            # 取消其他默认
            AIProvider.query.update({AIProvider.is_default: False})
            p.is_default = True
        if not pid:
            db.session.add(p)
        db.session.commit()
        flash("已保存")
        return redirect(url_for("admin_ai"))

    @app.route("/admin/ai/delete/<int:pid>", methods=["POST"])
    @login_required
    def admin_ai_delete(pid):
        p = AIProvider.query.get_or_404(pid)
        db.session.delete(p)
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/admin/ai/set_default/<int:pid>", methods=["POST"])
    @login_required
    def admin_ai_set_default(pid):
        p = AIProvider.query.get_or_404(pid)
        AIProvider.query.update({AIProvider.is_default: False})
        p.is_default = True
        p.enabled = True
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/admin/ai/test/<int:pid>", methods=["POST"])
    @login_required
    def admin_ai_test(pid):
        """测试模型连通性"""
        from utils import ai_chat_stream, _build_messages
        p = AIProvider.query.get_or_404(pid)
        snap = {
            "id": p.id, "name": p.name,
            "provider_type": p.provider_type or "openai",
            "base_url": p.base_url or "",
            "api_key": p.api_key or "",
            "model": p.model or "",
            "extra_config": p.extra_config or "",
            "web_search": bool(p.web_search),
        }
        chunks = []
        err = None
        try:
            messages = _build_messages("你好，请用一句话介绍自己。", [], use_web=False, use_knowledge=False)
            for line in ai_chat_stream("你好，请用一句话介绍自己。", [], snap,
                                       use_web=False, use_knowledge=False,
                                       fallback_config={}, prebuilt_messages=messages):
                if line.startswith("data: "):
                    import json as _j
                    try:
                        obj = _j.loads(line[6:].strip())
                        if obj.get("type") == "delta":
                            chunks.append(obj.get("content") or "")
                        elif obj.get("type") == "error":
                            err = obj.get("msg")
                    except Exception:
                        continue
        except Exception as e:
            err = str(e)
        if err and not chunks:
            return jsonify({"ok": False, "msg": err})
        return jsonify({"ok": True, "answer": ("".join(chunks))[:200]})

    # ===== 湾湾鲸角色 / 开场白 / 追问策略 配置 =====
    DEFAULT_PERSONA_PROMPT = (
        "你是「湾湾鲸」🐬——粤港澳大湾区的中华白海豚（粉色海豚），头顶有橙色和绿色珊瑚芽，"
        "专门帮应届毕业生使用青年人才驿站的 AI 客服。\n\n"
        "【你的人设】\n"
        "- 形象：粉色中华白海豚，圆滚滚大脑袋、酒红色大眼睛、白色腮帮、头顶橙绿珊瑚芽\n"
        "- 自称：可以偶尔说\"小鲸/湾湾\"，但不要太频繁，避免出戏\n"
        "- 语气：亲切、活泼、专业，带着海豚的灵动感；偶尔加 🐬 / 💧 / 📍 等小表情\n"
        "- 背景：你是 2025 粤港澳大湾区全运会吉祥物的 AI 化身，对珠三角格外熟悉\n\n"
        "【你的能力范围】\n"
        "1. 介绍珠三角各市青年人才驿站的位置、申请方式、入住条件\n"
        "2. 讲解人才认定、生活补贴、租房补贴、落户等政策入口\n"
        "3. 解答\"我能不能申请\"\"怎么联系\"\"住几天\"\"需要什么材料\"等具体问题\n\n"
        "【回答规则】\n"
        "- **引用规范**：当你的回答内容来自下方【知识库检索】时，请在对应句末以 [1]、[2] 等角标标注引用编号；不要编造引用编号。\n"
        "- 优先基于下方【知识库】回答；知识库没有的信息要明确说\"我也没查到详细资料，建议直接打电话核实\"。\n"
        "- 给出具体可执行的建议，比如\"广州的话推荐看 XX 驿站，电话 138...，地址 XXX\"。\n"
        "- 涉及政策时附上官方链接（从知识库取）。\n"
        "- 回答要简洁（不超过 250 字），分点呈现，避免空话套话。\n"
        "- 当问题超出范围（让你写代码、聊天气、问其他城市），礼貌引导回大湾区驿站话题。\n"
        "- 永远不要假装自己是 ChatGPT/DeepSeek/通义千问；你就是「湾湾鲸」。"
    )
    DEFAULT_PERSONA_GREETING = (
        "🐬 <b>湾湾鲸</b>来啦！我是粤港澳大湾区的小海豚，"
        "专门帮应届毕业生找驿站、查政策~"
    )
    DEFAULT_PERSONA_QUICKS = [
        "我是 2026 届，深圳哪些驿站适合我？",
        "广州人才补贴怎么申请？",
        "东莞松山湖驿站联系方式？",
        "驿站码丢了怎么办？",
    ]

    def _get_or_create_persona():
        p = AIPersona.query.order_by(AIPersona.id).first()
        if not p:
            p = AIPersona(
                name="湾湾鲸",
                emoji="🐬",
                tagline="AI 驿站助手",
                system_prompt=DEFAULT_PERSONA_PROMPT,
                greeting=DEFAULT_PERSONA_GREETING,
                quick_asks=json.dumps(DEFAULT_PERSONA_QUICKS, ensure_ascii=False),
                followup_enabled=True,
                followup_strategy="smart",
                followup_max=2,
                followup_template="",
                enabled=True,
            )
            db.session.add(p)
            db.session.commit()
        return p

    @app.route("/admin/ai/persona", methods=["GET"])
    @login_required
    def admin_ai_persona():
        p = _get_or_create_persona()
        return render_template("admin_ai_persona.html", persona=p,
                                quick_asks_text="\n".join(p.get_quick_asks()),
                                default_prompt=DEFAULT_PERSONA_PROMPT)

    @app.route("/admin/ai/persona/save", methods=["POST"])
    @login_required
    def admin_ai_persona_save():
        p = _get_or_create_persona()
        p.name = (request.form.get("name") or "湾湾鲸").strip()[:64]
        p.emoji = (request.form.get("emoji") or "🐬").strip()[:16]
        p.tagline = (request.form.get("tagline") or "AI 驿站助手").strip()[:120]
        p.system_prompt = (request.form.get("system_prompt") or "").strip()
        p.greeting = (request.form.get("greeting") or "").strip()
        # quick_asks：textarea 一行一条
        raw = request.form.get("quick_asks") or ""
        items = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        p.quick_asks = json.dumps(items[:12], ensure_ascii=False)
        # 追问策略
        p.followup_enabled = request.form.get("followup_enabled") == "1"
        strategy = (request.form.get("followup_strategy") or "smart").strip()
        if strategy not in ("off", "smart", "always"):
            strategy = "smart"
        p.followup_strategy = strategy
        try:
            p.followup_max = max(1, min(5, int(request.form.get("followup_max") or 2)))
        except Exception:
            p.followup_max = 2
        p.followup_template = (request.form.get("followup_template") or "").strip()
        p.enabled = request.form.get("enabled") == "1"
        db.session.commit()
        flash("湾湾鲸 角色设定已保存")
        return redirect(url_for("admin_ai_persona"))

    @app.route("/admin/ai/persona/reset", methods=["POST"])
    @login_required
    def admin_ai_persona_reset():
        """一键恢复默认 system prompt / 开场白 / 示例问题"""
        p = _get_or_create_persona()
        p.system_prompt = DEFAULT_PERSONA_PROMPT
        p.greeting = DEFAULT_PERSONA_GREETING
        p.quick_asks = json.dumps(DEFAULT_PERSONA_QUICKS, ensure_ascii=False)
        p.followup_enabled = True
        p.followup_strategy = "smart"
        p.followup_max = 2
        p.followup_template = ""
        db.session.commit()
        return jsonify({"ok": True})

    # ===== 知识库管理 =====
    @app.route("/admin/knowledge")
    @login_required
    def admin_knowledge():
        category = request.args.get("category", "").strip()
        kw = request.args.get("kw", "").strip()
        q = KnowledgeEntry.query
        if category:
            q = q.filter_by(category=category)
        if kw:
            q = q.filter(db.or_(KnowledgeEntry.question.like(f"%{kw}%"),
                                KnowledgeEntry.answer.like(f"%{kw}%")))
        rows = q.order_by(KnowledgeEntry.category, KnowledgeEntry.sort, KnowledgeEntry.id.desc()).all()
        cats = sorted(set(e.category or "未分类" for e in KnowledgeEntry.query.all()))
        return render_template("admin_knowledge.html", entries=rows, cats=cats,
                               q_cat=category, q_kw=kw)

    @app.route("/admin/knowledge/save", methods=["POST"])
    @login_required
    def admin_knowledge_save():
        eid = request.form.get("id")
        e = KnowledgeEntry.query.get(int(eid)) if eid else KnowledgeEntry()
        e.category = request.form.get("category", "").strip() or "未分类"
        e.question = request.form.get("question", "").strip()
        e.answer = request.form.get("answer", "").strip()
        e.keywords = request.form.get("keywords", "").strip() or None
        e.sort = int(request.form.get("sort") or 0)
        e.enabled = request.form.get("enabled") == "1"
        if not e.question or not e.answer:
            flash("问题与答案不能为空")
            return redirect(url_for("admin_knowledge"))
        if not eid:
            db.session.add(e)
        db.session.commit()
        flash("已保存")
        return redirect(url_for("admin_knowledge"))

    @app.route("/admin/knowledge/delete/<int:eid>", methods=["POST"])
    @login_required
    def admin_knowledge_delete(eid):
        e = KnowledgeEntry.query.get_or_404(eid)
        db.session.delete(e)
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/admin/knowledge/toggle/<int:eid>", methods=["POST"])
    @login_required
    def admin_knowledge_toggle(eid):
        e = KnowledgeEntry.query.get_or_404(eid)
        e.enabled = not e.enabled
        db.session.commit()
        return jsonify({"ok": True, "enabled": e.enabled})

    # ============================================================
    # ⑩ 多模态知识库（文档/链接/笔记）
    # ============================================================
    @app.route("/admin/kb")
    @login_required
    def admin_kb():
        from models import KnowledgeDoc
        q_type = (request.args.get("type") or "").strip()
        q_kw = (request.args.get("kw") or "").strip()
        q = KnowledgeDoc.query
        if q_type:
            q = q.filter_by(doc_type=q_type)
        if q_kw:
            q = q.filter(KnowledgeDoc.title.like(f"%{q_kw}%"))
        docs = q.order_by(KnowledgeDoc.created_at.desc()).limit(200).all()
        # 分类下拉
        cats = sorted({d.category or "未分类" for d in KnowledgeDoc.query.all() if d.category})
        # 各类型计数
        from sqlalchemy import func
        type_counts = dict(db.session.query(KnowledgeDoc.doc_type, func.count(KnowledgeDoc.id))
                            .group_by(KnowledgeDoc.doc_type).all())
        return render_template("admin_kb.html",
                               docs=docs, q_type=q_type, q_kw=q_kw,
                               cats=cats, type_counts=type_counts)

    @app.route("/admin/kb/upload", methods=["POST"])
    @login_required
    def admin_kb_upload():
        """上传文档：支持 pdf/docx/txt/md，以及图片 (png/jpg/jpeg/webp/gif)"""
        from models import KnowledgeDoc
        from kb_ingest import ingest
        file = request.files.get("file")
        if not file or not file.filename:
            flash("请选择文件")
            return redirect(url_for("admin_kb"))
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        DOC_EXTS = {"pdf", "docx", "txt", "md", "markdown"}
        IMG_EXTS = {"png", "jpg", "jpeg", "webp", "gif"}
        if ext not in DOC_EXTS and ext not in IMG_EXTS:
            flash(f"暂不支持 .{ext}（支持 pdf/docx/txt/md 和 png/jpg/jpeg/webp/gif）")
            return redirect(url_for("admin_kb"))
        is_image = ext in IMG_EXTS

        # 保存文件
        sub_dir = "kb/images" if is_image else "kb"
        kb_dir = os.path.join(app.config["UPLOAD_FOLDER"], sub_dir)
        os.makedirs(kb_dir, exist_ok=True)
        safe_name = secure_filename(file.filename) or f"doc_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.{ext}"
        save_path = os.path.join(kb_dir, safe_name)
        cnt = 1
        base, e = os.path.splitext(safe_name)
        while os.path.exists(save_path):
            save_path = os.path.join(kb_dir, f"{base}_{cnt}{e}")
            cnt += 1
        file.save(save_path)
        size = os.path.getsize(save_path)

        title = (request.form.get("title") or "").strip() or os.path.splitext(file.filename)[0]
        category = (request.form.get("category") or "").strip() or None

        doc = KnowledgeDoc(
            title=title[:300],
            doc_type="image" if is_image else "doc",
            category=category,
            file_path=save_path,
            file_name=file.filename[:300],
            mime=file.mimetype or "",
            size=size,
            status="pending",
            enabled=True,
        )
        db.session.add(doc)
        db.session.commit()

        ok, msg = ingest(doc.id)
        flash(("✅ " if ok else "❌ ") + msg)
        return redirect(url_for("admin_kb"))

    @app.route("/admin/kb/url", methods=["POST"])
    @login_required
    def admin_kb_add_url():
        """从 URL 抓取网页正文"""
        from models import KnowledgeDoc
        from kb_ingest import ingest
        url = (request.form.get("url") or "").strip()
        title = (request.form.get("title") or "").strip()
        category = (request.form.get("category") or "").strip() or None
        if not url or not url.startswith(("http://", "https://")):
            flash("请填入合法的 URL（必须以 http:// 或 https:// 开头）")
            return redirect(url_for("admin_kb"))
        doc = KnowledgeDoc(
            title=title or "(待解析)",
            doc_type="url",
            category=category,
            source_url=url,
            status="pending",
            enabled=True,
        )
        db.session.add(doc)
        db.session.commit()
        ok, msg = ingest(doc.id)
        flash(("✅ " if ok else "❌ ") + msg)
        return redirect(url_for("admin_kb"))

    @app.route("/admin/kb/note", methods=["POST"])
    @login_required
    def admin_kb_add_note():
        """新建文本笔记（直接粘贴长文）"""
        from models import KnowledgeDoc
        from kb_ingest import ingest
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        category = (request.form.get("category") or "").strip() or None
        if not title or not content:
            flash("标题和内容都必须填写")
            return redirect(url_for("admin_kb"))
        doc = KnowledgeDoc(
            title=title[:300],
            doc_type="note",
            category=category,
            summary=content,  # 暂存原文供解析
            status="pending",
            enabled=True,
        )
        db.session.add(doc)
        db.session.commit()
        ok, msg = ingest(doc.id)
        flash(("✅ " if ok else "❌ ") + msg)
        return redirect(url_for("admin_kb"))

    @app.route("/admin/kb/<int:did>/reparse", methods=["POST"])
    @login_required
    def admin_kb_reparse(did):
        from kb_ingest import ingest
        ok, msg = ingest(did)
        return jsonify({"ok": ok, "msg": msg})

    @app.route("/admin/kb/<int:did>/toggle", methods=["POST"])
    @login_required
    def admin_kb_toggle(did):
        from models import KnowledgeDoc
        d = KnowledgeDoc.query.get_or_404(did)
        d.enabled = not d.enabled
        db.session.commit()
        return jsonify({"ok": True, "enabled": d.enabled})

    @app.route("/admin/kb/<int:did>/delete", methods=["POST"])
    @login_required
    def admin_kb_delete(did):
        from models import KnowledgeDoc
        d = KnowledgeDoc.query.get_or_404(did)
        # 物理删文件（可选，保留更安全）
        try:
            if d.file_path and os.path.exists(d.file_path):
                os.remove(d.file_path)
        except Exception:
            pass
        db.session.delete(d)
        db.session.commit()
        return jsonify({"ok": True})

    @app.route("/admin/kb/<int:did>")
    @login_required
    def admin_kb_detail(did):
        """文档详情：列出所有 chunks（后台才能看完整原文）"""
        from models import KnowledgeDoc, KnowledgeChunk
        d = KnowledgeDoc.query.get_or_404(did)
        chunks = (KnowledgeChunk.query.filter_by(doc_id=did)
                  .order_by(KnowledgeChunk.chunk_index).all())
        return render_template("admin_kb_detail.html", doc=d, chunks=chunks)

    @app.route("/admin/kb/citation/<int:chunk_id>")
    @login_required
    def admin_kb_citation(chunk_id):
        """从对话引文角标跳转到此处：完整原文 + 文档信息（仅管理员可看）"""
        from models import KnowledgeChunk
        c = KnowledgeChunk.query.get_or_404(chunk_id)
        kw = (request.args.get("kw") or "").strip()
        return render_template("admin_kb_citation.html", chunk=c, doc=c.doc, kw=kw)

    @app.route("/api/kb/peek/<int:chunk_id>")
    @code_required
    def api_kb_peek(chunk_id):
        """前台 hover 引文角标时调用：返回脱敏的标题/类型/摘要预览，绝不暴露原文全文"""
        from models import KnowledgeChunk
        c = KnowledgeChunk.query.get(chunk_id)
        if not c or not c.enabled or not c.doc or not c.doc.enabled:
            return jsonify({"ok": False, "msg": "资料不存在或已下线"}), 404
        d = c.doc
        # 仅返回 120 字预览 + 类型 + 标题；原文/链接均不返回
        snippet = (c.content or "")[:120]
        if len(c.content or "") > 120:
            snippet += "…"
        return jsonify({
            "ok": True,
            "title": d.title,
            "type": d.type_label(),
            "icon": d.type_icon(),
            "page_no": c.page_no,
            "snippet": snippet,
            "tip": "完整原文仅后台可查",
        })

    @app.route("/admin/kb/citations")
    @login_required
    def admin_kb_citations_log():
        """问答审计日志：哪些问题命中了哪些资料"""
        from models import CitationLog
        rows = CitationLog.query.order_by(CitationLog.created_at.desc()).limit(200).all()
        items = []
        for r in rows:
            try:
                cites = json.loads(r.citations or "[]")
            except Exception:
                cites = []
            items.append({"id": r.id, "q": r.question, "time": r.created_at, "cites": cites})
        return render_template("admin_kb_citations.html", items=items)

    # ============================================================
    # 图片相关：受控访问
    # ============================================================
    @app.route("/api/kb/thumb/<int:doc_id>")
    @code_required
    def api_kb_thumb(doc_id):
        """前台受控缩略图：仅返回压缩后的 200px 缩略图（带"参考"水印），原图不暴露
        - 必须是已启用的图片类型 KnowledgeDoc
        - 不允许下载原图
        """
        from models import KnowledgeDoc
        from io import BytesIO
        d = KnowledgeDoc.query.get(doc_id)
        if not d or not d.enabled or d.doc_type != "image" or not d.file_path:
            abort(404)
        if not os.path.exists(d.file_path):
            abort(404)
        try:
            from PIL import Image, ImageDraw, ImageFont
            img = Image.open(d.file_path)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            # 缩略 200px
            w, h = img.size
            target = 200
            ratio = target / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            # 加水印
            try:
                draw = ImageDraw.Draw(img, "RGBA")
                wm = "湾湾鲸·参考"
                # 用默认字体
                font = ImageFont.load_default()
                tw, th = draw.textbbox((0, 0), wm, font=font)[2:]
                draw.rectangle([img.width - tw - 10, img.height - th - 6,
                                img.width, img.height], fill=(0, 0, 0, 110))
                draw.text((img.width - tw - 5, img.height - th - 4), wm,
                          fill=(255, 255, 255, 220), font=font)
            except Exception:
                pass
            buf = BytesIO()
            img.save(buf, "JPEG", quality=80)
            buf.seek(0)
            return Response(buf.read(), mimetype="image/jpeg",
                            headers={"Cache-Control": "private, max-age=3600"})
        except Exception:
            abort(500)

    @app.route("/admin/kb/raw/<int:doc_id>")
    @login_required
    def admin_kb_raw_image(doc_id):
        """后台原图（管理员专用）"""
        from models import KnowledgeDoc
        d = KnowledgeDoc.query.get_or_404(doc_id)
        if not d.file_path or not os.path.exists(d.file_path):
            abort(404)
        return send_file(d.file_path, mimetype=d.mime or None)

    @app.route("/api/ai/upload-image", methods=["POST"])
    @code_required
    def api_ai_upload_image():
        """前台用户：上传图片让 AI 看图回答
        步骤：保存到 uploads/user_q/ → 调视觉模型描述 → 返回描述给前端注入对话
        """
        from kb_ingest import describe_image
        file = request.files.get("file")
        if not file or not file.filename:
            return jsonify({"ok": False, "msg": "未上传图片"}), 400
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in {"png", "jpg", "jpeg", "webp", "gif"}:
            return jsonify({"ok": False, "msg": "仅支持 png/jpg/webp/gif"}), 400

        # 限制大小 8MB
        file.seek(0, 2)
        sz = file.tell()
        file.seek(0)
        if sz > 8 * 1024 * 1024:
            return jsonify({"ok": False, "msg": "图片不能超过 8MB"}), 400

        # 保存（按驿站码 + 时间戳分目录）
        u_dir = os.path.join(app.config["UPLOAD_FOLDER"], "user_q",
                              str(session.get("code_id") or "anon"))
        os.makedirs(u_dir, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        save_name = f"{ts}_{secure_filename(file.filename)}"
        save_path = os.path.join(u_dir, save_name)
        file.save(save_path)

        # 调视觉模型描述
        try:
            description = describe_image(save_path)
        except Exception as e:
            return jsonify({"ok": False, "msg": f"看图失败：{e}"}), 500

        return jsonify({
            "ok": True,
            "description": description,
            "preview_url": url_for("api_user_image_thumb", filename=save_name),
        })

    @app.route("/api/user-image/<path:filename>")
    @code_required
    def api_user_image_thumb(filename):
        """前台用户上传的图片：仅自己能看缩略图"""
        from io import BytesIO
        u_dir = os.path.join(app.config["UPLOAD_FOLDER"], "user_q",
                              str(session.get("code_id") or "anon"))
        full = os.path.join(u_dir, secure_filename(filename))
        if not os.path.exists(full):
            abort(404)
        try:
            from PIL import Image
            img = Image.open(full)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            w, h = img.size
            target = 280
            if max(w, h) > target:
                ratio = target / max(w, h)
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
            buf = BytesIO()
            img.save(buf, "JPEG", quality=85)
            buf.seek(0)
            return Response(buf.read(), mimetype="image/jpeg")
        except Exception:
            return send_file(full)



    # ============================================================
    # 初始化
    # ============================================================
    with app.app_context():
        db.create_all()
        # 自动迁移：为已存在的旧库补充新字段（SQLite 不支持完整 ALTER，用原生 SQL）
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        with db.engine.begin() as conn:
            # Station 新增字段
            existing_cols = {c["name"] for c in insp.get_columns("station")}
            new_station_cols = {
                "contact_name": "VARCHAR(64)",
                "contact_phone": "VARCHAR(32)",
                "apply_url": "VARCHAR(500)",
                "wechat_qr": "VARCHAR(500)",
                "requirements": "TEXT",
                "materials": "TEXT",
                "free_days": "INTEGER",
            }
            for col, ddl in new_station_cols.items():
                if col not in existing_cols:
                    conn.execute(text(f"ALTER TABLE station ADD COLUMN {col} {ddl}"))
                    print(f"[MIGRATE] station.{col} 已添加")
            # AccessLog 新增字段
            existing_log = {c["name"] for c in insp.get_columns("access_log")}
            for col, ddl in {"event": "VARCHAR(32) DEFAULT 'page_view'",
                             "station_id": "INTEGER"}.items():
                if col not in existing_log:
                    conn.execute(text(f"ALTER TABLE access_log ADD COLUMN {col} {ddl}"))
                    print(f"[MIGRATE] access_log.{col} 已添加")

        if not Admin.query.first():
            admin = Admin(username=app.config["DEFAULT_ADMIN_USER"])
            admin.set_password(app.config["DEFAULT_ADMIN_PASS"])
            db.session.add(admin)
            db.session.commit()
            print(f"[INIT] 已创建默认管理员: {app.config['DEFAULT_ADMIN_USER']} / {app.config['DEFAULT_ADMIN_PASS']}")

        # 首次启动种子政策入口
        from models import CityPolicy
        if CityPolicy.query.count() == 0:
            from utils import seed_city_policies
            seed_city_policies()

        # 首次启动种子知识库
        from models import KnowledgeEntry
        if KnowledgeEntry.query.count() == 0:
            from utils import seed_knowledge
            seed_knowledge()

        # 根据 config 自动创建默认 AI 服务（如果没有任何配置）
        from utils import seed_default_ai_provider
        seed_default_ai_provider()

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
