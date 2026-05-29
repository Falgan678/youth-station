# -*- coding: utf-8 -*-
"""查看/创建驿站码"""
import sys, io, os
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app
from models import db, AccessCode

app = create_app()

with app.app_context():
    codes = AccessCode.query.order_by(AccessCode.id).all()
    print(f"\n📋 当前共 {len(codes)} 个驿站码:")
    for c in codes[:10]:
        on = "✅" if c.enabled else "⛔"
        print(f"  {on}  {c.code:<20} 备注={c.remark or '—':<20} 已用 {c.used_count} 次")

    # 创建一个 DEMO2026 给体验用
    demo = AccessCode.query.filter_by(code="DEMO2026").first()
    if not demo:
        demo = AccessCode(code="DEMO2026", remark="体验用·永久", enabled=True)
        db.session.add(demo)
        db.session.commit()
        print(f"\n✨ 已创建体验码: DEMO2026 (永久有效)")
    else:
        demo.enabled = True
        demo.expire_at = None
        db.session.commit()
        print(f"\n✨ 体验码 DEMO2026 已启用 (永久有效)")
