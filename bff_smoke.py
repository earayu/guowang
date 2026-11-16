#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""BFF 冒烟自检：把 8 个端点跑一遍，落证据 JSON。

用途：证明"业务界面调 API"是真的通的，且耗时是实测值。
评委/客户要看时，跑这一个脚本就是全部证据。

用法：先起 python sgcc_bff.py，再 python bff_smoke.py
输出：国网Demo_C方案_BFF真跑证据.json + 控制台 PASS/FAIL
"""
import json
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("BFF", "http://127.0.0.1:8787")
OUT = os.path.join(HERE, "国网Demo_C方案_BFF真跑证据.json")

rec = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
       "target": BASE, "steps": []}


def call(method, path, body=None, timeout=180):
    url = BASE + path
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.loads(r.read().decode("utf-8"))
        return payload, round(time.time() - t0, 2), None
    except Exception as e:                                        # noqa: BLE001
        detail = ""
        if hasattr(e, "read"):
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                pass
        return None, round(time.time() - t0, 2), "%s %s" % (e, detail)


def step(name, method, path, body=None, probe=None, timeout=180):
    payload, el, err = call(method, path, body, timeout)
    s = {"step": name, "method": method, "path": path, "elapsed_s": el,
         "ok": err is None, "error": err}
    if payload is not None and probe:
        s.update(probe(payload) or {})
    rec["steps"].append(s)
    print("%-26s %-5s %6.2fs  %s" % (name, method, el,
                                     "OK" if s["ok"] else "FAIL " + str(err)[:90]))
    return payload


def main():
    h = step("健康检查", "GET", "/api/health",
             probe=lambda d: {"account": d.get("account"), "kbs": d.get("kbs")})
    if not h or not h.get("ok"):
        print("\nBFF 未就绪，先运行 python sgcc_bff.py")
        json.dump(rec, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        return 2

    step("库清单", "GET", "/api/kbs",
         probe=lambda d: {"kbs": len(d.get("items", [])),
                          "tender": sum(1 for x in d["items"] if x["side"] == "tender"),
                          "bid": sum(1 for x in d["items"] if x["side"] == "bid")})

    d1 = step("文档列表(冷)", "GET", "/api/docs?kb=col2de7406a4c8a6e56",
              probe=lambda d: {"docs": len(d.get("items", [])), "cache": d.get("_cache")})
    step("文档列表(热)", "GET", "/api/docs?kb=col2de7406a4c8a6e56",
         probe=lambda d: {"docs": len(d.get("items", [])), "cache": d.get("_cache")})

    q = urllib.parse.quote("投标有效期 日历天")
    sr = step("检索(荆州)", "GET", "/api/search?kb=col8fe7f3d2e3d2dac5&q=" + q,
              probe=lambda d: {"hits": d.get("total"), "cache": d.get("_cache"),
                               "has_handle": bool(d.get("hits") and d["hits"][0].get("handle")),
                               "top_doc": (d.get("hits") or [{}])[0].get("doc")})

    handle = None
    if sr and sr.get("hits"):
        handle = sr["hits"][0].get("handle")
    if handle:
        rd = step("原文回读", "GET", "/api/read?handle=" + urllib.parse.quote(handle),
                  probe=lambda d: {"doc": d.get("doc"), "section": d.get("section"), "cache": d.get("_cache"),
                                   "lines": d.get("count"),
                                   "evidence_line": next(
                                       (x["text"][:100] for x in d.get("lines", [])
                                        if "投标有效期" in x["text"]), None)})
    else:
        rec["steps"].append({"step": "原文回读", "ok": False, "error": "检索未返回 handle"})
        print("%-26s SKIP  检索无 handle" % "原文回读")

    step("判定矩阵", "GET", "/api/matrix",
         probe=lambda d: {"bidders": len(d.get("rows", [])),
                          "cells": sum(len(r.get("cells", {})) for r in d.get("rows", []))})

    body = {"batch_id": "152507", "fields": ["bid.validity_days"],
            "section_no": "152507-1102002-4004", "side": "bid",
            "bidder": "荆州楚元智能装备有限公司"}
    ex = step("提交抽取任务", "POST", "/api/extract", body,
              probe=lambda d: {"job_id": d.get("job_id"), "state": d.get("state")})
    if ex and ex.get("job_id"):
        jid = ex["job_id"]
        t0 = time.time()
        final = None
        for _ in range(45):
            time.sleep(2)
            jb, _, err = call("GET", "/api/job/" + jid, timeout=60)
            if jb and jb.get("state") in ("done", "failed"):
                final = jb
                break
        el = round(time.time() - t0, 2)
        f = ((final or {}).get("result") or {}).get("fields", [{}])[0] if final else {}
        rec["steps"].append({
            "step": "抽取任务完成", "method": "GET", "path": "/api/job/" + jid,
            "elapsed_s": el, "ok": bool(final and final.get("state") == "done"),
            "note_single_field": "单字段实测；多字段历史中位 23s",
            "state": (final or {}).get("state"), "error": (final or {}).get("error"),
            "field": f.get("field"), "value_text": f.get("value_text"),
            "value_num": f.get("value_num"), "verified": f.get("verified"),
            "quoted_span": f.get("quoted_span"),
            "fn_version": (final or {}).get("version_number"),
            "run_id": (final or {}).get("run_id")})
        print("%-26s GET   %6.2fs  %s  %s=%s verified=%s"
              % ("抽取任务完成", el, (final or {}).get("state"),
                 f.get("field"), f.get("value_text"), f.get("verified")))

    ok = [s for s in rec["steps"] if s.get("ok")]
    rec["summary"] = {"total": len(rec["steps"]), "passed": len(ok),
                      "failed": len(rec["steps"]) - len(ok)}
    rec["verdict"] = "PASS" if len(ok) == len(rec["steps"]) else "FAIL"
    json.dump(rec, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("\n%s  %d/%d  → %s" % (rec["verdict"], len(ok), len(rec["steps"]), OUT))
    return 0 if rec["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
