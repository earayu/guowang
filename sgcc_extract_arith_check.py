# -*- coding: utf-8 -*-
"""在部署前用本地构造的 Markdown 表格离线验证 _extract_bid_price_items。

平台往返一次约 40 秒，本地能先证明的错不该留到平台上发现。
三类边界都要覆盖：①算术正确 ②某行小数点错位 ③合计行与逐行之和不符。
"""
import sys
sys.path.insert(0, "sgcc_fn_field_extract")

import main as M


class Hit(dict):
    def get(self, k, d=None):
        return dict.get(self, k, d)


def md(rows):
    out = ["| 行项目号 | 物料描述 | 数量 | 单位 | 不含税单价（元） | 不含税合价（元） | 税率 |",
           "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return Hit(content="\n".join(out), source="分项报价表_测试_152507-1102002-4004.xlsx")


GOOD = [
    ["100035912500010", "装置", 1, "套", "306,000.00", "306,000.00", "13%"],
    ["100035917800010", "装置", 1, "套", "1,639,080.00", "1,639,080.00", "13%"],
    ["100035912200010", "装置", 1, "套", "4,079,790.00", "4,079,790.00", "13%"],
    ["100034915900360", "装置", 1, "套", "9,000,000.00", "9,000,000.00", "13%"],
    ["合计", "", "", "", "", "15,024,870.00", ""],
]

# 第 3 行合价少一位：单价 4,079,790 × 1 应为 4,079,790，合价写 407,979
BAD_LINE = [list(r) for r in GOOD]
BAD_LINE[2] = ["100035912200010", "装置", 1, "套", "4,079,790.00", "407,979.00", "13%"]
BAD_LINE[4] = ["合计", "", "", "", "", "11,352,979.00", ""]

# 数量 2 时单价×数量与合价不符
BAD_QTY = [list(r) for r in GOOD]
BAD_QTY[0] = ["100035912500010", "装置", 2, "套", "306,000.00", "306,000.00", "13%"]

# 无合计行
NO_TOTAL = [list(r) for r in GOOD[:4]]


def show(tag, rows, expect_bad):
    f = M._extract_bid_price_items([md(rows)], "测试投标人")
    bad = [i["item_no"] for i in f.items if i["arith_ok"] is False]
    print("== %s" % tag)
    print("   items=%d sum=%s declared=%s bad=%s"
          % (len(f.items), f.items_sum_yuan, f.declared_total_yuan, bad))
    print("   reason:", f.reason[:150])
    assert len(f.items) == 4, "应取到 4 条物料，实得 %d" % len(f.items)
    if expect_bad:
        assert bad == expect_bad, "应识别出坏行 %s，实得 %s" % (expect_bad, bad)
    else:
        assert not bad, "不应有坏行，实得 %s" % bad
    print("   PASS")


show("① 算术正确（4 行 + 合计一致）", GOOD, [])
show("② 第 3 行小数点错位", BAD_LINE, ["100035912200010"])
show("③ 数量 2 但合价只算 1 件", BAD_QTY, ["100035912500010"])
show("④ 无合计行（declared 为 None，不冤枉）", NO_TOTAL, [])

f = M._extract_bid_price_items([md(NO_TOTAL)], "测试")
assert f.declared_total_yuan is None, "无合计行时不应编造合计值"
print("\n全部通过：算术校验、坏行定位、合计缺失三件事都成立")
