# -*- coding: utf-8 -*-
"""F3 · 46 条否决情形全链路端到端（v2 六家版）。

与 V1 的差别（V1 是 5 家、未含税口径、受审侧读旧证据）：
  1. 受审侧 6 家全部**现场 invoke**，不再读上一轮证据文件。理由是 v2 的
     逐行报价明细（items）在旧证据里没有落盘，只有「N 条/一致」的结论；
     行 10/行 11 要逐行对位，拿结论当输入等于把结论再算一遍。
  2. 签章类字段按抽取原文解析，不硬编码 True。v2 的襄阳剧本就是
     「电子签章名称与投标人不是同一人」，硬编码会把这条判成合规。
  3. 行 10 的口径按 dispatch v2（含税对含税）。v1 那张表拿未含税行价
     比含税限价，在 v2 数据上会漏掉宜昌那一行（差额 6.69 万）。
  4. 期望判否的规则若因基准侧缺字段跑不了，记 blocked 并写明缺哪个字段，
     既不算通过也不算失败——不拿假定值把 46 条填满。

输出：国网Demo_F3_46条规则端到端_真跑证据_V2.json
中间件：_f3v2_bid_live.json（现场抽取原文，含 items 明细，可复核）
"""
import io
import json
import os
import re
import subprocess
import sys
import time

CLI = "./apemind-cli/apemind.exe"
FN = "sgcc-field-extract"
SECTION = "152507-1102002-4004"
SCOPE = "4004"
F2 = "国网Demo_F2受审侧抽取v2_真跑证据.json"
LIVE = "_f3v2_bid_live.json"
OUT = "国网Demo_F3_46条规则端到端_真跑证据_V2.json"
DISPATCH = "国网Demo_规则可执行化_46条分派表_V2.json"

BID_FIELDS = ["bid.bidder_name", "bid.seal_present", "bid.seal_valid", "bid.seal_name",
              "bid.price_items", "bid.price_total_ex_tax", "bid.committed_delivery_date",
              "bid.validity_days", "bid.tax_rate", "bid.legal_rep_name", "bid.bond_amount"]
TENDER_FIELDS = ["tender.price_cap", "tender.required_validity_days",
                 "tender.required_delivery_date", "tender.bond_required"]

# 法定税率集合：外部法规常量，不是从文件抽的（与 V1 同口径，单独标注来源）
LEGAL_TAX = [0.13, 0.09, 0.06, 0.03, 0.01, 0.0]
LEGAL_TAX_SRC = "财税〔2018〕32 号、财政部税务总局海关总署公告 2019 年第 39 号：13%/9%/6%/3%/1%/0"

WAIT = (10, 25, 45, 70)


def run(args, timeout=300):
    p = subprocess.run([CLI] + args, capture_output=True, text=True,
                       encoding="utf-8", timeout=timeout)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def invoke(payload, tag):
    """现场调用抽取函数。链路每几分钟抖一次，退避重试，失败要显式记下来。"""
    path = "_f3v2_in_%s.json" % tag
    io.open(path, "w", encoding="utf-8").write(json.dumps(payload, ensure_ascii=False))
    last = ""
    for attempt in range(len(WAIT) + 1):
        rc, out, err = run(["function", "invoke", FN, "--input", path, "--json"])
        if rc == 0:
            d = json.loads(out)["data"]
            return d.get("output"), {"run_id": d.get("id"),
                                     "version": d.get("version_number"),
                                     "status": d.get("status"),
                                     "ms": d.get("elapsed_ms"),
                                     "attempts": attempt + 1,
                                     "error": d.get("error_message")}
        last = (err or out)[-300:]
        if "network_unavailable" in last or "timed out" in last.lower():
            if attempt < len(WAIT):
                time.sleep(WAIT[attempt])
            continue
        break
    return None, {"error": last, "attempts": attempt + 1}


# ---------------------------------------------------------------- 原文解析
def parse_seal_present(t):
    """签章是否加盖。否定优先。

    真跑抓到的坑：同一语义模型会给三种表述——
      「是（已加盖电子签章）」（襄阳）、「通过」（宜昌）、「是」（恩施）。
    原实现只认含「加盖/签章」的，后两种被当成「无法判定」→ 规则按缺字段不判，
    页面却显示字段有值，客户点开就会问「字段明明在，为什么说缺」。
    所以肯定侧补上 是/有/通过/已签。"""
    t = str(t or "").strip()
    if any(x in t for x in ("未加盖", "无电子签章", "未签章", "缺签章", "未盖", "否", "没有")):
        return False
    if any(x in t for x in ("加盖", "签章", "通过", "已签", "是", "有")):
        return True
    return None


def parse_seal_valid(t):
    """签章有效性。否定词优先：襄阳的原文是「验证通过（签章主体与投标人不一致）」，
    只找「通过」二字会判成有效——这正是 v1 E2E 误伤过的地方。"""
    t = str(t or "")
    if any(x in t for x in ("不一致", "不符", "无效", "未通过", "失败", "不能验证")):
        return False
    if "通过" in t or "一致" in t:
        return True
    return None


def parse_date(t):
    m = re.search(r"\d{4}-\d{2}-\d{2}", str(t or ""))
    return m.group(0) if m else None


def build_tender(out):
    tf = {f["field"]: f for f in out["fields"]}
    tender, src = {}, {}
    for k, f in tf.items():
        src[k] = {"method": f.get("method"), "verified": f.get("verified"),
                  "value_text": f.get("value_text"), "source": f.get("source"),
                  "applicable": f.get("applicable")}
        if f.get("value_text") == "NOT_FOUND":
            continue
        if k == "tender.price_cap":
            tender["tender.price_cap_items"] = [
                {"item_no": i["item_no"], "cap_yuan": i["cap_yuan"]} for i in (f.get("items") or [])]
            tender["tender.price_cap"] = f.get("items_sum_yuan")
            tender["tender.price_cap_applicable"] = bool(f.get("applicable"))
        else:
            # 交货期是 ISO 日期串，value_num 为空；按原文取，别送 None 进判定层
            tender[k] = (f.get("value_text") if k == "tender.required_delivery_date"
                         else f.get("value_num"))
            if f.get("applicable") is False:
                tender[k + ".__na"] = True
    tender["legal.tax_rate_set"] = LEGAL_TAX
    return tender, src


def build_bid(b):
    """把一家投标人的现场抽取结果翻译成判定层 ctx。"""
    ctx, notes = {}, []
    fs = {f["field"]: f for f in b["fields"]}

    def g(name):
        return fs.get(name) or {}

    ctx["bid.bidder_name"] = b["bidder"]

    f = g("bid.seal_present")
    ctx["bid.seal_present"] = parse_seal_present(f.get("value_text"))
    if ctx["bid.seal_present"] is None:
        notes.append("seal_present 原文无法判定：%s" % f.get("value_text"))

    f = g("bid.seal_valid")
    ctx["bid.seal_valid"] = parse_seal_valid(f.get("value_text"))
    if ctx["bid.seal_valid"] is None:
        notes.append("seal_valid 原文无法判定：%s" % f.get("value_text"))

    # 签章名称做归一：同一字段模型会给「XX有限公司」和「XX有限公司（电子签章）」两种写法，
    # 直接比会把后缀当成「签章主体与投标人不是同一人」→ 恩施被误判（真跑抓到）。
    _sn = str(g("bid.seal_name").get("value_text") or "")
    _sn = re.sub(r"[（(]\s*电子签章\s*[)）]", "", _sn).strip()
    ctx["bid.seal_name"] = _sn or None

    for name, key in (("bid.validity_days", "bid.validity_days"),
                      ("bid.tax_rate", "bid.tax_rate"),
                      ("bid.price_total_ex_tax", "bid.price_total_ex_tax")):
        f = g(name)
        ctx[key] = f.get("value_num")

    ctx["bid.legal_rep_name"] = g("bid.legal_rep_name").get("value_text")
    ctx["bid.committed_delivery_date"] = parse_date(
        g("bid.committed_delivery_date").get("value_text"))

    f = g("bid.bond_amount")
    if f.get("applicable") is False:
        ctx["bid.bond_amount"] = None
        ctx["bid.bond_amount.__na"] = True
    else:
        ctx["bid.bond_amount"] = f.get("value_num")

    f = g("bid.price_items")
    items, seen = [], set()
    for it in (f.get("items") or []):
        no = it.get("item_no")
        if not no or no in seen:          # docx 汇总表与 xlsx 分项表同数据，按行号去重
            continue
        seen.add(no)
        items.append({"item_no": no, "qty": it.get("qty"),
                      "unit_price_yuan": it.get("unit_price_yuan"),
                      "amount_yuan": it.get("amount_yuan"),
                      "calc_amount_yuan": it.get("calc_amount_yuan"),
                      "arith_ok": it.get("arith_ok")})
    ctx["bid.price_items"] = items
    ctx["bid.price_items.items_sum_yuan"] = sum((i.get("amount_yuan") or 0) for i in items)
    dec = f.get("declared_total_yuan")
    if isinstance(dec, (int, float)) and dec:
        ctx["bid.price_items.declared_total_yuan"] = dec

    return ctx, notes, {"items_count": len(items),
                        "items_sum_yuan": ctx["bid.price_items.items_sum_yuan"],
                        "declared_total_yuan": dec}


def row_of(defect_rule):
    m = re.search(r"(\d+)", str(defect_rule or ""))
    return int(m.group(1)) if m else None


def main():
    sys.path.insert(0, ".")
    import sgcc_rule_runner as R

    rules = json.load(io.open(DISPATCH, encoding="utf-8"))["rules"]
    by_row = {r["row"]: r for r in rules}

    f2 = json.load(io.open(F2, encoding="utf-8"))
    cached = {}
    if os.path.exists(LIVE):
        try:
            cached = {x["code"]: x for x in json.load(io.open(LIVE, encoding="utf-8"))["bidders"]}
        except Exception:
            cached = {}

    # ---------- 1. 基准侧现场抽取 ----------
    print("[基准侧] 现场抽取 %d 个字段 ..." % len(TENDER_FIELDS))
    t_out, t_meta = invoke({"batch_id": "152507", "fields": TENDER_FIELDS,
                            "scope_hint": SCOPE, "section_no": SECTION,
                            "side": "tender"}, "tender")
    if t_out is None:
        raise SystemExit("基准侧抽取失败：" + str(t_meta.get("error"))[-300:])
    tender, tender_src = build_tender(t_out)
    print("   run=%s v%s 交货期=%s" % (t_meta["run_id"], t_meta["version"],
                                      tender_src["tender.required_delivery_date"]["value_text"]))

    # ---------- 2. 受审侧 6 家现场抽取 ----------
    bids, bid_meta = [], {}
    live = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "bidders": []}
    for b in f2["bidders"]:
        code, name = b["code"], b["bidder"]
        # 只复用「真抽到了字段」的家。失败记录也进了缓存文件，若一并复用，
        # 缺的那家会被当成已完成，永远补不上——断点续跑反而把缺陷固化了。
        if code in cached and cached[code].get("fields") and not cached[code].get("error"):
            rec = cached[code]
            src = "cache"
        else:
            print("[受审侧 %s] %s ..." % (code, b["expect"]))
            src = "live"
            out, meta = invoke({"batch_id": "152507", "fields": BID_FIELDS,
                                "scope_hint": "", "section_no": SECTION,
                                "side": "bid", "bidder": name}, "bid_%s" % code)
            rec = {"code": code, "bidder": name, "meta": meta, "fields": []}
            if out is None:
                rec["error"] = str(meta.get("error"))[-300:]
                print("   失败：", rec["error"])
            else:
                # 只留判定要用到的原文，别把整包 trace 塞进证据里
                keep = ("field", "value_text", "value_num", "applicable", "method",
                        "verified", "source", "items", "declared_total_yuan", "items_sum_yuan")
                rec["fields"] = [{k: f.get(k) for k in keep} for f in out["fields"]]
                print("   字段 %d 个，累计 %.1fs" % (len(rec["fields"]), (meta.get("ms") or 0) / 1000.0))
            time.sleep(2)
        live["bidders"].append(rec)
        if rec.get("fields"):
            ctx, notes, extra = build_bid(rec)
            ctx["__code"] = code
            bids.append((b, ctx, notes, extra))
            bid_meta[code] = {"run_id": rec["meta"].get("run_id"),
                              "version": rec["meta"].get("version"),
                              "source": src, "notes": notes, "items": extra}
    io.open(LIVE, "w", encoding="utf-8").write(json.dumps(live, ensure_ascii=False, indent=1))

    if len(bids) != 6:
        raise SystemExit("只跑到 %d 家，6 家未齐不算通过（链路抖动请重跑，缓存会复用已成功的家）" % len(bids))

    # ---------- 3. 哪些规则能被现有字段喂饱 ----------
    available = set(tender)
    for _, ctx, _, _ in bids:
        available |= set(ctx)
    runnable, skipped = [], []
    for r in rules:
        need = set(r["needs"])
        missing = sorted(need - available)
        if missing:
            skipped.append({"rule_id": r["rule_id"], "row": r["row"],
                            "exec_path": r["exec_path"], "missing_fields": missing})
        else:
            runnable.append(r)

    # ---------- 4. 逐家判定 ----------
    matrix, problems = [], []
    for b, ctx, notes, extra in bids:
        c2 = dict(tender)
        c2.update(ctx)
        group = [x[1] for x in bids]
        rows = [R.run_rule(r, c2, group) for r in runnable]

        want_row = row_of(b["defect_rule"])
        want_rule = (by_row.get(want_row) or {}).get("rule_id")
        skipped_ids = {s["rule_id"] for s in skipped}

        decided, blocked = [], None
        for r in rows:
            should_bad = (r["rule_id"] == want_rule)
            is_bad = (r["state"] == R.STATE_FAIL)
            ok = (is_bad == should_bad)
            decided.append({"rule_id": r["rule_id"], "row": r["row"],
                            "category": r["category"], "subcategory": r["subcategory"],
                            "state": r["state"], "should_fail": should_bad, "ok": ok,
                            "reason": r["reason"], "evidence": r["evidence"],
                            "item_check": r.get("item_check")})
            if not ok:
                problems.append({"bidder": b["bidder"], "rule_id": r["rule_id"],
                                 "row": r["row"], "should_fail": should_bad,
                                 "state": r["state"], "reason": r["reason"]})

        # 期望判否的那条若跑不了，是「没验」不是「通过」
        if want_rule and want_rule in skipped_ids:
            s = [x for x in skipped if x["rule_id"] == want_rule][0]
            blocked = {"rule_id": want_rule, "row": want_row,
                       "missing_fields": s["missing_fields"],
                       "why": "基准侧字段未抽到，本条无法机器判定，转人工澄清"}
            problems = [p for p in problems if not (p["bidder"] == b["bidder"]
                                                    and p["row"] == want_row)]

        matrix.append({
            "bidder": b["bidder"], "code": b["code"], "expect": b["expect"],
            "should_fail": want_rule, "should_fail_row": want_row,
            "decided": decided,
            "fail_count": sum(1 for d in decided if d["state"] == R.STATE_FAIL),
            "blocked": blocked,
            "ok": all(d["ok"] for d in decided) and blocked is None,
            "input_notes": notes,
        })

    # ---------- 5. 覆盖统计 ----------
    MACHINE = ("DET", "EXTRACT_DET")
    machine_rules = [r for r in rules if r["exec_path"] in MACHINE]
    machine_runnable = [r for r in runnable if r["exec_path"] in MACHINE]

    blocked_fields = {}
    for s in skipped:
        for f in s["missing_fields"]:
            blocked_fields.setdefault(f, []).append(s["rule_id"])
    blocked_fields = dict(sorted(blocked_fields.items(), key=lambda kv: -len(kv[1])))

    ev = {
        "meta": {
            "title": "46 条否决情形 · 全链路端到端（v2 六家，真实抽取 → 逐条判定）",
            "section_no": SECTION,
            "generated": time.strftime("%Y-%m-%d %H:%M:%S"),
            "tender_extract": {"run_id": t_meta["run_id"], "version": t_meta["version"],
                               "attempts": t_meta.get("attempts"), "fields": tender_src},
            "bid_extract": {"source": "现场 invoke（%s）" % LIVE,
                            "bidders": bid_meta,
                            "note": "6 家 × 11 字段现场抽取；逐行报价明细一并落盘，行10/行11 按行对位"},
            "dispatch": DISPATCH,
            "row10_basis": "含税对含税：投标行含税 = 未含税行合价 ×(1+税率)，与限价表含税行限价比",
            "data_nature": "投标侧为合成演示数据；物料/行项目号/限价/交货期取自 152507 公开招标文件",
            "honesty": ("只对依赖字段全部来自真实抽取的规则出结论；期望判否但缺字段的记 blocked，"
                        "不拿场景假定值填满 46 条。法定税率集合为外部法规常量，单列来源。"),
            "legal_tax_rate_set": {"values": LEGAL_TAX, "source": LEGAL_TAX_SRC},
        },
        "coverage": {
            "rules_total": len(rules),
            "machine_rules": len(machine_rules),
            "machine_runnable": len(machine_runnable),
            "machine_runnable_rows": [r["row"] for r in machine_runnable],
            "machine_blocked": len(machine_rules) - len(machine_runnable),
            "human_path_rules": len(rules) - len(machine_rules),
            "decided_on_page": len(runnable),
            "runnable_ids": [r["rule_id"] for r in runnable],
            "expected_fail_hit": sum(1 for m in matrix if m["blocked"] is None and m["ok"]),
            "expected_fail_blocked": sum(1 for m in matrix if m["blocked"] is not None),
        },
        "blocked_fields": blocked_fields,
        "skipped_rules": skipped,
        "matrix": matrix,
        "problems": problems,
    }
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(ev, ensure_ascii=False, indent=1))

    # ---------- 6. 人读摘要 ----------
    print("=" * 88)
    print("46 条：机器可判 %d，本次字段喂饱 %d（行 %s），卡字段 %d"
          % (len(machine_rules), len(machine_runnable),
             ",".join(str(r["row"]) for r in machine_runnable),
             len(machine_rules) - len(machine_runnable)))
    for m in matrix:
        tag = "命中" if (m["blocked"] is None and m["ok"]) else (
            "BLOCKED 行%s 缺 %s" % (m["blocked"]["row"], ",".join(m["blocked"]["missing_fields"]))
            if m["blocked"] else "有偏差")
        print("\n%-26s 剧本：%-30s %s" % (m["bidder"], m["expect"], tag))
        for d in m["decided"]:
            if d["state"] == R.STATE_FAIL or d["should_fail"]:
                mark = "判否" if d["state"] == R.STATE_FAIL else "未否"
                print("   行%-3s %-12s %-14s %s %s" % (d["row"], d["subcategory"],
                                                      d["state"], mark,
                                                      "" if d["ok"] else "← 与剧本不符"))
                if d.get("item_check") and d["item_check"].get("over"):
                    for o in d["item_check"]["over"]:
                        print("      超限价行：%s" % json.dumps(o, ensure_ascii=False))
    print("\n与剧本不符 %d 处" % len(problems))
    for p in problems:
        print("  ", p)
    print("输出：", OUT)
    return 0 if not problems else 1


if __name__ == "__main__":
    sys.exit(main())
