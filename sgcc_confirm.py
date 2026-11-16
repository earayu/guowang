# -*- coding: utf-8 -*-
"""补传 3 份 409 同名 .doc → 确认入库（排除 DIAG 诊断件）→ 启动索引。"""
import os, json, time
import ape_api as a

ROOT = r"C:\Users\linkz\WorkBuddy\PC办公"
EXPAND = os.path.join(ROOT, "国网样本_展开")
STATE = os.path.join(ROOT, "sgcc_run_state.json")
ULOG = os.path.join(ROOT, "sgcc_upload_log.json")
OUT = os.path.join(ROOT, "sgcc_confirm_log.json")


def main():
    st = json.load(open(STATE, encoding="utf-8"))
    cid = st["collection_id"]
    ulog = json.load(open(ULOG, encoding="utf-8"))
    a.login()

    # 1) 补传 3 份 DOCUMENT_NAME_CONFLICT 的 .doc，加唯一后缀
    dup = [(k, v) for k, v in ulog.items()
           if not v.get("ok") and v["ext"] == ".doc"]
    print("409 .doc to retry:", len(dup), flush=True)
    for i, (k, v) in enumerate(dup, 1):
        p = os.path.join(EXPAND, k.replace("/", os.sep))
        stem, ext = os.path.splitext(v["display_name"])
        name = f"{stem}_dup{i}{ext}"
        if len(name) > 160:
            name = stem[:150] + f"_dup{i}{ext}"
        with open(p, "rb") as f:
            r = a.S.post(f"{a.BASE}/api/v2/collections/{cid}/documents/upload",
                         params=a.ws(), files={"file": (name, f)}, timeout=300)
        v2 = dict(v)
        v2.update({"display_name": name, "status": r.status_code,
                   "ok": r.status_code < 300,
                   "resp": r.text[:300] if r.status_code >= 300 else "",
                   "retry_of_409": True})
        ulog[k + f"#dup{i}"] = v2
        print(f"  retry {i}", r.status_code, name[:80], r.text[:180], flush=True)
    json.dump(ulog, open(ULOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    # 2) 暂存池清单，排除 DIAG 诊断件
    d = a.S.get(f"{a.BASE}/api/v2/collections/{cid}/documents/staged",
                params=a.ws(), timeout=120).json()
    docs = d.get("documents") or []
    real = [x for x in docs if not str(x.get("filename", "")).startswith("DIAG")]
    diag = [x for x in docs if str(x.get("filename", "")).startswith("DIAG")]
    ids = [x["document_id"] for x in real]
    print("STAGED total", d.get("total"), "real", len(real), "diag_excluded", len(diag),
          flush=True)

    # 3) 先删除 DIAG 暂存件（尽力而为，失败不影响主流程）
    for x in diag:
        try:
            rr = a.S.delete(f"{a.BASE}/api/v2/collections/{cid}/documents/{x['document_id']}",
                            params=a.ws(), timeout=30)
            print("  delete diag", rr.status_code, x["filename"][:40], flush=True)
        except Exception as e:
            print("  delete diag err", str(e)[:80], flush=True)

    # 4) 确认入库（不自动起索引，便于单独记录索引耗时）
    t0 = time.time()
    r = a.S.post(f"{a.BASE}/api/v2/collections/{cid}/documents/confirm",
                 params=a.ws(), json={"document_ids": ids, "start_indexing": False},
                 timeout=600)
    print("CONFIRM", r.status_code, r.text[:600], flush=True)
    confirm = {"status": r.status_code, "resp": r.text[:1200],
               "elapsed_s": round(time.time() - t0, 1),
               "requested": len(ids)}
    if r.status_code >= 300:
        json.dump(confirm, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        raise SystemExit("confirm failed")

    # 5) 显式启动索引
    t1 = time.time()
    r2 = a.S.post(f"{a.BASE}/api/v2/collections/{cid}/documents/start-indexing",
                  params=a.ws(), json={"document_ids": ids}, timeout=600)
    print("START_INDEX", r2.status_code, r2.text[:600], flush=True)
    confirm.update({"index_status": r2.status_code, "index_resp": r2.text[:1200],
                    "index_elapsed_s": round(time.time() - t1, 1),
                    "confirmed_ids": ids,
                    "diag_excluded": [x["filename"] for x in diag],
                    "at": time.strftime("%Y-%m-%d %H:%M:%S")})
    st["confirm_at"] = confirm["at"]
    st["confirmed_count"] = len(ids)
    st["index_started_at"] = confirm["at"]
    st["upload_ok"] = len(ids)
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(confirm, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("SAVED", OUT, flush=True)


if __name__ == "__main__":
    main()
