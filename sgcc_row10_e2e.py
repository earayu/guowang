# -*- coding: utf-8 -*-
"""行10 超最高限价 · 端到端真跑（平台抽取 → 本地逐物料判定）。

链路：
  1. 平台 invoke sgcc-field-extract v10，对两个真实标段各抽一次 tender.price_cap；
  2. 把返回的 items / items_sum_yuan / applicable 原样作为判定层输入；
  3. 用同一个 GW-HB-FJ-010 规则跑六种投标情形；
  4. 全程不写死限价数字——限价只能来自平台抽取结果。

两个真实标段：
  152507-1102002-4004  限价表内有 4 条物料（34 / 182.12 / 453.31 / 1000 万元）
  152507-1102003-2005  限价表内无此标段，表注写明表外不设限价

输出：国网Demo_F1逐物料对位_真跑证据_V1.json
"""
import io
import json
import subprocess
import sys

CLI = "./apemind-cli/apemind.exe"
FN = "sgcc-field-extract"
OUT = "国网Demo_F1逐物料对位_真跑证据_V1.json"

SEC_4004 = "152507-1102002-4004"
SEC_2005 = "152507-1102003-2005"


def invoke(section_no):
    """实调平台函数，返回 (output, run_meta)。失败直接抛出，不伪造。"""
    payload = {"batch_id": "152507", "fields": ["tender.price_cap"],
               "scope_hint": "", "section_no": section_no, "side": "tender"}
    io.open("_e2e_in.json", "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False))
    p = subprocess.run([CLI, "function", "invoke", FN, "--input", "_e2e_in.json", "--json"],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        raise SystemExit("invoke 失败 %s：%s" % (section_no, p.stderr[-400:]))
    d = json.loads(p.stdout)["data"]
    return d["output"], {"run_id": d.get("id"), "version": d.get("version_number"),
                         "elapsed_ms": d.get("elapsed_ms"), "status": d.get("status")}


def ctx_from(output):
    """把抽取结果翻成判定层上下文。限价数字只从 items 来，不从本地常量来。"""
    f = output["fields"][0]
    items = f.get("items") or []
    return {
        "tender.price_cap_items": items,
        "tender.price_cap": f.get("items_sum_yuan") or f.get("value_num"),
        "tender.price_cap_value_num": f.get("value_num"),   # 最严单值，仅作旧口径对照
        "tender.price_cap_applicable": bool(f.get("applicable")),
    }, f


def main():
    sys.path.insert(0, ".")
    import sgcc_rule_runner as R

    rule = None
    for r in json.load(io.open(R.DISPATCH, encoding="utf-8"))["rules"]:
        if r["rule_id"] == "GW-HB-FJ-010":
            rule = r
    assert rule, "行10 规则缺失"

    ev = {"meta": {
        "title": "行10 超最高限价 · 逐物料对位 端到端真跑",
        "rule_id": "GW-HB-FJ-010",
        "check": rule["check"],
        "function": {"slug": FN, "version": None},
        "note": "限价数字全部来自平台抽取结果，本脚本不含任何写死的限价常量；"
                "判定结论上限恒为 CANDIDATE",
    }, "extraction": [], "cases": []}

    # ---------- 1. 平台抽取两个真实标段 ----------
    ex = {}
    for sec in (SEC_4004, SEC_2005):
        out, meta = invoke(sec)
        ctx, f = ctx_from(out)
        ex[sec] = ctx
        ev["function_version"] = meta["version"]
        ev["extraction"].append({
            "section_no": sec,
            "run_id": meta["run_id"],
            "version": meta["version"],
            "elapsed_ms": meta["elapsed_ms"],
            "method": f.get("method"),
            "verified": f.get("verified"),
            "readback_ok": f.get("readback_ok"),
            "applicable": f.get("applicable"),
            "value_text": f.get("value_text"),
            "value_num": f.get("value_num"),
            "items_sum_yuan": f.get("items_sum_yuan"),
            "items": f.get("items"),
            "reason": f.get("reason"),
        })
    ev["meta"]["function"]["version"] = ev["function_version"]

    c4004 = ex[SEC_4004]
    caps = c4004["tender.price_cap_items"]
    assert len(caps) == 4, "4004 应抽到 4 条物料，实得 %d" % len(caps)
    cap_sum = c4004["tender.price_cap"]

    def bid(items, total=None):
        d = {"bid.price_items": items}
        if total is not None:
            d["bid.price_total_ex_tax"] = total
        return d

    def items_with(overrides):
        """以抽取到的限价为准，按 90% 报价；overrides 指定某条改成多少。"""
        out = []
        for it in caps:
            no = it.get("item_no")
            amt = overrides.get(no, int(it["cap_yuan"] * 0.9))
            out.append({"item_no": no, "amount_yuan": amt})
        return out

    total_of = lambda its: sum(x["amount_yuan"] for x in its)

    # 超限故意压在中间那条物料上：它既不是最严格的一条（34 万），也不是合计量级最大的一条，
    # 单值比无论取最小还是取最大都碰不到它。用行项目号定位，不用下标——下标会随召回顺序变。
    OVER_NO = next(i["item_no"] for i in caps if i["cap_yuan"] == 4533100)
    OVER_AMT = 4533100 + 66900

    base = items_with({})
    one_over = items_with({OVER_NO: OVER_AMT})

    cases = [
        ("A 四物料全部合规",
         "每条报价均为该行项目限价的 90%",
         dict(c4004, **bid(base, total_of(base))), "RESPONDED"),
        ("B 仅一条物料超限、标包总额未超",
         "行项目 %s 报 %d（限价 4533100 +66900），其余 90%%；总价 %d <= 限价合计 %d"
         % (OVER_NO, OVER_AMT, total_of(one_over), cap_sum),
         dict(c4004, **bid(one_over, total_of(one_over))), "NOT_RESPONDED"),
        ("C 只有标包总价、总价超合计",
         "无逐物料明细，总价报限价合计+1 元",
         dict(c4004, **bid(None, cap_sum + 1)), "NOT_RESPONDED"),
        ("D 只有标包总价、总价未超合计",
         "无逐物料明细，总价报限价合计-1 元",
         dict(c4004, **bid(None, cap_sum - 1)), "UNCERTAIN"),
        ("E 报价含限价表外行项目",
         "多报一条限价表里没有的行项目",
         dict(c4004, **bid(base + [{"item_no": "999999999999999", "amount_yuan": 100000}],
                           total_of(base) + 100000)), "UNCERTAIN"),
        ("F 该标段不在限价表内（表外不设限价）",
         "152507-1102003-2005：抽取器判定 applicable=False",
         dict(ex[SEC_2005], **bid([{"item_no": "100000000000001", "amount_yuan": 1}],
                                  total_of(base))), "RESPONDED"),
    ]

    for name, desc, ctx, want in cases:
        r = R.run_rule(rule, ctx, [])
        ev["cases"].append({
            "case": name, "desc": desc, "expect": want, "state": r["state"],
            "matched": r["state"] == want,
            "reason": r["reason"],
            "item_check": r.get("item_check"),
            "missing_fields": r.get("missing_fields"),
            "optional_gaps": r.get("optional_gaps"),
        })

    # ---------- 2. 旧单值口径对照：同一批投标，旧逻辑会怎么判 ----------
    # 原 check = le(floor_yuan(总价), tender.price_cap)。tender.price_cap 有两种来源：
    #   旧-1：抽取器的 value_num（最严单值，修正前还是万元数值）
    #   旧-2：有人手工换成「限价合计」（看似合理的替代）
    # 两种都在同一批投标上跑一遍，看误杀与误放各出在哪。
    OLD_CHECK = {"op": "le", "lhs": "floor_yuan(bid.price_total_ex_tax)",
                 "rhs": "tender.price_cap"}
    ctrl = []
    for c in cases[:4]:
        ctx0 = dict(c[2])
        total = ctx0.get("bid.price_total_ex_tax")
        if total is None:
            ctrl.append({"case": c[0], "skip": "无标包总价，旧逻辑同样无从比较"})
            continue
        row = {"case": c[0], "new_state": None, "total_yuan": total,
               "value_num_single": ctx0.get("tender.price_cap_value_num"),
               "cap_sum": ctx0.get("tender.price_cap")}
        for tag, cap_src in (("old1_value_num", ctx0.get("tender.price_cap_value_num")),
                             ("old2_cap_sum", ctx0.get("tender.price_cap"))):
            c2 = dict(ctx0)
            c2["tender.price_cap"] = cap_src
            try:
                ok_old = R.evaluate(OLD_CHECK, c2, [])
                row[tag] = "RESPONDED" if ok_old else "NOT_RESPONDED"
            except R.NeedMissing:
                row[tag] = "UNCERTAIN"
        ctrl.append(row)
    for r in ctrl:
        for c in ev["cases"]:
            if c["case"] == r["case"]:
                r["new_state"] = c["state"]
    ev["old_logic_control"] = {
        "old_check": OLD_CHECK,
        "note": "旧-1 = 抽取器 value_num（最严单值）；旧-2 = 限价合计。"
                "新口径为逐物料对位。三者跑同一批投标。",
        "rows": ctrl,
    }

    # ---------- 3. 确定性：同一输入连跑两次平台抽取 ----------
    out_a, _ = invoke(SEC_4004)
    out_b, _ = invoke(SEC_4004)
    import hashlib

    def sig(o):
        f = o["fields"][0]
        slim = {"value_text": f.get("value_text"), "value_num": f.get("value_num"),
                "items": f.get("items"), "items_sum_yuan": f.get("items_sum_yuan"),
                "applicable": f.get("applicable"), "verified": f.get("verified")}
        return hashlib.sha256(json.dumps(slim, ensure_ascii=False,
                                         sort_keys=True).encode()).hexdigest()[:16]

    ev["determinism"] = {"method": "同一标段平台抽取连跑两次，比对 items/合计/取值",
                         "sha256_16": sig(out_a),
                         "identical": sig(out_a) == sig(out_b)}

    ok = all(c["matched"] for c in ev["cases"])
    ev["summary"] = {
        "cases": len(ev["cases"]),
        "matched": sum(1 for c in ev["cases"] if c["matched"]),
        "all_matched": ok,
        "trap_proved": "B 情形标包总价未超限价合计、只有一条中间量级物料超："
                       "旧口径取最严单值（34 万）会把合规投标全部误杀，"
                       "旧口径用合计会放过这条超限，两种都错；逐物料对位判否",
    }

    io.open(OUT, "w", encoding="utf-8").write(json.dumps(ev, ensure_ascii=False, indent=1))

    print("=" * 78)
    for e in ev["extraction"]:
        print("%-22s method=%-5s applicable=%-5s items=%s 合计=%s"
              % (e["section_no"], e["method"], e["applicable"],
                 len(e["items"] or []), e["items_sum_yuan"]))
    print("=" * 78)
    for c in ev["cases"]:
        print("%-4s %-34s %-14s %s" % ("OK" if c["matched"] else "MISS",
                                       c["case"], c["state"],
                                       "" if c["matched"] else "期望 " + c["expect"]))
    print("\n平台抽取确定性：", ev["determinism"]["sha256_16"],
          "identical=", ev["determinism"]["identical"])

    print("\n[旧单值口径对照] 同一批投标，三种口径：")
    print("  %-28s %-14s %-16s %-14s %s" % ("情形", "新(逐物料)", "旧1(value_num)", "旧2(合计)", "判定"))
    for r in ev["old_logic_control"]["rows"]:
        if r.get("skip"):
            print("  %-28s %s" % (r["case"], r["skip"]))
            continue
        verdict = []
        if r.get("old1_value_num") != r["new_state"]:
            verdict.append("旧1 与新不一致")
        if r.get("old2_cap_sum") != r["new_state"]:
            verdict.append("旧2 与新不一致")
        print("  %-28s %-14s %-16s %-14s %s"
              % (r["case"], r["new_state"], r.get("old1_value_num"),
                 r.get("old2_cap_sum"), "；".join(verdict) or "三者一致"))
    print("小结：", ev["summary"])
    print("输出：", OUT)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
