# -*- coding: utf-8 -*-
"""把分派表行10（GW-HB-FJ-010 超最高限价）从「单值比」升级为「逐物料对位」。

改成什么的理由：
  原 check = le(floor_yuan(bid.price_total_ex_tax), tender.price_cap)
  限价表是按「网省采购申请行项目号」逐条列的，一个标段常有多条物料、各自一个限价
  （实测 152507-1102002-4004 命中 4 条：34 / 182.12 / 453.31 / 1000 万元）。
  单值比只能挑一条（取最小则过严、取最大则过松），会把只超其中一条的投标误判成全部超，
  也会把合计没超但某条物料超的投标误判成合规。

升级后：
  新算子 per_item_within_cap，键 = 行项目号，逐条比；
  拿不到逐物料报价、只有标包总价时，只允许「总价 > 限价合计」单向判否——
  总价没超不能判合规，因为可能某条物料超。这是刻意的不对称。

只改行10 一条，其余 45 条不动。
"""
import io
import json

SRC = "国网Demo_规则可执行化_46条分派表_V1.json"

NEW_CHECK = {
    "op": "per_item_within_cap",
    "lhs": "bid.price_items",
    "rhs": "tender.price_cap_items",
    "fallback_total": "floor_yuan(bid.price_total_ex_tax)",
    "key": "item_no",
}
NEW_NEEDS = ["tender.price_cap_items"]
NEW_OPTIONAL = ["bid.price_items", "bid.price_total_ex_tax"]

data = json.load(io.open(SRC, encoding="utf-8"))

hit = 0
for r in data["rules"]:
    if r["rule_id"] == "GW-HB-FJ-010":
        old = json.dumps(r["check"], ensure_ascii=False)
        r["check"] = NEW_CHECK
        r["needs"] = NEW_NEEDS
        r["optional_needs"] = NEW_OPTIONAL
        r["why_this_path"] = (
            "最高限价按行项目号逐条列的，判定必须逐物料对位；"
            "只有总价时仅允许单向判否（总价超合计即超），总价未超不判合规")
        r["upgrade"] = {
            "from": old,
            "reason": "限价表逐物料，单值比会误杀/误放",
            "asymmetry": "total 分支只出 NOT_RESPONDED，不出 RESPONDED",
        }
        hit += 1

assert hit == 1, "行10 未命中或重复：%d" % hit

m = data["meta"]
for op in ("per_item_within_cap",):
    if op not in m["dsl_ops"]:
        m["dsl_ops"].append(op)
m["dsl_total_ops"] = len(m["dsl_ops"])
m["title"] = "国网湖北 46 条否决情形 · 可执行化分派表 V1（行10 逐物料对位）"
m["change_log"] = m.get("change_log", []) + [{
    "at": "2026-11-14",
    "row": 10,
    "what": "check 由 le(总价, 单值限价) 改为 per_item_within_cap(逐物料报价, 逐物料限价)",
    "needs_split": {"required": NEW_NEEDS, "optional": NEW_OPTIONAL},
    "note": "needs 只保留限价明细为必需项；投标侧两项为 optional，"
            "避免「只拿到总价」时反向保护把单向判否吞成 UNCERTAIN",
}]

io.open(SRC, "w", encoding="utf-8").write(
    json.dumps(data, ensure_ascii=False, indent=1))

print("行10 已升级；dsl_total_ops =", m["dsl_total_ops"], "规则总数 =", len(data["rules"]))
print("新 check =", json.dumps(NEW_CHECK, ensure_ascii=False))
