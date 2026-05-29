# -*- coding: utf-8 -*-
"""排查湾湾鲸点击无反应"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests

s = requests.Session()
s.get("http://localhost:5000/")
s.post("http://localhost:5000/api/portal/login", json={"code": "DEMO2026"})
r = s.get("http://localhost:5000/index")

# 抓取关键代码块
text = r.text
# 找 ai-bubble 块
m = re.search(r'<div id="ai-bubble"[^>]*>.*?</div>\s*</div>', text, re.S)
if m:
    print("[ai-bubble HTML]")
    print(m.group(0)[:500])

# 找 toggleAI 函数
m2 = re.search(r'function toggleAI\(\) \{.*?\n\s*\}', text, re.S)
if m2:
    print("\n[toggleAI 函数]")
    print(m2.group(0))

# 检查 z-index
print("\n[z-index 相关]")
for line in text.split("\n"):
    if "z-index" in line and ("ai-bubble" in line or "9998" in line or "10000" in line or "9999" in line):
        print("  " + line.strip()[:120])

# 检查可能遮挡的元素
print("\n[#ai-panel 默认样式]")
m3 = re.search(r"#ai-panel \{[^}]+\}", text)
if m3:
    print(m3.group(0)[:300])
