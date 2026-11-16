# -*- coding: utf-8 -*-
"""回读 bid_packs_v2/ 的 24 个文件，核对「纸面上到底写了什么」。

不采信生成脚本的输入参数，只认文件里真实存在的文字与单元格：
  1. 三处金额是否一致（分项报价表 xlsx / 投标函 / 开标一览表）
  2. 行级含税合价是否超该行含税限价
  3. 签章主体与投标人是否为同一人
  4. 投标有效期、税率、交货承诺是否就是剧本设定的值
  5. 各册章节是否齐全

产出 _verify_report.json，并把逐家结论打到控制台。
"""
import json
import os
import re

from docx import Document
from openpyxl import load_workbook

OUT = "bid_packs_v2"
SECTION = "152507-1102002-4004"
CAPS = {"100034915900360": 10000000, "100035912200010": 4533100,
        "100035912500010": 340000, "100035917800010": 1821200}
CAP_SUM = sum(CAPS.values())

NUM = r"([0-9][0-9,]*\.?[0-9]*)"

# ---- 证件校验位（与生成器同一套国标算法，回读时独立复算）
_CH = "0123456789ABCDEFGHJKLMNPQRTUWXY"
_CW = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]


def uscc_ok(s):
    if len(s) != 18 or any(c not in _CH for c in s):
        return False
    t = sum(_CH.index(s[i]) * _CW[i] for i in range(17))
    c = 31 - t % 31
    return _CH[0 if c == 31 else c] == s[17]


_IW = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]


def id_ok(s):
    return (len(s) == 18 and s[:17].isdigit()
            and s[17] == "10X98765432"[sum(int(s[i]) * _IW[i] for i in range(17)) % 11])


def f(v):
    return float(str(v).replace(",", "")) if v not in (None, "", "—") else None


def docx_text(path):
    d = Document(path)
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:
        for r in t.rows:
            for c in r.cells:
                parts.append(c.text)
    return "\n".join(parts), d


def check_one(code, short, name, gt):
    res = {"code": code, "short": short, "bidder": name, "checks": [], "values": {}}

    def add(item, ok, detail):
        res["checks"].append({"item": item, "pass": bool(ok), "detail": detail})

    px = os.path.join(OUT, "分项报价表_%s_%s.xlsx" % (short, SECTION))
    pd = os.path.join(OUT, "投标文件_%s_%s_价格文件.docx" % (short, SECTION))
    bd = os.path.join(OUT, "投标文件_%s_%s_商务文件.docx" % (short, SECTION))
    td = os.path.join(OUT, "投标文件_%s_%s_技术文件.docx" % (short, SECTION))

    exist = all(os.path.exists(p) for p in (px, pd, bd, td))
    add("四份文件齐全", exist, "价格/商务/技术/xlsx")
    if not exist:
        return res

    # ---- xlsx
    wb = load_workbook(px, data_only=True)
    ws = wb["分项报价表"]
    rows, tot = [], None
    for r in ws.iter_rows(min_row=5, values_only=True):
        if r[0] == "合计":
            tot = r
            break
        if r[1] and str(r[1]).startswith("100"):
            rows.append({"no": str(r[1]), "exc_amt": f(r[7]), "rate": str(r[8]),
                         "inc_amt": f(r[10]), "inc_unit": f(r[9])})
    xlsx_inc = tot[10] if tot else None
    xlsx_exc = tot[7] if tot else None
    res["values"]["xlsx_inc_total"] = f(xlsx_inc)
    res["values"]["xlsx_exc_total"] = f(xlsx_exc)
    res["values"]["xlsx_rows"] = len(rows)
    add("xlsx 行项目数=4", len(rows) == 4, "实际 %d 行" % len(rows))

    # 行级算术自洽：未含税 = 含税/(1+税率)
    rate = float(rows[0]["rate"].replace("%", "")) / 100.0 if rows else 0
    res["values"]["tax_rate"] = rate
    drift = []
    for r in rows:
        expect = round(r["inc_amt"] / (1 + rate), 2)
        if abs(expect - r["exc_amt"]) > 0.02:
            drift.append((r["no"], expect, r["exc_amt"]))
    add("行级 未含税=含税÷(1+税率)", not drift, "偏差行 %s" % (drift or "无"))

    # 行级超限价
    over = [r["no"] for r in rows if r["inc_amt"] > CAPS[r["no"]]]
    res["values"]["over_cap_items"] = over
    res["values"]["total_over_cap"] = (res["values"]["xlsx_inc_total"] or 0) > CAP_SUM

    # ---- 价格文件
    ptext, pdoc = docx_text(pd)
    m = re.search(r"（¥" + NUM + r"）", ptext)
    letter_inc = f(m.group(1)) if m else None
    m2 = re.search(r"未含税价人民币 " + NUM + r" 元", ptext)
    letter_exc = f(m2.group(1)) if m2 else None
    m3 = re.search(r"合计人民币（小写）：" + NUM + r" 元", ptext)
    open_inc = f(m3.group(1)) if m3 else None
    res["values"]["letter_inc"] = letter_inc
    res["values"]["letter_exc"] = letter_exc
    res["values"]["open_table_inc"] = open_inc

    add("投标函含税总价 = xlsx 合计", letter_inc == res["values"]["xlsx_inc_total"],
        "投标函 %s / xlsx %s" % (letter_inc, res["values"]["xlsx_inc_total"]))
    add("开标一览表 = xlsx 合计", open_inc == res["values"]["xlsx_inc_total"],
        "开标一览表 %s / xlsx %s" % (open_inc, res["values"]["xlsx_inc_total"]))
    add("投标函未含税 = xlsx 合计", letter_exc == res["values"]["xlsx_exc_total"],
        "投标函 %s / xlsx %s" % (letter_exc, res["values"]["xlsx_exc_total"]))

    # 大写金额回填：能与数字对上（粗校验：长度≥10 且含"元"）
    mu = re.search(r"人民币 ([零壹贰叁肆伍陆柒捌玖拾佰仟万亿元角分整]{6,})", ptext)
    add("含税总价有大写金额", bool(mu), (mu.group(1) if mu else "未找到"))

    # ---- 商务文件
    btext, bdoc = docx_text(bd)
    m = re.search(r"电子签章验证：(.*)", btext)
    seal_line = m.group(1).strip() if m else ""
    m = re.search(r"签章已加盖，签章主体为「(.+?)」，与投标人「(.+?)」不一致", btext)
    if m:
        seal_name, seal_owner = m.group(1), m.group(2)
    else:
        seal_name, seal_owner = name, name
    res["values"]["seal_name"] = seal_name
    res["values"]["seal_matches_bidder"] = (seal_name == seal_owner)
    # 本项不是「必须一致」，而是「文件是否如实呈现剧本设定」——
    # 一致与否由 ground truth 决定，纸面与真值对得上才算过。
    add("签章主体与剧本一致",
        (seal_name == seal_owner) == gt["bid.seal_owner_matches_bidder"],
        "签章「%s」 vs 投标人「%s」（剧本期望%s）"
        % (seal_name, seal_owner, "一致" if gt["bid.seal_owner_matches_bidder"] else "不一致"))

    # 商务章节数
    heads = re.findall(r"^(一|二|三|四|五|六|七|八|九|十|十一|十二|十三|十四)、", btext, re.M)
    add("商务册章节=14", len(set(heads)) >= 14, "检出 %d 个章节标题" % len(set(heads)))

    # ---- 技术文件
    ttext, tdoc = docx_text(td)
    for k, label in (("技术偏差表", "技术偏差表"), ("技术特性参数响应表", "技术特性参数响应表"),
                     ("货物组件材料配置表", "货物组件材料配置表"),
                     ("施工组织与进度计划", "施工组织与进度计划"),
                     ("质量保证与风险管理", "质量保证与风险管理")):
        add("技术册含「%s」" % label, k in ttext, "命中" if k in ttext else "缺失")

    # 技术参数响应表：带 * 的必满足项必须逐条覆盖（规范书 T01~T06 共 21 项）
    tptab = None
    for t in tdoc.tables:
        if "招标人要求值" in " ".join(c.text for c in t.rows[0].cells):
            tptab = t
            break
    nrow = len(tptab.rows) - 1 if tptab else 0
    star = sum(1 for r in (tptab.rows[1:] if tptab else [])
               if "*" in r.cells[1].text)
    res["values"]["tech_param_rows"] = nrow
    res["values"]["star_param_hits"] = star
    add("技术参数表覆盖全部 21 项带*必满足参数", star >= 21, "带 * 项 %d / 总行 %d" % (star, nrow))
    add("技术响应表有「偏差」列且逐条填无偏差",
        bool(tptab) and "偏差" in " ".join(c.text for c in tptab.rows[0].cells)
        and all("无偏差" in r.cells[4].text for r in tptab.rows[1:]),
        "%d 行逐条对照" % nrow)

    # 交货承诺
    dl = "2026-07-15" if "2026-07-15" in ttext else "2026-04-20"
    res["values"]["committed_delivery_pkg1"] = dl
    add("包1 交货承诺已在文中明示", dl in ttext and "2026-04-20" in ttext,
        "承诺 %s，要求 2026-04-20" % dl)

    # 有效期
    mv = re.search(r"自投标截止日起 (\d+) 日历天", ptext)
    validity = int(mv.group(1)) if mv else None
    res["values"]["validity_days"] = validity
    add("投标有效期与剧本一致", validity == gt["bid.validity_days"],
        "实际 %s 日（剧本 %s 日，要求 90 日）" % (validity, gt["bid.validity_days"]))

    # 税率
    mt = re.search(r"增值税税率 (\d+)%", ptext)
    tax = int(mt.group(1)) if mt else None
    res["values"]["tax_rate_text"] = tax
    add("税率与剧本一致", (tax or 0) / 100.0 == gt["bid.tax_rate"],
        "实际 %s%%（剧本 %.0f%%，法定集合 13/9/6/3/1/0）"
        % (tax, gt["bid.tax_rate"] * 100))

    # ================= 真实性核验（第二版新增） =================
    # 1) 证件：号码位数与国标校验位必须算得过，评标时一验就露
    mus = re.search(r"\b(9[0-9A-HJ-NPQRTUWXY]{17})\b", btext + ptext)
    res["values"]["uscc"] = mus.group(1) if mus else None
    add("统一社会信用代码校验位合法", bool(mus) and uscc_ok(mus.group(1)),
        (mus.group(1) + " 校验通过") if mus and uscc_ok(mus.group(1))
        else ("%s 校验失败" % mus.group(1) if mus else "未找到 18 位代码"))

    ids = re.findall(r"公民身份号码：(\S{18})", btext)
    res["values"]["id_numbers"] = ids
    add("身份证 18 位且校验位合法", bool(ids) and all(id_ok(x) for x in ids),
        "、".join("%s(%s)" % (x, "通过" if id_ok(x) else "失败") for x in ids) or "未找到")

    # 2) 占位符残留：某某 / example.com / 虚构行政区，一眼假
    bad_ph = [w for w in ("某某", "example.com", "华中市", "高新技术产业园")
              if w in (btext + ptext + ttext)]
    add("无占位符残留", not bad_ph, "命中 %s" % (bad_ph or "无"))

    # 反污染：投标件内不得出现剧本/结论性词汇，否则抽取侧读两字就能猜结论（假绿）
    leak = [w for w in ("违规", "否决", "剧本", "对照组", "触发条款", "真值", "ground truth")
            if w in (btext + ptext + ttext)]
    res["values"]["leak_words"] = leak
    xtext = " ".join(str(v) for sh in wb.worksheets
                     for row in sh.iter_rows(values_only=True) for v in row if v is not None)
    leak += [w for w in ("违规", "否决", "剧本", "对照组", "触发条款", "真值")
             if w in xtext and w not in leak]
    add("投标件内无剧本/结论泄露（含 xlsx）", not leak, "命中 %s" % (leak or "无"))

    # 3) 财务表内部勾稽：负债总额 ÷ 资产总额 必须等于表列资产负债率
    ftab = None
    for t in bdoc.tables:
        if "资产负债率" in " ".join(c.text for c in t.rows[0].cells):
            ftab = t
            break
    badf, revs = [], []
    if ftab:
        for r in ftab.rows[1:]:
            cs = [c.text.strip() for c in r.cells]
            if cs[0].startswith("三年"):
                continue
            asset, debt = f(cs[3]), f(cs[4])
            rate = float(cs[5].strip("%"))
            revs.append(f(cs[1]))
            if asset and abs(debt / asset * 100 - rate) > 0.15:
                badf.append("%s 实算 %.2f%% 表列 %.1f%%"
                            % (cs[0], debt / asset * 100, rate))
    add("财务表 负债÷资产=表列负债率", bool(ftab) and not badf,
        "；".join(badf) if badf else ("勾稽一致" if ftab else "未找到财务表"))
    add("营业收入三年递增", len(revs) == 3 and revs[0] > revs[1] > revs[2],
        " > ".join("%.0f" % v for v in revs))

    # 4) 报价合理性：真实投标一般落在限价 80%~100%，且报到百元位
    tot_inc = res["values"]["xlsx_inc_total"] or 0
    add("含税报价落在限价 80%~100%", CAP_SUM * 0.80 <= tot_inc <= CAP_SUM,
        "{:,.0f} 元 = 限价的 {:.1f}%".format(tot_inc, tot_inc / CAP_SUM * 100))
    odd = [r["no"] for r in rows if r["inc_unit"] % 100 != 0]
    add("行级报价报至百元位", not odd, "非整百行 %s" % (odd or "无"))

    return res


def main():
    truth = json.load(open(os.path.join(OUT, "_ground_truth_v3.json"), encoding="utf-8"))
    out = []
    print("=" * 100)
    print("%-4s %-24s %-14s %-14s %-6s %-5s %s"
          % ("简称", "投标人", "含税总额", "未含税总额", "税率", "有效期", "自检"))
    print("-" * 100)
    for b in truth["bidders"]:
        r = check_one(b["code"], b["short"], b["bidder_name"], b["ground_truth"])
        r["expect"] = b["expect"]
        r["defect_rule"] = b["defect_rule"]
        gt = b["ground_truth"]
        r["match_ground_truth"] = {
            "inc_total": r["values"].get("xlsx_inc_total") == gt["bid.price_total_inc_tax"],
            "exc_total": r["values"].get("xlsx_exc_total") == gt["bid.price_total_ex_tax"],
            "over_cap": r["values"].get("over_cap_items") == gt["bid.over_cap_items"],
            "seal": r["values"].get("seal_matches_bidder") == gt["bid.seal_owner_matches_bidder"],
            "validity": r["values"].get("validity_days") == gt["bid.validity_days"],
            "tax": (r["values"].get("tax_rate_text") or 0) / 100.0 == gt["bid.tax_rate"],
            "delivery": r["values"].get("committed_delivery_pkg1") ==
                        gt["bid.committed_delivery"]["100034915900360"],
        }
        passed = sum(1 for c in r["checks"] if c["pass"])
        r["passed"], r["total"] = passed, len(r["checks"])
        out.append(r)
        allmatch = all(r["match_ground_truth"].values())
        print("%-4s %-24s %-14s %-14s %-6s %-5s %d/%d %s"
              % (b["short"], b["bidder_name"],
                 "{:,.2f}".format(r["values"].get("xlsx_inc_total") or 0),
                 "{:,.2f}".format(r["values"].get("xlsx_exc_total") or 0),
                 "%s%%" % r["values"].get("tax_rate_text"),
                 "%s日" % r["values"].get("validity_days"),
                 passed, len(r["checks"]),
                 "真值一致" if allmatch else "★不一致"))

    print("-" * 100)
    tot_pass = sum(r["passed"] for r in out)
    tot_all = sum(r["total"] for r in out)
    bad = [r for r in out if not all(r["match_ground_truth"].values())]
    print("自检项合计：%d/%d 通过；与 ground truth 不一致的家数：%d" % (tot_pass, tot_all, len(bad)))

    # 跨家核验：同标包多家报同价，在真实开标里就是串标嫌疑
    import collections
    tots = [r["values"].get("xlsx_inc_total") or 0 for r in out]
    dup = [v for v, n in collections.Counter(tots).items() if n > 1]
    spread = (max(tots) - min(tots)) / max(tots) * 100
    print("跨家核验：报价互不相同 %s；最高/最低价差 %.1f%%（%s ~ %s）"
          % ("是" if not dup else "否（重复 %s）" % dup, spread,
             "{:,.0f}".format(min(tots)), "{:,.0f}".format(max(tots))))
    for r in bad:
        for k, v in r["match_ground_truth"].items():
            if not v:
                print("   ✗ %s 的 %s 与真值不一致" % (r["short"], k))

    # 剧本书面证据
    print("\n剧本是否真的落在纸上：")
    for r in out:
        ev = []
        if r["values"].get("over_cap_items"):
            ev.append("超限价行 %s" % "、".join(r["values"]["over_cap_items"]))
        if not r["values"].get("seal_matches_bidder"):
            ev.append("签章主体「%s」≠投标人" % r["values"]["seal_name"])
        if r["values"].get("validity_days") != 90:
            ev.append("有效期 %s 日" % r["values"]["validity_days"])
        if r["values"].get("tax_rate_text") not in (13, 9, 6, 3, 1, 0):
            ev.append("税率 %s%%" % r["values"]["tax_rate_text"])
        if r["values"].get("committed_delivery_pkg1") != "2026-04-20":
            ev.append("包1 承诺 %s" % r["values"]["committed_delivery_pkg1"])
        print("  %-4s %s" % (r["short"], "；".join(ev) if ev else "无缺陷（对照组）"))

    json.dump({"section": SECTION, "cap_sum": CAP_SUM, "bidders": out},
              open(os.path.join(OUT, "_verify_report.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("\n报告：%s/_verify_report.json" % OUT)


if __name__ == "__main__":
    main()
