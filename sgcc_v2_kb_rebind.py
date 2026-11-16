# -*- coding: utf-8 -*-
"""把 sgcc_fn_field_extract/main.py 的 BIDDER_KBS 换成 v2 六家新库。

为什么必须改：v2 换了企业全称（v1 是「华中某某电气有限公司」，v2 是
「华中电力监测技术（湖北）有限公司」），且新增第 6 家恩施。旧映射的两个
维度都对不上——名字查不到→走 BID_KBS 兜底→5 家混库检索被挤占，
表现为字段随机丢失，且不报错。这是静默失败，必须显式改。
"""
import io
import json
import os
import re
import sys

MAP = "bid_packs_v2/_v2_kb_map.json"
FN = "sgcc_fn_field_extract/main.py"


def main():
    if not os.path.exists(MAP):
        raise SystemExit("缺映射文件 %s，先跑 sgcc_v2_kb_ingest.py" % MAP)
    m = json.load(io.open(MAP, encoding="utf-8"))
    rows = [b for b in m["bidders"] if b["kb"]]
    if len(rows) != 6:
        raise SystemExit("映射不全：只有 %d 家，应为 6 家" % len(rows))

    s = io.open(FN, encoding="utf-8").read()

    lines = []
    for b in rows:
        lines.append('    "%s": "%s",' % (b["name"], b["kb"]))
    block = "BIDDER_KBS = {\n" + "\n".join(lines) + "\n}"

    s2, n = re.subn(r"BIDDER_KBS = \{.*?\n\}", block, s, count=1, flags=re.S)
    if n != 1:
        raise SystemExit("未找到 BIDDER_KBS 定义块")

    # 注释同步：旧注释说的是「5 家／2 个文件」，v2 是 6 家／4 个文件
    s2 = s2.replace(
        "# 每家一个库。单库只放 2 个文件、约 20 个块，limit=20 即覆盖全文，",
        "# 每家一个库（v2：6 家 × 4 份，三册 docx + 分项报价表 xlsx）。\n"
        "# 单库只放本家文件，limit=20 即覆盖全文，")

    io.open(FN, "w", encoding="utf-8").write(s2)

    print("BIDDER_KBS 已更新为 %d 家：" % len(rows))
    for b in rows:
        print("  %-4s %-30s %s" % (b["code"], b["name"], b["kb"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
