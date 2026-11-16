# -*- coding: utf-8 -*-
"""轮询国网样本知识库的解析 / 三类索引状态（支持分页，上限 100/页）。"""
import json, time, os, datetime
import ape_api as a

ROOT = r"C:\Users\linkz\WorkBuddy\PC办公"
STATE = os.path.join(ROOT, "sgcc_run_state.json")
OUT = os.path.join(ROOT, "sgcc_index_status.json")
DEADLINE_S = 3600


def all_docs(cid):
    page, out = 1, []
    while True:
        d = a.S.get(f"{a.BASE}/api/v2/collections/{cid}/documents",
                    params=a.ws({"page": page, "page_size": 100}), timeout=90).json()
        out.extend(d.get("items") or [])
        if not d.get("has_next"):
            return out, d.get("total")
        page += 1


def main():
    st = json.load(open(STATE, encoding="utf-8"))
    cid = st["collection_id"]
    a.login()
    t0 = time.time()
    last_sig, snap_rows = None, []
    print(f"POLL START {time.strftime('%H:%M:%S')} cid={cid}", flush=True)
    while time.time() - t0 < DEADLINE_S:
        try:
            rows, total = all_docs(cid)
        except Exception as e:
            print("POLL ERR", type(e).__name__, str(e)[:200], flush=True)
            time.sleep(20)
            continue
        cnt = {}
        for x in rows:
            for key in ("status", "vector_index_status", "fulltext_index_status",
                        "graph_index_status"):
                cnt[key] = cnt.get(key, {})
                v = str(x.get(key))
                cnt[key][v] = cnt[key].get(v, 0) + 1
        pending = sum(v for k, v in (cnt.get("status") or {}).items()
                      if k in ("RUNNING", "PENDING", "QUEUED", "UPLOADED"))
        idx_pending = sum(1 for x in rows if any(
            str(x.get(k)) in ("RUNNING", "PENDING", "QUEUED", "UPLOADED", "None")
            for k in ("vector_index_status", "fulltext_index_status", "graph_index_status")))
        sig = json.dumps(cnt, ensure_ascii=False, sort_keys=True) + f"|{len(rows)}"
        if sig != last_sig:
            print(time.strftime("%H:%M:%S"), "docs", len(rows), "/", total,
                  "pending_parse", pending, "pending_index", idx_pending,
                  json.dumps(cnt, ensure_ascii=False), flush=True)
            last_sig = sig
        # 以「文档解析全部进入终态」为完成判据；索引三类状态并列记录供报告标注，
        # 避免个别文档某种索引字段恒为 null 时无限阻塞。
        if rows and pending == 0:
            print("ALL_DONE (all documents terminal; index fields may still vary)", flush=True)
            snap_rows = rows
            break
        time.sleep(25)
    else:
        print("TIMEOUT", flush=True)
        snap_rows, _ = all_docs(cid)

    res = {
        "checked_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_s": round(time.time() - t0, 1),
        "doc_count": len(snap_rows),
        "docs": [{k: x.get(k) for k in
                  ("id", "name", "status", "vector_index_status",
                   "fulltext_index_status", "graph_index_status",
                   "index_failures", "file_type", "size")}
                 for x in snap_rows],
    }
    json.dump(res, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    fails = [d for d in res["docs"] if d.get("index_failures") or
             str(d.get("status")) in ("FAILED", "ERROR")]
    print("SAVED", OUT, "| parse/index failed:", len(fails), flush=True)
    for d in fails[:30]:
        print("  FAIL", str(d.get("name"))[:80], d.get("status"),
              d.get("index_failures"), flush=True)


if __name__ == "__main__":
    main()
