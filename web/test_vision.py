# -*- coding: utf-8 -*-
"""测试 GLM-4V-Flash 视觉理解 + 端到端图片问答"""
import sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import base64
import requests

# 1. 生成一张测试图（模拟一张应届生录用通知）
def make_test_image():
    img = Image.new("RGB", (640, 360), "#ffffff")
    draw = ImageDraw.Draw(img)
    # 标题
    try:
        font_big = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 28)
        font_mid = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 18)
        font_sm  = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 14)
    except Exception:
        font_big = font_mid = font_sm = ImageFont.load_default()
    draw.text((180, 24), "录用通知书", fill="#003366", font=font_big)
    draw.line([(40, 70), (600, 70)], fill="#003366", width=2)
    lines = [
        "尊敬的张三同学：",
        "",
        "  恭喜您通过腾讯科技（深圳）有限公司面试，",
        "  我司诚意邀请您于 2026 年 7 月 15 日入职。",
        "",
        "  岗位：高级软件工程师",
        "  地点：深圳市南山区科技园",
        "  薪资：年包 35 万元",
        "",
        "                    腾讯科技（深圳）有限公司",
        "                    2026年5月20日",
    ]
    for i, t in enumerate(lines):
        draw.text((50, 90 + i * 22), t, fill="#222222",
                  font=font_mid if i in (0, 9, 10) else font_sm)
    p = "data/test_offer.jpg"
    os.makedirs("data", exist_ok=True)
    img.save(p, "JPEG", quality=85)
    return p


img_path = make_test_image()
print(f"[+] 已生成测试图: {img_path}")

# 2. 直接测试 describe_image
from app import create_app
app = create_app()
with app.app_context():
    from kb_ingest import describe_image
    print("\n[直接调 GLM-4V]")
    desc = describe_image(img_path)
    print("视觉描述：")
    print(desc[:600])
    print("..." if len(desc) > 600 else "")

# 3. 端到端：登录前台 → 上传图片 → 看 stream
print("\n[端到端]")
s = requests.Session()
s.get("http://localhost:5000/")
r = s.post("http://localhost:5000/api/portal/login", json={"code": "DEMO2026"})
print("login:", r.status_code)

# 先新建会话
r = s.post("http://localhost:5000/api/chat/sessions")
sid = r.json().get("id")
print(f"new session id={sid}")

# 上传图片（前台问图）
with open(img_path, "rb") as f:
    r = s.post("http://localhost:5000/api/ai/upload-image",
               files={"file": ("offer.jpg", f, "image/jpeg")})
j = r.json()
print(f"upload: ok={j.get('ok')} preview={j.get('preview_url')}")
print(f"AI 看图描述（前 200 字）：{j.get('description', '')[:200]}...")

# 注入到对话
desc = j.get("description") or ""
question = (
    f"[用户上传了一张图片，视觉模型识别如下]\n{desc}\n\n"
    f"[用户提问]\n这份录用通知能用来申请深圳青年驿站吗？"
)
r = s.post("http://localhost:5000/api/ai/stream", json={
    "question": question, "history": [],
    "use_web": False, "use_knowledge": True, "session_id": sid,
}, stream=True, timeout=60)

import json as _j
deltas = []
for line in r.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data:"):
        continue
    try:
        obj = _j.loads(line[5:].strip())
    except Exception:
        continue
    if obj.get("type") == "delta":
        deltas.append(obj.get("content", ""))
print(f"\nAI 回答: {''.join(deltas)[:800]}")
print("\n✅ 测试完成")
