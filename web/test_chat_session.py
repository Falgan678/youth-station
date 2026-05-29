# -*- coding: utf-8 -*-
"""测试多会话 API 链路"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests

s = requests.Session()
s.get("http://localhost:5000/")
r = s.post("http://localhost:5000/api/portal/login", json={"code": "DEMO2026"})
print("login:", r.status_code)

# 1) 列会话（应该是空的或者只有刚才测试时自动建的）
r = s.get("http://localhost:5000/api/chat/sessions")
print("\n[列会话]", r.status_code, r.json())

# 2) 新建一个
r = s.post("http://localhost:5000/api/chat/sessions")
print("\n[新建]", r.status_code, r.json())
sid = r.json().get("id")

# 3) 流式发消息（带 session_id）
print(f"\n[流式发消息到 session {sid}]")
r = s.post("http://localhost:5000/api/ai/stream", json={
    "question": "广州人才驿站电话多少",
    "history": [], "use_web": False, "use_knowledge": True,
    "session_id": sid,
}, stream=True, timeout=60)
print("status:", r.status_code)
sess_seen = False
delta_cnt = 0
for line in r.iter_lines(decode_unicode=True):
    if not line or not line.startswith("data:"):
        continue
    try:
        obj = json.loads(line[5:].strip())
    except Exception:
        continue
    if obj.get("type") == "session":
        sess_seen = True
        print(f"  收到 session 帧: id={obj.get('session_id')} title={obj.get('title')}")
    elif obj.get("type") == "delta":
        delta_cnt += 1
print(f"  session_seen={sess_seen} delta_count={delta_cnt}")

# 4) 拉历史
import time; time.sleep(1)
r = s.get(f"http://localhost:5000/api/chat/sessions/{sid}/messages")
print(f"\n[拉历史 sid={sid}]")
j = r.json()
print(f"  ok={j.get('ok')} title={j.get('title')} messages={len(j.get('items', []))}")
for m in j.get('items', []):
    print(f"  - [{m['role']}] {m['content'][:60]}...")
    if m.get('citations'):
        print(f"      引文: {len(m['citations'])} 条")

# 5) 列会话（应有这条）
r = s.get("http://localhost:5000/api/chat/sessions")
print("\n[再次列会话]", r.json())

# 6) 重命名
r = s.post(f"http://localhost:5000/api/chat/sessions/{sid}/rename",
           json={"title": "广州驿站咨询"})
print("\n[重命名]", r.json())

# 7) 清空
r = s.post(f"http://localhost:5000/api/chat/sessions/{sid}/clear")
print("\n[清空]", r.json())
r = s.get(f"http://localhost:5000/api/chat/sessions/{sid}/messages")
print(f"  清空后消息数: {len(r.json().get('items', []))}")

# 8) 删除
r = s.delete(f"http://localhost:5000/api/chat/sessions/{sid}")
print("\n[删除]", r.json())

print("\n✅ 全部 API 通过")
