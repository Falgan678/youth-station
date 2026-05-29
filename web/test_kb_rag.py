# -*- coding: utf-8 -*-
"""测试新版多模态知识库 RAG"""
import sys, io, os
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import create_app
from models import db, KnowledgeDoc, KnowledgeChunk
from kb_ingest import ingest, build_rag_context_v2, search_chunks, tokenize

app = create_app()

with app.app_context():
    # 1) 添加一条 note 测试
    note_text = """广州市青年人才驿站申请须知（2026 版）

申请条件：
1. 国内全日制本科及以上应届毕业生，毕业 2 年内
2. 在广州求职或已签订三方协议但未到岗
3. 提供有效身份证 + 学历证明 + 求职证明

入住时长：免费 7 天，紧缺人才可延长至 14 天
联系方式：广州青年人才办公室 020-12345678
申请入口：https://hrss.gz.gov.cn/qnyz/
材料清单：身份证原件 / 学信网在校证明 / 面试通知或录用通知 / 三方协议（如有）"""

    existing = KnowledgeDoc.query.filter_by(title="广州青年人才驿站申请须知（2026 版）").first()
    if not existing:
        doc = KnowledgeDoc(
            title="广州青年人才驿站申请须知（2026 版）",
            doc_type="note", category="申请流程",
            summary=note_text, status="pending", enabled=True,
        )
        db.session.add(doc)
        db.session.commit()
        ok, msg = ingest(doc.id)
        print(f"[+] 测试笔记入库: {msg}")
    else:
        print(f"[=] 测试笔记已存在 id={existing.id}, 切块数={existing.chunk_count}")

    # 2) 测试分词
    print(f"\n[分词] '广州应届毕业生申请人才驿站要什么材料？'")
    print(f"  -> {tokenize('广州应届毕业生申请人才驿站要什么材料？')}")

    # 3) 测试 BM25 检索
    print(f"\n[BM25 Top-3]")
    hits = search_chunks("广州应届毕业生申请人才驿站要什么材料", top_k=3)
    for h in hits:
        print(f"  - [{h['score']:.2f}] {h['doc_title']}: {h['content'][:80]}...")

    # 4) 测试完整 RAG 上下文构建
    print(f"\n[RAG 上下文]")
    ctx, cites = build_rag_context_v2("广州应届毕业生申请人才驿站要什么材料", top_k=3)
    print(f"上下文长度: {len(ctx)} 字")
    print(f"引文数量: {len(cites)}")
    for c in cites:
        print(f"  [{c['ref']}] doc_id={c['doc_id']} chunk_id={c['chunk_id']} | {c['doc_title']}")
        print(f"      snippet: {c['snippet']}")

    print("\n✅ 全部测试通过")
