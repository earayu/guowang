# -*- coding: utf-8 -*-
"""抽取器 items 结构本地自检（不是真跑证据，只验结构不炸、列不错位）。

真跑证据在平台 invoke（见 国网Demo_F1逐物料对位_真跑证据_V1.json）。
这里把 apemind_fn 换成桩，直接喂真实限价表的 Markdown 行，
确认 _extract_price_cap 能把 4 条物料拆成 items 且 cap_yuan 换算正确。
"""
import importlib.util
import sys
import types

# --- 桩：平台运行时才有的 apemind_fn ---
stub = types.ModuleType("apemind_fn")


class Context:          # noqa: D101
    pass


stub.Context = Context
sys.modules["apemind_fn"] = stub

spec = importlib.util.spec_from_file_location("sgcc_extract", "sgcc_fn_field_extract/main.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

HEADER = ("| 标段号 | 网省采购申请行项目号 | 数量 | 单位 | 物料描述 | 最高限价（万元） |")
SEP = "| --- | --- | --- | --- | --- | --- |"
ROWS = [
    "| 152507-1102002-4004 | 100035912500010 | 1 | 套 | 线路在线监测装置,电缆隧道在线监测系统 | 34 |",
    "| 152507-1102002-4004 | 100035917800010 | 1 | 套 | 线路在线监测装置,电缆隧道在线监测系统 | 182.12 |",
    "| 152507-1102002-4004 | 100035912200010 | 1 | 套 | 线路在线监测装置,电缆隧道在线监测系统 | 453.31 |",
    "| 152507-1102002-4004 | 100034915900360 | 1 | 套 | 线路在线监测装置,电缆隧道在线监测系统 | 1000 |",
    "| 152507-1102002-4005 | 100035910000001 | 2 | 台 | 别的物料 | 12 |",
]

# 补足 15 行完整性闸门（另造 10 行无关标段）
for i in range(10):
    ROWS.append("| 152507-1102009-90%02d | 1000359100001%02d | 1 | 套 | 填充物料%d | %d |"
                % (i, i, i, 10 + i))

content = "\n".join([HEADER, SEP] + ROWS)
hits = [{"source": "国网湖北电力2025年新增第一次物资公开招标采购文件（152507）.docx",
         "content": content}]

out = mod._extract_price_cap(hits, "152507-1102002-4004")
print("method =", out.method, "| verified =", out.verified, "| applicable =", out.applicable)
print("value_num(最严，仅供粗筛) =", out.value_num)
print("items_sum_yuan =", out.items_sum_yuan)
print("items =")
for it in out.items:
    print("  ", it["item_no"], it["cap_wan"], "万元 →", it["cap_yuan"], "元 |", it["desc"][:18])

assert len(out.items) == 4, "应命中 4 条物料，实得 %d" % len(out.items)
assert out.items_sum_yuan == 16694300, "合计应为 16694300，实得 %s" % out.items_sum_yuan
assert [x["item_no"] for x in out.items] == ["100035912500010", "100035917800010",
                                             "100035912200010", "100034915900360"]
print("\n结构自检：通过（4 条物料、合计 1669.43 万、行项目号未错位）")
