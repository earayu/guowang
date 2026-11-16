# -*- coding: utf-8 -*-
"""把评审 P0/P1 改进幂等打进对客页面。

幂等：UX-UPGRADE 标记块先删后插；结构改动靠"已存在则跳过"判定。
不改任何判定数据、不改规则表、不改 BID_CASE / RULES 内容。
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "国网物资部_评标辅助工作台_W3.html")
CSS = os.path.join(HERE, "_ux", "ux.css")
JS = os.path.join(HERE, "_ux", "ux.js")
BAK = os.path.join(HERE, "_bak_w3_before_ux.html")

css = open(CSS, encoding="utf-8").read()
js = open(JS, encoding="utf-8").read()

html = open(TARGET, encoding="utf-8").read()
orig_len = len(html)

# 只在第一次打补丁时备份；重复执行不覆盖备份，保证可回退到最早版本
if not os.path.exists(BAK):
    shutil.copy2(TARGET, BAK)
    print("[bak] 已备份 ->", os.path.basename(BAK))
else:
    print("[bak] 备份已存在，保持不动")

changes = []

# ---------- 1. 清掉旧的注入块 ----------
html = re.sub(r"\n<!-- UX-UPGRADE:CSS:BEGIN -->.*?<!-- UX-UPGRADE:CSS:END -->\n", "\n", html, flags=re.S)
html = re.sub(r"\n<!-- UX-UPGRADE:JS:BEGIN -->.*?<!-- UX-UPGRADE:JS:END -->\n", "\n", html, flags=re.S)

# ---------- 2. 注入 CSS ----------
if "</head>" not in html:
    sys.exit("找不到 </head>")
css_block = ("\n<!-- UX-UPGRADE:CSS:BEGIN -->\n<style id=\"ux-upgrade\">\n"
             + css + "\n</style>\n<!-- UX-UPGRADE:CSS:END -->\n")
html = html.replace("</head>", css_block + "</head>", 1)
changes.append("注入可用性样式层")

# ---------- 3. 跳转链接 + 主区可聚焦 ----------
if 'class="ux-skip"' not in html:
    if "<body>" not in html:
        sys.exit("找不到 <body>")
    html = html.replace(
        "<body>",
        "<body>\n<a class=\"ux-skip\" href=\"#mainRegion\">跳到主内容</a>", 1)
    changes.append("加跳转主内容链接")

if 'id="mainRegion"' not in html:
    html = html.replace('<div class="main">',
                        '<div class="main" id="mainRegion" tabindex="-1">', 1)
    changes.append("主区可聚焦")

# ---------- 4. 顶栏：身份 / 留痕 / 字号 ----------
if 'class="ux-topbar"' not in html:
    topbar = (
        '\n      <div class="ux-topbar">\n'
        '        <div class="ux-seg" role="group" aria-label="当前身份">\n'
        '          <button type="button" data-role="expert" class="on" title="评标专家：可看、可录结论">评标专家</button>\n'
        '          <button type="button" data-role="owner" title="招标人：可看全量、可导出，不录评审结论">招标人</button>\n'
        '          <button type="button" data-role="sup" title="监督：只看不改，报价摘要脱敏">监督</button>\n'
        '        </div>\n'
        '        <button class="ux-tool" type="button" id="uxAuditOpen">操作留痕</button>\n'
        '        <div class="ux-fs" role="group" aria-label="字号">\n'
        '          <button type="button" data-fs="sm" aria-label="小号字">A-</button>\n'
        '          <button type="button" data-fs="md" class="on" aria-label="默认字号">A</button>\n'
        '          <button type="button" data-fs="lg" aria-label="大号字">A+</button>\n'
        '        </div>\n'
        '      </div>'
    )
    m = re.search(r'<div class="right">', html)
    if not m:
        sys.exit("找不到顶栏 .right")
    html = html[:m.end()] + topbar + html[m.end():]
    changes.append("顶栏加身份切换/留痕/字号")

# ---------- 5. 抽屉无障碍属性 ----------
if 'id="drawer"' in html and 'aria-labelledby="dTitle"' not in html.split('id="dBody"')[0][-400:]:
    html = html.replace('<div class="drawer" id="drawer">',
                        '<div class="drawer" id="drawer" role="dialog" aria-labelledby="dTitle" aria-hidden="true">', 1)
    changes.append("抽屉补 role/aria")

# ---------- 6. 投标页自证文案折叠 ----------
if '<details class="fold"' not in html:
    pat = re.compile(r'<div class="block-warn">(.*?)</div>', re.S)
    m = pat.search(html)
    if not m:
        sys.exit("找不到 block-warn 段")
    inner = m.group(1).strip()
    folded = (
        '<details class="fold" id="uxBidWarn">\n'
        '        <summary>受审对象已入库：6 家 24 份受控合成投标包'
        '<span class="fx">基准 46 条 · 每家单库隔离 · 合成件不替代真实受审（点开看五点说明）</span></summary>\n'
        '        <div class="bw-body">' + inner + '</div>\n'
        '      </details>'
    )
    html = html[:m.start()] + folded + html[m.end():]
    changes.append("五点说明折叠为可展开块")

# ---------- 7. 投标页 KPI 改为本页结果指标 ----------
old_kpi = (
    '<div class="card kpi"><div class="lab">审批基准条款</div><div class="val num">46<small>条</small></div>'
    '<div class="foot">否决情形全部适用项 · 已就绪</div></div>\n'
    '        <div class="card kpi"><div class="lab">受审投标包</div><div class="val num">6<small>家</small></div>'
    '<div class="foot">24 份 · 1 家对照 + 5 家各带一处违规</div></div>\n'
    '        <div class="card kpi"><div class="lab">受审字段对位</div><div class="val num" style="color:var(--green)">66<small>/66</small></div>'
    '<div class="foot">6 家 × 11 字段 · 跨家零串值</div></div>\n'
    '        <div class="card kpi"><div class="lab">机器判定跑通</div><div class="val num">8<small>/25 条</small></div>'
    '<div class="foot">其余 17 条卡在待抽字段</div></div>'
)
new_kpi = (
    '<div class="card kpi"><div class="lab">受审投标包</div><div class="val num">6<small>家</small></div>'
    '<div class="foot">24 份 · 1 家对照 + 5 家各带一处违规</div></div>\n'
    '        <div class="card kpi"><div class="lab">已核格子</div><div class="val num">48<small>格</small></div>'
    '<div class="foot">6 家 × 8 条机器可判规则</div></div>\n'
    '        <div class="card kpi"><div class="lab">机器判否</div><div class="val num" style="color:var(--red)">5<small>处</small></div>'
    '<div class="foot">5 家各 1 处 · 格内附字段值与原文</div></div>\n'
    '        <div class="card kpi"><div class="lab">通过（未触发）</div><div class="val num" style="color:var(--green)">43<small>格</small></div>'
    '<div class="foot">含对照 1 家 8 格全通</div></div>'
)
if old_kpi in html:
    html = html.replace(old_kpi, new_kpi, 1)
    changes.append("投标页 KPI 改为结果指标（48 格 / 判否 5 / 通过 43）")
elif "已核格子" in html:
    print("[skip] KPI 已是新版")
else:
    print("[warn] KPI 原文未精确匹配，跳过")

# ---------- 8. 覆盖率表加"补齐后累计" ----------
old_th = '<tr><th style="width:300px">缺的字段</th><th style="width:70px">卡住条数</th><th>被卡的规则</th></tr>'
new_th = ('<tr><th style="width:290px">缺的字段</th><th style="width:76px">卡住条数</th>'
          '<th style="width:112px">补齐后机器可判</th><th>被卡的规则</th></tr>')
if old_th in html:
    html = html.replace(old_th, new_th, 1)
    pairs = [
        ('bid.price_total', '2', '10 / 25'),
        ('bid.qualification_fields', '2', '12 / 25'),
        ('bid.format_completeness', '1', '13 / 25'),
        ('bid.voucher_index_viewable', '1', '14 / 25'),
        ('bid.alternative_declared', '1', '15 / 25'),
    ]
    for field, n, cum in pairs:
        old_row = '<tr><td class="mono" style="font-size:11.5px">%s</td><td class="num">%s</td>' % (field, n)
        if old_row in html:
            new_row = ('<tr><td class="mono" style="font-size:11.5px">%s</td><td class="num">%s</td>'
                       '<td class="num" style="color:var(--brand)">%s</td>' % (field, n, cum))
            html = html.replace(old_row, new_row, 1)
    changes.append("覆盖率表加累计解锁列（10→15 / 25）")
elif "补齐后机器可判" in html:
    print("[skip] 覆盖率表已含累计列")

# ---------- 8.5 判定语义：把「判否（判定式成立）」这类自相矛盾的表述换成业务话 ----------
SEM = [
    ("RESPONDED:'未触发（判定式不成立或情形不适用）'", "RESPONDED:'通过（未命中本条否决情形）'"),
    ("NOT_RESPONDED:'判否（判定式成立）'", "NOT_RESPONDED:'判否（命中本条否决情形）'"),
    ("{t:'通过',   c:'t-grn', d:'判定式不成立，本条未触发'}", "{t:'通过',   c:'t-grn', d:'未命中本条否决情形'}"),
    ("{t:'判否',   c:'t-red', d:'判定式成立，候选否决项'}", "{t:'判否',   c:'t-red', d:'命中本条否决情形，候选否决项'}"),
]
sem_hit = 0
for old, new in SEM:
    if old in html:
        html = html.replace(old, new, 1)
        sem_hit += 1
if sem_hit:
    changes.append("判定结论文案业务化（%d 处）" % sem_hit)
else:
    print("[warn] 判定文案未匹配到，检查是否已改过")

# ---------- 9. 留痕模态 + 读屏公告 ----------
if 'id="uxAuditModal"' not in html:
    modal = (
        '\n<!-- UX-UPGRADE: modal -->\n'
        '<div class="ux-mask" id="uxAuditMask"></div>\n'
        '<div class="ux-modal" id="uxAuditModal" role="dialog" aria-modal="true" aria-labelledby="uxAuditTitle">\n'
        '  <div class="mh"><div class="t" id="uxAuditTitle">操作留痕</div><span class="sp"></span>\n'
        '    <button class="ux-btn" type="button" id="uxAuditExport">导出 CSV</button>\n'
        '    <button class="ux-btn" type="button" id="uxAuditClose">关闭</button>\n'
        '  </div>\n'
        '  <div class="mb" id="uxAuditBody"></div>\n'
        '  <div class="mf">本机浏览器记录，演示级；生产版须接服务端审计（操作人 / IP / 时间不可篡改）。</div>\n'
        '</div>\n'
        '<div id="uxLive" class="sr-only" aria-live="polite"></div>\n'
        '<div id="uxRoleNote" class="sr-only"></div>\n'
    )
    html = html.replace("</body>", modal + "</body>", 1)
    changes.append("加留痕面板与读屏公告")

# ---------- 9b. 注入法源数据（A1 溯源）----------
PROV_SRC = os.path.join(HERE, "国网Demo_规则法源溯源表_V1.json")
if os.path.exists(PROV_SRC):
    import json as _json
    _d = _json.load(open(PROV_SRC, encoding="utf-8"))
    slim = {}
    for r in _d["rules"]:
        p = r["provenance"]
        slim[r["rule_id"]] = {
            "row": r["row"],
            "cat": r["category"],
            "sub": r["subcategory"],
            "clause": p["clause"],
            "trow": p["table_row"],
            "para": p["para_index"],
            "text": p["text_in_tender"] or "",
            "cls": r["legal"]["class_cn"],
            "laws": [(i["law"] + (i["article"] or "") + (i["item"] or ""))
                     if i.get("article") else i["law"]
                     for i in r["legal"]["items"]],
        }
    prov_block = ('\n<script id="uxProvData" type="application/json">'
                  + _json.dumps(slim, ensure_ascii=False, separators=(",", ":"))
                  + "</script>\n")
    html = re.sub(r'\n<script id="uxProvData" type="application/json">.*?</script>\n', "\n", html, flags=re.S)
    html = html.replace("</body>", prov_block + "</body>", 1)
    changes.append("注入 46 条法源数据（%d 条）" % len(slim))

# ---------- 10. 注入 JS ----------
js_block = ("\n<!-- UX-UPGRADE:JS:BEGIN -->\n<script>\n"
            + js + "\n</script>\n<!-- UX-UPGRADE:JS:END -->\n")
html = html.replace("</body>", js_block + "</body>", 1)
changes.append("注入交互脚本")

open(TARGET, "w", encoding="utf-8", newline="\n").write(html)

print("\n=== 已应用 ===")
for c in changes:
    print(" -", c)
print("\n体积：%d -> %d 字节（+%d）" % (orig_len, len(html), len(html) - orig_len))
print("回退：cp _bak_w3_before_ux.html 国网物资部_评标辅助工作台_W3.html")
