# -*- coding: utf-8 -*-
"""造 5 份受控合成投标包（1 份合规 + 4 份各带一处典型违规）。

为什么必须合成：知识库 173 条目里投标文件 0 份，受审侧 bid.* 全空，
46 条否决情形里有 21 条要拿投标侧事实去比，没有投标件就一条都验不了。

合成不等于编造：所有物料、行项目号、限价、交货日期全部取自
152507-1102002-4004 的真实招标文件与货物清单，只有「投标人名称、报价、
签章名、有效期、税率」这几项是按剧本设定的——这四个正是要被判的地方。

每份文件都带「合成演示数据」水印，不与真实投标件混放，也不冒充真件。

产出：
  bid_packs/投标文件_<简称>_152507-1102002-4004.docx
  bid_packs/分项报价表_<简称>_152507-1102002-4004.xlsx
  bid_packs/_ground_truth.json     每家的期望值，供后续判定比对
"""
import io
import json
import os

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

OUT_DIR = "bid_packs"

# 真实限价（152507-1102002-4004 限价表 4 条物料，万元折元）
CAPS = [
    ("100035912500010", "线路在线监测装置,电缆隧道在线监测系统", 1, "套", 340000),
    ("100035917800010", "线路在线监测装置,电缆隧道在线监测系统", 1, "套", 1821200),
    ("100035912200010", "线路在线监测装置,电缆隧道在线监测系统", 1, "套", 4533100),
    ("100034915900360", "线路在线监测装置,电缆隧道在线监测系统", 1, "套", 10000000),
]
CAP_SUM = sum(c[4] for c in CAPS)          # 16694300
SECTION = "152507-1102002-4004"
PACKAGE = "包1 线路在线监测装置"

# 剧本：每家只改该改的那几项，其余保持一致，便于逐条归因
COMPANIES = [
    {"code": "HZ", "short": "华中", "name": "华中某某电气有限公司",
     "legal": "陈某某", "seal_name": "华中某某电气有限公司", "seal_valid": "有效",
     "validity": 90, "tax": 13, "prices": None,
     "expect": "全合规", "defect": None,
     "defect_note": "对照组：无违规，四条机器可判规则应全部判为未触发"},

    {"code": "XY", "short": "襄阳", "name": "襄阳某某开关有限公司",
     "legal": "孙某某", "seal_name": "襄阳某某电力设备有限公司", "seal_valid": "有效",
     "validity": 90, "tax": 13, "prices": None,
     "expect": "违规-签章名不一致", "defect": "GW-HB-FJ-004",
     "defect_note": "电子签章名称「襄阳某某电力设备有限公司」与投标人「襄阳某某开关有限公司」不是同一人"},

    {"code": "YC", "short": "宜昌", "name": "宜昌某某输变电有限公司",
     "legal": "赵某某", "seal_name": "宜昌某某输变电有限公司", "seal_valid": "有效",
     "validity": 90, "tax": 13,
     "prices": {"100035912200010": 4600000},     # 限价 4533100，超 66900
     "expect": "违规-单条物料超最高限价", "defect": "GW-HB-FJ-010",
     "defect_note": "行项目 100035912200010 报 4600000，超该行限价 4533100 共 66900；"
                    "但标包总额 15545080 仍低于限价合计 16694300，单值比抓不到"},

    {"code": "JZ", "short": "荆州", "name": "荆州某某智能装备有限公司",
     "legal": "周某某", "seal_name": "荆州某某智能装备有限公司", "seal_valid": "有效",
     "validity": 60, "tax": 13, "prices": None,
     "expect": "违规-投标有效期不足", "defect": "GW-HB-FJ-016",
     "defect_note": "投标有效期 60 日历天，招标文件要求 90 日历天"},

    {"code": "HS", "short": "黄石", "name": "黄石某某电力科技有限公司",
     "legal": "吴某某", "seal_name": "黄石某某电力科技有限公司", "seal_valid": "有效",
     "validity": 90, "tax": 11, "prices": None,
     "expect": "违规-税率不在法定集合", "defect": "GW-HB-FJ-017",
     "defect_note": "增值税税率 11%，不在 13/9/6/3/1/0 法定集合内"},
]


def price_of(company):
    """按限价 90% 报价；剧本里指定了某行项目金额的，用指定值。"""
    rows = []
    for no, desc, qty, unit, cap in CAPS:
        amt = (company["prices"] or {}).get(no) or int(cap * 0.9 // 1)
        rows.append({"item_no": no, "desc": desc, "qty": qty, "unit": unit,
                     "unit_price": amt, "amount": amt * qty})
    return rows


def qty_total(rows):
    return sum(r["amount"] for r in rows)


def money(v):
    """带千分位，模拟真实报价表排版。"""
    return "{:,.2f}".format(v)


def build_xlsx(c, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "分项报价表"

    thick = Side(style="thin", color="B0B0B0")
    border = Border(left=thick, right=thick, top=thick, bottom=thick)

    ws["A1"] = "分项报价表"
    ws["A1"].font = Font(size=14, bold=True)
    ws.merge_cells("A1:G1")
    ws["A1"].alignment = Alignment(horizontal="center")

    ws["A2"] = "标段号：%s    标段名称：%s    投标人：%s" % (SECTION, PACKAGE, c["name"])
    ws.merge_cells("A2:G2")

    heads = ["行项目号", "物料描述", "数量", "单位", "不含税单价（元）", "不含税合价（元）", "税率"]
    for j, h in enumerate(heads, 1):
        cell = ws.cell(row=3, column=j, value=h)
        cell.font = Font(bold=True)
        cell.fill = PatternFill("solid", fgColor="DDEBF7")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for i, r in enumerate(rows, 4):
        vals = [r["item_no"], r["desc"], r["qty"], r["unit"],
                money(r["unit_price"]), money(r["amount"]), "%d%%" % c["tax"]]
        for j, v in enumerate(vals, 1):
            cell = ws.cell(row=i, column=j, value=v)
            cell.border = border
            if j in (3, 5, 6, 7):
                cell.alignment = Alignment(horizontal="right")

    tr = 4 + len(rows)
    ws.cell(row=tr, column=1, value="合计").font = Font(bold=True)
    ws.cell(row=tr, column=6, value=money(qty_total(rows))).font = Font(bold=True)
    for j in range(1, 8):
        ws.cell(row=tr, column=j).border = border
        ws.cell(row=tr, column=j).fill = PatternFill("solid", fgColor="F2F2F2")

    ws.cell(row=tr + 2, column=1,
            value="投标人（盖章）：" + c["name"])
    ws.cell(row=tr + 3, column=1,
            value="注：本表为【合成演示数据 · 非真实投标文件】，仅用于系统验证。")

    for col, w in (("A", 20), ("B", 42), ("C", 8), ("D", 8),
                   ("E", 18), ("F", 18), ("G", 8)):
        ws.column_dimensions[col].width = w

    ws2 = wb.create_sheet("声明")
    ws2["A1"] = "本文件为合成演示数据"
    ws2["A1"].font = Font(bold=True, size=12)
    ws2["A2"] = "不含任何真实投标人信息；物料、行项目号、限价取自 152507 公开招标文件。"
    ws2["A3"] = "剧本设定项：投标人名称、报价、电子签章名称、投标有效期、增值税税率。"
    ws2["A4"] = "对应剧本：" + c["expect"]

    path = os.path.join(OUT_DIR, "分项报价表_%s_%s.xlsx" % (c["short"], SECTION))
    wb.save(path)
    return path


def build_docx(c, rows):
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "宋体"
    st.font.size = Pt(10.5)

    warn = doc.add_paragraph()
    warn.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = warn.add_run("【合成演示数据 · 非真实投标文件 · 仅用于系统验证】")
    run.font.size = Pt(9)
    run.font.bold = True
    run.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = t.add_run("投 标 文 件")
    tr.font.size = Pt(18)
    tr.font.bold = True

    sub = doc.add_paragraph()
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub.add_run("标段号：%s    标段名称：%s" % (SECTION, PACKAGE)).font.size = Pt(11)

    def h(text):
        p = doc.add_paragraph()
        p.add_run(text).font.bold = True
        return p

    def kv(k, v):
        doc.add_paragraph("%s：%s" % (k, v))

    h("一、投标函")
    doc.add_paragraph("致：国网湖北省电力有限公司")
    doc.add_paragraph(
        "我方已仔细研究 %s 招标文件的全部内容，愿意按本投标文件的承诺承担本标段的供货及相关服务。"
        % PACKAGE)

    h("二、投标人基本情况")
    kv("投标人名称", c["name"])
    kv("法定代表人", c["legal"])
    kv("统一社会信用代码", "91420100MA4K%05dX" % (sum(ord(ch) for ch in c["code"]) * 37 % 100000))
    kv("注册地址", "湖北省%s市某某工业园区 %d 号" % (c["short"], 8 + len(c["code"])))
    kv("所投标段号", SECTION)

    h("三、投标报价")
    total = qty_total(rows)
    kv("投标总价（不含税）", "人民币 %s 元（%s）" % (money(total), money(total)))
    kv("增值税税率", "%d%%" % c["tax"])
    doc.add_paragraph("分项报价详见随附《分项报价表》。")

    h("四、投标有效期")
    kv("投标有效期", "自投标截止日起 %d 日历天" % c["validity"])

    h("五、交货期承诺")
    kv("首批交货日期", "2026-05-10")
    kv("交货地点", "湖北省孝感市应城市 施工现场地面交货")
    kv("交货方式", "施工现场地面交货")

    h("六、投标保证金")
    kv("投标保证金", "本项目免收投标保证金")

    h("七、电子签章")
    doc.add_paragraph(
        "本投标文件已通过招标人招投标交易平台信息系统加盖电子签章，签章数据电文与纸质文件具有同等法律效力。")
    kv("电子签章名称", c["seal_name"])
    kv("签章验证状态", c["seal_valid"])
    kv("签章时间", "2026-10-18 15:32:07")

    h("八、资格及其他事项声明")
    doc.add_paragraph(
        "我方承诺本投标文件所附全部证明材料真实有效，不存在弄虚作假、串通投标、行贿等违法违规情形；"
        "不存在被列入失信被执行人、重大税收违法失信主体名单的情形。")

    doc.add_paragraph("")
    p = doc.add_paragraph("投标人（电子签章）：" + c["seal_name"])
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph("2026 年 10 月 18 日").alignment = WD_ALIGN_PARAGRAPH.RIGHT

    path = os.path.join(OUT_DIR, "投标文件_%s_%s.docx" % (c["short"], SECTION))
    doc.save(path)
    return path


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    truth = {"meta": {
        "title": "152507-1102002-4004 受控合成投标包",
        "section_no": SECTION,
        "cap_items": [{"item_no": n, "desc": d, "qty": q, "unit": u, "cap_yuan": cap}
                      for n, d, q, u, cap in CAPS],
        "cap_sum_yuan": CAP_SUM,
        "nature": "合成演示数据，不含真实投标人信息；物料/行项目号/限价取自 152507 公开招标文件",
        "designed_fields": ["投标人名称", "报价", "电子签章名称", "投标有效期", "增值税税率"],
        "required_validity_days": 90,
        "required_delivery_date": "2026-05-10",
        "legal_tax_rates": [0.13, 0.09, 0.06, 0.03, 0.01, 0.0],
    }, "bidders": []}

    for c in COMPANIES:
        rows = price_of(c)
        px = build_xlsx(c, rows)
        pd = build_docx(c, rows)
        truth["bidders"].append({
            "code": c["code"],
            "bidder_name": c["name"],
            "files": [os.path.basename(pd), os.path.basename(px)],
            "expect": c["expect"],
            "defect_rule": c["defect"],
            "defect_note": c["defect_note"],
            "ground_truth": {
                "bid.bidder_name": c["name"],
                "bid.seal_name": c["seal_name"],
                "bid.seal_valid": True,
                "bid.validity_days": c["validity"],
                "bid.tax_rate": c["tax"] / 100.0,
                "bid.committed_delivery_date": "2026-05-10",
                "bid.price_total_ex_tax": qty_total(rows),
                "bid.price_items": [{"item_no": r["item_no"], "amount_yuan": r["amount"]}
                                    for r in rows],
            },
            "derived": {
                "over_cap_items": [r["item_no"] for r in rows
                                   if r["amount"] > dict((n, cap) for n, _, _, _, cap in CAPS)[r["item_no"]]],
                "total_over_cap_sum": qty_total(rows) > CAP_SUM,
            },
        })
        print("%-6s %-24s 总额=%-12s 违规=%s"
              % (c["short"], c["name"], money(qty_total(rows)), c["defect"] or "无"))

    io.open(os.path.join(OUT_DIR, "_ground_truth.json"), "w", encoding="utf-8").write(
        json.dumps(truth, ensure_ascii=False, indent=1))
    print("\n合计限价 =", money(CAP_SUM))
    print("产出目录：", OUT_DIR)


if __name__ == "__main__":
    main()
