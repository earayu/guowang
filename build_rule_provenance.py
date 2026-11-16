# -*- coding: utf-8 -*-
"""建立 46 条规则的招标文件法源：把分派表逐条对齐到真实招标文件"前附表之二 初步评审标准"表格。

为什么要对齐而不是直接按顺序编号：
  表格行序与规则行序理论上一致，但一旦招标文件换版本（1525K1 / 152507 是两个包），
  行序可能偏移。用文本相似度校验，错位立刻能看出来，避免把条款号挂错——挂错比不挂更糟。

产出：_provenance/match_check.txt（对齐校验）、国网Demo_规则法源溯源表_V1.json
用法：python build_rule_provenance.py
"""
import io
import json
import os
import re
from difflib import SequenceMatcher

DISPATCH = "国网Demo_规则可执行化_46条分派表_V2.json"
PARAS = os.path.join("_tender_text", "152507_paragraphs.jsonl")
OUT_DIR = "_provenance"
TENDER_NAME = "国网湖北电力2025年新增第一次物资公开招标采购文件（152507）"

# 否决情形表在段落流中的绝对区间（由 extract_tender_text.py 产出后人工核定的表头/表尾）
TBL_HEAD = "序号 | 评审内容 | 否决情形 | 否决事项"
TBL_FIRST_CAT = "形式评审"


def load_paras():
    rows = []
    with io.open(PARAS, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                rows.append(json.loads(ln))
    return rows


def slice_table(rows):
    """从表头开始取连续的 '评审类 | 子类 | 正文' 三列行，遇到非三列行即止。"""
    start = None
    for i, r in enumerate(rows):
        if r["text"].strip() == TBL_HEAD:
            start = i
            break
    if start is None:
        raise SystemExit("未找到初步评审标准表头")
    out = []
    for r in rows[start + 1:]:
        parts = [p.strip() for p in r["text"].split(" | ")]
        if len(parts) < 3:
            break
        cat, sub, text = parts[0], parts[1], parts[2]
        if cat not in ("形式评审", "资格评审", "响应性评审", "其他事项"):
            break
        out.append({"para": r["i"], "category": cat, "subcategory": sub,
                    "text": text, "raw": r["text"]})
    return out


def norm(s):
    s = re.sub(r"[\s　]+", "", s or "")
    s = s.replace("（", "(").replace("）", ")").replace("，", ",").replace("。", ".")
    return s


def sim(a, b):
    return SequenceMatcher(None, norm(a)[:400], norm(b)[:400]).ratio()


def clause_no(cat, sub):
    """初步评审标准的三级条款号（招标文件第三章 2.1.1/2.1.2/2.1.3）。"""
    return {"形式评审": "2.1.1", "资格评审": "2.1.2",
            "响应性评审": "2.1.3"}.get(cat, "2.1.1~2.1.3")


def main():
    rules = json.load(io.open(DISPATCH, encoding="utf-8"))["rules"]
    rows = load_paras()
    tbl = slice_table(rows)
    os.makedirs(OUT_DIR, exist_ok=True)

    lines = []
    lines.append("规则条数 %d / 表格行数 %d" % (len(rules), len(tbl)))
    if len(rules) != len(tbl):
        lines.append("!! 数量不一致，需人工核对")

    out = []
    bad = 0
    for i, r in enumerate(rules):
        t = tbl[i] if i < len(tbl) else None
        s = sim(r["rule_text"], t["text"]) if t else 0.0
        flag = "OK" if s >= 0.90 else ("WARN" if s >= 0.60 else "MISMATCH")
        if flag != "OK":
            bad += 1
        lines.append("%02d %s  sim=%.3f %s  cat=%s/%s  para=%s" % (
            i + 1, r["rule_id"], s, flag,
            (t or {}).get("category"), (t or {}).get("subcategory"), (t or {}).get("para")))
        rec = dict(r)
        rec["provenance"] = {
            "doc": TENDER_NAME,
            "doc_format": "docx",
            "chapter": "第三章 评标办法（综合评估法）",
            "section": "前附表之二：初步评审标准",
            "clause": clause_no((t or {}).get("category"), (t or {}).get("subcategory")),
            "table_row": i + 1,
            "para_index": (t or {}).get("para"),
            "category": (t or {}).get("category"),
            "subcategory": (t or {}).get("subcategory"),
            "text_in_tender": (t or {}).get("text"),
            "match_sim": round(s, 4),
            "match_flag": flag,
        }
        out.append(rec)

    io.open(os.path.join(OUT_DIR, "match_check.txt"), "w",
            encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    io.open(os.path.join(OUT_DIR, "rules_with_provenance.json"), "w",
            encoding="utf-8", newline="\n").write(
        json.dumps({"n": len(out), "rules": out}, ensure_ascii=False, indent=1))
    print("\n".join(lines))
    print("\n非 OK 条数:", bad)


if __name__ == "__main__":
    main()
