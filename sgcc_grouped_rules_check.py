# -*- coding: utf-8 -*-
"""跨家聚合规则的算子级验证。

行39（同标包不同投标人法定代表人相同）、行32（同品牌同型号多代理）、
行46（报价超平均值规定值）这三条，单看一份投标文件永远判不出来——
它们的判据在「同标包的其他投标人身上」。现有 5 家的法人各不相同、
报价四家相同，所以用真实数据跑这三条只会得到「全部通过」。
「全部通过」证明不了规则有效，只证明了它没报错。

这份脚本用构造数据专门验证判否路径：先把条件做成必然成立，看规则是否判否；
再改成必然不成立，看是否放过。两侧都要动，只测一侧等于只测了一半。

明确标注：这里的数据是构造的，用来验证算子，不代表任何真实投标情形。
真实判否要等投标文件到位。
"""
import io, json, sys

sys.path.insert(0, ".")
import sgcc_rule_runner as R

RULES = {r["rule_id"]: r for r in
         json.load(io.open("国网Demo_规则可执行化_46条分派表_V2.json",
                           encoding="utf-8"))["rules"]}

TENDER = {
    "tender.bid_open_date": "2026-10-20",
    "tender.required_validity_days": 90,
    "tender.deadline": "2026-10-20T09:00:00",
}

cases = []


def run(rule_id, ctx, group):
    return R.run_rule(RULES[rule_id], ctx, group)


def case(tag, rule_id, ctx, group, want):
    r = run(rule_id, ctx, group)
    ok = (r["state"] == want)
    cases.append({"case": tag, "rule_id": rule_id, "want": want,
                  "got": r["state"], "ok": ok, "reason": r["reason"]})
    print("%-46s %-12s 期望 %-14s 实得 %-14s %s"
          % (tag, rule_id.replace("GW-HB-FJ-", "行"), want, r["state"],
             "OK" if ok else "!!"))
    print("    ", r["reason"][:130])


P, F, U = R.STATE_PASS, R.STATE_FAIL, R.STATE_UNK

# ---------------- 行11：分项报价算术 ----------------
# 真实 5 家的报价表算术都是对的，所以行11 在真实数据上只会 PASS。
# 判否路径必须在这里证：某一行小数点错位、合计与逐行之和不符，各造一次。
def items(rows):
    out = []
    for no, qty, up, amt in rows:
        calc = round(float(qty) * float(up), 2)
        out.append({"item_no": no, "qty": qty, "unit_price_yuan": up,
                    "amount_yuan": amt, "calc_amount_yuan": calc,
                    "arith_ok": (abs(calc - float(amt)) <= 0.01)})
    return out


# ---------------- 行10：单条物料超最高限价（含税口径） ----------------
# 限价表（附表一）是含税限价，投标分项报价表是未含税合价。这个口径差在 v2 真实数据上
# 直接决定判否：宜昌那行未含税 407.08 万 < 限价 453.31 万，含税 460 万却超了 6.69 万。
# 三侧都要证：含税恰等于限价（放）、含税超 1 元（否）、缺税率（不得判合规）。
CAP10 = {"tender.price_cap_items": [{"item_no": "A1", "cap_yuan": 340000},
                                     {"item_no": "A2", "cap_yuan": 4533100}],
         "tender.price_cap_applicable": True}


def cap_case(tag, rows, tax, want):
    ctx = dict(CAP10)
    ctx["bid.price_items"] = [
        {"item_no": no, "qty": 1, "unit_price_yuan": amt, "amount_yuan": amt,
         "calc_amount_yuan": amt} for no, amt in rows]
    if tax is not None:
        ctx["bid.tax_rate"] = tax
    else:
        ctx.pop("bid.tax_rate", None)
    case(tag, "GW-HB-FJ-010", ctx, [ctx], want)


cap_case("行10 含税恰等于限价（300884.96×1.13→340000）",
         [("A1", 300884.96), ("A2", 4011592.92)], 0.13, P)
cap_case("行10 未含税 407.08 万未超、含税 460 万超限（宜昌形态）",
         [("A1", 300884.96), ("A2", 4070796.46)], 0.13, F)
cap_case("行10 含税超 1 元（边界）",
         [("A1", 300885.90), ("A2", 4011592.92)], 0.13, F)
cap_case("行10 缺税率 → 不得判合规",
         [("A1", 300884.96), ("A2", 4011592.92)], None, U)

OK_ITEMS = items([("A1", 1, 306000, 306000), ("A2", 1, 1639080, 1639080)])
BAD_ITEMS = items([("A1", 1, 306000, 306000), ("A2", 1, 4079790, 407979)])
BADQ_ITEMS = items([("A1", 2, 306000, 306000), ("A2", 1, 1639080, 1639080)])

c11 = {"bid.price_items": OK_ITEMS, "bid.price_items.declared_total_yuan": 1945080}
case("行11 两行算术与合计全对", "GW-HB-FJ-011", c11, [c11], P)

c11b = {"bid.price_items": BAD_ITEMS, "bid.price_items.declared_total_yuan": 713979}
case("行11 A2 行小数点错位（4079790→407979）", "GW-HB-FJ-011", c11b, [c11b], F)

c11c = {"bid.price_items": BADQ_ITEMS, "bid.price_items.declared_total_yuan": 1945080}
case("行11 A1 数量 2 但合价只算 1 件", "GW-HB-FJ-011", c11c, [c11c], F)

c11d = {"bid.price_items": OK_ITEMS, "bid.price_items.declared_total_yuan": 2000000}
case("行11 逐行都对但合计行对不上", "GW-HB-FJ-011", c11d, [c11d], F)

# ---------------- 行13：投标保证金 ----------------
# 真实场景里招标免收保证金，行13 靠「不适用」判未触发。
# 判否路径（要求交、没交/交少了）在这一侧补齐。
t13 = dict(TENDER, **{"tender.bond_required": 50000})
c13 = {"bid.bond_amount": 50000, "bid.bond_form": "bank_transfer",
       "bid.bond_basic_account_proof": True,
       "tender.bond_required": 50000}
case("行13 足额缴纳 + 基本账户证明", "GW-HB-FJ-013", c13, [c13], P)

c13b = {"bid.bond_amount": 30000, "bid.bond_form": "bank_transfer",
        "bid.bond_basic_account_proof": True, "tender.bond_required": 50000}
case("行13 缴 3 万但要求 5 万（不足）", "GW-HB-FJ-013", c13b, [c13b], F)

c13c = {"bid.bond_amount": 50000, "bid.bond_form": "bank_transfer",
        "bid.bond_basic_account_proof": False, "tender.bond_required": 50000}
case("行13 银行汇款但无基本账户证明", "GW-HB-FJ-013", c13c, [c13c], F)

c13d = {"bid.bond_amount": None, "bid.bond_amount.__na": True,
        "tender.bond_required": None, "tender.bond_required.__na": True}
case("行13 招标免收保证金 → 未触发", "GW-HB-FJ-013", c13d, [c13d], P)

# ---------------- 行39：法定代表人重复 ----------------
g1 = [{"bid.bidder_name": "甲", "bid.legal_rep_name": "陈某某"},
      {"bid.bidder_name": "乙", "bid.legal_rep_name": "孙某某"},
      {"bid.bidder_name": "丙", "bid.legal_rep_name": "赵某某"}]
case("行39 三家法人各不相同", "GW-HB-FJ-039", g1[0], g1, P)

g2 = [{"bid.bidder_name": "甲", "bid.legal_rep_name": "陈某某"},
      {"bid.bidder_name": "乙", "bid.legal_rep_name": "陈某某"},
      {"bid.bidder_name": "丙", "bid.legal_rep_name": "赵某某"}]
case("行39 甲乙两家法人同为陈某某", "GW-HB-FJ-039", g2[0], g2, F)
case("行39 同一组，丙家视角也应判否", "GW-HB-FJ-039", g2[2], g2, F)

# ---------------- 行32：同品牌同型号多代理 ----------------
g3 = [{"bid.bidder_name": "甲", "bid.manufacturer_name": "某制造商",
       "bid.brand_model": "X-100", "bid.agent_of": "某制造商"},
      {"bid.bidder_name": "乙", "bid.manufacturer_name": "另一制造商",
       "bid.brand_model": "Y-200", "bid.agent_of": "另一制造商"}]
case("行32 两家代理不同制造商", "GW-HB-FJ-032", g3[0], g3, P)

g4 = [{"bid.bidder_name": "甲", "bid.manufacturer_name": "某制造商",
       "bid.brand_model": "X-100", "bid.agent_of": "某制造商"},
      {"bid.bidder_name": "乙", "bid.manufacturer_name": "某制造商",
       "bid.brand_model": "X-100", "bid.agent_of": "某制造商"}]
case("行32 两家同时代理同一制造商", "GW-HB-FJ-032", g4[0], g4, F)

# ---------------- 行46：报价超平均值规定值 ----------------
# 阈值规则取 {base: 均价, mult: 1.10}：报价不得超过均价的 110%。
# 这个 1.10 是构造值，只为验证算子；真实阈值招标文件里没给出（只有评分用 W1/W2），
# 所以真实数据上行46 永远应该是「阈值不可参数化 → 待澄清」。
t46 = dict(TENDER, **{"tender.avg_price_threshold_rule": {"base": "peer.price_avg", "mult": 1.10}})
g5 = [{"bid.bidder_name": "甲", "bid.price_total": 1000000},
      {"bid.bidder_name": "乙", "bid.price_total": 1000000},
      {"bid.bidder_name": "丙", "bid.price_total": 1000000}]
avg5 = sum(x["bid.price_total"] for x in g5) / 3
c5 = dict(t46, **g5[0], **{"peer.price_avg": avg5})
case("行46 三家等额报价（=均价，未超 110%%）".replace("%%", "%"), "GW-HB-FJ-046", c5, g5, P)

g6 = [{"bid.bidder_name": "甲", "bid.price_total": 1000000},
      {"bid.bidder_name": "乙", "bid.price_total": 1000000},
      {"bid.bidder_name": "丙", "bid.price_total": 1500000}]
avg6 = sum(x["bid.price_total"] for x in g6) / 3
c6 = dict(t46, **g6[2], **{"peer.price_avg": avg6})
case("行46 丙家 150 万，超均价 116.7%%".replace("%%", "%"), "GW-HB-FJ-046", c6, g6, F)

# 阈值抽不到时必须待澄清，不能默认通过
t46b = dict(TENDER, **{"tender.avg_price_threshold_rule": R.MISSING})
c6b = dict(t46b, **g6[2], **{"peer.price_avg": avg6})
case("行46 招标文件未给出阈值 → 必须待澄清", "GW-HB-FJ-046", c6b, g6, U)

# ---------------- 汇总 ----------------
bad = [c for c in cases if not c["ok"]]
ev = {
    "meta": {
        "title": "规则算子边界验证（行10/11/13/32/39/46）",
        "version": "V2（按 v2 六家重跑；新增行10 含税口径四例）",
        "nature": "构造数据验证算子。不代表任何真实投标情形，不作业务结论。",
        "why_needed": ("行32/39/46 的判据在「同标包其他投标人」身上，单份文件判不出来。"
                       "v2 六家法人各不相同、六家报价互不相同（下浮 84.5%~93.4%），"
                       "用真实数据跑这三条只会全过——全过证明不了规则会判否。"
                       "行10 在真实数据上能判否（宜昌含税超限 6.69 万），但「恰等于限价」"
                       "「超 1 元」「缺税率」这三个边界只能构造。"),
        "runner": "sgcc_rule_runner.py",
        "dispatch": "国网Demo_规则可执行化_46条分派表_V2.json",
        "row10_basis": "含税对含税（amount_basis=tax_incl，未含税行合价×(1+税率) 后向下取整到元）",
    },
    "cases": cases,
    "summary": {"total": len(cases), "passed": len(cases) - len(bad), "failed": len(bad)},
}
io.open("国网Demo_F4规则算子边界_验证_V2.json", "w", encoding="utf-8").write(
    json.dumps(ev, ensure_ascii=False, indent=1))
print("\n%d/%d 通过" % (len(cases) - len(bad), len(cases)))
if bad:
    print("失败项：", [(c["case"], c["want"], c["got"]) for c in bad])
sys.exit(1 if bad else 0)
