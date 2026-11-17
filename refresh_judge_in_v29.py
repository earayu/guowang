#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用 sgcc-field-extract v29（金额两位小数）重抽六家投标侧字段，
重建 _judge_in_<代号>.json，再触发 BFF 判定快照重算。"""
import json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BFF = os.environ.get("BFF", "http://127.0.0.1:8797")
CODES = ["华中", "襄阳", "宜昌", "荆州", "黄石", "恩施"]
SECTION = "152507-1102002-4004"

def http(method, path, body=None, timeout=120):
    req = urllib.request.Request(BFF + path,
        data=json.dumps(body).encode() if body else None, method=method,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def extract(side, bidder, fields):
    j = http("POST", "/api/extract", {"batch_id": "152507", "side": side,
        "bidder": bidder, "fields": fields, "section_no": SECTION})
    jid = j["job_id"]
    for _ in range(60):
        time.sleep(3)
        job = http("GET", "/api/job/" + jid)
        if job.get("state") in ("done", "failed"):
            if job.get("state") != "done":
                raise RuntimeError("extract failed: %s" % job.get("error"))
            return job["result"]["fields"]
    raise RuntimeError("extract timeout")

def main():
    out = {}
    for code in CODES:
        p = os.path.join(HERE, "_judge_in_%s.json" % code)
        snap = json.load(open(p, encoding="utf-8"))
        bidder = snap["bidder"]
        print("[%s] %s 重抽…" % (code, bidder), flush=True)
        fields = [f["field"] for f in snap["bid_fields"]]
        new = {}
        for i in range(0, len(fields), 6):
            for f in extract("bid", bidder, fields[i:i+6]):
                new[f["field"]] = f
        snap["bid_fields"] = [new[k] for k in fields if k in new]
        # peer_facts 引用 bid.bidder_name / bid.legal_rep_name，同步刷新
        for pf in snap.get("peer_facts", []):
            pass  # peer 名与法人不变，仅 price 类字段不进 peer_facts，保持原样
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, ensure_ascii=False, indent=1)
        out[code] = {f["field"]: f.get("value_text") for f in snap["bid_fields"]}
        print("  price_items:", str(out[code].get("bid.price_items"))[:80], flush=True)
    json.dump(out, open(HERE + "/_judge_in_refresh_v29.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("重建完成，触发判定快照重算…", flush=True)
    r = http("POST", "/api/judge/refresh", {"codes": CODES}, timeout=400)
    print(json.dumps(r, ensure_ascii=False)[:400])

if __name__ == "__main__":
    main()
