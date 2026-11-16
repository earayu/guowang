# -*- coding: utf-8 -*-
"""分派表升级：行11 改成逐行报价算术自校验。

原来行11 是 `round2(mul(qty, unit_price)) == round2(price_total)`，
把整张分项报价表压成「一个数量 × 一个单价 = 一个总价」。这在多物料标包里
根本不成立：4 条物料各有数量单价，压成一个数以后，某一行小数点错位
会被另外三行抵消，总额看着还对——行11 要抓的恰恰就是这种错。

改成按行项目号逐行比，并把「表内合计 ≠ 逐行之和」也算触发。
"""
import io, json

P = "国网Demo_规则可执行化_46条分派表_V1.json"
d = json.load(io.open(P, encoding="utf-8"))

for r in d["rules"]:
    if r["rule_id"] == "GW-HB-FJ-011":
        r["needs"] = ["bid.price_items"]
        r["check"] = {"op": "per_item_amount_check", "lhs": "bid.price_items"}
        r["why_this_path"] = (
            "行11 的否决情形是「投标报价小数点错误导致单价总价都出现明显错误」，"
            "判定必须逐行：①每行 数量×不含税单价 应等于该行不含税合价；"
            "②表内合计行应等于逐行合价之和。压成单值比会让一行错位被其余行抵消。")
        r["optional_needs"] = ["bid.price_total_ex_tax"]
        print("行11 已改为逐行算术校验")

    if r["rule_id"] == "GW-HB-FJ-013":
        # 保证金情形：招标明确免收时本条不成立。NA 由判定层按 applicable 处理，
        # 但把「形式」字段从必填降为可选——免收时它本来就取不到。
        r["needs"] = ["bid.bond_amount", "tender.bond_required"]
        r["optional_needs"] = ["bid.bond_form", "bid.bond_basic_account_proof"]
        r["why_this_path"] = (
            "招标文件写明「本项目免收投标保证金」时，本条否决情形不成立，"
            "判定层按 applicable=False 直接判未触发；只有招标要求保证金时才比金额、形式、"
            "基本账户证明三件事。")
        print("行13 已拆 needs/optional_needs")

d["meta"].setdefault("change_log", []).append({
    "rev": len(d["meta"].get("change_log") or []) + 1,
    "what": "行11 改逐行算术校验（per_item_amount_check）；行13 拆 needs 与 optional_needs",
    "why": "单值比与免收保证金两种情形都会静默判错",
    "dsl_ops": 16,
})
json.dump(d, io.open(P, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

ops = set()


def walk(n):
    if isinstance(n, dict):
        if "op" in n:
            ops.add(n["op"])
        for v in n.values():
            walk(v)
    elif isinstance(n, list):
        for v in n:
            walk(v)


for r in d["rules"]:
    walk(r.get("check"))
print("DSL 算子数：", len(ops))
print("算子：", sorted(ops))
