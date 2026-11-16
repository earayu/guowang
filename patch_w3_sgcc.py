# -*- coding: utf-8 -*-
"""把评标工作台换成国网视觉（VI 主色 PANTONE 3292C 深绿 + 3278C 亮绿 + 186C 国网红）。

只动视觉层与顶栏结构，不碰任何数据、判定逻辑、实时判定补丁。
幂等：可重复执行，每次按当前 HTML 重打，不会叠加。

跑法：python patch_w3_sgcc.py
"""
import io
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "国网物资部_评标辅助工作台_W3.html")

MARK_SKIN = "sgcc-skin"

# ---------------------------------------------------------------- 顶栏
TOP_NEW = '''  <div class="top">
    <div class="sg-brand">
      <svg class="sg-mark" viewBox="0 0 28 28" aria-hidden="true">
        <circle cx="14" cy="14" r="13.2" fill="#fff"/>
        <g fill="none" stroke="#00524B" stroke-width="1.85" stroke-linecap="round">
          <path d="M1.1 16.8c4.6-2.9 9.2-1.4 12.9 1.5 3.7 2.9 8.3 4.4 12.9 1.5"/>
          <path d="M10.2 23.4c-.7-3.7 1.3-6.9 4.2-9.5 2.9-2.6 4.9-5.8 4.2-9.5"/>
        </g>
      </svg>
      <span class="sg-name"><b>国家电网</b><i>STATE GRID</i></span>
    </div>
    <span class="sg-vr"></span>
    <div class="sg-sys">物资采购评标辅助工作台</div>
    <div class="batch">
      <span class="bl">采购项目</span>
      <select class="sel" id="batchSel">
        <option>1525K1 · 2025年物资类用户受托工程框架协议 · 4 标包</option>
        <option>152507 · 2025年新增第一次物资公开招标 · 14 标包</option>
      </select>
      <span class="projnote">两笔独立采购 · 各自一套评审基准</span>
    </div>
    <div class="right">
      <span class="sg-dotline"><i></i>文档库 155 份 · 解析/索引全绿</span>
      <span class="sg-user"><i class="sg-ava">评</i>评标专家</span>
      <span class="pill-gov">辅助工具 · 不作判定</span>
    </div>
  </div>

  <div class="crumb">
    <span>首页</span><i>&#8250;</i><span>物资采购管理</span><i>&#8250;</i><span>评标管理</span><i>&#8250;</i><b class="cr">评标辅助工作台</b>
    <span class="csp"></span>
    <span class="corg">国网湖北省电力有限公司 · 物资部</span>
    <i>&#183;</i><span>采购批次 1525K1</span>
    <i>&#183;</i><span>演示数据 2026-11-14</span>
  </div>
'''

ROOT_NEW = ''':root{
  /* 国网 VI 标准色：主色 PANTONE 3292C 深绿；辅助 3278C 亮绿、186C 国网红 */
  --ink:#16241F; --ink2:#4A5A54; --ink3:#7E8D87;
  --line:#DCE5E1; --line2:#EDF2F0;
  --bg:#F1F5F3; --bg2:#F4F8F6; --card:#FFFFFF;
  --brand:#00524B; --brand2:#00965E; --brandsoft:#E8F2EF;
  --red:#C8102E; --redsoft:#FDEEF0;
  --amber:#B45309; --ambersoft:#FFF6E6;
  --green:#0B6B45; --greensoft:#E7F5EE;
  --radius:2px;
}'''

SKIN_CSS = '''
/* ======================= 国网视觉层 =======================
   主色 PANTONE 3292C 深绿 #00524B / 辅助 3278C 亮绿 #00965E
   警示 PANTONE 186C 国网红 #C8102E
   形制取国网业务系统通行做法：直角卡片、细描边、左侧绿条导航、
   面包屑、表头浅绿灰、状态标签方角描边、平铺无重阴影。
   ======================================================== */
body{font-family:-apple-system,BlinkMacSystemFont,"Microsoft YaHei","PingFang SC","Hiragino Sans GB",sans-serif;
  letter-spacing:.1px}

/* 骨架：56 顶栏 + 30 面包屑 */
.shell{grid-template-rows:56px 30px 1fr}

/* 顶栏 */
.top{height:56px;gap:14px;padding:0 18px;
  background:linear-gradient(180deg,#00594F 0%,#00524B 100%);
  border-bottom:2px solid #00965E}
.sg-brand{display:flex;align-items:center;gap:8px;flex:0 0 auto}
.sg-brand .sg-mark{width:26px;height:26px;flex:0 0 26px;display:block}
.sg-name{display:flex;flex-direction:column;line-height:1}
.sg-name b{font-size:14px;font-weight:600;letter-spacing:1.6px;color:#fff}
.sg-name i{font-style:normal;font-size:7px;letter-spacing:.85px;color:rgba(255,255,255,.6);margin-top:3px}
.sg-vr{width:1px;height:24px;background:rgba(255,255,255,.24);flex:0 0 1px}
.sg-sys{font-size:14.5px;font-weight:500;color:#fff;letter-spacing:.5px;white-space:nowrap}
.top .batch{gap:7px;font-size:12px;color:rgba(255,255,255,.82);margin-left:8px;min-width:0}
.top .batch .bl{color:rgba(255,255,255,.58);white-space:nowrap}
.top .sel{background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.26);border-radius:2px;
  padding:3px 8px;max-width:340px;text-overflow:ellipsis}
.top .sel:hover{background:rgba(255,255,255,.18)}
.top .projnote{color:rgba(255,255,255,.52)}
.top .right{gap:12px;font-size:12px;color:rgba(255,255,255,.8)}
.sg-dotline{display:flex;align-items:center;white-space:nowrap}
.sg-dotline i{width:6px;height:6px;border-radius:50%;background:#5BE49B;margin-right:6px;
  box-shadow:0 0 0 3px rgba(91,228,155,.18)}
.sg-user{padding-left:12px;border-left:1px solid rgba(255,255,255,.22);color:#fff;
  white-space:nowrap;display:flex;align-items:center;gap:6px}
.sg-user .sg-ava{display:inline-flex;align-items:center;justify-content:center;
  width:19px;height:19px;border-radius:50%;background:rgba(255,255,255,.16);
  border:1px solid rgba(255,255,255,.34);font-size:10px;font-style:normal;color:#fff}
.top .pill-gov{border-radius:2px;color:#FFE7B8;border:1px solid rgba(255,231,184,.4);
  background:rgba(255,231,184,.09);padding:1px 8px}

/* 面包屑 */
.crumb{grid-row:2;grid-column:1/-1;display:flex;align-items:center;gap:7px;
  padding:0 18px;background:#fff;border-bottom:1px solid var(--line);
  font-size:11.5px;color:var(--ink3);white-space:nowrap;overflow:hidden}
.crumb i{font-style:normal;color:#A8B6B1;font-size:12px;line-height:1}
.crumb b{font-weight:600;color:var(--ink);display:flex;align-items:center}
.crumb b.cr{color:#00524B}
.crumb b.cr::before{content:"";width:3px;height:9px;background:#00965E;margin-right:5px}
.crumb .csp{flex:1}
.crumb .corg{color:var(--ink2)}

/* 侧导航 */
.nav{padding:10px 0 18px}
.nav .grp{font-size:11px;color:#8A9993;padding:12px 18px 5px;letter-spacing:1px;font-weight:500}
.nav .grp::after{content:"";display:block;width:14px;height:2px;background:#00965E;margin-top:5px;opacity:.55}
.nav a{padding:8px 18px;border-left:3px solid transparent;font-size:13px;color:var(--ink2)}
.nav a:hover{background:#F4F8F6;color:#00524B}
.nav a.on{background:#E8F2EF;color:#00524B;border-left-color:#00965E;font-weight:600}
.nav a.on .ic{opacity:1}
.nav .cnt{background:#EFF3F1;color:#7E8D87;border-radius:2px;padding:0 5px}
.nav a.on .cnt{background:#D3E6DF;color:#00524B;font-weight:600}

/* 内容区 */
.main{padding:18px 24px 60px}
.h1{position:relative;padding-left:10px;margin-left:-10px;font-size:18px;font-weight:600;
  color:var(--ink);letter-spacing:.3px;margin-bottom:4px;line-height:1.45}
.h1::before{content:"";position:absolute;left:0;top:4px;bottom:4px;width:3px;
  background:#00965E;border-radius:1px}
.sub{font-size:12.5px;color:var(--ink3);margin-bottom:18px;line-height:1.8}
.st{font-size:13.5px;font-weight:600;color:var(--ink);margin:22px 0 10px}
.st .ln{background:var(--line)}

/* 卡片 */
.card{border:1px solid var(--line);border-radius:2px;padding:14px 16px;background:var(--card)}
.kpi .lab{font-size:12px;color:var(--ink3);display:flex;align-items:center}
.kpi .lab::before{content:"";width:3px;height:10px;background:#00965E;margin-right:6px;opacity:.8}
.kpi .val{font-size:26px;font-weight:600;color:#00524B;letter-spacing:-.4px;line-height:1.3}
.kpi .val small{font-size:12.5px;font-weight:400;color:var(--ink3)}
.kpi .foot{font-size:11.5px;color:var(--ink3);line-height:1.7}
.seg .sv{color:#00524B;font-weight:600}
.seg.hollow .sv{color:var(--ink3)}

/* 表格 */
table{border:1px solid var(--line);border-radius:2px}
th{background:#F3F7F5;color:#55665F;font-weight:600;font-size:11.5px;
  border-bottom:1px solid var(--line);letter-spacing:.2px;padding:9px 12px}
td{border-bottom:1px solid var(--line2);color:var(--ink2);padding:10px 12px}
tbody tr:hover{background:#FAFCFB}
.ck:hover td{background:#F5FAF8}
.ck td:last-child{color:#00965E;font-weight:500}
.dgrid .h{background:#F3F7F5;color:#55665F;font-weight:500}

/* 标签：方角细描边，国网业务系统通行样式 */
.tag{border-radius:2px;border:1px solid transparent;padding:0 6px;line-height:1.65;
  font-size:11px;font-weight:500;letter-spacing:.1px}
.t-red{background:#FDEEF0;color:#C8102E;border-color:#F3C3CA}
.t-amb{background:#FFF6E6;color:#B45309;border-color:#F0D6A8}
.t-grn{background:#E7F5EE;color:#0B6B45;border-color:#B7DCC8}
.t-blu{background:#E8F2EF;color:#00524B;border-color:#BFD9D5}
.t-gry{background:#F3F6F4;color:#64746F;border-color:#DCE4E1}

/* 证据等级 */
.ev{border-radius:2px;border-color:var(--line);color:#7A8A84;padding:0 5px;line-height:16px}
.ev.t i{background:#0B6B45}
.ev.b i{background:#00965E}
.ev.a i{background:#B45309}
.ev.h i{background:#A9B5B0}

/* 版本对比 */
.vcard{border-radius:2px}
.vs .mid{color:#9AA8A2}

/* 页内 tab */
.tabs{border-bottom:1px solid var(--line)}
.tabs button.on{color:#00524B;border-bottom-color:#00965E;font-weight:600}

/* 抽屉 */
.drawer{top:86px;width:432px;border-left:1px solid var(--line);
  box-shadow:-2px 0 14px rgba(0,50,45,.06)}
.drawer .dh{background:#F4F8F6;border-bottom:1px solid var(--line);padding:12px 16px}
.drawer .dh .t{position:relative;padding-left:10px;font-size:13px;font-weight:600;color:var(--ink)}
.drawer .dh .t::before{content:"";position:absolute;left:0;top:2px;bottom:2px;width:3px;background:#00965E}
.drawer .dh .x{color:#7E8D87}
.drawer .dh .x:hover{color:#00524B}
.quote{background:#F7FAF9;border-left:3px solid #00965E;border-radius:0 2px 2px 0}

/* 按钮 */
.btn{border-radius:2px;border-color:var(--line);color:var(--ink2);padding:6px 13px}
.btn:hover{border-color:#9CC8BF;color:#00524B}
.btn.pri{background:#00524B;border-color:#00524B;color:#fff;font-weight:500}
.btn.pri:hover{background:#00625A;border-color:#00625A;color:#fff}
.sample span{border-radius:2px}
.sample span:hover{border-color:#9CC8BF;color:#00524B}
.askbox{border-radius:2px}
.ans{border-radius:2px}
.cite{border-radius:2px}
.cite b{color:#00524B}
.cite:hover{border-color:#9CC8BF;color:#00524B}

/* 生命周期 */
.lchip{border-radius:2px}
.lchip:hover{border-color:#00965E;background:#F2F8F5}
.lchip.on{border-color:#00965E;background:#E8F2EF;box-shadow:inset 2px 0 0 #00965E}
.lchip.on span{color:#00524B;font-weight:500}
.lph{border-bottom:1px dashed #D7E2DE;color:#8A9993}
.lbox{border-radius:2px}
.lgate{background:#EAF4F1;border-color:#BFD9D5;color:#0B4A44;border-radius:2px}
.lnote{border-radius:2px}
.heat .hcell{border-radius:1px}
.bar-h{border-radius:0}
.bar-h i{background:#00965E;border-radius:0}
.stage .s.done{color:#4A5A54}
.stage .s.done::after{background:#00965E;border-color:#00965E}
.stage .s.now{color:#00524B;font-weight:600}
.stage .s.now::after{background:#00524B;border-color:#00524B}
.note{border-radius:2px;background:#FAFCFB}
.block-warn{border-radius:2px;border-color:#F0D6A8;border-left:3px solid #B45309}
.comp{border-radius:2px;border-color:#F0D6A8;background:#FFFCF4}
.hl{background:#FFF3CD;color:#7A4F00}
.bidsrc{border-radius:2px}

/* 滚动条：细、浅，不抢视觉 */
*::-webkit-scrollbar{width:9px;height:9px}
*::-webkit-scrollbar-track{background:#F4F7F5}
*::-webkit-scrollbar-thumb{background:#C9D6D1;border-radius:0}
*::-webkit-scrollbar-thumb:hover{background:#AEBEB8}

/* 键盘可达性 */
a:focus-visible,button:focus-visible,select:focus-visible,
[data-c]:focus-visible{outline:2px solid #00965E;outline-offset:1px}
'''

ROOT_RE = re.compile(r":root\s*\{.*?\n\}", re.S)
TOP_RE = re.compile(r"  <div class=\"top\">.*?\n  </div>\n\n  <nav class=\"nav\">", re.S)
SKIN_RE = re.compile(r"<style id=\"" + MARK_SKIN + r"\">.*?</style>\n", re.S)

# 旧版蓝色系的硬编码值（内联 style 里改不动的那种），统一换到国网色系。
# 只作用于皮肤层之前的内容，避免动到本脚本自己写的样式。
COLOR_FIX = [
    ("#CFE0F5", "#BFD9D5"),   # 浅蓝描边 → 国网浅绿描边
    ("#FBFDFF", "#F5FAF8"),   # 卡片渐变起色
    ("#1D4A7A", "#0B4A44"),   # 深蓝字 → 深墨绿
    ("#B9CDE4", "#9CC8BF"),   # hover 描边
    ("#C7CFDA", "#9CC8BF"),
    ("#D8E5F5", "#D3E6DF"),   # 导航计数底
    ("#0A4478", "#00625A"),   # 主按钮 hover
    ("#F7FAFD", "#F5FAF8"),   # 行 hover
    ("#FCFDFE", "#FAFCFB"),
    ("#F6F7F9", "#F1F5F3"),   # 旧页面底色兜底
    ("#F6F8FB", "#F4F8F6"),   # 旧浅蓝块底（实时判定区）
    ("#FEF3F2", "#FDEEF0"),   # 旧判否红底
    ("#FFFAEB", "#FFF6E6"),   # 旧提示黄底
    ("#F2F4F7", "#F3F6F4"),   # 旧灰标签底
]


def main():
    if not os.path.exists(TARGET):
        raise SystemExit("找不到页面：%s" % TARGET)
    src = io.open(TARGET, encoding="utf-8").read()
    before = len(src)

    # 1) 色板（每次都按最新重写，保证新增变量能生效）
    src, n = ROOT_RE.subn(lambda m: ROOT_NEW, src, count=1)
    if n != 1:
        raise SystemExit(":root 块没匹配上，页面结构变了，先别打补丁")
    print("色板：已换成国网 VI")

    # 2) 顶栏 + 面包屑（每次都重打：旧顶栏与「顶栏+面包屑」两种形态都能匹配，
    #    这样改脚本里的文案/结构后重跑即可生效，不需要手工回滚）
    src, n = TOP_RE.subn(lambda m: TOP_NEW + "\n  <nav class=\"nav\">", src, count=1)
    if n != 1:
        raise SystemExit("顶栏块没匹配上（<div class=\"top\">…</div> 到 <nav class=\"nav\">）")
    print("顶栏：已换国网标识 + 面包屑")

    # 3) 旧蓝色硬编码清理（先摘旧皮肤，免得改到皮肤自己）
    src = SKIN_RE.sub("", src)
    hits = 0
    for old, new in COLOR_FIX:
        if old in src:
            hits += src.count(old)
            src = src.replace(old, new)
    print("旧蓝色值：替换 %d 处" % hits)

    # 4) 视觉覆盖层
    skin = '<style id="%s">%s</style>\n' % (MARK_SKIN, SKIN_CSS)
    if "</head>" not in src:
        raise SystemExit("找不到 </head>")
    src = src.replace("</head>", skin + "</head>", 1)
    print("视觉层：已注入（%d 行）" % SKIN_CSS.count("\n"))

    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
    print("写回：%s  %d -> %d 字节" % (os.path.basename(TARGET), before, len(src)))


if __name__ == "__main__":
    main()
