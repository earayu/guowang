# -*- coding: utf-8 -*-
"""把「原文里本来就有、之前没声明」的四类字段补进受审侧真值。

原则：期望值一律从 docx/xlsx 原文读出来，不手填。手填的真值和手写的抽取器
可能同时错，对表还显示通过——那种通过毫无意义。
"""
import io, json, re
from docx import Document
from openpyxl import load_workbook

GT = "bid_packs/_ground_truth.json"
gt = json.load(io.open(GT, encoding="utf-8"))


def para_map(doc):
    out = {}
    for p in doc.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        m = re.match(r"^([^：:]{2,20})[：:]\s*(.+)$", t)
        if m:
            out[m.group(1).strip()] = m.group(2).strip()
    return out


for b in gt["bidders"]:
    tag = b["files"][0].split("_")[1]          # 投标文件_华中_xxx.docx → 华中
    kv = para_map(Document("bid_packs/" + b["files"][0]))
    g = b["ground_truth"]

    legal = kv.get("法定代表人", "")
    bond_txt = kv.get("投标保证金", "")
    g["bid.legal_rep_name"] = legal
    # 「本项目免收投标保证金」→ 金额不适用、形式 none。
    # 这不是把抽取失败记成 0，而是文件明确写了不收，属于「不适用」的有效结论。
    if "免收" in bond_txt:
        g["bid.bond_amount"] = None
        g["bid.bond_form"] = "none"
        g["bid.bond_applicable"] = False
    else:
        m = re.search(r"([\d,]+(?:\.\d+)?)\s*元", bond_txt)
        g["bid.bond_amount"] = int(m.group(1).replace(",", "")) if m else None
        g["bid.bond_form"] = ("bank_transfer" if "汇款" in bond_txt else
                              "bank_guarantee" if "保函" in bond_txt else "other")
        g["bid.bond_applicable"] = True
    # 投标文件里没有联合体协议书条款 → 非联合体
    g["bid.is_consortium"] = ("联合体" in json.dumps(kv, ensure_ascii=False)
                              and "联合体协议书" in json.dumps(kv, ensure_ascii=False))

    # 逐行数量/单价：从分项报价表读，和合价一起作为算术校验的真值
    wb = load_workbook("bid_packs/" + b["files"][1])
    ws = wb["分项报价表"]
    rows = {}
    for r in ws.iter_rows(min_row=4, values_only=True):
        if not r or not r[0] or not re.fullmatch(r"\d{10,}", str(r[0]).strip()):
            continue
        no = str(r[0]).strip()
        rows[no] = {"qty": float(r[2]), "unit_price_yuan": float(str(r[4]).replace(",", "")),
                    "amount_yuan": int(round(float(str(r[5]).replace(",", "")))),
                    "tax_rate": float(str(r[6]).replace("%", "")) / 100.0}
    for it in g["bid.price_items"]:
        row = rows.get(it["item_no"])
        if row:
            it.update(qty=row["qty"], unit_price_yuan=row["unit_price_yuan"])
    g["bid.price_items_sum_yuan"] = sum(i["amount_yuan"] for i in g["bid.price_items"])
    declared = None
    for r in ws.iter_rows(values_only=True):
        if r and r[0] and "合计" in str(r[0]):
            for c in r[1:]:
                try:
                    v = float(str(c).replace(",", ""))
                    if v > 1000:
                        declared = int(round(v))
                        break
                except (TypeError, ValueError):
                    continue
    g["bid.declared_total_yuan"] = declared
    print("%-6s legal=%-6s bond=%-10s(%s) sum=%d declared=%s"
          % (b["code"], legal, g["bid.bond_amount"], g["bid.bond_form"],
             g["bid.price_items_sum_yuan"], declared))

gt["meta"]["version"] = "v2"
gt["meta"]["added_fields"] = ["法定代表人", "投标保证金金额/形式", "是否联合体", "逐行数量与单价"]
gt["meta"]["added_note"] = ("这四项原文里本来就有，此前只是抽取器没声明。"
                            "期望值全部由 docx/xlsx 原文解析得出，非手填。")
json.dump(gt, io.open(GT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已写回", GT)
