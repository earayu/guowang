# -*- coding: utf-8 -*-
"""汇总上传 / 索引 / 跑题 / 客观基准，输出可供报告引用的摘要。"""
import os, json, collections

ROOT = r"C:\Users\linkz\WorkBuddy\PC办公"
P = lambda n: os.path.join(ROOT, n)


def load(n, default=None):
    p = P(n)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else (default or {})


def main():
    ul = load("sgcc_upload_log.json", {})
    st = load("sgcc_run_state.json", {})
    idx = load("sgcc_index_status.json", {})
    qa = load("sgcc_l1_results.json", {})
    gt = load("sgcc_ground_truth.json", {})

    print("=" * 72)
    print("STATE", json.dumps(st, ensure_ascii=False))
    print("=" * 72)
    print("UPLOAD")
    oks = [v for v in ul.values() if v.get("ok")]
    fails = [v for v in ul.values() if not v.get("ok")]
    print(" total", len(ul), "ok", len(oks), "fail", len(fails),
          "elapsed_s", st.get("upload_elapsed_s"))
    print(" ok by ext", dict(collections.Counter(v["ext"] for v in oks)))
    print(" fail by ext", dict(collections.Counter(v["ext"] for v in fails)))
    print(" fail sample", [(v["display_name"][:50], v["status"], v["resp"][:80])
                           for v in fails[:3]])
    print(" bytes uploaded MB", round(sum(v["size"] for v in oks) / 1048576, 2))
    print(" slowest", [(v["display_name"][:46], v["seconds"])
                       for v in sorted(oks, key=lambda x: -x["seconds"])[:5]])

    print("=" * 72)
    print("INDEX")
    docs = idx.get("docs") or []
    print(" checked_at", idx.get("checked_at"), "elapsed_s", idx.get("elapsed_s"),
          "doc_count", idx.get("doc_count"), len(docs))
    for k in ("status", "vector_index_status", "fulltext_index_status",
              "graph_index_status"):
        print(" ", k, dict(collections.Counter(str(x.get(k)) for x in docs)))
    bad = [x for x in docs if x.get("index_failures") or
           str(x.get("status")) in ("FAILED", "ERROR")]
    print(" FAILED docs", len(bad))
    for x in bad[:25]:
        print("   ", str(x.get("name"))[:78], x.get("status"),
              str(x.get("index_failures"))[:120])
    doc_bad = [x for x in docs if str(x.get("name", "")).lower().endswith(".doc")]
    print(" .doc docs in collection", len(doc_bad))
    for x in doc_bad[:6]:
        print("   ", str(x.get("name"))[:70], x.get("status"),
              x.get("vector_index_status"), x.get("fulltext_index_status"))

    print("=" * 72)
    print("GROUND TRUTH")
    print(" v6 filename hits", gt.get("v6_evidence"))
    print(" corpus", gt.get("corpus"))
    for v in gt.get("v1_pair", []):
        print(" pair", v["file"][:52], "chars", v["chars"],
              {k: v["keyword_counts"].get(k) for k in
               ["型式试验", "检测报告", "业绩", "型号", "评标办法", "技术得分"]})

    print("=" * 72)
    print("QA RESULTS")
    for r in qa.get("results", []):
        ans = r.get("answer") or ""
        flags = {
            "未找到": ("未找到" in ans or "知识库中未找到" in ans),
            "需人工判定": "需人工判定" in ans or "人工判定" in ans,
            "越界_违规终局": "属于违规" in ans or "构成违规" in ans or "应否决" in ans,
            "分数数字": bool(__import__("re").search(r"技术得分[：:]\s*\d", ans)),
            "表格": "|" in ans and "---" in ans,
        }
        print(f" {r['name']:<20} status={r.get('status')} sec={r.get('seconds')} "
              f"wall={r.get('wall_seconds')} tools={r.get('tool_calls')} "
              f"touched={len(r.get('touched_docs') or [])} "
              f"cited_docs={len(r.get('cited_docs') or [])} "
              f"cites={r.get('citations')} ans_len={len(ans)}")
        print("    flags", flags, "err", str(r.get("error") or r.get("error_message"))[:120])
        print("    answer head:", ans.replace("\n", " ")[:220])


if __name__ == "__main__":
    main()
