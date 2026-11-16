# -*- coding: utf-8 -*-
"""把 6 家合成投标件转成纯文本，放进隔离目录供盲评使用。

隔离原则：
  输出目录 _blind_only/ 里**只放**投标件正文与 46 条否决情形清单，
  不放 _ground_truth*.json、不放引擎判定结果、不放任何"答案"。
  盲评专家（人或其他 agent）拿到的材料里不应有真值，否则实验无效。

用法：python extract_bid_packs.py
产出：_blind_only/<代号>_<公司>_投标件全文.txt
      _blind_only/00_否决情形清单.md
"""
import io
import json
import os

SRC = "bid_packs_v2"
OUT = "_blind_only"
GT = os.path.join(SRC, "_ground_truth_v3.json")


def docx_text(path):
    import docx
    d = docx.Document(path)
    out = []
    for p in d.paragraphs:
        t = (p.text or "").strip()
        if t:
            out.append(t)
    for ti, tb in enumerate(d.tables):
        out.append("[表 %d]" % (ti + 1))
        for row in tb.rows:
            cells = [(c.text or "").strip().replace("\n", " ") for c in row.cells]
            if any(cells):
                out.append(" | ".join(cells))
    return "\n".join(out)


def xlsx_text(path):
    try:
        import openpyxl
    except ImportError:
        return "(openpyxl 未安装，分项报价表未展开)"
    wb = openpyxl.load_workbook(path, data_only=True)
    out = []
    for ws in wb.worksheets:
        out.append("[工作表 %s]" % ws.title)
        for row in ws.iter_rows(values_only=True):
            vals = ["" if v is None else str(v) for v in row]
            if any(x.strip() for x in vals):
                out.append(" | ".join(vals))
    return "\n".join(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    gt = json.load(io.open(GT, encoding="utf-8"))

    for b in gt["bidders"]:
        code, name = b["code"], b["bidder_name"]
        parts = ["# 投标件全文 · %s（代号 %s）\n" % (name, code),
                 "> 本文件由投标人递交的三册投标文件与分项报价表逐字提取，未做筛选、未做标注。\n"]
        for fn in b["files"]:
            p = os.path.join(SRC, fn)
            if not os.path.exists(p):
                parts.append("\n## %s（文件缺失）\n" % fn)
                continue
            parts.append("\n## %s\n" % fn)
            parts.append(xlsx_text(p) if fn.lower().endswith(".xlsx") else docx_text(p))
            parts.append("")
        txt = "\n".join(parts)
        with io.open(os.path.join(OUT, "%s_%s_投标件全文.txt" % (code, name)),
                     "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        print(code, name, len(txt), "字")

    # 否决情形清单（只给规则，不给任何判定结果）
    d = json.load(io.open("国网Demo_规则法源溯源表_V1.json", encoding="utf-8"))
    L = ["# 评标办法 · 否决情形清单（46 条）\n",
         "来源：第三章 评标办法（综合评估法）→ 前附表之二 初步评审标准。",
         "以下为招标文件原文，按表格行序排列。\n"]
    for r in d["rules"]:
        p = r["provenance"]
        L.append("**%d. %s**　[%s / %s]\n" % (r["row"], r["rule_id"], r["category"], r["subcategory"]))
        L.append("> " + (p["text_in_tender"] or "").strip() + "\n")
    io.open(os.path.join(OUT, "00_否决情形清单.md"), "w",
            encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("清单已写入", OUT)


if __name__ == "__main__":
    main()
