# -*- coding: utf-8 -*-
"""把术语库 / 规则库 / 业务闭环三个页签接入唯一演示入口（静态快照，不发请求）"""
import io
import json
import re

BASE = 'c:/Users/linkz/WorkBuddy/PC办公/'
HTML_IN = BASE + '国网Demo_演示控制台_V7_before_assets.html'   # 打补丁前的原始快照，保证可重复运行
HTML_OUT = BASE + '国网Demo_演示控制台_V7.html'
EMBED = BASE + 'sgcc_assets_embed.json'

s = io.open(HTML_IN, encoding='utf-8').read()
assets = json.load(io.open(EMBED, encoding='utf-8'))
js_data = json.dumps(assets, ensure_ascii=False).replace('</', '<\\/')

def once(old, new):
    global s
    n = s.count(old)
    assert n == 1, 'count=%d for %r' % (n, old[:90])
    s = s.replace(old, new, 1)

# ---------------------------------------------------------------- 1. CSS 增补
CSS = r'''
  .assetbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin:10px 0;padding:9px 11px;border:1px solid var(--line);border-radius:8px;background:#fafbfc}
  .assetbar input,.assetbar select{font:inherit;font-size:11.5px;border:1px solid var(--line2);border-radius:6px;padding:6px 9px;background:#fff;color:var(--ink)}
  .assetbar input{min-width:250px;flex:1}
  .assetbar label{font-size:11px;color:var(--muted)}
  .assetbar .cnt{font-size:11px;color:var(--navy);font-weight:600;margin-left:auto}
  details.rule{border:1px solid var(--line);border-radius:6px;background:#fcfdfe;padding:5px 8px;margin:2px 0}
  details.rule summary{cursor:pointer;font-size:11px;color:var(--muted)}
  details.rule .full{font-size:11.5px;line-height:1.7;color:var(--ink);padding:7px 2px 2px;border-top:1px dashed var(--line2);margin-top:6px}
  .small{font-size:10.5px;color:var(--faint)}
  .twocol{display:grid;grid-template-columns:1fr 1fr;gap:10px}
'''
once('  a{color:var(--navy)}\n</style>', '  a{color:var(--navy)}\n' + CSS + '</style>')

# ---------------------------------------------------------------- 2. header / banner / footer
once('<h1>国网招标审核 · 演示控制台 V7</h1>',
     '<h1>国网招标审核 · 演示控制台 V7</h1>\n'
     '    <div class="sub" style="margin-top:4px"><b>V7.1 增补（13:25）</b>：业务术语库 68 条 · 专家评审规则 46 行 · 省侧规则扩展位 12 条 · 业务闭环判定　｜　<b>V7.2 索引复核（14:13）：四类 155 全绿</b></div>')
once('读数截至 2026-11-14 13:09，页面<b>不发任何检索或写请求</b>',
     '题库读数截至 2026-11-14 13:09，术语与规则资产增补于 13:25，索引活查 14:13:11（四类 155 全绿），页面<b>不发任何检索或写请求</b>')
once('      <span class="b">CLI v0.7.56</span>',
     '      <span class="b">CLI v0.7.56</span>\n'
     '      <span class="b ok">术语 68 · 规则 46</span>\n'
     '      <span class="b">平台 Skill 已上传</span>')
once('      <div><span>自动判定控件</span><b>0 个</b></div>',
     '      <div><span>自动判定控件</span><b>0 个</b></div>\n'
     '      <div><span>业务术语</span><b>68 条</b></div>\n'
     '      <div><span>评审规则</span><b>46 行</b></div>')
once('本页负责把已落盘的证据、页面布局与合规约束讲清楚。<b>不是已实现的业务系统，不是验收结论。</b>',
     '本页负责把已落盘的证据、页面布局、<b>业务术语与专家评审规则资产</b>讲清楚。<b>不是已实现的业务系统，不是验收结论；规则台账不是可执行规则引擎。</b>')
once('读数截至 2026-11-14 13:09（GMT+8），来自',
     '资产增补 2026-11-14 13:25 / 索引活查 14:13:11（GMT+8，解析·向量·全文·图谱均 155 全绿），资产来自 V5 真跑答案与调研报告；原始读数来自')
once('<div><span>图谱 ACTIVE</span><b>106 / 155</b></div>',
     '<div><span>图谱 ACTIVE</span><b>155 / 155</b></div>')

# ------------------------------------------------- 2b. 14:13 索引全绿复核（V7.2，不涂改历史快照）
once('          <tr><td>文档解析</td><td>106 COMPLETE / 49 RUNNING</td><td>服务端仍在收敛，不把半绿说成全绿</td></tr>',
     '          <tr><td>文档解析</td><td>106 COMPLETE / 49 RUNNING（12:58 快照）</td><td>14:13:11 复跑活查已 <b>155 COMPLETE</b>；保留原始快照，不把历史半绿涂改成全绿</td></tr>')
once('          <tr><td>图谱索引</td><td><b>106 ACTIVE / 32 RUNNING / 17 PENDING</b></td><td><b>未全绿</b> → 所有结论标注「基于向量 + 全文，图谱能力未验证」</td></tr>',
     '          <tr><td>图谱索引</td><td><b>106 ACTIVE / 32 RUNNING / 17 PENDING</b>（12:58 快照）</td><td>14:13:11 已 <b>155 ACTIVE 全绿</b>；但 8 题答案产出在收敛前、<b>未跑 A5「+图谱」对照轮</b> → 答案口径仍是「基于向量 + 全文」，<b>图谱增强效果未验证</b>，不因索引全绿倒推</td></tr>')
once('        <div class="note warn"><b>必须并列的一句话：</b>图谱还没收敛完，所以今天所有答案都是「向量 + 全文」口径，图谱增强效果<b>没有验证</b>，不承诺。</div>',
     '        <div class="note ok"><b>演示时必须并列的一句话（14:13 口径）：</b>四类索引现在都是 <b>155 全绿</b>；但今天展示的 8 题答案全部产出在图谱收敛之前，且没有跑「+图谱」对照轮，所以<b>索引全绿 ≠ 图谱增强效果已验证</b>。答案口径仍是「基于向量 + 全文」，效果不承诺；A5 对照轮是后续补做项，不是本次演示结论。</div>')
once('        <div class="note"><b>快照之外的实时读数：</b>13:06:20 复跑只读活查脚本 <code>sgcc_status_check.py</code> → 解析 <b>112 COMPLETE / 43 RUNNING</b>，图谱 <b>112 ACTIVE / 32 RUNNING / 11 PENDING</b>。服务端持续收敛，本页数字是 12:58 快照；<b>演示时以脚本实时读数为准，照数说</b>，不改本页快照冒充实时。</div>',
     '        <div class="note"><b>演示前最后一次活查（14:13:11，GMT+8）：</b><code>sgcc_status_check.py</code> → 文档 <b>155</b>、解析 <b>155 COMPLETE</b>、向量 <b>155 ACTIVE</b>、全文 <b>155 ACTIVE</b>、图谱 <b>155 ACTIVE</b>，<b>四类全绿</b>。上方表格是 12:58 / 13:06 的历史快照轨迹，<b>刻意保留不涂改</b>；现场以演示前复跑的实时读数为准，照数说。</div>')
once('          <li>图谱未收敛时统一标注「基于向量 + 全文，图谱能力未验证」</li>',
     '          <li>索引状态与结论口径分列：四类全绿也<b>不倒推</b>「图谱增强已验证」；答案按「基于向量 + 全文」口径标注</li>')

# ---------------------------------------------------------------- 3. nav 三个页签
once('      <div class="ttl" style="margin-top:10px">合规</div>',
     '      <div class="ttl" style="margin-top:10px">业务资产（13:25 增补）</div>\n'
     '      <button class="tab" data-p="b1">B1 业务术语库<small>68 条 · 按 P1–P9 痛点分组</small></button>\n'
     '      <button class="tab" data-p="b2">B2 专家评审规则库<small>46 行原文 · 12 条省侧参考位</small></button>\n'
     '      <button class="tab" data-p="b3">B3 业务闭环判定<small>能闭什么 / 不能闭什么</small></button>\n'
     '      <div class="ttl" style="margin-top:10px">合规</div>')

# ---------------------------------------------------------------- 4. 三个 section
SECTIONS = r'''
      <!-- B1 业务术语库 -->
      <section class="page" id="b1">
        <div class="ph"><div><h2>B1 · 业务术语库</h2><p>从国网物资采购部门「解决痛点」的角度组织：术语 → 同义/易混 → 关联痛点 → 业务含义 → demo 用法 → 证据状态 → AI 禁做。</p></div><span class="tag cand">68 条 · G1–G10</span></div>
        <div class="note"><b>术语是检索扩词、提示词约束与页面字段，不因入库而获得判定权。</b>证据标记：【A】政策原文｜【B】公开披露｜【C】二手待核｜【T】本轮真跑/样本原文｜【H】顾问整理｜【P】厂商能力声明。<b>【C】【H】类不得当作已核实事实对客引用。</b></div>
        <div class="note ok"><b>为什么按痛点分组：</b>物资部门不会问「什么叫否决情形」，会问「同一批次两版文件打架谁说了算」「专家尺度不一怎么查」。因此本库用 P1–P9 痛点做检索入口，演示时可从客户的一句话痛点反查术语，再落到 P3/P4 的证据页。</div>
        <div class="assetbar">
          <input id="termQ" placeholder="搜术语 / 同义词 / 业务含义 / 痛点编号，例如：伪命中、资格预审、P9" autocomplete="off">
          <label>分组</label><select id="termG"><option value="">全部 10 组</option></select>
          <span class="cnt" id="termCount">—</span>
        </div>
        <table>
          <tr><th style="width:15%">术语</th><th style="width:15%">同义 / 易混</th><th style="width:7%">痛点</th><th style="width:25%">物资部门视角含义</th><th style="width:18%">demo 内用法</th><th style="width:8%">证据</th><th style="width:12%">AI 禁做</th></tr>
          <tbody id="termBody"></tbody>
        </table>
        <div class="note warn"><b>与 V6 故意失败题的呼应：</b>「技术得分」在正文出现 3 次，命中它只是<b>术语伪命中</b>（T48），不等于库里有打分记录（T60）。术语库把这两个词并列登记，就是为了让 AI 不拿「评分标准说明」凑答案。</div>
        <div class="note">机器可读资产：<code>国网Demo_业务术语库_V1.json</code>；平台侧已上传 <code>sgcc-bid-review-glossary-rules</code>（Skill <code>skil3c96316cf7960d9a3ab5</code>，v1，已启用，<b>未挂载到任何 Agent</b>，未在问答中验证效果）。</div>
      </section>

      <!-- B2 专家评审规则库 -->
      <section class="page" id="b2">
        <div class="ph"><div><h2>B2 · 专家评审规则库</h2><p>把真实样本第三章「评标办法前附表之二·初步评审标准」的否决情形表逐行维护成可检索、可核对、可维护的规则台账。</p></div><span class="tag real">46 行 · V5 真跑原文</span></div>
        <div class="note"><b>来源（不是编的）：</b><code>sgcc_l1_results.json → V5</code>（turn <code>turn2b0c5bc86a956549</code>，192.9 s / 72 条摘录 / 13,472 字符）逐条回读「否决情形」表 46 行；适用 152507（14 标包）与 1525K1（4 标包，含资格预审/后审双版）共 18 个标包采购文件，同表同文，<b>第 46 行按版本不同</b>。</div>
        <div class="note bad"><b><code>executable = false</code>：</b>本台账是<b>规则证据</b>，不是可执行规则引擎。命中只产 <code>CANDIDATE · 候选待核</code>；<b>自动否决 / 判定违规 / 赋分 / 定标 / 代签一律禁止</b>。46 行为 AI 逐条回读的原文摘录，<b>尚未经业务方对照原文核对</b>。</div>
        <div class="assetbar">
          <input id="ruleQ" placeholder="搜规则 ID / 原文关键词，例如：保证金、签章、业绩、不平衡报价" autocomplete="off">
          <label>类别</label><select id="ruleC"><option value="">全部 4 类</option></select>
          <span class="cnt" id="ruleCount">—</span>
        </div>
        <table>
          <tr><th style="width:14%">规则 ID</th><th style="width:4%">行</th><th style="width:12%">类别 / 子项</th><th style="width:40%">否决事项（原文逐字，点击展开）</th><th style="width:9%">状态</th><th style="width:21%">AI 可做 / 禁做 · 确认角色</th></tr>
          <tbody id="ruleBody"></tbody>
        </table>
        <h3>省侧专家评审规则 · 扩展位（12 条，<b>参考位，不是已入库规则</b>）</h3>
        <div class="note warn">下列为各单位<b>自行披露的公开实践</b>，本轮<b>未取得任何省公司正式规则原文</b>，因此一律标 <code>REFERENCE_ONLY</code>，不进可执行规则集、不参与检索命中、不参与任何结论。须业务方提供规则文本与适用批次并人工确认后，才允许入库。</div>
        <table>
          <tr><th style="width:10%">单位</th><th style="width:34%">规则资产形态 / 做法</th><th style="width:14%">披露规模</th><th style="width:9%">证据</th><th style="width:15%">本 demo 状态</th><th style="width:18%">说明</th></tr>
          <tbody id="provBody"></tbody>
        </table>
        <div class="note">规则库全字段（章节、代表文件、来源、状态机、版本差异、确认角色、4 项待办）见 <code>国网Demo_专家评审规则库_V1.json</code>。V5 第二部分「正文 10 余处否决条款」、第三部分版本差异、第四/五部分待澄清与候选待核项<b>已定位但未逐条结构化，本轮不预编</b>。</div>
      </section>

      <!-- B3 业务闭环判定 -->
      <section class="page" id="b3">
        <div class="ph"><div><h2>B3 · 业务闭环判定（术语与规则入库后）</h2><p>主公令「可以实现业务闭环」的落点：把能闭的一段讲实，把不能闭的一段讲清，避免用合规红线换演示效果。</p></div><span class="tag human">口径判定</span></div>
        <h3>本轮新增资产闭合了哪一段</h3>
        <table>
          <tr><th>新增资产</th><th>真实状态</th><th>闭合的动作</th><th>仍未闭的动作</th></tr>
          <tr><td><b>业务术语库 68 条</b></td><td>本地 JSON + 平台 Skill 已上传（v1 / enabled / 未挂 Agent）</td><td>客户痛点话术 → 业务术语 → 检索扩词 → 页面字段，<b>「听懂业务」这一段闭合</b></td><td>未在真实问答中验证效果；【C】【H】类术语待业务方确认</td></tr>
          <tr><td><b>专家评审规则 46 行</b></td><td>由 V5 真跑答案抽取，CANDIDATE，executable=false</td><td>结论 → 规则条款 → 原文位置，<b>「依据可查可核」这一段闭合（R2 由半闭进到可核级）</b></td><td>规则生效、命中判定、灰度回滚、规则版本与结论绑定</td></tr>
          <tr><td><b>省侧扩展位 12 条</b></td><td>REFERENCE_ONLY，未取得正式规则原文</td><td>把「按省公司本地化配置」的<b>路径与字段</b>留出</td><td>规则原文、适用批次、业务方确认 —— 一律未到位</td></tr>
          <tr><td><b>状态机 CANDIDATE → …</b></td><td>AI 只置 CANDIDATE；后三态只由人工置位</td><td>前端与规则库共用一套口径，<b>责任边界可视化</b></td><td>复核动作、会签、审计归档仍未实现</td></tr>
        </table>
        <h3>R1–R6 更新后状态（与 V1 矩阵对照）</h3>
        <table>
          <tr><th>环</th><th>V1 矩阵</th><th>现在</th><th>依据 / 仍缺</th></tr>
          <tr><td>R1 知识闭环</td><td>✅ 已闭</td><td><span class="pill ok">✅ 已闭</span></td><td>155 份入库、14:13:11 活查解析/向量/全文/图谱四类均 155 全绿；知识库文档数未因本次新增资产改变</td></tr>
          <tr><td>R2 审查闭环</td><td>🟡 半闭</td><td><span class="pill ok">🟢 证据与规则可核级闭合</span></td><td><b>本轮唯一实质升级</b>：8 题全量真跑 + 46 行规则台账 + 68 条术语；仍只出候选与依据</td></tr>
          <tr><td>R3 判定闭环</td><td>❌ 未闭</td><td><span class="pill bad">❌ 未闭，且本轮不闭</span></td><td>可执行规则引擎外置；<b>195 号文第十一条禁止 AI 自动否决</b></td></tr>
          <tr><td>R4 复核闭环</td><td>❌ 未闭</td><td><span class="pill bad">❌ 未闭</span></td><td>P5 只有闸门契约（A1 PASS），无复核工作台与签署动作</td></tr>
          <tr><td>R5 举证闭环</td><td>❌ 未闭</td><td><span class="pill warn">🟡 轨迹可举，档案未闭</span></td><td>turn / chat 事件轨迹可读；<code>admin audit list</code> exit 5，无业务操作级审计库</td></tr>
          <tr><td>R6 迭代闭环</td><td>🟡 半闭</td><td><span class="pill warn">🟡 半闭</span></td><td>8 题已落盘可作回归基线；<b>评测集未建</b>（见下方说明）</td></tr>
        </table>
        <div class="twocol">
          <div class="box real"><div class="h">✅ 可以说「实现了业务闭环」的范围</div><div class="m"><b>L1 demo 的标前体检业务闭环</b>：物资专责提出痛点 → 术语对齐 → 批次/标包定位 → 检索与回读原文 → 命中 46 行评审规则 → 出差异清单 / 待澄清事项表 → 全部标「候选待核」→ 交人工判定。<b>这条链今天能完整演示，且每一环都有真跑读数。</b></div></div>
          <div class="box"><div class="h">⛔ 不能说「闭环」的范围</div><div class="m">生产上线的责任链：规则生效与判定、专家复核会签、赋分计算、定标、审计归档。这不是能力缺口而是<b>政策红线</b>；若宣称已闭，等于宣称 AI 替代了招标人/评标委员会，会被合规部门当场问倒。</div></div>
        </div>
        <div class="note bad"><b>为什么不顺手建 Dataset 评测集：</b>评测集需要「参考答案」，而 8 题答案全是 <b>AI 自述、未经业务方对照原文核对</b>（G3 仍 1/3）。现在把 AI 答案写成标准答案，等于制造假绿基线。<b>本轮不建，等能判对错的对接人标注后再建。</b>这是主动的口径判定，不是漏做。</div>
        <div class="note ok"><b>收口一句话：</b>「术语让系统听懂物资部门的话，规则台账让每条结论能回到评标办法的原文；证据链与规则可核这一段今天闭环了，判定与签字始终留在招标人那边。」</div>
      </section>

'''
once('      <!-- GATE -->', SECTIONS + '      <!-- GATE -->')

# ---------------------------------------------------------------- 5. JS 数据与渲染
JS = r'''
  var ASSETS = __DATA__;
  function esc(v){return String(v==null?'':v).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');}
  function has(v,q){return String(v==null?'':v).toLowerCase().indexOf(q)>=0;}

  function fillSelect(id, values){
    var el=document.getElementById(id);
    values.forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;el.appendChild(o);});
  }
  fillSelect('termG', ASSETS.terms.map(function(t){return t.group;}).filter(function(v,i,a){return a.indexOf(v)===i;}));
  fillSelect('ruleC', ASSETS.rules.map(function(r){return r.category;}).filter(function(v,i,a){return a.indexOf(v)===i;}));

  function renderTerms(){
    var q=document.getElementById('termQ').value.trim().toLowerCase();
    var g=document.getElementById('termG').value;
    var rows=ASSETS.terms.filter(function(t){
      if(g && t.group!==g) return false;
      if(!q) return true;
      return [t.term,t.aliases,t.pain,t.meaning,t.demo_use,t.ai_cannot,t.id].some(function(x){return has(x,q);});
    });
    document.getElementById('termCount').textContent='显示 '+rows.length+' / '+ASSETS.terms.length+' 条';
    document.getElementById('termBody').innerHTML=rows.map(function(t){
      return '<tr><td><b>'+esc(t.term)+'</b><br><span class="small">'+esc(t.id)+'</span></td>'
        +'<td>'+esc(t.aliases)+'</td><td>'+esc(t.pain)+'</td><td>'+esc(t.meaning)+'</td>'
        +'<td>'+esc(t.demo_use)+'</td><td>'+esc(t.evidence)+'</td><td>'+esc(t.ai_cannot)+'</td></tr>';
    }).join('') || '<tr><td colspan="7" style="text-align:center;color:var(--faint);padding:18px">没有匹配项（空结果不写成「查到了」）</td></tr>';
  }

  function renderRules(){
    var q=document.getElementById('ruleQ').value.trim().toLowerCase();
    var c=document.getElementById('ruleC').value;
    var rows=ASSETS.rules.filter(function(r){
      if(c && r.category!==c) return false;
      if(!q) return true;
      return [r.rule_id,r.rule_text,r.category,r.subcategory,String(r.row)].some(function(x){return has(x,q);});
    });
    document.getElementById('ruleCount').textContent='显示 '+rows.length+' / '+ASSETS.rules.length+' 行';
    document.getElementById('ruleBody').innerHTML=rows.map(function(r){
      var txt=esc(r.rule_text);
      var brief=txt.length>52?txt.slice(0,52)+'…':txt;
      return '<tr><td><code>'+esc(r.rule_id)+'</code>'+(r.version_diff?'<br><span class="pill warn">双版差异</span>':'')+'</td>'
        +'<td>'+r.row+'</td><td>'+esc(r.category)+'<br><span class="small">'+esc(r.subcategory)+'</span></td>'
        +'<td><details class="rule"><summary>'+brief+'（点击展开原文）</summary><div class="full">'+txt+'</div></details></td>'
        +'<td><span class="pill cand">CANDIDATE</span><br><span class="small">候选待核</span></td>'
        +'<td><b>可做</b>：'+esc(r.ai_can)+'<br><b style="color:var(--bad)">禁做</b>：'+esc(r.ai_cannot)+'<br><span class="small">确认角色：'+esc(r.confirm_role)+'</span></td></tr>';
    }).join('') || '<tr><td colspan="6" style="text-align:center;color:var(--faint);padding:18px">没有匹配项</td></tr>';
  }

  document.getElementById('provBody').innerHTML=ASSETS.provinces.map(function(p){
    return '<tr><td><b>'+esc(p.unit)+'</b><br><span class="small">'+esc(p.id)+'</span></td>'
      +'<td>'+esc(p.practice)+'<br><span class="small">资产形态：'+esc(p.asset_form)+'</span></td>'
      +'<td>'+esc(p.disclosed_scale)+'</td><td>'+esc(p.evidence)+'</td>'
      +'<td><span class="pill warn">REFERENCE_ONLY</span><br><span class="small">'+esc(p.demo_status)+'</span></td>'
      +'<td>'+esc(p.note)+'</td></tr>';
  }).join('');

  ['termQ','termG'].forEach(function(id){document.getElementById(id).addEventListener(id==='termQ'?'input':'change',renderTerms);});
  ['ruleQ','ruleC'].forEach(function(id){document.getElementById(id).addEventListener(id==='ruleQ'?'input':'change',renderRules);});
  renderTerms(); renderRules();
'''
LIVE_HTML = r'''
        <div class="note" id="liveCard" style="margin-top:12px">
          <b>C8 实时取数 · 只经 fe-evidence-bridge</b>　<span id="liveState" class="pill warn">快照模式 · 桥接未连接</span>
          <div style="margin:9px 0">
            <button id="btnLive" type="button" style="font:inherit;font-size:11.5px;padding:6px 12px;border:1px solid var(--line2);border-radius:6px;background:#fff;color:var(--navy);cursor:pointer">刷新实时读数</button>
            <span class="small">　按钮只请求 127.0.0.1 桥接；桥接只调 apemind CLI 白名单只读命令，认证由 CLI 管。</span>
          </div>
          <div id="liveBody" class="small">未连接时此处不填任何数字；上方表格保持静态快照。</div>
        </div>
'''
LIVE_JS = r'''
  /* ---- C8 · 单一取数面：页面只 fetch 本地桥接，绝不直连 apemind.ai ---- */
  (function(){
    var BASE = location.protocol==='file:' ? 'http://127.0.0.1:8765' : '';
    var st=document.getElementById('liveState'), bd=document.getElementById('liveBody');
    if(!st||!bd) return;
    function esc(x){return String(x==null?'':x).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]});}
    function badge(t,ok){st.textContent=t;st.className=ok?'pill ok':'pill warn';}
    function get(u){return fetch(BASE+u,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('HTTP '+r.status);return r.json();});}
    function kv(o){return Object.keys(o).map(function(k){return esc(k)+' <b>'+esc(o[k])+'</b>';}).join('　｜　');}
    function render(status,allow,health){
      var c=status.data.counters;
      var rows=Object.keys(c).map(function(k){return '<tr><td><code>'+esc(k)+'</code></td><td>'+kv(c[k])+'</td></tr>';}).join('');
      bd.innerHTML='<div class="note ok"><b>桥接已连接 · 下列数字来自真实 CLI 调用，非页面预填</b><br>'
        +'CLI '+esc(health.data.cli_version)+' / allowlist '+esc(health.data.allowlist_version)
        +' / 版本一致 <b>'+esc(health.data.version_match)+'</b> / 账号 '+esc(health.data.account)
        +' / token 只在 CLI 侧，页面不持有</div>'
        +'<table><tr><th>CLI 原始状态字段</th><th>逐状态计数</th></tr>'+rows+'</table>'
        +'<div class="small">文档数 <b>'+status.data.documents+'</b> ｜ 分页 '+status.data.pages
        +' ｜ CLI request_id '+esc((status.data.cli_request_ids||[]).join(', '))
        +' ｜ 取数时间 '+esc(status.bridge.at)+'</div>'
        +'<div class="note"><b>单一取数面校验：</b>白名单 '+allow.data.command_count+' 条只读命令；禁止 '
        +esc(allow.data.forbidden_flags.join(' / '))+'；前端本页只 fetch 127.0.0.1 桥接，<b>不直连 apemind.ai</b>；'
        +'无通过 / 否决 / 赋分 / 定标控件；<code>--confirm</code> 永不自动拼接。</div>';
      badge('桥接已连接 · 实时读数',true);
    }
    var btn=document.getElementById('btnLive');
    if(btn) btn.addEventListener('click',function(){
      badge('正在经桥接取数…',false);
      Promise.all([get('/bridge/status'),get('/bridge/allowlist'),get('/bridge/health')])
        .then(function(r){render(r[0],r[1],r[2]);})
        .catch(function(e){badge('桥接未运行 · 静态快照模式',false);
          bd.innerHTML='<div class="note warn"><b>未连接（'+esc(e.message)+'）</b>：不填任何猜测数字，页面保持静态快照。启动命令 <code>python sgcc_bridge.py</code>，再用 <code>http://127.0.0.1:8765/</code> 打开本页。</div>';});
    });
    get('/bridge/health').then(function(h){
      if(h.data&&h.data.version_match) badge('桥接已连接 · 点「刷新实时读数」取数',true);
      else badge('桥接版本不一致 · 已阻断发问',false);
    }).catch(function(){badge('快照模式 · 桥接未连接',false);});
  })();
'''
JS = JS.replace('__DATA__', js_data) + '\n' + LIVE_JS
once('  var tid;\n  function toast(msg){', JS + '\n  var tid;\n  function toast(msg){')

# P1 section 内确定性插入实时卡片：不新增页签、不改动旧 12 页签结构
_i = s.index('<section class="page" id="p1">')
_j = s.index('</section>', _i)
s = s[:_j] + LIVE_HTML + s[_j:]

io.open(HTML_OUT, 'w', encoding='utf-8').write(s)

# ---------------------------------------------------------------- 6. 校验
tabs = re.findall(r'data-p="([^"]+)"', s)
pages = re.findall(r'<section class="page[^"]*" id="([^"]+)"', s)
buttons = re.findall(r'<button[^>]*>(.*?)</button>', s, re.S)
bad_btn = [re.sub(r'<[^>]+>', '', b).strip() for b in buttons
           if re.search(r'(通过|否决|赋分|定标)按钮|判定为|确认生效', re.sub(r'<[^>]+>', '', b))]
print('TABS', len(tabs), sorted(tabs))
print('PAGES', len(pages), sorted(pages))
print('TAB_PAGE_MATCH', sorted(tabs) == sorted(pages))
print('SECTION_BALANCE', s.count('<section'), s.count('</section>'))
print('BAD_BUTTONS', bad_btn)
for w in ('造船', '光明', '私有化', '信创'):
    print('FORBIDDEN_WORD', w, w in s)
print('ASSETS_IN_JS', 'var ASSETS =' in s, 'renderTerms()' in s)
print('SIZE_BYTES', len(s.encode('utf-8')))
