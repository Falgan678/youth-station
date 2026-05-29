# -*- coding: utf-8 -*-
"""测试 AI Provider 连通性"""
import sys, io, os, json
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from app import create_app
from models import db, AIProvider

app = create_app()


def test_provider(pid: int):
    with app.app_context():
        p = AIProvider.query.get(pid)
        if not p:
            print(f"❌ 未找到 id={pid}")
            return
        print(f"\n🔍 测试 [{p.id}] {p.name}")
        print(f"   base_url = {p.base_url}")
        print(f"   model    = {p.model}")
        url = (p.base_url or "").rstrip("/") + "/chat/completions"
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {p.api_key}", "Content-Type": "application/json"},
                json={
                    "model": p.model,
                    "messages": [{"role": "user", "content": "你好，请用一句话介绍你自己。"}],
                    "stream": False,
                    "max_tokens": 80,
                },
                timeout=30,
            )
            if r.status_code == 200:
                data = r.json()
                ans = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                print(f"   ✅ 连通成功")
                print(f"   回复: {ans.strip()[:200]}")
            else:
                print(f"   ❌ HTTP {r.status_code}: {r.text[:300]}")
        except Exception as e:
            print(f"   ❌ 异常: {e}")


def main():
    if len(sys.argv) < 2:
        # 测试所有
        with app.app_context():
            for p in AIProvider.query.all():
                test_provider(p.id)
    else:
        test_provider(int(sys.argv[1]))


if __name__ == "__main__":
    main()
