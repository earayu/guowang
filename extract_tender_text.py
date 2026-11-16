# -*- coding: utf-8 -*-
"""把真实招标文件（152507）抽成"段落号 + 文本"的清单，供 46 条规则溯源使用。

为什么带段落号：docx 没有稳定页码（分页由 Word 渲染决定，python 里拿不到），
能稳定引用的是"章节标题 + 段内序号"。对外说"第三章 2.1.1"靠正文编号，
对内核对靠 paragraph index，两者都要留。

用法：python extract_tender_text.py
产出：_tender_text/152507_paragraphs.jsonl
      _tender_text/152507_flat.txt
"""
import io
import json
import os
import zipfile

TENDER = os.path.join(
    "国网样本_展开", "S2_152507", "包1_完整招标文件_82077892985054871",
    "国网湖北电力2025年新增第一次物资公开招标采购文件（152507）.docx",
)
OUT_DIR = "_tender_text"


def iter_paragraphs(path):
    """按文档顺序产出 (index, text)。表格单元格里的文本也展开，但不打乱主序。"""
    import docx
    d = docx.Document(path)
    idx = 0
    for p in d.paragraphs:
        t = (p.text or "").strip()
        if t:
            idx += 1
            yield idx, t, (p.style.name if p.style is not None else "")
    # 表格按出现顺序追加，带 tbl 标记，避免正文里查不到的条款漏掉
    for ti, tb in enumerate(d.tables):
        for ri, row in enumerate(tb.rows):
            cells = []
            for c in row.cells:
                v = (c.text or "").strip().replace("\n", " ")
                if v:
                    cells.append(v)
            if cells:
                idx += 1
                yield idx, " | ".join(cells), f"TABLE#{ti}/R{ri}"


def main():
    if not os.path.exists(TENDER):
        raise SystemExit("招标文件不存在：" + TENDER)
    os.makedirs(OUT_DIR, exist_ok=True)
    rows = []
    with io.open(os.path.join(OUT_DIR, "152507_paragraphs.jsonl"), "w",
                 encoding="utf-8", newline="\n") as f:
        for idx, text, style in iter_paragraphs(TENDER):
            rec = {"i": idx, "style": style, "text": text}
            rows.append(rec)
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with io.open(os.path.join(OUT_DIR, "152507_flat.txt"), "w",
                 encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write("[%05d] %s\n" % (r["i"], r["text"]))
    print("paragraphs", len(rows))
    print("chars", sum(len(r["text"]) for r in rows))


if __name__ == "__main__":
    main()
