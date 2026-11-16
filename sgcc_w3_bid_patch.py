# -*- coding: utf-8 -*-
"""把受审侧真跑结果接进 W3 工作台（v-bid 视图）。

改四处，每处都断言只命中一次，防止误替换：
  1. 顶部说明块：从「受审对象尚未入库」改为「已入库 5 份合成投标包 + 合成数据声明」
  2. 四张 KPI：投标文件 0 份 → 5 份，新增字段一致率与机器判定条数
  3. 新增「本次受审结果」矩阵：5 家 × 4 条机器可判规则，点格看逐物料对位
  4. 46 条台账的「投标响应」列：4 条已对位的规则不再写「待投标文件入库」

数据全部来自 国网Demo_F3 / F2 真跑证据，不手填任何结论。
"""
import io
import json
import re

HTML = "国网物资部_评标辅助工作台_W3.html"
F2 = "国网Demo_F2受审侧抽取_真跑证据_V1.json"
F3 = "国网Demo_F3_46条规则端到端_真跑证据_V1.json"

CASE_ROWS = [("4", "GW-HB-FJ-004", "签章"),
             ("10", "GW-HB-FJ-010", "限价"),
             ("11", "GW-HB-FJ-011", "报价算术"),
             ("13", "GW-HB-FJ-013", "保证金"),
             ("16", "GW-HB-FJ-016", "有效期"),
             ("17", "GW-HB-FJ-017", "税率"),
             ("39", "GW-HB-FJ-039", "法人不重")]

f2 = json.load(io.open(F2, encoding="utf-8"))
f3 = json.load(io.open(F3, encoding="utf-8"))
html = io.open(HTML, encoding="utf-8").read()

# ---------- 组数据 ----------
case = []
for m in f3["matrix"]:
    cells = {}
    for rid_row, rid, short in CASE_ROWS:
        d = next((x for x in m["decided"] if x["rule_id"] == rid), None)
        if d is None:
            continue
        cells[rid_row] = {
            "state": d["state"],
            "reason": d["reason"],
            "items": (d.get("item_check") or {}).get("items"),
            "over": (d.get("item_check") or {}).get("over"),
            "basis": (d.get("item_check") or {}).get("basis"),
        }
    case.append({"bidder": m["bidder"], "expect": m["expect"],
                 "shouldFail": m["should_fail"], "fail": m["fail_count"],
                 "cells": cells})

cov = f3["coverage"]
summ = f2["summary"]
blocked = list(f3["blocked_fields"].items())[:5]

DATA = {"meta": {
    "section": f3["meta"]["section_no"],
    "fn": f3["meta"]["bid_extract"]["evidence"],
    "rulesTotal": cov["rules_total"],
    "machineRules": cov["machine_rules"],
    "machineRunnable": cov["machine_runnable"],
    "fnVersion": f3["meta"]["tender_extract"]["version"],
}, "rows": case,
    "cols": [[r, s] for r, _rid, s in CASE_ROWS],
    "blocked": [{"field": f, "rules": ids} for f, ids in blocked]}

# ---------- 1. 顶部说明块（整块替换，不是只换首句） ----------
# 只换开头那句会留下旧文案的「二、投标文件 0 份」，新旧叠在一起，
# 页面一边说已入库 5 份、一边说 0 份，自相矛盾。必须整块换。
_i = html.index('<section class="view" id="v-bid">')
_j = html.index('<div class="block-warn">', _i)
_k = html.index('</div>', _j) + len('</div>')
old_warn = html[_j:_k]
assert '投标文件 0 份' in old_warn, "定位到的警示块不是原文"

new_warn = (
    '<div class="block-warn">\n'
    '        <b>受审对象已入库：%d 份受控合成投标包。</b><br>\n'
    '        <b>一、基准侧已就绪：</b>本笔采购招标文件包，已提取 <b>46 条否决情形</b>并逐条回读到原文，'
    '形式 5 / 资格 25 / 响应性 15 / 其他 1 —— 这是审批投标文件时逐条对位的尺子。<br>\n'
    '        <b>二、受审侧已入库：</b>标段 <b>%s</b> 的 <b>5 家</b>投标包（1 家全合规 + 4 家各带一处典型违规），'
    '<b>每家单独一个受审库</b>，与基准库物理隔离。<br>\n'
    '        <b>三、为什么要分家建库：</b>5 家混在一个库里时，检索某一家的字段，'
    '前 20 条命中里有 19 条是别家的块，本家的块挤不进来——表现为「同一个字段时而抽到、时而抽不到」，'
    '而且每次掉的还不是同一个。这不是调参能解决的，只能物理隔离到「家」这一层。'
    '拆开之后单库只有 2 个文件，字段抽取不再依赖「这次排序对我有利」。<br>\n'
    '        <b>四、这 5 份是合成演示数据：</b>物料、行项目号、限价、交货期全部取自本笔采购的公开招标文件，'
    '只有投标人名称、报价、电子签章名称、投标有效期、增值税税率五项按剧本设定——这五项正是要被判的地方。'
    '每份文件首页都压了「合成演示数据」标记，不冒充真件。<br>\n'
    '        <b>五、为什么用合成件：</b>样本内 173 个条目全部为招标方文件，<b>无一份真实投标文件</b>；'
    '真实件需招标人从 ECP 平台按标包导出投标文件包后入库。合成件只用来验证'
    '「抽取 → 对位 → 判定」这条链路跑不跑得通，<b>不替代真实受审</b>。\n'
    '      </div>'
) % (len(case), DATA["meta"]["section"])

# ---------- 2. KPI ----------
# 不能用「row k4 … </div></div>」这种非贪婪正则：kpi 卡自带三层 div，
# 非贪婪会在第一张卡结尾就收口，把后面三张卡留在原地、结构直接错乱（实测掉了 22KB）。
# 改成按锚点切片：起点是本页 KPI 行，终点是紧跟其后的「初步评审三段」标题。
p_seg = html.index('<div class="st">初步评审三段')
p_kpi = html.rindex('<div class="row k4">', 0, p_seg)
old_kpi = html[p_kpi:p_seg]
assert old_kpi.count('class="card kpi"') == 4, "KPI 区应含 4 张卡，实得 %d" % old_kpi.count('class="card kpi"')

new_kpi = '''<div class="row k4">
        <div class="card kpi"><div class="lab">审批基准条款</div><div class="val num">46<small>条</small></div><div class="foot">否决情形全部适用项 · 已就绪</div></div>
        <div class="card kpi"><div class="lab">受审投标包</div><div class="val num">5<small>份</small></div><div class="foot">1 合规 + 4 违规 · 合成演示数据</div></div>
        <div class="card kpi"><div class="lab">受审字段对位</div><div class="val num" style="color:var(--green)">%d<small>/%d</small></div><div class="foot">逐字段与剧本比对 · 跨家零串值</div></div>
        <div class="card kpi"><div class="lab">机器判定跑通</div><div class="val num">%d<small>/%d 条</small></div><div class="foot">其余 %d 条卡在待抽字段</div></div>
      </div>''' % (summ["fields_ok"], summ["fields_total"],
                   cov["machine_runnable"], cov["machine_rules"], cov["machine_blocked"])

# ---------- 3. 受审结果矩阵 ----------
MATRIX = '''      <div class="st">本次受审结果<span class="ln"></span><span class="hint">5 家 × %(ncol)d 条机器可判规则 · 点任一格看对位明细与原文</span></div>
      <div class="card">
        <table id="bidCaseTbl">
          <tr><th style="width:160px">投标人</th><th style="width:150px">剧本设定</th>
%(ths)s
              <th style="width:74px">判否</th></tr>
        </table>
        <div class="mini" style="margin-top:10px;padding-top:10px;border-top:1px solid var(--line2)">
          七条规则全部由真实抽取的字段驱动，无手工填值：签章三项来自投标函，逐物料报价来自分项报价表，
          有效期、税率、法定代表人来自投标函与报价表。行10 按<b>行项目号逐条对位</b>，不看标包总价——
          宜昌那家总价比限价合计还低，但其中一条物料超了 6.69 万，单值比抓不到。
          行11 按<b>逐行验数量×单价=合价</b>，并把表内合计与逐行之和比对；压成单值比会让一行小数点错位被其他行抵消。
          行13 在招标文件写明「免收投标保证金」时按<b>情形不适用</b>判未触发，不当缺证挂起。
        </div>
      </div>

      <div class="st">卡在哪<span class="ln"></span><span class="hint">机器可判 25 条中跑通 %(run)d 条，其余按待抽字段聚合</span></div>
      <div class="card">
        <table>
          <tr><th style="width:300px">缺的字段</th><th style="width:70px">卡住条数</th><th>被卡的规则</th></tr>
%(rows)s
        </table>
        <div class="mini" style="margin-top:10px;padding-top:10px;border-top:1px solid var(--line2)">
          这是按字段聚合的补齐清单：补一个字段能一次解锁多条规则。<b>不拿场景假定值把 46 条填满</b>——
          那样跑出来好看，验的却是假定值，不是文件。
          其中行46「报价超过平均值规定值」<b>刻意不做机器判</b>：招标文件只给了评分用的
          区间平均价浮动参数（W1=-15%%、W2=10%%），那是算基准价评分的，不是否决阈值，
          拿它当判据会凭空造出一条判否理由。
        </div>
      </div>

'''

ths = "\n".join('              <th style="width:90px">行%s %s</th>' % (r, s)
                for r, _rid, s in CASE_ROWS)

blocked_rows = "\n".join(
    '          <tr><td class="mono" style="font-size:11.5px">%s</td><td class="num">%d</td>'
    '<td class="mini">%s</td></tr>'
    % (b["field"], len(b["rules"]), "、".join(b["rules"]))
    for b in DATA["blocked"])

MATRIX = MATRIX % {"run": cov["machine_runnable"], "rows": blocked_rows,
                   "ncol": len(CASE_ROWS), "ths": ths}

# ---------- 4. JS ----------
JS = '''
/* ---------------- 受审结果矩阵（数据来自 F3 真跑证据，静态嵌入） ---------------- */
const BID_CASE = %s;
function renderBidCase(){
  const tbl=document.getElementById('bidCaseTbl');
  if(!tbl) return;
  const ORDER=BID_CASE.cols.map(c=>c[0]);
  BID_CASE.rows.forEach((r,ri)=>{
    const tr=document.createElement('tr');
    let h='<td>'+esc(r.bidder)+'</td><td class="mini">'+esc(r.expect)+'</td>';
    ORDER.forEach(k=>{
      const c=r.cells[k];
      if(!c){h+='<td class="mini" style="color:var(--ink3)">未跑</td>';return;}
      let tag,color;
      if(c.state==='NOT_RESPONDED'){tag='判否';color='t-red';}
      else if(c.state==='RESPONDED'){tag='通过';color='t-grn';}
      else if(c.state==='UNCERTAIN'){tag='待澄清';color='t-amb';}
      else {tag='人判';color='t-gry';}
      let extra='';
      if(k==='10'&&c.over&&c.over.length) extra=' <span class="mini" style="color:var(--red)">超'+c.over.length+'条</span>';
      h+='<td><span class="tag '+color+'" data-c="'+ri+':'+k+'" style="cursor:pointer">'+tag+'</span>'+extra+'</td>';
    });
    h+='<td class="num">'+r.fail+'</td>';
    tr.innerHTML=h;
    tbl.appendChild(tr);
  });
  tbl.querySelectorAll('[data-c]').forEach(el=>{
    el.onclick=()=>{
      const [ri,k]=el.dataset.c.split(':');
      const r=BID_CASE.rows[ri], c=r.cells[k];
      const meta={'投标人':r.bidder,'剧本':r.expect,'结论':c.state,
                  '依据':'判定式由抽取字段直接计算，不经模型',
                  '对位口径':c.basis==='item'?'按行项目号逐条对位':c.basis==='total'?'仅取得标包总价':'—'};
      let body=c.reason||'';
      let quote=null;
      if(c.items&&c.items.length){
        const lines=c.items.map(x=>'  '+x.item_no+'  限价 '+(x.cap_yuan||0).toLocaleString()+
          '  报价 '+(x.bid_yuan==null?'未报价':x.bid_yuan.toLocaleString())+
          '  差额 '+((x.delta_yuan||0)>=0?'+':'')+(x.delta_yuan||0).toLocaleString()+
          '  ['+x.state+']').join('\\n');
        quote='行项目号 / 限价 / 报价 / 差额 / 状态\\n'+lines;
      }
      openDrawer('行'+k+' · '+r.bidder,meta,quote,body);
    };
  });
}
renderBidCase();
'''

js_block = JS % json.dumps(DATA, ensure_ascii=False)

# ---------- 应用 ----------
h = html
assert h.count(old_warn) == 1, "顶部说明块未唯一命中"
h = h.replace(old_warn, new_warn, 1)

assert h.count(old_kpi) == 1, "KPI 块未唯一命中"
h = h.replace(old_kpi, new_kpi, 1)

anchor = '      <div class="st">审查工作表'
assert h.count(anchor) == 1, "工作表标题未唯一命中"
h = h.replace(anchor, MATRIX + anchor, 1)

js_anchor = "renderBid();\n"
assert h.count(js_anchor) == 1, "renderBid 调用未唯一命中"
h = h.replace(js_anchor, "renderBid();\n" + js_block, 1)

# ---------- 5. 总览页的引导卡：0 份的说法也要跟着改 ----------
# 只改 v-bid 会留下一页说 0 份、另一页说 5 份，翻页即自相矛盾。
old_ov = '当前库内投标文件 0 份</b>，需招标人从 ECP 按标包导出后提供。'
assert h.count(old_ov) == 1, "总览引导卡未唯一命中"
h = h.replace(old_ov, '受审库已入库 5 份合成投标包</b>（1 合规 + 4 违规），真实投标件仍需招标人从 ECP 按标包导出。', 1)

io.open(HTML, "w", encoding="utf-8").write(h)
print("已写入", HTML, "| 矩阵 %d 家 | 卡字段 %d 组 | 文件 %d 字节"
      % (len(case), len(DATA["blocked"]), len(h)))
