# -*- coding: utf-8 -*-
"""按评标办法生成「每位评分专家一份」的评分表。

设计取舍（都写进表里，不藏在代码里）：
1. 商务 23 项来自招标文件原文（有行号可回溯）；技术评分标准在招标文件里是空段落，
   规则不在本文件内 → 表里留空骨架并标注来源缺口，不编造规则。
2. 报价是公式算的客观分，不需要专家打分，单列一张计算复核表。
3. 每项打分单元格加数据验证限制在允许区间内，防止填出 -5 或 999。
4. 汇总规则招标文件没写（"得分汇总/综合得分/去掉最高"全库零命中），
   默认按算术平均，并在表上标明"汇总规则待招标人确认"。

输出：_scoreform/评分表_152507-1102003-2005_智能终端.xlsx
"""
import json
import os

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "_scoreform", "commercial_items.json")
SRC_TECH = os.path.join(HERE, "_scoreform", "tech_items.json")
OUT = os.path.join(HERE, "_scoreform", "评分表_152507-1102003-2005_智能终端_含技术表.xlsx")

EXPERT_COUNT = 5          # 评标委员会：5 人及以上单数（投标人须知前附表 6.1.1）
PKG = "152507-1102003-2005"
PKG_NAME = "智能终端"
WEIGHT = {"tech": 0.50, "price": 0.40, "biz": 0.10}   # 前附表之六 第 10 行

THIN = Side(style="thin", color="BFBFBF")
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR_FILL = PatternFill("solid", fgColor="1F4E5A")
HDR_FILL_TECH = PatternFill("solid", fgColor="14505C")
GRP_FILL = PatternFill("solid", fgColor="E8F1EE")
WARN_FILL = PatternFill("solid", fgColor="FDECEA")
INPUT_FILL = PatternFill("solid", fgColor="FFF9E0")
TECH_SRC_FILL = PatternFill("solid", fgColor="FDF3E3")


def style_header(ws, row, ncol, fill=None):
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = fill or HDR_FILL
        cell.font = Font(bold=True, color="FFFFFF", size=10)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BOX


def build_expert_sheet(wb, idx, data, side="biz"):
    """side=biz 商务表（本项目招标文件原文）；side=tech 技术表（国网通用范本）。"""
    lab = "商务" if side == "biz" else "技术"
    name = "专家%d-%s" % (idx, lab)
    ws = wb.create_sheet(name)
    ws.sheet_view.showGridLines = False
    widths = [6, 16, 22, 11, 62, 10, 18]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.merge_cells("A1:G1")
    ws["A1"] = "评标委员会成员评分表 · %s部分" % lab
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 28

    if side == "biz":
        src_line = "招标文件前附表之三 · 原文可得"
        total_note = "百分制（含扣分项，可至 -8）"
        w_pct = WEIGHT["biz"]
    else:
        src_line = "国网通用范本 · 非本项目原文"
        total_note = "百分制（含扣分项，可至 27）"
        w_pct = WEIGHT["tech"]

    meta = [
        ("分标编号", PKG, "分标名称", PKG_NAME),
        ("专家编号", "专家 %d" % idx, "评标日期", "____年__月__日"),
        ("%s权重" % lab, "%d%%" % round(w_pct * 100), "本表分值", total_note),
        ("规则来源", src_line, "评分表", "第 %d 份 / 共 %d 份" % (idx, EXPERT_COUNT)),
    ]
    r = 2
    for a, b, c, d in meta:
        ws.cell(row=r, column=1, value=a).font = Font(bold=True, size=9)
        ws.cell(row=r, column=2, value=b).font = Font(size=9)
        ws.cell(row=r, column=3, value=c).font = Font(bold=True, size=9)
        ws.merge_cells(start_row=r, start_column=4, end_row=r, end_column=7)
        cell = ws.cell(row=r, column=4, value=d)
        cell.font = Font(size=9)
        if a == "规则来源" and side == "tech":
            cell.fill = TECH_SRC_FILL
        r += 1

    r += 1
    head_row = r
    heads = ["序号", "评分分组", "评审要素", "分值区间", "评分细则（按原文分档，专家据此择档）", "专家打分", "扣分/偏离说明"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=head_row, column=i, value=h)
    style_header(ws, head_row, 7, HDR_FILL if side == "biz" else HDR_FILL_TECH)
    ws.freeze_panes = ws.cell(row=head_row + 1, column=1)

    r = head_row + 1
    seq = 0
    for g in data["groups"]:
        # 分组标题行
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
        gc = ws.cell(row=r, column=1, value="%s（%s ~ %s）" % (g["name"], g["min"], g["max"]))
        gc.fill = GRP_FILL
        gc.font = Font(bold=True, size=10)
        gc.border = BOX
        r += 1
        for it in g["items"]:
            seq += 1
            ws.cell(row=r, column=1, value=seq)
            ws.cell(row=r, column=2, value=g["name"])
            ws.cell(row=r, column=3, value=it["element"])
            ws.cell(row=r, column=4, value="%s ~ %s" % (it["min"], it["max"]))
            basis = "\n".join("· " + b for b in it["basis"]) if it["basis"] else "（原文未给分档细则）"
            ws.cell(row=r, column=5, value=basis)
            sc = ws.cell(row=r, column=6, value=None)
            sc.fill = INPUT_FILL
            ws.cell(row=r, column=7, value="")
            for c in range(1, 8):
                cell = ws.cell(row=r, column=c)
                cell.border = BOX
                cell.alignment = Alignment(
                    vertical="top", wrap_text=(c == 5),
                    horizontal="center" if c in (1, 4, 6) else "left")
                if c != 6:
                    cell.font = Font(size=9)
            r += 1

    # 打分区间校验：每一项单独一条规则，防止填出区间外的分数
    rr = head_row + 1
    for g in data["groups"]:
        rr += 1
        for it in g["items"]:
            dv = DataValidation(
                type="decimal", operator="between",
                formula1=str(it["min"]), formula2=str(it["max"]),
                allow_blank=True,
                error="该项允许 %s ~ %s 分，请按评分细则择档。" % (it["min"], it["max"]),
                errorTitle="分数超出该项分值区间")
            ws.add_data_validation(dv)
            dv.add(ws.cell(row=rr, column=6))
            rr += 1

    # 合计
    ws.cell(row=r, column=5, value="%s得分合计（百分制）" % lab).font = Font(bold=True, size=10)
    ws.cell(row=r, column=5).alignment = Alignment(horizontal="right")
    tot = ws.cell(row=r, column=6, value="=SUM(F%d:F%d)" % (head_row + 1, r - 1))
    tot.font = Font(bold=True, size=11)
    tot.fill = PatternFill("solid", fgColor="D9E8E3")
    tot.border = BOX
    tot.alignment = Alignment(horizontal="center")
    ws.cell(row=r, column=7, value="（专家自校）").font = Font(size=8, italic=True)
    total_row = r

    r += 2
    ws.cell(row=r, column=1, value="专家签字：________________").font = Font(size=10)
    ws.cell(row=r, column=5, value="日期：________________").font = Font(size=10)
    r += 2
    if side == "biz":
        note = ("说明：本表评分细则逐条摘自招标文件第三章评标办法前附表之三（原文表体 84 行，"
                "对应 L1083–L1170），可按「规则来源」页回读核对。")
        nc_fill = None
    else:
        note = ("⚠ 来源提示：本表依据国网通用技术评分标准范本整理，不是本项目招标文件原文——"
                "152507 招标文件前附表之四标题之后为空白段落，正文无技术评分表。"
                "范本允许各省按品类调整分值倍数，正式评标前须与招标人 / ECP 平台网页版逐项核对。")
        nc_fill = TECH_SRC_FILL
    ws.merge_cells(start_row=r, start_column=1, end_row=r + 1, end_column=7)
    nc = ws.cell(row=r, column=1, value=note)
    nc.font = Font(size=8, color="666666" if side == "biz" else "854F0B")
    nc.alignment = Alignment(wrap_text=True, vertical="top")
    if nc_fill:
        nc.fill = nc_fill

    return total_row


def build_summary(wb, biz_rows, tech_rows):
    ws = wb.create_sheet("汇总（待确认规则）", 0)
    ws.sheet_view.showGridLines = False
    for i, w in enumerate([22, 14, 14, 14, 14, 26], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    ws.merge_cells("A1:F1")
    ws["A1"] = "评标得分汇总表 · %s %s" % (PKG, PKG_NAME)
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")
    ws.row_dimensions[1].height = 26

    ws["A3"] = "权重"
    ws["B3"] = "商务 %d%%" % round(WEIGHT["biz"] * 100)
    ws["C3"] = "技术 %d%%" % round(WEIGHT["tech"] * 100)
    ws["D3"] = "报价 %d%%" % round(WEIGHT["price"] * 100)
    for c in "ABCD":
        ws[c + "3"].font = Font(bold=True, size=9)
        ws[c + "3"].border = BOX

    heads = ["专家", "商务得分", "技术得分", "报价得分", "加权总分", "备注"]
    r = 5
    for i, h in enumerate(heads, 1):
        ws.cell(row=r, column=i, value=h)
    style_header(ws, r, 6)

    first = r + 1
    for i in range(EXPERT_COUNT):
        r += 1
        ws.cell(row=r, column=1, value="专家 %d" % (i + 1))
        ws.cell(row=r, column=2, value="='专家%d-商务'!F%d" % (i + 1, biz_rows[i]))
        ws.cell(row=r, column=3, value="='专家%d-技术'!F%d" % (i + 1, tech_rows[i]))
        ws.cell(row=r, column=4, value=None).fill = INPUT_FILL
        ws.cell(row=r, column=5,
                value="=ROUND(B{r}*{wb}+C{r}*{wt}+D{r}*{wp},2)".format(
                    r=r, wb=WEIGHT["biz"], wt=WEIGHT["tech"], wp=WEIGHT["price"]))
        ws.cell(row=r, column=6, value="报价分由计算表回填")
        for c in range(1, 7):
            ws.cell(row=r, column=c).border = BOX
            ws.cell(row=r, column=c).font = Font(size=9)
            ws.cell(row=r, column=c).alignment = Alignment(horizontal="center")
    last = r

    # 汇总：公开渠道一致指向 ECP 通用做法「去掉一个最高、一个最低后取平均」
    r += 1
    ws.cell(row=r, column=1, value="去极值后平均").font = Font(bold=True, size=9)
    f = "=IF(COUNT(E{a}:E{b})>2,ROUND((SUM(E{a}:E{b})-MAX(E{a}:E{b})-MIN(E{a}:E{b}))/(COUNT(E{a}:E{b})-2),2),ROUND(AVERAGE(E{a}:E{b}),2))".format(a=first, b=last)
    cell = ws.cell(row=r, column=5, value=f)
    cell.font = Font(bold=True, size=10)
    cell.border = BOX
    ws.cell(row=r, column=6, value="规则未在招标文件内载明").font = Font(size=8, color="B54708")
    r += 1
    ws.cell(row=r, column=1, value="算术平均（对照）").font = Font(size=9)
    ws.cell(row=r, column=5, value="=ROUND(AVERAGE(E%d:E%d),2)" % (first, last)).font = Font(size=9)

    r += 3
    ws.merge_cells(start_row=r, start_column=1, end_row=r + 3, end_column=6)
    warn = ("⚠ 汇总规则缺口：本项目招标文件全文检索「得分汇总」「综合得分」「去掉最高」均为 0 命中，"
            "文件没有规定多位专家如何合并成分。公开渠道一致指向 ECP 通用做法——去掉一个最高、"
            "一个最低后取算术平均，本表按此实现并同时给出算术平均作对照。"
            "正式评标须以招标人 / 电子评标系统确认的规则为准。")
    wc = ws.cell(row=r, column=1, value=warn)
    wc.fill = WARN_FILL
    wc.font = Font(size=9, color="B54708")
    wc.alignment = Alignment(wrap_text=True, vertical="center")
    return ws


def build_source_sheet(wb, biz_data, tech_data):
    ws = wb.create_sheet("规则来源")
    ws.sheet_view.showGridLines = False
    for i, w in enumerate([8, 16, 24, 12, 34, 34], 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws["A1"] = "规则来源与可得性（本页用于回溯，不参与评分）"
    ws["A1"].font = Font(bold=True, size=12)
    ws.row_dimensions[1].height = 24

    heads = ["序号", "评分分组", "评审要素", "分值区间", "来源", "回读位置 / 说明"]
    for i, h in enumerate(heads, 1):
        ws.cell(row=3, column=i, value=h)
    style_header(ws, 3, 6)

    r = 4
    seq = 0
    # 商务：A 级来源
    for g in biz_data["groups"]:
        for it in g["items"]:
            seq += 1
            ws.cell(row=r, column=1, value=seq)
            ws.cell(row=r, column=2, value=g["name"])
            ws.cell(row=r, column=3, value=it["element"])
            ws.cell(row=r, column=4, value="%s ~ %s" % (it["min"], it["max"]))
            ws.cell(row=r, column=5, value="A · 本项目招标文件原文")
            ws.cell(row=r, column=6, value="前附表之三 L1083–L1170，细则 %d 条" % len(it["basis"]))
            for c in range(1, 7):
                ws.cell(row=r, column=c).border = BOX
                ws.cell(row=r, column=c).font = Font(size=9)
            r += 1

    # 技术：C 级来源，整行标底色
    for g in tech_data["groups"]:
        for it in g["items"]:
            seq += 1
            ws.cell(row=r, column=1, value=seq)
            ws.cell(row=r, column=2, value=g["name"])
            ws.cell(row=r, column=3, value=it["element"])
            ws.cell(row=r, column=4, value="%s ~ %s" % (it["min"], it["max"]))
            ws.cell(row=r, column=5, value="C · 国网通用范本（非本文件）")
            ws.cell(row=r, column=6, value="细则 %d 条；用前须与 ECP 网页版核对" % len(it["basis"]))
            for c in range(1, 7):
                cell = ws.cell(row=r, column=c)
                cell.border = BOX
                cell.font = Font(size=9)
                cell.fill = TECH_SRC_FILL
            r += 1

    r += 1
    gaps = [
        ("技术评分标准", "本项目缺失", "前附表之四标题下是空段落，docx 正文无表格；"
                                     "标题注「可复制下载查看」，指国网 ECP 平台网页。"
                                     "本工作簿按 C 级通用范本补齐，须核对。"),
        ("专家评分汇总规则", "本项目缺失", "全文检索「得分汇总」「综合得分」「去掉最高」均 0 命中；"
                                        "公开渠道指向 ECP 通用做法：去掉最高最低后取平均。"),
        ("评分表表单格式", "本项目缺失", "全文检索「评分表」0 命中，招标文件不附纸质表单。"),
        ("专家人数", "可得", "投标人须知前附表 6.1.1：5 人及以上单数，技术经济专家不少于 2/3。"),
        ("分值权重", "可得", "前附表之六，14 个分标各不相同；本表按智能终端 50/40/10。"),
        ("报价算法", "可得", "前附表之五：区间平均价浮动法，基准价系数 C 由监察人员现场随机抽取。"),
    ]
    ws.cell(row=r, column=1, value="要素").font = Font(bold=True, size=10)
    ws.cell(row=r, column=2, value="可得性").font = Font(bold=True, size=10)
    ws.cell(row=r, column=3, value="核验依据").font = Font(bold=True, size=10)
    r += 1
    for a, b, c in gaps:
        ws.cell(row=r, column=1, value=a).font = Font(size=9, bold=True)
        ws.cell(row=r, column=2, value=b).font = Font(size=9)
        ws.merge_cells(start_row=r, start_column=3, end_row=r, end_column=6)
        cc = ws.cell(row=r, column=3, value=c)
        cc.font = Font(size=9)
        cc.alignment = Alignment(wrap_text=True, vertical="top")
        if "缺失" in b:
            for k in range(1, 7):
                ws.cell(row=r, column=k).fill = WARN_FILL
        r += 1

    r += 1
    ws.merge_cells(start_row=r, start_column=1, end_row=r + 2, end_column=6)
    note = ("来源分级：A = 本项目招标文件原文，可逐行回读；C = 公开渠道的国网通用范本转述，"
            "结构经三个独立来源交叉印证，且其商务部分与本地文件逐字一致，但仍不等于本项目的正式条款。"
            "对外使用 C 级内容前，必须与招标人或 ECP 平台核对。")
    nc = ws.cell(row=r, column=1, value=note)
    nc.font = Font(size=9, color="5F5E5A")
    nc.alignment = Alignment(wrap_text=True, vertical="top")


def main():
    with open(SRC, encoding="utf-8") as f:
        biz = json.load(f)
    with open(SRC_TECH, encoding="utf-8") as f:
        tech = json.load(f)

    wb = Workbook()
    wb.remove(wb.active)

    biz_rows, tech_rows = [], []
    for idx in range(1, EXPERT_COUNT + 1):
        biz_rows.append(build_expert_sheet(wb, idx, biz, "biz"))
        tech_rows.append(build_expert_sheet(wb, idx, tech, "tech"))
    build_summary(wb, biz_rows, tech_rows)
    build_source_sheet(wb, biz, tech)

    # 打印设置：A4 横向，每页容纳一张表
    for ws in wb.worksheets:
        ws.page_setup.orientation = "landscape"
        ws.page_setup.paperSize = 9
        ws.page_setup.fitToWidth = 1
        ws.sheet_properties.pageSetUpPr.fitToPage = True

    wb.save(OUT)
    print("已生成:", OUT)
    print("工作表:", [ws.title for ws in wb.worksheets])
    print("商务项:", biz["item_count"], "| 技术项:", tech["item_count"], "| 专家份数:", EXPERT_COUNT)


if __name__ == "__main__":
    main()
