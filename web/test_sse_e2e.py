# -*- coding: utf-8 -*-
"""端到端测试 SSE 引文链路"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import requests, json

s = requests.Session()
# 登录（先访问首页拿到 session cookie）
r = s.get("http://localhost:5000/")
print("home:", r.status_code)
r = s.post("http://localhost:5000/api/portal/login",
           json={"code": "DEMO2026"})
print("login:", r.status_code, "body:", r.text[:200])

# 调流式
r = s.post("http://localhost:5000/api/ai/stream",
           json={"question": "广州应届毕业生申请人才驿站要什么材料",
                 "history": [], "use_web": False, "use_knowledge": True},
           stream=True, timeout=60)
print("stream status:", r.status_code)
if r.status_code != 200:
    print("body:", r.text[:300])
    sys.exit(1)

frames = 0
cite = None
deltas = []
for line in r.iter_lines(decode_unicode=True):
    if not line:
        continue
    if not line.startswith("data:"):
        continue
    frames += 1
    try:
        obj = json.loads(line[5:].strip())
    except Exception:
        continue
    t = obj.get("type")
    if t == "citations":
        cite = obj.get("items", [])
        print(f"\n📖 收到 citations: {len(cite)} 条")
        for c in cite:
            print(f"  [{c['ref']}] {c['doc_title']} (chunk_id={c['chunk_id']})")
            print(f"      snippet: {c['snippet']}")
    elif t == "delta":
        deltas.append(obj.get("content", ""))
    elif t == "error":
        print("ERROR:", obj.get("msg"))
    if frames > 500:
        break

answer = "".join(deltas)
print(f"\n💬 总帧数: {frames}, delta: {len(deltas)}")
print(f"📝 AI 回复 (前 600 字): {answer[:600]}")
if "[1]" in answer or "[2]" in answer:
    print("\n✅ AI 回复中已出现引用角标 [N]")
else:
    print("\n⚠️ AI 回复中没出现 [N] 角标，可能是模型没听话；但不影响功能")
