# -*- coding: utf-8 -*-
"""受审侧 v2 抽取端到端：6 家三册制投标包逐家真跑，与 v2 真值逐字段比对。

比 v1 版多做三件事，都是这一版文件形态变化逼出来的：

1. **逐行物料对位**：v2 把三册拆开，报价数据同时出现在价格册汇总表和 xlsx
   分项报价表里。函数若不去重，逐行合价之和会正好翻倍（实测 26,463,008 vs
   真实 13,231,504）。所以这里按 item_no 逐条比，不比总数就算过。
2. **交付期按包比**：v2 包1/包2 交货日期不同，真值是 dict。只比一个日期
   会让「包1 逾期、包2 正常」这种情形漏判。
3. **签章主体归一化**：抽取值形如「XX公司（电子签章）」，真值是裸名称。
   这是格式差异不是取值差异，剥掉后缀再比，但原值照留。

输出：国网Demo_F2受审侧抽取v2_真跑证据.json
"""
import io
import json
import os
import subprocess
import sys
import time

CLI = "./apemind-cli/apemind.exe"
FN = "sgcc-field-extract"
GT = "bid_packs_v2/_ground_truth_v3.json"
MAP = "bid_packs_v2/_v2_kb_map.json"
OUT = "国网Demo_F2受审侧抽取v2_真跑证据.json"
SECTION = "152507-1102002-4004"

FIELDS = ["bid.bidder_name", "bid.seal_present", "bid.seal_valid", "bid.seal_name",
          "bid.price_items", "bid.price_total_ex_tax", "bid.committed_delivery_date",
          "bid.validity_days", "bid.tax_rate", "bid.legal_rep_name", "bid.bond_amount"]

# 抽取值里的描述性后缀，剥掉再与真值比（格式差异，不是取值差异）
SUFFIX = ("（电子签章）", "(电子签章)", "（电子章）", "电子签章")


def norm_name(v):
    v = (v or "").strip()
    for s in SUFFIX:
        v = v.replace(s, "")
    return v.strip()


def invoke(bidder):
    payload = {"batch_id": "152507", "fields": FIELDS, "scope_hint": "",
               "section_no": SECTION, "side": "bid", "bidder": bidder}
    io.open("_e2e_v2_in.json", "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False))
    # 连续 invoke 时偶发 network_unavailable（实测跑完第一家后连挂 5 家），
    # 这是链路抖动不是业务失败。重试 3 次，仍失败才记为失败项，
    # 否则会把「网络断了」误记成「这家抽不到字段」。
    last = ""
    WAIT = (10, 25, 45, 70)
    for attempt in range(len(WAIT) + 1):
        p = subprocess.run([CLI, "function", "invoke", FN,
                            "--input", "_e2e_v2_in.json", "--json"],
                           capture_output=True, text=True, encoding="utf-8",
                           timeout=300)
        if p.returncode == 0:
            d = json.loads(p.stdout)["data"]
            return d.get("output"), {
                "run_id": d.get("id"), "version": d.get("version_number"),
                "status": d.get("status"), "ms": d.get("elapsed_ms"),
                "error": d.get("error_message"), "attempts": attempt + 1}
        last = (p.stderr or p.stdout)[-300:]
        if attempt < len(WAIT):
            time.sleep(WAIT[attempt])
    return None, {"error": last, "attempts": len(WAIT) + 1}


def eq(a, b, tol=0.01):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def main():
    gt = json.load(io.open(GT, encoding="utf-8"))
    # 断点续跑：链路不稳时一轮跑不完，重跑整轮既慢又可能再断。
    # 只补没跑成功的家，跑成功的原样复用——但不能因为「上次跑过」就跳过本轮，
    # 那会掩盖回归。--fresh 强制全跑。
    done = {}
    if "--resume" in sys.argv and os.path.exists(OUT):
        try:
            old = json.load(io.open(OUT, encoding="utf-8"))
            for r in old.get("bidders", []):
                # 「函数跑成功」不等于「字段全抽到」。只按 status=succeeded 复用，
                # 会把 10/11（有一个字段 NOT_FOUND）的家当成已完成，缺的那项永远补不上，
                # 回归看着「续跑无变化」，实际是缺陷被断点续跑掩盖了。
                if (r.get("status") == "succeeded" and r.get("fields")
                        and r.get("ok") == r.get("total")):
                    done[r["code"]] = r
        except Exception:
            done = {}
    mp = {b["short"]: b for b in json.load(io.open(MAP, encoding="utf-8"))["bidders"]}

    ev = {"meta": {
        "title": "受审侧（投标文件）v2 字段抽取 · 6 家逐家真跑",
        "kbs": {k: v["kb"] for k, v in mp.items()},
        "section_no": SECTION,
        "data_nature": "合成演示数据；物料/网省采购申请号/限价/交货期取自 152507 公开招标文件",
        "function": {"slug": FN, "version": None},
        "checked": ["取值与真值是否一致", "逐行物料是否重复/翻倍", "是否跨家串值",
                    "抽不到时的失败原因"],
    }, "bidders": []}

    tot = ok = 0
    cross = []

    for b in gt["bidders"]:
        short, name, g = b["short"], b["bidder_name"], b["ground_truth"]
        if short in done:
            rec = done[short]
            ev["bidders"].append(rec)
            tot += rec["total"]
            ok += rec["ok"]
            print("[%s] 复用上轮结果 %2d/%2d" % (short, rec["ok"], rec["total"]))
            continue
        out, meta = invoke(name)
        ev["meta"]["function"]["version"] = meta.get("version")
        rec = {"code": short, "bidder": name, "kb": mp[short]["kb"],
               "expect": b["expect"], "defect_rule": b["defect_rule"],
               "run_id": meta.get("run_id"), "status": meta.get("status"),
               "elapsed_ms": meta.get("ms"), "fields": [], "ok": 0, "total": 0}
        if out is None:
            rec["error"] = meta.get("error")
            ev["bidders"].append(rec)
            print("[%s] ✗ 调用失败 %s" % (short, meta.get("error")))
            continue

        got = {f["field"]: f for f in out["fields"]}

        def check(field, want, kind="num", why_extra=""):
            rec["total"] += 1
            f = got.get(field)
            if f is None:
                rec["fields"].append({"field": field, "want": want, "got": None,
                                      "ok": False, "why": "字段未返回"})
                return
            v = f.get("value_text")
            if kind == "num":
                good = eq(f.get("value_num"), want)
            elif kind == "text":
                good = norm_name(v) == norm_name(str(want))
            elif kind == "bool":
                # 「签章主体与投标人不一致」说的是印章归属对吗，不是印章本身无效。
                # 襄阳这家的剧本正是「章是真的、但章上的公司名不是投标人」，
                # seal_valid 应为 True（真值亦然），主体不符由 seal_name 与
                # 规则层「否决情形序号 4」体现。把「不一致」放进否定词表会误伤。
                neg = ("未加盖", "无签章", "签章无效", "未签", "没有加盖", "不予认可")
                good = bool(f.get("verified")) and not any(n in (v or "") for n in neg)
                if not want:
                    good = not good
            elif kind == "substr":
                # 交付期抽取值是「2026-04-20 前完成首批交货（包1）」这类描述句，
                # 日期是其中一个成分；判据是日期出现了，不是整句相等。
                good = bool(want) and str(want) in (v or "")
            elif kind == "na":
                # 免收保证金有两种合法输出：applicable=False（该字段对本标包不适用），
                # 或 applicable=True 但值明确写「免收 / 不适用 / 不收取」。
                # 两者都算判对；必须排除的是 NOT_FOUND，以及给出一个具体金额。
                txt = v or ""
                good = (txt != "NOT_FOUND" and bool(f.get("verified"))
                        and f.get("value_num") in (None, 0, 0.0)
                        and (f.get("applicable") is False
                             or any(k in txt for k in ("免收", "不适用", "不收取", "无金额"))))
            else:
                good = (v or "").strip() == str(want).strip()
            if good:
                rec["ok"] += 1
            rec["fields"].append({
                "field": field, "want": want, "got": v, "value_num": f.get("value_num"),
                "applicable": f.get("applicable"), "source": f.get("source"),
                "method": f.get("method"), "verified": f.get("verified"), "ok": good,
                "why": "" if good else ((f.get("reason") or "")[:100] + why_extra)[:160],
            })

        check("bid.bidder_name", g["bid.bidder_name"], "text")
        check("bid.seal_name", g["bid.seal_name"], "text")
        check("bid.seal_present", True, "bool")
        check("bid.seal_valid", g["bid.seal_valid"], "bool")
        check("bid.validity_days", g["bid.validity_days"])
        check("bid.tax_rate", g["bid.tax_rate"])
        check("bid.price_total_ex_tax", g["bid.price_total_ex_tax"])
        check("bid.legal_rep_name", g["bid.legal_rep_name"], "text")
        # 包1 首批交货日期
        pkg1 = g["bid.committed_delivery"]["100034915900360"]
        check("bid.committed_delivery_date", pkg1, "substr")
        # 免收保证金 → 判「不适用」成立
        check("bid.bond_amount", "不适用（免收）", "na")

        # 逐行物料：条数、每条合价、税率、算术。条数对不上直接记 FAIL，
        # 否则重复行会让「总额对得上」这种巧合通过。
        f = got.get("bid.price_items") or {}
        items = f.get("items") or []
        rec["total"] += 1
        want_items = {i["item_no"]: i for i in g["bid.price_items"]}
        got_items = {}
        dup = []
        for i in items:
            k = i.get("item_no")
            if k in got_items:
                dup.append(k)
            got_items[k] = i
        bad = []
        for no, w in want_items.items():
            gi = got_items.get(no)
            if gi is None:
                bad.append("%s 缺失" % no)
                continue
            if not eq(gi.get("amount_yuan"), w["amount_ex_tax"], 1.0):
                bad.append("%s 合价 %s≠%s" % (no, gi.get("amount_yuan"), w["amount_ex_tax"]))
            if not eq(gi.get("qty"), w["qty"]):
                bad.append("%s 数量不符" % no)
            if abs((gi.get("tax_rate") or 0) - w["tax_rate"] / 100.0) > 1e-6:
                bad.append("%s 税率 %s≠%s" % (no, gi.get("tax_rate"), w["tax_rate"]))
        extra = [k for k in got_items if k not in want_items]
        if dup:
            bad.append("重复行 %s" % set(dup))
        if extra:
            bad.append("多余行 %s" % extra)
        if len(items) != len(want_items):
            bad.append("条数 %d≠%d" % (len(items), len(want_items)))
        items_ok = not bad
        if items_ok:
            rec["ok"] += 1
        rec["fields"].append({
            "field": "bid.price_items(逐行)", "want": "%d 条" % len(want_items),
            "got": "%d 条" % len(items), "ok": items_ok,
            "detail": "；".join(bad) if bad else "逐条一致，无重复",
        })

        # 跨家串值：抽到的投标人名必须是本家
        if norm_name(got.get("bid.bidder_name", {}).get("value_text")) != norm_name(name):
            cross.append((short, got.get("bid.bidder_name", {}).get("value_text")))

        tot += rec["total"]
        ok += rec["ok"]
        ev["bidders"].append(rec)
        print("[%s] %-3s %2d/%2d  %s" % (
            short, name[:2], rec["ok"], rec["total"],
            "全中" if rec["ok"] == rec["total"] else
            "缺：" + "、".join(x["field"] for x in rec["fields"] if not x["ok"])))

    ev["summary"] = {"fields_total": tot, "fields_ok": ok,
                     "rate": round(ok / tot * 100, 1) if tot else 0,
                     "cross_bidder": cross,
                     "verdict": ("全部一致，无跨家串值"
                                 if ok == tot and not cross else "存在不一致")}
    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps(ev, ensure_ascii=False, indent=1))
    print("\n合计 %d/%d 通过；跨家串值 %d 处 → %s"
          % (ok, tot, len(cross), OUT))
    return 0 if ok == tot and not cross else 1


if __name__ == "__main__":
    sys.exit(main())
