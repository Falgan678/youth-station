# -*- coding: utf-8 -*-
"""
一键添加 / 更新 AI Provider 的工具脚本
用法：
  python add_ai_provider.py glm <api_key>
  python add_ai_provider.py hunyuan <api_key>
  python add_ai_provider.py list
"""
import sys
import io
import os

# Windows 控制台 UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from models import db, AIProvider

app = create_app()


PRESETS = {
    "glm": {
        "name": "GLM-4-Flash（智谱免费）",
        "provider_type": "openai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-flash",
        "web_search": False,
        "sort": 20,
    },
    "glm-plus": {
        "name": "GLM-4-Plus（智谱旗舰）",
        "provider_type": "openai",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-plus",
        "web_search": False,
        "sort": 25,
    },
    "hunyuan": {
        "name": "腾讯混元 Turbo S",
        "provider_type": "openai",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "model": "hunyuan-turbos-latest",
        "web_search": True,
        "sort": 30,
    },
    "hunyuan-large": {
        "name": "腾讯混元 Large",
        "provider_type": "openai",
        "base_url": "https://api.hunyuan.cloud.tencent.com/v1",
        "model": "hunyuan-large",
        "web_search": False,
        "sort": 35,
    },
}


def upsert(key: str, api_key: str):
    if key not in PRESETS:
        print(f"❌ 未知预设: {key}")
        print(f"   可用预设: {', '.join(PRESETS.keys())}")
        return False

    preset = PRESETS[key]
    with app.app_context():
        # 同名服务则更新，否则新增
        prov = AIProvider.query.filter_by(name=preset["name"]).first()
        action = "更新"
        if not prov:
            prov = AIProvider()
            db.session.add(prov)
            action = "新增"

        prov.name = preset["name"]
        prov.provider_type = preset["provider_type"]
        prov.base_url = preset["base_url"]
        prov.model = preset["model"]
        prov.api_key = api_key
        prov.web_search = preset.get("web_search", False)
        prov.sort = preset.get("sort", 10)
        prov.enabled = True
        # 不抢默认，保留 DeepSeek 作为默认
        if prov.is_default is None:
            prov.is_default = False

        db.session.commit()
        print(f"✅ {action}成功：{prov.name}")
        print(f"   id={prov.id}  base_url={prov.base_url}")
        print(f"   model={prov.model}  web_search={prov.web_search}")
        return True


def list_all():
    with app.app_context():
        ps = AIProvider.query.order_by(AIProvider.sort).all()
        print(f"\n📋 当前共 {len(ps)} 个 AI 服务：")
        print("-" * 80)
        for p in ps:
            star = "⭐" if p.is_default else "  "
            on = "✅" if p.enabled else "⛔"
            web = "🌐" if p.web_search else "  "
            key_show = (p.api_key[:8] + "..." + p.api_key[-4:]) if p.api_key else "(未设)"
            print(f" {star} {on} {web}  [{p.id:>2}] {p.name:<28} model={p.model:<32} key={key_show}")
        print("-" * 80)


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    if cmd == "list":
        list_all()
        return
    if len(sys.argv) < 3:
        print("❌ 请提供 API Key")
        print(__doc__)
        return
    upsert(cmd, sys.argv[2])
    list_all()


if __name__ == "__main__":
    main()
