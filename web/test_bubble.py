# -*- coding: utf-8 -*-
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests

s = requests.Session()
s.get("http://localhost:5000/")
r = s.post("http://localhost:5000/api/portal/login", json={"code": "DEMO2026"})
print("login:", r.status_code, r.json())

r = s.get("http://localhost:5000/index")
print("\nindex 状态:", r.status_code)
text = r.text
print("含 ai-bubble:", 'id="ai-bubble"' in text)
print("含 toggleAI 函数:", "function toggleAI" in text)
print("含 onclick=\"toggleAI()\":", 'onclick="toggleAI()"' in text)

# 检查是否被 jinja {% if %} 注释掉了
if 'id="ai-bubble"' not in text:
    if "code_id" in text:
        print("\n⚠️ 看起来 session.code_id 判断出问题了")
    else:
        print("\n⚠️ 浮窗根本没渲染")
