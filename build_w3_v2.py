# -*- coding: utf-8 -*-
"""生成 W3 页面 v2 数据：6 家 × 8 条机器规则，每格带字段值 + 原文引用。

数据来源（全部真跑，不编）：
  - 判定：国网Demo_F3_46条规则端到端_真跑证据_V2.json
  - 抽取：国网Demo_F2受审侧抽取v2_真跑证据.json
  - 原文：bid_packs_v2/ 下 24 份文件（按字段关键词定位段落/表行）
输出：国网Demo_W3v2_页面数据_6家8条.json
"""
import io
import json
import os
import re

import docx
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
F3 = os.path.join(HERE, "国网Demo_F3_46条规则端到端_真跑证据_V2.json")
F2 = os.path.join(HERE, "国网Demo_F2受审侧抽取v2_真跑证据.json")
PACKS = os.path.join(HERE, "bid_packs_v2")
OUT = os.path.join(HERE, "国网Demo_W3v2_页面数据_6家8条.json")
# F3 那次现场抽取的逐行明细（判定层只落 item_check，行11 的算术证据在这里）
LIVE = os.path.join(HERE, "_f3v2_bid_live.json")

# 8 条机器可跑规则 → 依赖字段 + 原文定位键
COLS = [
    (4, "签章", "GW-HB-FJ-004", ["bid.seal_name", "bid.seal_present", "bid.seal_valid"]),
    (7, "交货期", "GW-HB-FJ-007", ["bid.committed_delivery_date"]),
    (10, "限价", "GW-HB-FJ-010", ["bid.price_items"]),
    (11, "报价算术", "GW-HB-FJ-011", ["bid.price_items"]),
    (13, "保证金", "GW-HB-FJ-013", ["bid.bond_amount"]),
    (16, "有效期", "GW-HB-FJ-016", ["bid.validity_days"]),
    (17, "税率", "GW-HB-FJ-017", ["bid.tax_rate"]),
    (39, "法人不重", "GW-HB-FJ-039", ["bid.legal_rep_name"]),
]

FIELD_LABEL = {
    "bid.bidder_name": "投标人名称",
    "bid.seal_name": "电子签章名称",
    "bid.seal_present": "签章是否加盖",
    "bid.seal_valid": "签章是否有效",
    "bid.validity_days": "投标有效期",
    "bid.tax_rate": "增值税税率",
    "bid.price_total_ex_tax": "未含税总价",
    "bid.legal_rep_name": "法定代表人",
    "bid.committed_delivery_date": "承诺交货期",
    "bid.bond_amount": "投标保证金",
    "bid.price_items": "分项报价表",
}

# 原文定位：正则按优先级排列。只认「能当判据」的那一句，不做全文模糊匹配——
# 关键词模糊匹配会把「授权委托书…有效期与投标有效期一致」当成投标有效期原句，
# 也会把封面「投标人：…」当成签章验证结论，演示时点开就露馅。
FIELD_PATTERNS = {
    "bid.validity_days": [
        r"投标有效期\s*\|[^|\n]*\|[^|\n]*\|[^|\n]*",
        r"投标有效期[^。\n]{0,40}\d+\s*日历天",
        r"投标有效期[^。\n]{0,40}\d+\s*日",
    ],
    "bid.seal_valid": [
        r"电子签章验证[：:][^。\n]*",
        r"签章[^。\n]{0,40}不一致",
        r"签章主体为「[^」]+」[^。\n]*",
    ],
    "bid.seal_name": [
        r"签章主体为「[^」]+」",
        r"投\s*标\s*人[：:][^|。\n]{2,60}（电子签章）",
        r"投标人[：:][^|。\n]{2,60}（电子签章）",
    ],
    "bid.seal_present": [
        r"电子签章验证[：:][^。\n]*",
        r"[^。\n]{0,20}电子签章[^。\n]{0,40}",
    ],
    "bid.tax_rate": [r"增值税税率\s*[\d.]+%", r"税率\s*[\d.]+%"],
    "bid.bond_amount": [r"投标保证金[^。\n]{0,70}", r"免收[^。\n]{0,40}"],
    "bid.price_items": [
        r"行项目号[^|\n]*\|[^|\n]*\|[^|\n]*\|[^|\n]*",
        r"网省采购申请号[^|\n]*\|[^|\n]*",
    ],
    "bid.legal_rep_name": [r"法定代表人[：:]\s*[^\s|，。、]{2,10}"],
    "bid.price_total_ex_tax": [r"未含税价[^。\n]{0,60}", r"合计[^。\n]{0,40}"],
    "bid.committed_delivery_date": [
        r"交货期（包1[^|\n]*\|[^|\n]*\|[^|\n]*\|[^|\n]*",
        r"[^。\n]{0,20}首批交货最早可安排至\s*\d{4}-\d{2}-\d{2}[^。\n]*",
        r"交货[^。\n]{0,40}\d{4}-\d{2}-\d{2}[^。\n]{0,40}",
        r"交货[^。\n]{0,30}\d{4}\s*年\s*\d{1,2}\s*月",
    ],
}


def read_docx(path):
    """返回 [(位置说明, 文本)]，含段落与表格行。"""
    out = []
    d = docx.Document(path)
    for i, p in enumerate(d.paragraphs):
        t = (p.text or "").strip()
        if t:
            out.append(("第%d段" % (i + 1), t))
    for ti, tb in enumerate(d.tables):
        for ri, row in enumerate(tb.rows):
            cells = [(c.text or "").strip() for c in row.cells]
            if any(cells):
                out.append(("表%d第%d行" % (ti + 1, ri + 1), " | ".join(cells)))
    return out


def read_xlsx(path):
    out = []
    wb = openpyxl.load_workbook(path, data_only=True)
    for ws in wb.worksheets:
        for ri, row in enumerate(ws.iter_rows(values_only=True)):
            cells = ["" if c is None else str(c).strip() for c in row]
            if any(cells):
                out.append(("表%s第%d行" % (ws.title, ri + 1), " | ".join(cells)))
    return out


def money(x):
    try:
        return "{:,}".format(int(round(float(x))))
    except Exception:
        return str(x)


def days_between(a, b):
    """返回 a - b 的天数（a 晚于 b 为正）。"""
    import datetime

    def parse(s):
        m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", str(s))
        return datetime.date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None

    da, db = parse(a), parse(b)
    return (da - db).days if da and db else None


def mk_calc(row, state, fmap, tender, legal_names, item_check=None, live_items=None):
    """按规则把「字段值 + 招标阈值」拼成人能看懂的算式。不写没有依据的话。"""
    def g(f):
        return (fmap.get(f) or {}).get("got")

    if row == 4:
        seal, bidder = g("bid.seal_name"), g("bid.bidder_name")
        if not seal or not bidder:
            return None
        seal_clean = re.sub(r"[（(]电子签章[)）]", "", str(seal)).strip()
        same = seal_clean == str(bidder).strip()
        return "签章主体「%s」 %s 投标人「%s」" % (seal_clean, "=" if same else "≠", bidder)

    if row == 7:
        got, req = g("bid.committed_delivery_date"), tender.get("delivery")
        d = days_between(got, req)
        if d is None:
            return None
        if d > 0:
            return "承诺交货 %s − 要求 %s = 晚 %d 天（正数即不满足）" % (
                re.search(r"\d{4}-\d{2}-\d{2}", str(got)).group(0), req, d)
        if d == 0:
            return "承诺交货 %s = 要求 %s（同日，满足）" % (
                re.search(r"\d{4}-\d{2}-\d{2}", str(got)).group(0), req)
        return "承诺交货 %s ≤ 要求 %s（早 %d 天，满足）" % (
            re.search(r"\d{4}-\d{2}-\d{2}", str(got)).group(0), req, -d)

    if row == 10:
        items = (item_check or {}).get("items") or []
        if not items:
            return None
        over = [x for x in items if (x.get("delta_yuan") or 0) > 0]
        caps = tender.get("caps") or {}
        if over:
            o = over[0]
            return "行项目 %s：含税报价 %s > 限价 %s（超 %s）；其余 %d 行未超" % (
                o["item_no"], money(o["bid_yuan"]), money(o["cap_yuan"]),
                money(o["delta_yuan"]), len(items) - len(over))
        s = sum(x.get("bid_yuan") or 0 for x in items)
        cap = sum(x.get("cap_yuan") or 0 for x in items)
        return "%d 行逐条比各自限价：全部未超；合计 %s ≤ 限价合计 %s" % (
            len(items), money(s), money(cap))

    if row == 11:
        items = live_items or []
        ok = [x for x in items if x.get("arith_ok")]
        if not items:
            return None
        bad = [x for x in items if not x.get("arith_ok")]
        if bad:
            b = bad[0]
            return "行项目 %s：数量 %s × 单价 %s = %s，表列合价 %s（差 %s）" % (
                b["item_no"], b.get("qty"), money(b.get("unit_price_yuan")),
                money(b.get("calc_amount_yuan")), money(b.get("amount_yuan")),
                money((b.get("amount_yuan") or 0) - (b.get("calc_amount_yuan") or 0)))
        return "%d 行逐行验「数量 × 单价 = 合价」，全部相符（元取整容差 ≤ 0.5 元）" % len(ok)

    if row == 13:
        return "招标文件：%s → 情形不适用，不按「缺缴纳凭证」判否" % (
            tender.get("bond") or "本项目免收投标保证金")

    if row == 16:
        got, req = g("bid.validity_days"), tender.get("validity")
        m = re.search(r"(\d+)", str(got) or "")
        if not m or not req:
            return None
        d = int(m.group(1)) - int(req)
        return "承诺 %s 日历天 %s 要求 %d 日（差 %d 天）" % (
            m.group(1), "<" if d < 0 else "≥", req, abs(d))

    if row == 17:
        got = g("bid.tax_rate")
        if got is None:
            return None
        m = re.search(r"[\d.]+", str(got))
        if not m:
            return None
        rate = float(m.group(0))
        if rate <= 1 and "%" not in str(got):
            rate *= 100
        legal = [13, 9, 6, 3]
        hit = any(abs(rate - x) < 0.01 for x in legal)
        return "%s%% %s 法定税率集合 {13%%, 9%%, 6%%, 3%%}" % (
            ("%g" % rate), "∈" if hit else "∉")

    if row == 39:
        names = [n for n in legal_names if n]
        if not names:
            return None
        return "本标包 %d 家法定代表人：%s → 无重复" % (len(names), "、".join(names))

    return None


def load_pack(short):
    """读一家 4 份文件的全文行；返回 [(文件名, 位置, 文本)]"""
    files = []
    for ext in ("商务文件.docx", "价格文件.docx", "技术文件.docx"):
        p = os.path.join(PACKS, "投标文件_%s_152507-1102002-4004_%s" % (short, ext))
        if os.path.exists(p):
            files.append((os.path.basename(p).replace("投标文件_%s_152507-1102002-4004_" % short, ""),
                          read_docx(p)))
    p = os.path.join(PACKS, "分项报价表_%s_152507-1102002-4004.xlsx" % short)
    if os.path.exists(p):
        files.append(("分项报价表.xlsx", read_xlsx(p)))
    return files


def find_quote(pack, field):
    """按正则优先级定位原句，返回 {source, loc, quote} 或 None（找不到就如实返回 None）。"""
    for pat in FIELD_PATTERNS.get(field) or []:
        rx = re.compile(pat)
        for src, lines in pack:
            for loc, text in lines:
                m = rx.search(text)
                if m:
                    q = text if len(text) <= 220 else text[:220] + "…"
                    return {"source": src, "loc": loc, "quote": q,
                            "match": m.group(0)[:160]}
    return None


def parse_tender(f3):
    """从 F3 证据里取出本次判定实际使用的基准侧阈值，不另造数。"""
    tf = ((f3.get("meta") or {}).get("tender_extract") or {}).get("fields") or {}

    def vt(k):
        return (tf.get(k) or {}).get("value_text")

    caps = {}
    for part in re.split(r"[、,]", vt("tender.price_cap") or ""):
        m = re.match(r"\s*(\d{8,})\s*[:：]\s*([\d.]+)", part)
        if m:
            caps[m.group(1)] = int(round(float(m.group(2)) * 10000))
    validity = re.search(r"(\d+)", vt("tender.required_validity_days") or "")
    mdel = re.search(r"\d{4}-\d{2}-\d{2}", vt("tender.required_delivery_date") or "")
    return {
        "caps": caps,
        "validity": int(validity.group(1)) if validity else None,
        "delivery": mdel.group(0) if mdel else None,
        "bond": vt("tender.bond_required"),
        "source": "国网Demo_F3_46条规则端到端_真跑证据_V2.json · meta.tender_extract",
    }


def main():
    f3 = json.load(io.open(F3, encoding="utf-8"))
    f2 = json.load(io.open(F2, encoding="utf-8"))
    tender = parse_tender(f3)

    live_items, live_fields = {}, {}
    if os.path.exists(LIVE):
        lv = json.load(io.open(LIVE, encoding="utf-8"))
        for b in lv.get("bidders", []):
            live_fields[b["code"]] = {f["field"]: f for f in b.get("fields", [])}
            for f in b.get("fields", []):
                if f.get("field") == "bid.price_items":
                    live_items[b["code"]] = f.get("items") or []

    ext = {b["code"]: b for b in f2["bidders"]}
    legal_names = []
    for b in f2["bidders"]:
        for f in b.get("fields", []):
            if f["field"] == "bid.legal_rep_name" and f.get("got"):
                legal_names.append(str(f["got"]).strip())
    rows = []
    for m in f3["matrix"]:
        code = m["code"]
        short = code
        pack = load_pack(short)
        b = ext.get(code) or {}
        # 字段值以 F3 那次现场抽取为准（与判定同源），F2 只作兜底。
        # 两批数据混着用会出现「页面显示字段有值、判定却说缺字段」的自相矛盾。
        fmap = {}
        for f in b.get("fields", []):
            fname = f["field"].split("(")[0].strip()
            fmap[fname] = f
        for fname, f in (live_fields.get(code) or {}).items():
            fmap[fname] = {"field": fname, "got": f.get("value_text"),
                           "value_num": f.get("value_num"),
                           "applicable": f.get("applicable"),
                           "verified": f.get("verified"),
                           "method": f.get("method"),
                           "source": f.get("source"),
                           "items": f.get("items")}

        cells = {}
        for rec in m["decided"]:
            r = rec["row"]
            if r not in [c[0] for c in COLS]:
                continue
            dep = next(c[3] for c in COLS if c[0] == r)
            fields = []
            for fname in dep:
                f = fmap.get(fname)
                if not f:
                    continue
                item = {
                    "field": fname,
                    "label": FIELD_LABEL.get(fname, fname),
                    "got": f.get("got"),
                    "num": f.get("value_num"),
                    "applicable": f.get("applicable"),
                    "verified": f.get("verified"),
                    "method": f.get("method"),
                    "source_doc": f.get("source"),
                }
                q = find_quote(pack, fname)
                if q:
                    item.update(q)
                fields.append(item)

            cells[str(r)] = {
                "state": rec["state"],
                "reason": rec.get("reason"),
                "calc": mk_calc(r, rec["state"], fmap, tender, legal_names,
                                 rec.get("item_check"), live_items.get(code)),
                "evidence": rec.get("evidence"),
                "basis": (rec.get("item_check") or {}).get("basis") if rec.get("item_check") else None,
                "items": (rec.get("item_check") or {}).get("items") if rec.get("item_check") else None,
                "over": (rec.get("item_check") or {}).get("over") if rec.get("item_check") else None,
                "fields": fields,
            }

        rows.append({
            "code": code,
            "short": short,
            "bidder": m["bidder"],
            "expect": m["expect"],
            "shouldFail": m.get("should_fail"),
            "shouldFailRow": m.get("should_fail_row"),
            "fail": m["fail_count"],
            "kb": b.get("kb"),
            "runId": b.get("run_id"),
            "cells": cells,
        })

    blocked = f3.get("blocked_fields") or []
    if isinstance(blocked, dict):
        blocked = [{"field": k, "rules": v} for k, v in blocked.items()]

    data = {
        "meta": {
            "section": "152507-1102002-4004",
            "fnVersion": 27,
            "extractEvidence": os.path.basename(F2),
            "judgeEvidence": os.path.basename(F3),
            "rulesTotal": f3["coverage"]["rules_total"],
            "machineRules": f3["coverage"]["machine_rules"],
            "machineRunnable": f3["coverage"]["machine_runnable"],
            "machineBlocked": f3["coverage"]["machine_blocked"],
            "decidedOnPage": f3["coverage"]["decided_on_page"],
            "humanPathRules": f3["coverage"]["human_path_rules"],
            "expectedFailHit": f3["coverage"]["expected_fail_hit"],
            "generated": "2026-11-14T21:50+08:00",
            "nature": "六份投标件均为按真实招标文件条款构造的合成演示数据；条款、格式、校验位、限价对应真文件，企业主体与报价为构造。",
        },
        "cols": [{"row": c[0], "label": c[1], "rule": c[2]} for c in COLS],
        "rows": rows,
        "blocked": blocked,
    }
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=1))

    # 自检：72？不，48 格
    n = sum(len(r["cells"]) for r in rows)
    nq = sum(1 for r in rows for c in r["cells"].values()
             for f in (c["fields"] or []) if f.get("quote"))
    print("写出", OUT)
    print("家数", len(rows), "| 格数", n, "| 带原文引用的字段条目", nq)
    for r in rows:
        st = {k: v["state"][:4] for k, v in r["cells"].items()}
        print("  %-6s fail=%d %s" % (r["short"], r["fail"], st))


if __name__ == "__main__":
    main()
