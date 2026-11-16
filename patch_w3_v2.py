# -*- coding: utf-8 -*-
"""把 W3 的「投标文件审批」从 v1（5 家 / 7 条）切到 v2（6 家 / 8 条）。

只改这一块：判定矩阵数据、表头一列（行7）、渲染函数、四处口径文案。
其余视图（生命周期 / 基准口径 / 条款核验 / 澄清 / 问答 / 术语）一字不动。
"""
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "_bak_w3_v1_5家7条.html")
HTML = os.path.join(HERE, "国网物资部_评标辅助工作台_W3.html")
DATA = os.path.join(HERE, "国网Demo_W3v2_页面数据_6家8条.json")

data = json.load(io.open(DATA, encoding="utf-8"))
blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))

s = io.open(SRC, encoding="utf-8").read()   # 每轮都从 v1 基线重建，保证幂等
orig_len = len(s)
report = []


def rep(old, new, tag, count=1):
    global s
    n = s.count(old)
    if n != count:
        report.append("✗ %s：命中 %d，期望 %d" % (tag, n, count))
        return False
    s = s.replace(old, new)
    report.append("✓ %s" % tag)
    return True


# ---- 1. 判定矩阵数据整行替换 ----
m = re.search(r"const BID_CASE = \{.*?\};\n", s, re.S)
if not m:
    raise SystemExit("找不到 BID_CASE 定义")
s = s[:m.start()] + "const BID_CASE = " + blob + ";\n" + s[m.end():]
report.append("✓ BID_CASE 换成 6 家 8 条（含字段值与原文引用）")

# ---- 2. 表头补行7 列 ----
rep('<th style="width:90px">行4 签章</th>',
    '<th style="width:90px">行4 签章</th>\n              <th style="width:84px">行7 交货期</th>',
    "表头补「行7 交货期」列")

# ---- 3. 渲染函数整体替换 ----
NEW_FN = r"""function renderBidCase(){
  const tbl=document.getElementById('bidCaseTbl');
  if(!tbl) return;
  const ORDER=BID_CASE.cols.map(c=>String(c.row));
  BID_CASE.rows.forEach((r,ri)=>{
    const tr=document.createElement('tr');
    let h='<td><b>'+esc(r.bidder)+'</b></td><td class="mini">'+esc(r.expect)+'</td>';
    ORDER.forEach(k=>{
      const c=r.cells[k];
      if(!c){h+='<td class="mini" style="color:var(--ink3)">未跑</td>';return;}
      let tag,color;
      if(c.state==='NOT_RESPONDED'){tag='判否';color='t-red';}
      else if(c.state==='RESPONDED'){tag='通过';color='t-grn';}
      else if(c.state==='UNCERTAIN'){tag='缺字段';color='t-amb';}
      else {tag='人判';color='t-gry';}
      let extra='';
      if(c.over&&c.over.length) extra=' <span class="mini" style="color:var(--red)">超'+c.over.length+'条</span>';
      h+='<td><span class="tag '+color+'" data-c="'+ri+':'+k+'" style="cursor:pointer">'+tag+'</span>'+extra+'</td>';
    });
    h+='<td class="num">'+r.fail+'</td>';
    tr.innerHTML=h;
    tbl.appendChild(tr);
  });
  tbl.querySelectorAll('[data-c]').forEach(el=>{
    el.onclick=()=>{
      const p=el.dataset.c.split(':');
      const ri=parseInt(p[0],10), k=p[1];
      const r=BID_CASE.rows[ri], c=r.cells[k];
      const col=BID_CASE.cols.filter(x=>String(x.row)===k)[0]||{};
      const st={RESPONDED:'未触发（判定式不成立或情形不适用）',
                NOT_RESPONDED:'判否（判定式成立）',
                UNCERTAIN:'缺字段，按规则不判',
                NEED_HUMAN:'需人工判定'}[c.state]||c.state;
      const meta={'投标人':esc(r.bidder),'剧本设定':esc(r.expect)||'—',
                  '本条结论':st,'规则号':col.rule||'—',
                  '对位口径':c.basis==='item'?'按行项目号逐条对位':(c.basis==='total'?'仅取得标包总价':'按抽取字段直接计算'),
                  '受审库':r.kb||'—','抽取批':r.runId||'—'};
      let q='';
      if(c.calc) q+='【算式】'+esc(c.calc)+'\n\n';
      if(c.fields&&c.fields.length){
        c.fields.forEach(f=>{
          q+='【'+f.label+'】'+(f.got==null?'未抽到':esc(String(f.got)))+'\n';
          if(f.source_doc) q+='   取自：'+esc(f.source_doc)+'\n';
          if(f.quote) q+='   '+f.source+' · '+f.loc+'\n   「'+esc(f.quote)+'」\n';
          q+='\n';
        });
      } else {q='本格无字段级明细。\n\n';}
      if(c.items&&c.items.length){
        q+='【逐行对位】行项目号 / 限价 / 报价 / 差额 / 状态\n';
        c.items.forEach(x=>{
          q+='  '+x.item_no+'   '+(x.cap_yuan||0).toLocaleString()+'   '+
             (x.bid_yuan==null?'未报价':x.bid_yuan.toLocaleString())+'   '+
             ((x.delta_yuan||0)>=0?'+':'')+(x.delta_yuan||0).toLocaleString()+'   ['+x.state+']\n';
        });
        q+='\n';
      }
      let foot='判据输出：'+(c.reason||'—');
      if(c.state==='UNCERTAIN'){
        foot+='\n该格按规则不判：缺 '+String(c.reason||'').replace(/^.*缺字段：/,'')+
              '，不猜、不按场景假定值补齐——补一个假定值能让 46 条全绿，但验的是假定值，不是文件。';
      } else if(c.state==='NOT_RESPONDED'){
        foot+='\n本格只给候选否决项与依据，最终认定权在评标委员会。';
      } else {
        foot+='\n判定式由抽取字段直接计算，不经模型自由判断。';
      }
      openDrawer('行'+k+' '+col.label+' · '+r.bidder,meta,q,foot);
    };
  });
}
renderBidCase();"""

mm = re.search(r"function renderBidCase\(\)\{.*?\nrenderBidCase\(\);", s, re.S)
if not mm:
    raise SystemExit("找不到 renderBidCase")
s = s[:mm.start()] + NEW_FN + s[mm.end():]
report.append("✓ renderBidCase 改为 8 列 + 字段值与原文抽屉")

# ---- 4. 文案 ----
rep('<span class="hint">5 家 × 7 条机器可判规则 · 点任一格看对位明细与原文</span>',
    '<span class="hint">6 家 × 8 条机器可判规则 · 点任一格看字段值、判据与原文</span>',
    "受审结果标题：5 家 7 条 → 6 家 8 条")

rep('<b>5 家</b>投标包（1 家全合规 + 4 家各带一处典型违规）',
    '<b>6 家</b>投标包（1 家对照 · 5 家各带一处典型违规）',
    "受审侧入库家数 5 → 6")

rep('拆开之后单库只有 2 个文件，字段抽取不再依赖「这次排序对我有利」。',
    '拆开之后单库只有 4 个文件，字段抽取不再依赖「这次排序对我有利」。',
    "单库文件数 2 → 4")

rep('受审库已入库 5 份合成投标包</b>（1 合规 + 4 违规）',
    '受审库已入库 6 家 24 份合成投标包</b>（1 家对照 + 5 家各带一处典型违规）',
    "首页摘要 5 份 → 6 家 24 份")

rep('<span class="hint">机器可判 25 条中跑通 7 条，其余按待抽字段聚合</span>',
    '<span class="hint">机器可判 25 条中跑通 8 条，其余按待抽字段聚合</span>',
    "卡在哪标题：跑通 7 条 → 8 条")

rep('七条规则全部由真实抽取的字段驱动，无手工填值：签章三项来自投标函，逐物料报价来自分项报价表，\n          有效期、税率、法定代表人来自投标函与报价表。',
    '八条规则全部由真实抽取的字段驱动，无手工填值：签章三项来自投标函与签章验证页，逐物料报价来自分项报价表，\n          有效期、税率、交货期、法定代表人来自投标函、偏差表与报价表。行7 比的是<b>承诺交货日 vs 货物清单首批要求日</b>，'
    '恩施承诺 2026-07-15、要求 2026-04-20，晚 86 天，且它自己在偏差表里如实写了——这是响应性不符，不是虚假材料。',
    "八条规则说明 + 行7 讲法")

rep('<b>四、这 5 份是合成演示数据：</b>',
    '<b>四、这 6 家 24 份是合成演示数据：</b>',
    "合成件声明家数")


rep('<b>受审对象已入库：5 份受控合成投标包。</b>',
    '<b>受审对象已入库：6 家 24 份受控合成投标包。</b>',
    "横幅：5 份 → 6 家 24 份")

rep('<div class="val num">5<small>份</small></div><div class="foot">1 合规 + 4 违规 · 合成演示数据</div>',
    '<div class="val num">6<small>家</small></div><div class="foot">24 份 · 1 家对照 + 5 家各带一处违规</div>',
    "KPI 受审投标包：5 份 → 6 家 24 份")

rep('<div class="lab">机器判定跑通</div><div class="val num">7<small>/25 条</small></div><div class="foot">其余 18 条卡在待抽字段</div>',
    '<div class="lab">机器判定跑通</div><div class="val num">8<small>/25 条</small></div><div class="foot">其余 17 条卡在待抽字段</div>',
    "KPI 机器判定：7 → 8 条，18 → 17")


rep('<div class="lab">受审字段对位</div><div class="val num" style="color:var(--green)">55<small>/55</small></div><div class="foot">逐字段与剧本比对 · 跨家零串值</div>',
    '<div class="lab">受审字段对位</div><div class="val num" style="color:var(--green)">66<small>/66</small></div><div class="foot">6 家 × 11 字段 · 跨家零串值</div>',
    "KPI 字段对位：55/55（5家）→ 66/66（6家）")


rep('物料、行项目号、限价、交货期全部取自本笔采购的公开招标文件，只有投标人名称、报价、电子签章名称、投标有效期、增值税税率五项按剧本设定——这五项正是要被判的地方。',
    '物料、行项目号、限价、交货期要求全部取自本笔采购的公开招标文件，只有投标人名称、报价、电子签章名称、投标有效期、增值税税率、承诺交货期六项按剧本设定——这六项正是要被判的地方。',
    "合成件声明：五项 → 六项（v2 多了交货期）")

io.open(HTML, "w", encoding="utf-8").write(s)
print("\n".join(report))
print("文件 %d → %d 字节" % (orig_len, len(s)))
bad = [x for x in report if x.startswith("✗")]
print("VERDICT:", "PASS 全部命中" if not bad else "FAIL " + str(bad))
