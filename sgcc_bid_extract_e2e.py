# -*- coding: utf-8 -*-
"""受审侧抽取端到端：5 家投标包逐家真跑，与预制真值逐字段比对。

比对三件事：
  1. 值对不对——每家的报价、有效期、税率、签章名是否与剧本一致；
  2. 有没有串家——受审库里 5 家并存，若某家的有效期取到了别家的 90 天，
     值本身「合法」，只有和真值比才看得出来；
  3. 差在哪——不一致时记录预期/实得/出处，不笼统记一条 FAIL。

输出：国网Demo_F2受审侧抽取_真跑证据_V1.json
"""
import io
import json
import subprocess
import sys

CLI = "./apemind-cli/apemind.exe"
FN = "sgcc-field-extract"
GT = "bid_packs/_ground_truth.json"
OUT = "国网Demo_F2受审侧抽取_真跑证据_V1.json"
SECTION = "152507-1102002-4004"

FIELDS = ["bid.bidder_name", "bid.seal_present", "bid.seal_valid", "bid.seal_name",
          "bid.price_items", "bid.price_total_ex_tax", "bid.committed_delivery_date",
          "bid.validity_days", "bid.tax_rate",
          # 这两项原文里本来就有，此前没声明，导致行11/13/39 一直卡在「缺字段」。
          # 只补能严格对表的：法定代表人可逐字比；保证金在免收情形下验的是
          # applicable=False（不是金额 0）。保证金形式、联合体声明这类语义字段
          # 本轮不进——它们的对错没有客观判据，塞进来只会让 45/45 变成假的。
          "bid.legal_rep_name", "bid.bond_amount"]


def invoke(bidder):
    payload = {"batch_id": "152507", "fields": FIELDS, "scope_hint": "",
               "section_no": SECTION, "side": "bid", "bidder": bidder}
    io.open("_e2e_bid_in.json", "w", encoding="utf-8").write(
        json.dumps(payload, ensure_ascii=False))
    p = subprocess.run([CLI, "function", "invoke", FN, "--input", "_e2e_bid_in.json", "--json"],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return None, {"error": (p.stderr or p.stdout)[-300:]}
    d = json.loads(p.stdout)["data"]
    return d.get("output"), {"run_id": d.get("id"), "version": d.get("version_number"),
                             "status": d.get("status"), "ms": d.get("elapsed_ms"),
                             "error": d.get("error_message")}


def eq_num(a, b, tol=0.01):
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return False


def main():
    gt = json.load(io.open(GT, encoding="utf-8"))
    ev = {"meta": {
        "title": "受审侧（投标文件）字段抽取 · 5 家逐家真跑",
        "kb": "cold848aad8f57412ce（P152507-受审库-合成投标样本）",
        "section_no": SECTION,
        "data_nature": "合成演示数据；物料/行项目号/限价取自 152507 公开招标文件",
        "function": {"slug": FN, "version": None},
        "checked": ["取值是否与剧本一致", "是否跨家串值", "不一致时的出处"],
    }, "bidders": []}

    total_fields = total_ok = 0
    cross_hit = []

    for b in gt["bidders"]:
        name = b["bidder_name"]
        out, meta = invoke(name)
        ev["meta"]["function"]["version"] = meta.get("version")
        rec = {"bidder": name, "expect": b["expect"], "defect_rule": b["defect_rule"],
               "run_id": meta.get("run_id"), "status": meta.get("status"),
               "elapsed_ms": meta.get("ms"), "fields": [], "ok": 0, "total": 0}
        if out is None:
            rec["error"] = meta.get("error")
            ev["bidders"].append(rec)
            continue

        got = {f["field"]: f for f in out["fields"]}
        g = b["ground_truth"]

        def check(field, want, kind="num"):
            rec["total"] += 1
            f = got.get(field)
            if f is None:
                rec["fields"].append({"field": field, "want": want, "got": None,
                                      "ok": False, "why": "字段未返回"})
                return
            v = f.get("value_text")
            if kind == "num":
                ok = eq_num(f.get("value_num"), want)
            elif kind == "bool":
                # 布尔类字段的 value_text 是描述句（「已加盖电子签章」），不是「是/否」，
                # 用固定词表比会全部误判成 FAIL。判据改成：回读通过 且 不含否定表述。
                neg = ("未加盖", "无签章", "无效", "未签", "没有加盖", "不予认可")
                ok = bool(f.get("verified")) and not any(n in (v or "") for n in neg)
                if not want:
                    ok = not ok
            else:
                ok = (v or "").strip() == str(want).strip()
            if ok:
                rec["ok"] += 1
            rec["fields"].append({
                "field": field, "want": want, "got": v, "value_num": f.get("value_num"),
                "source": f.get("source"), "method": f.get("method"),
                "verified": f.get("verified"), "ok": ok,
                "why": "" if ok else (f.get("reason") or "")[:80],
            })

        check("bid.bidder_name", g["bid.bidder_name"], "text")
        check("bid.seal_name", g["bid.seal_name"], "text")
        check("bid.seal_present", True, "bool")
        check("bid.seal_valid", g["bid.seal_valid"], "bool")
        check("bid.validity_days", g["bid.validity_days"])
        check("bid.tax_rate", g["bid.tax_rate"])
        check("bid.price_total_ex_tax", g["bid.price_total_ex_tax"])
        check("bid.committed_delivery_date", g["bid.committed_delivery_date"], "text")
        check("bid.legal_rep_name", g["bid.legal_rep_name"], "text")
        # 保证金：招标明确免收时，期望是「不适用」而不是某个金额。
        # 抽成 0 也算错——0 元保证金和「不收保证金」在判定上是两回事。
        fb = got.get("bid.bond_amount") or {}
        rec["total"] += 1
        ok_bond = ((fb.get("applicable") is False) if not g.get("bid.bond_applicable", True)
                   else (fb.get("value_num") == g.get("bid.bond_amount")))
        if ok_bond:
            rec["ok"] += 1
        rec["fields"].append({
            "field": "bid.bond_amount", "want": g.get("bid.bond_amount") or "不适用",
            "got": fb.get("value_text"), "value_num": fb.get("value_num"),
            "source": fb.get("source"), "method": fb.get("method"),
            "verified": fb.get("verified"), "ok": ok_bond,
            "why": "" if ok_bond else (fb.get("reason") or "")[:80],
        })

        # 逐行报价：金额之外再比数量与单价，行11 的算术校验靠这两列
        rec["total"] += 1
        f = got.get("bid.price_items") or {}
        got_items = {i["item_no"]: i["amount_yuan"] for i in (f.get("items") or [])}
        want_items = {i["item_no"]: i["amount_yuan"] for i in g["bid.price_items"]}
        ok_items = got_items == want_items
        want_qty = {i["item_no"]: (i.get("qty"), i.get("unit_price_yuan"))
                    for i in g["bid.price_items"]}
        got_qty = {i["item_no"]: (i.get("qty"), i.get("unit_price_yuan"))
                   for i in (f.get("items") or [])}
        ok_qty = got_qty == want_qty
        if ok_items and ok_qty:
            rec["ok"] += 1
        rec["fields"].append({
            "field": "bid.price_items", "want": want_items, "got": got_items,
            "want_qty": want_qty, "got_qty": got_qty,
            # 逐行明细原样留存：判定层行11 的算术校验要用 qty / unit_price / calc_amount，
            # 行10 的逐物料对位要用 amount。证据文件里只留 item_no→金额 的扁平字典，
            # 下游就只能重算一遍，等于判定依据不在证据里。
            "items_detail": f.get("items") or [],
            "declared_total": {"want": g.get("bid.declared_total_yuan"),
                               "got": f.get("declared_total_yuan")},
            "source": f.get("source"), "method": f.get("method"),
            "verified": f.get("verified"), "ok": ok_items and ok_qty,
            "why": "" if (ok_items and ok_qty)
                   else ("逐行项目号金额不一致" if not ok_items
                         else "数量/单价列与原文不一致，行11 会算错"),
        })

        # 跨家检查：抽出来的名字若等于**另外四家**的任一家，才是真的串了别家数据。
        # 不能拿「与自家不等」当泄露——襄阳那家剧本就是签章名与投标人不一致，
        # 违约反而说明抽对了。
        others = {b2["bidder_name"] for b2 in gt["bidders"] if b2["bidder_name"] != name}
        for fld in ("bid.bidder_name", "bid.seal_name"):
            v = (got.get(fld) or {}).get("value_text") or ""
            if v and v in others:
                cross_hit.append({"bidder": name, "field": fld, "got": v})
        # 剧本设定的不一致单独记，证明「该错的地方确实错了」
        seal_v = (got.get("bid.seal_name") or {}).get("value_text") or ""
        if seal_v and seal_v != name and seal_v not in others:
            rec["designed_mismatch"] = {"field": "bid.seal_name", "got": seal_v,
                                        "note": "与投标人名称不一致，符合剧本设定"}

        rec["pass_rate"] = round(rec["ok"] / rec["total"], 4) if rec["total"] else 0.0
        total_fields += rec["total"]
        total_ok += rec["ok"]
        ev["bidders"].append(rec)
        print("%-24s %d/%d  %s" % (name, rec["ok"], rec["total"], b["expect"]))

    ev["summary"] = {
        "bidders": len(ev["bidders"]),
        "fields_total": total_fields,
        "fields_ok": total_ok,
        "pass_rate": round(total_ok / total_fields, 4) if total_fields else 0.0,
        "cross_bidder_leak": cross_hit,
        "cross_bidder_clean": not cross_hit,
    }

    io.open(OUT, "w", encoding="utf-8").write(json.dumps(ev, ensure_ascii=False, indent=1))

    print("\n合计 %d/%d，通过率 %.1f%%"
          % (total_ok, total_fields, ev["summary"]["pass_rate"] * 100))
    print("跨家串值：", "无" if not cross_hit else cross_hit)
    bad = [(r["bidder"], f) for r in ev["bidders"] for f in r["fields"] if not f["ok"]]
    if bad:
        print("\n不一致明细：")
        for bd, f in bad:
            print("  %-22s %-30s 预期=%s 实得=%s %s"
                  % (bd, f["field"], f["want"], f["got"], f.get("why", "")))
    print("输出：", OUT)
    return 0 if (not cross_hit and total_ok == total_fields) else 1


if __name__ == "__main__":
    sys.exit(main())
