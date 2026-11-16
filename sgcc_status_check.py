# -*- coding: utf-8 -*-
"""演示前只读活查：知识库文档解析与三类索引状态。

只调用 GET /documents，不写库、不改配置、不启动索引。
用法：
  "C:/Users/linkz/.workbuddy/binaries/python/envs/default/Scripts/python.exe" sgcc_status_check.py
"""
import json
import collections
import time
import os
import ape_api as a

ROOT = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(ROOT, "sgcc_run_state.json")
KEYS = ("status", "vector_index_status", "fulltext_index_status", "graph_index_status")


def all_docs(cid):
    rows, page = [], 1
    while True:
        d = a.S.get(
            f"{a.BASE}/api/v2/collections/{cid}/documents",
            params=a.ws({"page": page, "page_size": 100}), timeout=90
        ).json()
        rows.extend(d.get("items") or [])
        if not d.get("has_next"):
            return rows, d.get("total")
        page += 1


def main():
    st = json.load(open(STATE, encoding="utf-8"))
    cid = st["collection_id"]
    a.login()
    rows, total = all_docs(cid)
    cnt = {k: dict(collections.Counter(str(x.get(k)) for x in rows)) for k in KEYS}
    print("=" * 66)
    print("演示前活查 |", time.strftime("%Y-%m-%d %H:%M:%S"), "| 知识库", cid)
    print("=" * 66)
    print(f"文档数: {len(rows)} / total={total}")
    for k, label in zip(KEYS, ("文档解析", "向量索引", "全文索引", "图谱索引")):
        parts = " / ".join(f"{v} {n}" for v, n in sorted(cnt[k].items()))
        print(f"{label}: {parts}")
    graph = cnt["graph_index_status"]
    if any(v not in ("ACTIVE", "None") for v in graph):
        print("\n[口径] 图谱未全绿 -> 所有结论标注「基于向量 + 全文，图谱能力未验证」。")
    else:
        print("\n[口径] 图谱已收敛，可在报告中更新读数后补 A5 对照轮。")
    vec = cnt["vector_index_status"]
    full = cnt["fulltext_index_status"]
    print(f"[口径] 向量 ACTIVE={vec.get('ACTIVE', 0)}，全文 ACTIVE={full.get('ACTIVE', 0)}；"
          "不得把配额限流自动重试说成解析失败。")
    print("[口径] 本脚本只读；真实问答请到 apemind.ai 原生会话，演示壳不发请求。")


if __name__ == "__main__":
    main()
