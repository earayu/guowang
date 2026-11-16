# -*- coding: utf-8 -*-
"""判定函数平台真跑：6 家逐一 invoke sgcc-rule-judge，与 F3 基线逐条对比。

为什么必须上平台真跑：本地回归证明的是"同一份代码跑同一份输入得到同一结果"，
证明不了"平台沙箱里 import 得到、schema 收得住、运行时不超时"。
这台机器的 CLI 每次调用还有 2.4~3.6s 进程开销，演示要讲"实时"就得先摸清这个数。

输入只用现场的抽取原文（_f3v2_tender_out.json 合并 v27 交货期 + _f3v2_bid_live.json），
不预热任何判定结论。peer_facts 只给法定代表人（行39 唯一需要的跨家字段），
避免把整套 items 当同行事实塞进去。

产出：国网Demo_F4_判定函数_平台真跑证据_V1.json
"""
import io
import json
import os
import subprocess
import sys
import time

CLI = "./apemind-cli/apemind.exe"
FN = "sgcc-rule-judge"
F3 = "国网Demo_F3_46条规则端到端_真跑证据_V2.json"
LIVE = "_f3v2_bid_live.json"
TENDER_OUT = "_f3v2_tender_out.json"
OUT = "国网Demo_F4_判定函数_平台真跑证据_V1.json"

WAIT = (8, 20, 40)


def run(args, timeout=300):
    p = subprocess.run([CLI] + args, capture_output=True, text=True,
                       encoding="utf-8", timeout=timeout)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def invoke(payload, tag, attempt=0):
    path = "_judge_in_%s.json" % tag
    io.open(path, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False))
    t0 = time.time()
    rc, out, err = run(["function", "invoke", FN, "--input", path, "--json"])
    wall = round((time.time() - t0) * 1000)
    if rc == 0:
        d = json.loads(out)["data"]
        return d.get("output"), {"run_id": d.get("id"), "version": d.get("version_number"),
                                 "status": d.get("status"), "ms": d.get("elapsed_ms"),
                                 "wall_ms": wall, "attempts": attempt + 1,
                                 "error": d.get("error_message")}
    last = (err or out)[-400:]
    if attempt < len(WAIT) and ("network_unavailable" in last or "timed out" in last.lower()):
        time.sleep(WAIT[attempt])
        return invoke(payload, tag, attempt + 1)
    return None, {"error": last, "attempts": attempt + 1, "wall_ms": wall}


def tender_fields(f3):
    """基准侧：out 文件给 items/value_num，证据 meta 给 v27 的交货期。"""
    tf = json.load(io.open(TENDER_OUT, encoding="utf-8"))["fields"]
    meta = f3["meta"]["tender_extract"]["fields"]
    out = []
    for f in tf:
        m = meta.get(f["field"]) if isinstance(meta, dict) else None
        if m and m.get("value_text") not in (None, "NOT_FOUND"):
            f = dict(f, value_text=m["value_text"])
        out.append(f)
    return out


def slim_facts(fields, bidder):
    """只留跨家规则要用的两个字段。"""
    fs = {f.get("field"): f.get("value_text") for f in fields}
    return {"bid.bidder_name": bidder, "bid.legal_rep_name": fs.get("bid.legal_rep_name")}


def main():
    f3 = json.load(io.open(F3, encoding="utf-8"))
    live = json.load(io.open(LIVE, encoding="utf-8"))
    tf = tender_fields(f3)
    bids = live["bidders"]

    report = {"meta": {
        "title": "判定函数 sgcc-rule-judge 平台真跑（6 家 × 46 条，对照 F3 基线）",
        "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "function": FN,
        "rule_set": "V2",
        "section_no": f3["meta"]["section_no"],
        "inputs": {"tender": TENDER_OUT + " + F3 meta 的 v27 交货期", "bids": LIVE},
    }, "cases": [], "summary": {}}

    total_cmp, total_bad = 0, 0
    for m in f3["matrix"]:
        bidder = m["bidder"]
        rec = next(b for b in bids if b["bidder"] == bidder)
        peers = [slim_facts(b["fields"], b["bidder"]) for b in bids if b["bidder"] != bidder]
        payload = {"section_no": f3["meta"]["section_no"], "bidder": bidder,
                   "tender_fields": tf, "bid_fields": rec["fields"], "peer_facts": peers}

        out, meta = invoke(payload, rec["code"])
        if out is None:
            report["cases"].append({"bidder": bidder, "code": rec["code"],
                                    "error": meta, "diffs": None})
            print("%-4s 调用失败：%s" % (rec["code"], str(meta)[:200]))
            continue

        got = {r["rule_id"]: r for r in out["rows"]}
        diffs = []
        for d in m["decided"]:
            total_cmp += 1
            g = got.get(d["rule_id"])
            if g is None:
                diffs.append({"rule_id": d["rule_id"], "row": d["row"],
                              "base": d["state"], "now": "MISSING_RULE"})
            elif g["state"] != d["state"]:
                diffs.append({"rule_id": d["rule_id"], "row": d["row"],
                              "base": d["state"], "now": g["state"],
                              "now_reason": g.get("reason")})
        total_bad += len(diffs)

        report["cases"].append({
            "bidder": bidder, "code": rec["code"], "expect": m["expect"],
            "run": meta,
            "total": out["total"], "decided": out["decided"], "counts": out["counts"],
            "fail_rows": out["fail_rows"], "uncertain_rows": out["uncertain_rows"],
            "rule_set_sha": out["rule_set_sha"], "elapsed_ms": out["elapsed_ms"],
            "key_rows": {str(k): next((r["state"] for r in out["rows"] if r["row"] == k), None)
                         for k in (4, 7, 10, 11, 13, 16, 17, 39)},
            "diffs": diffs,
            "fail_reasons": [{"row": r["row"], "rule_id": r["rule_id"], "reason": r["reason"]}
                             for r in out["rows"] if r["state"] == "NOT_RESPONDED"],
            "sample_item_check": next((r.get("item_check") for r in out["rows"]
                                       if r.get("item_check")), None),
        })
        print("%-4s %-6s run=%s v%s %5sms 计数=%s 判否行=%s 不一致=%d"
              % (rec["code"], bidder[:6], str(meta.get("run_id"))[-8:], meta.get("version"),
                 meta.get("ms"), out["counts"], out["fail_rows"], len(diffs)))

    report["summary"] = {
        "cases": len(report["cases"]),
        "compared": total_cmp,
        "mismatch": total_bad,
        "all_pass": total_bad == 0 and total_cmp > 0,
    }
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(report, ensure_ascii=False, indent=1))
    print("\n对比 %d 条，不一致 %d 条 → %s" % (total_cmp, total_bad,
                                          "PASS" if report["summary"]["all_pass"] else "FAIL"))
    print("证据：%s" % OUT)
    return 0 if report["summary"]["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
