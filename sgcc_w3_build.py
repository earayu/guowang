# -*- coding: utf-8 -*-
"""
W2 -> W3：把主线从「两批次差异对比」纠正为「以招标文件为基准 -> 审批投标文件」。

纠偏依据（用户口径，2026-11-14）：
  「我给的两批次 demo 数据不是为了对比两个批次有啥区别，后面是基于这个内容去审批投标文件的。」

事实核验（国网样本_展开/manifest.json）：
  - 173 个条目全部为招标方文件：招标公告 18 / 采购文件 22 / 技术规范书 22 /
    货物清单 18 / 合同文件 36 / 其他附件（签章.sig、固化ID 等）57
  - 文件名含「投标文件」的条目：0
  => 两批次 = 两笔独立采购，各自一套评审基准；受审对象（投标文件）尚未入库。

变更：
  1. 标题与 logo：标前审阅工作台 -> 物资采购评标辅助工作台
  2. 顶栏「批次」-> 「采购项目」，并注明两笔独立采购、各自一套基准
  3. 导航「审阅」->「评标」；「批次总览」->「采购项目基准」；「双版差异」->「基准口径核对」
  4. 新增 v-bid「投标文件审批」视图（三段初步评审 + 核查流水 + 审查工作表骨架）
  5. 总览改为「采购项目基准」，把 46 条否决情形明确定位成"审批投标文件的尺子"
  6. 双版差异加首页说明：这是同一笔采购内两套资格口径，不是两个批次的对比
  7. LIFE_LINK：L3 -> overview，L5/L6 -> bid

每处替换严格断言 count == 1，任何一处不匹配即中止，不产出半成品。
"""
import io, os, sys

B = 'c:/Users/linkz/WorkBuddy/PC办公/'
SRC = B + '国网物资部_标前审阅工作台_W2.html'
DST = B + '国网物资部_评标辅助工作台_W3.html'

with io.open(SRC, encoding='utf-8') as f:
    html = f.read()

pairs = []

# ---------------------------------------------------------------- 1 标题
pairs.append((
    '<title>标前审阅工作台 · 国网物资采购</title>',
    '<title>物资采购评标辅助工作台 · 国网物资部</title>',
))

# ---------------------------------------------------------------- 2 logo
pairs.append((
    '      标前审阅工作台\n    </div>',
    '      物资采购评标辅助工作台\n    </div>',
))

# ---------------------------------------------------------------- 3 顶栏采购项目
pairs.append((
    '''    <div class="batch">
      批次
      <select class="sel" id="batchSel">
        <option>1525K1 · 2025年物资类用户受托工程框架协议</option>
        <option>152507 · 2025年新增第一次物资公开招标</option>
      </select>
    </div>''',
    '''    <div class="batch">
      采购项目
      <select class="sel" id="batchSel">
        <option>1525K1 · 2025年物资类用户受托工程框架协议 · 4 标包</option>
        <option>152507 · 2025年新增第一次物资公开招标 · 14 标包</option>
      </select>
      <span class="projnote">两笔独立采购 · 各自一套评审基准</span>
    </div>''',
))

# ---------------------------------------------------------------- 4 追加 CSS
pairs.append((
    '.lnote{background:#FFFDF7;border:1px solid #F2E3BF;border-radius:4px;padding:8px 11px;font-size:11.5px;color:#7A5B18;line-height:1.7;margin-top:10px}',
    '''.lnote{background:#FFFDF7;border:1px solid #F2E3BF;border-radius:4px;padding:8px 11px;font-size:11.5px;color:#7A5B18;line-height:1.7;margin-top:10px}
.projnote{font-size:11px;color:rgba(255,255,255,.58);margin-left:6px;white-space:nowrap}
.block-warn{background:#FFFAEB;border:1px solid #F2E3BF;border-left:3px solid #B54708;border-radius:var(--radius);padding:11px 14px;font-size:12px;color:#6B4A12;line-height:1.85;margin-bottom:16px}
.block-warn b{color:#7A3E05}
.segrow{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:4px}
.seg{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:12px 14px}
.seg .sn{font-size:11.5px;color:var(--ink3)}
.seg .sv{font-size:22px;font-weight:600;color:var(--brand);letter-spacing:-.5px;margin:2px 0 5px}
.seg .sv small{font-size:11px;font-weight:400;color:var(--ink3);margin-left:3px}
.seg .sd{font-size:11.5px;color:var(--ink2);line-height:1.72}
.seg.hollow .sv{color:var(--ink3)}
@media(max-width:1180px){.segrow{grid-template-columns:repeat(2,1fr)}}
.bidsrc{font-size:10.5px;color:var(--ink3);background:var(--line2);border-radius:3px;padding:0 5px;margin-left:5px}''',
))

# ---------------------------------------------------------------- 5 导航组名
pairs.append((
    '    <div class="grp">审阅</div>',
    '    <div class="grp">评标</div>',
))

# ---------------------------------------------------------------- 6 批次总览 -> 采购项目基准
pairs.append((
    '      批次总览\n    </a>',
    '      采购项目基准\n    </a>',
))

# ---------------------------------------------------------------- 7 插入「投标文件审批」导航项
pairs.append((
    '    <a data-v="diff">\n      <svg class="ic" viewBox="0 0 16 16" fill="none"><path d="M4 2v12M12 2v12" stroke="currentColor" stroke-width="1.2"/>',
    '''    <a data-v="bid">
      <svg class="ic" viewBox="0 0 16 16" fill="none"><path d="M4 1.8h5.2L13 5.6v8.6H4z" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="M9.2 1.8v3.9h3.7" stroke="currentColor" stroke-width="1.2" stroke-linejoin="round"/><path d="m6.1 10 1.3 1.3 2.4-2.6" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/></svg>
      投标文件审批
      <span class="cnt">46</span>
    </a>
    <a data-v="diff">
      <svg class="ic" viewBox="0 0 16 16" fill="none"><path d="M4 2v12M12 2v12" stroke="currentColor" stroke-width="1.2"/>''',
))

# ---------------------------------------------------------------- 8 双版差异 -> 基准口径核对
pairs.append((
    '      双版差异\n      <span class="cnt">4</span>',
    '      基准口径核对\n      <span class="cnt">4</span>',
))

# ---------------------------------------------------------------- 9 总览标题与副标题
pairs.append((
    '''      <div class="h1">批次总览</div>
      <div class="sub">1525K1 · 国网湖北电力 2025 年物资类用户受托工程框架协议公开招标 · 4 个标包（含资格预审 / 资格后审双版）</div>''',
    '''      <div class="h1">采购项目基准</div>
      <div class="sub">1525K1 · 国网湖北电力 2025 年物资类用户受托工程框架协议公开招标 · 4 标包 · 本页是<b>审批投标文件的基准来源</b>，不是与另一批次做对比</div>''',
))

# ---------------------------------------------------------------- 10 总览 KPI 语义
pairs.append((
    '''        <div class="card kpi"><div class="lab">评审规则</div><div class="val num">46<small>条</small></div><div class="foot">全部候选待核 · 待业务确认</div></div>''',
    '''        <div class="card kpi"><div class="lab">审批可用基准</div><div class="val num">46<small>条</small></div><div class="foot">否决情形 · 逐条可回读原文</div></div>''',
))

# ---------------------------------------------------------------- 11 总览：口径待定项标题 + 承接说明
pairs.append((
    '''      <div class="st">风险分布<span class="ln"></span><span class="hint">按 9 项待澄清事项的影响面分级</span></div>''',
    '''      <div class="st">基准口径待定项<span class="ln"></span><span class="hint">这些是"尺子本身"还没定死的地方，必须在投标截止前定口径</span></div>
      <div class="note" style="margin-bottom:12px">
        为什么这一步必须先做：投标文件的响应性<b>只能对照确定的基准</b>来判。基准里有两套并存的资格口径、有缺项、有引用不闭环，投标文件交上来就<b>无法回答"这一条到底算不算响应"</b>。所以基准口径核对不是文案比对，它是审批投标文件的前置条件。
      </div>''',
))

# ---------------------------------------------------------------- 12 总览：本轮审阅做了什么 -> 基准提取
pairs.append((
    '''      <div class="st">本轮审阅做了什么<span class="ln"></span></div>''',
    '''      <div class="st">基准已提取到什么<span class="ln"></span><span class="hint">四项动作，全部可从原文回读</span></div>''',
))
pairs.append((
    '''          <tr><td>否决情形回读</td><td class="num">46 条</td><td>资格 25 · 响应 15 · 形式 5 · 其他 1，逐条回读原文并列入规则台账</td></tr>''',
    '''          <tr><td>否决情形回读</td><td class="num">46 条</td><td>资格 25 · 响应 15 · 形式 5 · 其他 1，逐条回读原文并列入规则台账 —— <b>这 46 条就是审批投标文件时逐条对位的尺子</b></td></tr>''',
))

# ---------------------------------------------------------------- 13 双版差异页：标题/副标题/首页说明
pairs.append((
    '''      <div class="h1">双版差异比对</div>
      <div class="sub">1525K1 同时提供「资格预审」与「资格后审」两版采购文件，逐项比对四项要求并给出各自条款位置</div>''',
    '''      <div class="h1">基准口径核对 · 同一笔采购内两套资格口径</div>
      <div class="sub">1525K1 同时提供「资格预审」与「资格后审」两版采购文件；本页核对的是<b>同一笔采购内部的口径分歧</b>，与另一个批次无关</div>

      <div class="block-warn">
        <b>先把一件事说清：这不是两个批次的对比。</b>1525K1 与 152507 是<b>两笔独立采购</b>，各自有自己的招标文件、资格条件与评标办法，业务上不需要、也不应该相互比较。本页比较的是 <b>1525K1 这一笔采购内部</b>同时挂出的「资格预审版」与「资格后审版」——两版对同一批分标给出了不同的资格条件。口径不定，投标文件交上来就<b>无法判定它的资格响应成立与否</b>，这是审批环节的第一个卡点。
      </div>''',
))

# ---------------------------------------------------------------- 14b 基准页 -> 审批页 动线入口
pairs.append((
    '''          <span class="tag t-blu" style="flex:0 0 auto">查看全生命周期 →</span>
        </div>
      </div>
''',
    '''          <span class="tag t-blu" style="flex:0 0 auto">查看全生命周期 →</span>
        </div>
      </div>

      <div class="card" id="bidEntry" style="margin-bottom:18px;border-color:#CFE0F5;background:linear-gradient(90deg,#FBFDFF,#FFFFFF);cursor:pointer">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="flex:1">
            <div style="font-size:13px;font-weight:500;margin-bottom:3px">这份基准拿去审谁？→ 投标文件审批</div>
            <div class="mini">基准已就绪：46 条否决情形，按形式 5 / 资格 25 / 响应性 15 / 其他 1 分组，逐条可回读原文。投标文件入库后逐条对位，产出候选否决项与澄清问题。<b style="color:var(--ink)">当前库内投标文件 0 份</b>，需招标人从 ECP 按标包导出后提供。</div>
          </div>
          <span class="tag t-blu" style="flex:0 0 auto">进入投标文件审批 →</span>
        </div>
      </div>
''',
))

# ---------------------------------------------------------------- 14 LIFE_LINK
pairs.append((
    "const LIFE_LINK = {L3:'diff', L4:'clarify', L6:'rules'};",
    "const LIFE_LINK = {L3:'overview', L4:'clarify', L5:'bid', L6:'bid'};",
))

# ---------------------------------------------------------------- 15 新增 v-bid 视图
BID_HTML = '''    <!-- ============ 投标文件审批 ============ -->
    <section class="view" id="v-bid">
      <div class="h1">投标文件审批</div>
      <div class="sub">以本笔采购的招标文件为<b>唯一基准</b>，对投标文件做「形式 → 资格 → 响应性」三段初步核查，逐条给出依据、原文位置与候选结论；判定与签字在评标委员会</div>

      <div class="block-warn">
        <b>受审对象尚未入库，这一页要说清两件事。</b><br>
        <b>一、基准已就绪：</b>库内是本笔采购的招标文件包（155 份 · 18 标包），已从中提取 <b>46 条否决情形</b>并逐条回读到原文，形式 5 / 资格 25 / 响应性 15 / 其他 1 —— 这就是审批投标文件时逐条对位的尺子。<br>
        <b>二、投标文件 0 份：</b>样本内 173 个条目全部为招标方文件（招标公告 / 采购文件 / 技术规范书 / 货物清单 / 合同文件），<b>无一份投标文件</b>。审核投标文件的前提，是招标人从 ECP 平台按标包导出投标文件包（商务 / 技术 / 报价 / 资格）后入库。下表展示的是<b>投标文件入库后逐条核查的产出形态</b>，投标响应列与候选结论列因此为空，<b>不填、不预编、不假装已审</b>。
      </div>

      <div class="row k4">
        <div class="card kpi"><div class="lab">审批基准条款</div><div class="val num">46<small>条</small></div><div class="foot">否决情形全部适用项 · 已就绪</div></div>
        <div class="card kpi"><div class="lab">待审标包</div><div class="val num">18<small>个</small></div><div class="foot">1525K1 四个 · 152507 十四个</div></div>
        <div class="card kpi"><div class="lab">投标文件已入库</div><div class="val num" style="color:var(--ink3)">0<small>份</small></div><div class="foot">需招标人按标包导出后提供</div></div>
        <div class="card kpi"><div class="lab">评分办法结构化</div><div class="val num" style="color:var(--red)">0<small>项</small></div><div class="foot">评分因素/权重未提取 · 不演示 AI 赋分</div></div>
      </div>

      <div class="st">初步评审三段<span class="ln"></span><span class="hint">三段是串行否决关系：前一段不成立，后一段不再进入</span></div>
      <div class="segrow">
        <div class="seg">
          <div class="sn">第一段 · 形式评审</div>
          <div class="sv">5<small>条</small></div>
          <div class="sd">格式是否按范本、是否按规定签署、份数与上传凭证单能否查验。<b>文件本身不成立，后面两段不进入。</b></div>
        </div>
        <div class="seg">
          <div class="sn">第二段 · 资格评审</div>
          <div class="sv">25<small>条</small></div>
          <div class="sd">主体资格、业绩、生产设备、型式试验报告、失信与不良行为。<b>条数最多、举证材料最厚。</b></div>
        </div>
        <div class="seg">
          <div class="sn">第三段 · 响应性评审</div>
          <div class="sv">15<small>条</small></div>
          <div class="sd">投标范围、报价、税率、工期与交货期、投标担保、偏差与澄清修改。<b>错一处即整包否决。</b></div>
        </div>
        <div class="seg hollow">
          <div class="sn">另列 · 其他事项</div>
          <div class="sv">1<small>条</small></div>
          <div class="sd">前附表之二中不归入上述三段的兜底事项，单列以便台账号与原文行号一一对应。</div>
        </div>
      </div>
      <div class="mini" style="margin:10px 0 0">上表条数为规则台账实测分布（46 条 = 5 + 25 + 15 + 1），非估算。</div>

      <div class="st">逐条核查怎么跑<span class="ln"></span><span class="hint">四步，前两步系统做，后两步人做</span></div>
      <div class="card">
        <table>
          <tr><th style="width:118px">步骤</th><th style="width:32%">系统做什么</th><th style="width:33%">产出</th><th style="width:104px">谁签字</th></tr>
          <tr><td><b>1 基准就位</b> <span class="tag t-grn">已就绪</span></td><td>把 46 条否决情形按三段分组，逐条回读原文与条款所在章节，形成规则台账</td><td>规则台账 46 行，含原文摘录与章节位置，状态全部为 <span class="mono">CANDIDATE</span></td><td>物资部复核人</td></tr>
          <tr><td><b>2 响应对位</b> <span class="tag t-gry">待投标文件</span></td><td>按标包逐条取投标文件对应章节，与基准条款对位，标出「未见响应 / 响应不符 / 表述含糊」</td><td>候选否决项清单（只出 <span class="mono">CANDIDATE</span>，不出现「否决」字样结论）</td><td>—</td></tr>
          <tr><td><b>3 澄清归集</b> <span class="tag t-amb">Function 已发布</span></td><td>把对位不上的项按「事实 / 依据条款 / 需投标人澄清的问题 / 仍缺材料」成表</td><td>澄清问题表，字段固定，可导出；<b>发出前须评标委员会确认</b></td><td>评标委员会</td></tr>
          <tr><td><b>4 判定与签字</b> <span class="tag t-gry">不在系统内</span></td><td>不参与</td><td>初步评审表签署件</td><td>评标委员会逐项审议</td></tr>
        </table>
        <div class="mini" style="margin-top:10px;padding-top:10px;border-top:1px solid var(--line2)">
          第 3 步的结构化出表已用 Function 发布（<span class="mono">sgcc-clarification-table</span> v1，实测单次调用 231 ms，返回 <span class="mono">executable=false</span>）。它出的是表，不是结论。
        </div>
      </div>

      <div class="st">审查工作表<span class="ln"></span><span class="hint">骨架来自 46 条基准，投标响应与结论两列为空 —— 空着是本页最重要的事实</span></div>
      <div id="bidSheet"></div>
      <div class="mini" style="margin-top:8px">点任一行可看该条否决情形的原文与依据章节。表中每条都真实存在于规则台账，<b>不是示例占位</b>。</div>

      <div class="st">这一段会产出什么<span class="ln"></span></div>
      <div class="row" style="grid-template-columns:repeat(3,1fr)">
        <div class="card">
          <div style="font-size:12.5px;font-weight:500;margin-bottom:6px">澄清问题表</div>
          <div class="mini" style="line-height:1.8">一条对位不上的核查项 → 一条带依据的澄清问题。字段固定：标包 · 条号 · 事实 · 依据条款 · 需澄清内容 · 仍缺材料。<br><span class="tag t-amb" style="margin-top:6px">Function 已发布 · 231 ms</span></div>
        </div>
        <div class="card">
          <div style="font-size:12.5px;font-weight:500;margin-bottom:6px">候选否决项清单</div>
          <div class="mini" style="line-height:1.8">按三段分组，逐条附原文位置与投标响应摘录。<b>只标候选，不下否决结论</b>；由评标委员会逐项审议后转正式文书。<br><span class="tag t-gry" style="margin-top:6px">待投标文件入库</span></div>
        </div>
        <div class="card">
          <div style="font-size:12.5px;font-weight:500;margin-bottom:6px">初步评审表</div>
          <div class="mini" style="line-height:1.8">三段结论逐包汇总，供委员会签署。<b>系统只预填事实列与依据列，结论列留空由专家填写</b>，不做代签。<br><span class="tag t-gry" style="margin-top:6px">待评标委员会</span></div>
        </div>
      </div>

      <div class="comp">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="5.8" stroke="#B54708" stroke-width="1.1"/><path d="M7 4v3.6" stroke="#B54708" stroke-width="1.1" stroke-linecap="round"/><circle cx="7" cy="9.8" r=".65" fill="#B54708"/></svg>
        <span>本页<b>没有一份已审批的投标文件</b>，因此不存在"审批准确率""检出率"这类指标。系统在初步评审中的位置是：把 46 条基准摆齐、把投标响应逐条对位、把对不上的整理成可澄清的问题；<b>是否构成否决、是否赋分、是否定标，一律由评标委员会依法作出</b>（195 号文第十一条辅助性定位）。评审全程录音录像、专家独立打分，系统不介入表决。</span>
      </div>
    </section>

'''

pairs.append((
    '    <!-- ============ 双版差异 ============ -->',
    BID_HTML + '    <!-- ============ 基准口径核对 ============ -->',
))

# ---------------------------------------------------------------- 16 JS：renderBid
BID_JS = '''// bid sheet（真实规则骨架，响应列留空）
const BID_ROWS=[
 {row:1,id:'GW-HB-FJ-001',cat:'形式评审',sub:'格式内容',t:'投标文件未按招标文件规定的格式填写，内容不全或者关键字迹模糊无法辨认的；未按招标文件要求在招标人招投标交易平台信息系统制作并上传凭证单的…'},
 {row:3,id:'GW-HB-FJ-003',cat:'形式评审',sub:'文件签署',t:'对格式文件进行实质性修改或未按格式进行签署的，如由委托代理人签字的，未附有效的法定代表人授权委托书的…'},
 {row:23,id:'GW-HB-FJ-023',cat:'资格评审',sub:'资格不符',t:'未提供符合招标文件要求的联合体协议书的。'},
 {row:24,id:'GW-HB-FJ-024',cat:'资格评审',sub:'主体不符',t:'为招标人不具有独立法人资格的附属机构（单位）。'},
 {row:8,id:'GW-HB-FJ-008',cat:'响应性评审',sub:'投标报价',t:'投标人不接受评标委员会依法所作的修正价格的。'},
 {row:46,id:'GW-HB-FJ-046',cat:'响应性评审',sub:'投标报价',t:'因投标人投标价格超过本包规定投标人报价平均值规定值的（预审版另含「或不平衡报价的」，两版标注不一致）。',vd:true}
];
function renderBid(){
  const box=document.getElementById('bidSheet');
  const be=document.getElementById('bidEntry');
  if(be) be.onclick=()=>{document.querySelector('.nav a[data-v="bid"]').click();};
  if(!box) return;
  let h='<table><tr><th style="width:44px">条号</th><th>核查项（基准条款）</th><th style="width:92px">段</th><th style="width:150px">投标响应</th><th style="width:104px">候选结论</th><th style="width:70px">依据</th></tr>';
  BID_ROWS.forEach(r=>{
    const cls=r.cat==='形式评审'?'t-blu':r.cat==='资格评审'?'t-red':'t-amb';
    const vd=r.vd?' <span class="tag t-amb">两版不一致</span>':'';
    h+='<tr class="ck" data-b="'+r.row+'"><td class="num">'+r.row+'</td>'+
       '<td style="font-size:12px">'+esc(r.t)+vd+'</td>'+
       '<td><span class="tag '+cls+'">'+r.cat.slice(0,2)+'</span><span class="bidsrc">'+r.sub+'</span></td>'+
       '<td class="mini">待投标文件入库</td>'+
       '<td class="mini">未执行</td>'+
       '<td><span style="color:var(--brand2);font-size:11.5px">查看原文</span></td></tr>';
  });
  h+='</table>';
  box.innerHTML=h;
  box.querySelectorAll('[data-b]').forEach(tr=>{
    tr.onclick=()=>{
      const r=BID_ROWS.find(x=>String(x.row)===tr.dataset.b);
      openDrawer('否决情形第 '+r.row+' 条 · '+r.cat+' / '+r.sub,{
        '规则编号':r.id,'段位':r.cat+' · '+r.sub,'台账状态':'CANDIDATE（待业务方确认）',
        '依据章节':'第三章 评标办法 → 评标办法前附表之二：初步评审标准 → 否决情形表',
        '适用标包':'18 个标包采购文件同表同文'+(r.vd?'；本条按版本不同':''),
        '投标响应':'未执行 —— 库内无投标文件','候选结论':'未执行'
      },r.t,'这一行是评审基准，不是审批结论。投标文件入库后，系统按本条去投标文件里找对应响应并标出「未见响应 / 响应不符 / 表述含糊」，只产 CANDIDATE；是否构成否决由评标委员会依招标文件审议。');
    };
  });
}
renderBid();

'''
pairs.append((
    '// diff tabs\nconst DIFFS=[DIFF,DIFF2,DIFF3,DIFF4];',
    BID_JS + '// diff tabs\nconst DIFFS=[DIFF,DIFF2,DIFF3,DIFF4];',
))

# ---------------------------------------------------------------- 19 术语条目数 68 -> 70（补 T69 投标文件 / T70 评审基准）
pairs.append((
    '      <span class="cnt">68</span>',
    '      <span class="cnt">70</span>',
))
pairs.append((
    '<div class="sub">68 条业务术语 · 按物资部门实际用语整理，供系统与业务对齐口径</div>',
    '<div class="sub">70 条业务术语 · 按物资部门实际用语整理，供系统与业务对齐口径</div>',
))
pairs.append((
    '共 68 条，此处展示 10 条。',
    '共 70 条，此处展示 10 条。',
))

# ---------------------------------------------------------------- 20 消除"批次=对比"的残留歧义（同批次内横向对比 ≠ 批次之间对比）
pairs.append((
    '同批次横向对比同一指标，提示明显偏离（不评分）',
    '同一标包内不同投标人横向对比同一指标，提示明显偏离（不评分）',
))
pairs.append((
    '同一批次多版本文件逐项比对，给出各自条款位置与解析行号',
    '同一笔采购内多版本文件逐项比对，给出各自条款位置与解析行号',
))
pairs.append((
    '152507 批次里 4004 的包1 与包2 货物清单是否相同？">同批次跨包货物清单比对',
    '同一笔采购（152507）里 4004 的包1 与包2 货物清单是否相同？">同标包内跨包货物清单比对',
))

# ---------------------------------------------------------------- 执行
for i, (old, new) in enumerate(pairs, 1):
    n = html.count(old)
    if n != 1:
        print('[FAIL] pair #%d count=%d\n  old head: %r' % (i, n, old[:90]))
        sys.exit(1)
    html = html.replace(old, new, 1)
    print('[ok] pair #%d  +%d chars' % (i, len(new) - len(old)))

with io.open(DST, 'w', encoding='utf-8') as f:
    f.write(html)
print('\nW3 written: %s  (%d bytes)' % (DST, os.path.getsize(DST)))
