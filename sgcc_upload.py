# -*- coding: utf-8 -*-
"""国网招标样本：全量上传 173 份（未脱敏、未删减），逐份记录成功/失败。

口径：
- 用户授权「同意上传 SaaS / 不用脱敏 / 全部」→ 全部 173 份逐份提交，含 .sign 与 .doc；
- 不改任何文件字节；仅在 multipart filename 上加「批次_品类__」前缀以便引用可区分标包；
- 每份结果即时落盘，可断点续传；失败不隐藏；
- 全部结束后启动三类索引。
"""
import os, re, json, time, sys
import ape_api as a

ROOT = r"C:\Users\linkz\WorkBuddy\PC办公"
EXPAND = os.path.join(ROOT, "国网样本_展开")
STATE = os.path.join(ROOT, "sgcc_run_state.json")
LOG = os.path.join(ROOT, "sgcc_upload_log.json")
MAXNAME = 160


def goods_tag(item, files):
    """从同标包货物清单名提取品类标识。"""
    seg = item["path"].split("/")
    if len(seg) < 3:
        return item["batch"]
    batch, pkg = seg[0], seg[1]
    cand = [x for x in files
            if x["path"].startswith(batch + "/" + pkg + "/") and x["ext"] == ".xlsx"]
    tag = ""
    if cand:
        stem = os.path.splitext(os.path.basename(cand[0]["path"]))[0]
        stem = re.sub(r"^货物清单_[0-9A-Za-z]+_", "", stem)
        stem = re.sub(r"\d{8}_\d{6}_\d+$", "", stem)
        tag = stem[:26]
    if pkg.startswith("包2_"):
        tag += "_B2"
    prefix = "S1K1" if batch == "S1_1525K1" else "S2507"
    return f"{prefix}_{tag}" if tag else prefix


def display_name(item, tag):
    base = os.path.basename(item["path"])
    ext = os.path.splitext(base)[1]
    name = f"{tag}__{base}"
    if len(name) > MAXNAME:
        keep = MAXNAME - len(tag) - len(ext) - 2
        name = f"{tag}__{os.path.splitext(base)[0][:keep]}{ext}"
    return name


def main():
    st = json.load(open(STATE, encoding="utf-8"))
    cid = st["collection_id"]
    m = json.load(open(os.path.join(EXPAND, "manifest.json"), encoding="utf-8"))
    files = [x for x in m["items"] if x["kind"] == "file"]
    log = {}
    if os.path.exists(LOG):
        log = json.load(open(LOG, encoding="utf-8"))

    a.login()
    t0 = time.time()
    print(f"START {time.strftime('%H:%M:%S')} cid={cid} total={len(files)}", flush=True)

    for i, item in enumerate(files, 1):
        key = item["path"]
        if log.get(key, {}).get("ok"):
            continue
        tag = goods_tag(item, files)
        dn = display_name(item, tag)
        p = os.path.join(EXPAND, key.replace("/", os.sep))
        ts = time.time()
        rec = {"display_name": dn, "batch": item["batch"], "ext": item["ext"],
               "size": item["size"], "sha1": item["sha1"], "path": key}
        try:
            with open(p, "rb") as f:
                r = a.S.post(
                    f"{a.BASE}/api/v2/collections/{cid}/documents/upload",
                    params=a.ws(), files={"file": (dn, f)}, timeout=300)
            rec["status"] = r.status_code
            rec["ok"] = r.status_code < 300
            rec["resp"] = r.text[:400] if r.status_code >= 300 else ""
            if rec["ok"]:
                try:
                    rec["doc_id"] = r.json().get("id")
                except Exception:
                    pass
        except Exception as e:
            rec["ok"] = False
            rec["status"] = -1
            rec["resp"] = f"{type(e).__name__}: {e}"[:400]
        rec["seconds"] = round(time.time() - ts, 1)
        log[key] = rec
        json.dump(log, open(LOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"[{i:3d}/{len(files)}] {'OK  ' if rec['ok'] else 'FAIL'} "
              f"{rec['seconds']:6.1f}s {rec['status']:>4} {dn[:88]} "
              f"{rec['resp'][:110]}", flush=True)

    ok = [k for k, v in log.items() if v.get("ok")]
    fail = [k for k, v in log.items() if not v.get("ok")]
    print(f"UPLOAD DONE {time.strftime('%H:%M:%S')} ok={len(ok)} fail={len(fail)} "
          f"elapsed={round(time.time()-t0,1)}s", flush=True)
    print("FAILED LIST:", json.dumps(
        [{"name": log[k]["display_name"], "ext": log[k]["ext"],
          "status": log[k]["status"], "resp": log[k]["resp"]} for k in fail],
        ensure_ascii=False)[:2000], flush=True)

    r = a.start_indexing(cid)
    st["index_started_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    st["upload_ok"] = len(ok)
    st["upload_fail"] = len(fail)
    st["upload_elapsed_s"] = round(time.time() - t0, 1)
    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("INDEX_START", bool(r), flush=True)


if __name__ == "__main__":
    main()
