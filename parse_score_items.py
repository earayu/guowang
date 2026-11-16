# -*- coding: utf-8 -*-
"""把招标文件里的「商务评审细则」解析成结构化评分项。

为什么做这一步：评分表不是从库里找现成的（全库"评分表"零命中），
只能把评标办法里的规则条文固化成表单。这里先证明规则是可结构化的。

输出：_scoreform/commercial_items.json
"""
import json
import os
import re

import docx

HERE = os.path.dirname(os.path.abspath(__file__))
DOCX = os.path.join(
    HERE, "国网样本_展开", "S2_152507", "包1_完整招标文件_82077892985054871",
    "国网湖北电力2025年新增第一次物资公开招标采购文件（152507）.docx")
OUT_DIR = os.path.join(HERE, "_scoreform")
os.makedirs(OUT_DIR, exist_ok=True)

GROUP_RE = re.compile(r"^\s*([一二三四五六七八九十]+)、(.*?)（([-－\d]+)[-－]([-－\d]+)）\s*$")
ITEM_RE = re.compile(r"^(.*?)（([-－\d]+)[-－]([-－\d]+)）\s*$")


def clean(s):
    return (s or "").replace("\u00a0", " ").strip()


def find_table(doc, must_contain):
    for t in doc.tables:
        head = " ".join(clean(c.text) for c in t.rows[0].cells)
        if must_contain in head:
            return t
    return None


def main():
    doc = docx.Document(DOCX)
    tbl = find_table(doc, "评审要素")
    if tbl is None:
        # 表头可能是「项目 / 评审要素 / 评审细则」
        for t in doc.tables:
            if any("评审要素" in clean(c.text) for c in t.rows[0].cells):
                tbl = t
                break
    if tbl is None:
        raise SystemExit("没找到商务评审细则表")

    rows = []
    for r in tbl.rows:
        cells = [clean(c.text) for c in r.cells]
        rows.append(cells)

    # docx 的垂直合并单元格在 python-docx 里每行都返回同一段文字，
    # 所以不能"每行都是一个新项"，要按内容是否变化判断是新项还是续行。
    groups = []
    cur_group = None
    cur_item = None
    prev_c1 = None
    for cells in rows[1:]:
        c0 = clean(cells[0]) if len(cells) > 0 else ""
        c1 = clean(cells[1]) if len(cells) > 1 else ""
        c2 = clean(cells[2]) if len(cells) > 2 else ""

        # 分组名变化 → 起新组
        if c0 and (cur_group is None or c0 != cur_group["raw"]):
            g = GROUP_RE.match(c0)
            if g:
                cur_group = {"name": clean(g.group(2)),
                             "min": float(g.group(3).replace("－", "-")),
                             "max": float(g.group(4).replace("－", "-")),
                             "raw": c0, "items": []}
                groups.append(cur_group)
                prev_c1 = None

        # 评审要素名变化 → 起新项
        if c1 and c1 != prev_c1 and cur_group is not None:
            m = ITEM_RE.match(c1)
            if m:
                cur_item = {"element": clean(m.group(1)),
                            "min": float(m.group(2).replace("－", "-")),
                            "max": float(m.group(3).replace("－", "-")),
                            "basis": [c2] if c2 else [],
                            "group": cur_group["name"]}
                cur_group["items"].append(cur_item)
                prev_c1 = c1
                continue

        # 其余都是上一项的细则续行
        if cur_item is not None and c2:
            cur_item["basis"].append(c2)

    items = [g for g in groups if g.get("items")]

    total_min = sum(i["min"] for g in items for i in g["items"])
    total_max = sum(i["max"] for g in items for i in g["items"])
    n_items = sum(len(g["items"]) for g in items)

    out = {
        "source": "国网湖北电力2025年新增第一次物资公开招标采购文件（152507）.docx",
        "section": "评标办法前附表之三：商务评分标准（商务评审细则，表体 84 行）",
        "table_rows": len(rows),
        "item_count": n_items,
        "group_count": len(items),
        "sum_min": total_min,
        "sum_max": total_max,
        "groups": items,
    }
    with open(os.path.join(OUT_DIR, "commercial_items.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print("解析表体行数:", len(rows))
    print("分组数:", len(items), "| 评分要素项数:", n_items)
    print("分值合计: %s ~ %s" % (total_min, total_max))
    for g in items:
        print("  %s（%s~%s）共 %d 项" % (g["name"], g["min"], g["max"], len(g["items"])))
        for it in g["items"]:
            print("     %-22s %s~%s  细则 %d 条" % (it["element"], it["min"], it["max"], len(it["basis"])))


if __name__ == "__main__":
    main()
