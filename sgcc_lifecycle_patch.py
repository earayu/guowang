# -*- coding: utf-8 -*-
"""
工作台 W1 → W2：新增「评审全生命周期闭环」视图。

原则：
  1. 不新增第三个文件做平行系统，直接升版工作台（W1 留档）。
  2. 默认视图仍是 overview，life 作为导航第一项 —— 保证旧 34 项核验零回归。
  3. 数据全部来自 国网Demo_评审全生命周期闭环资产_V1.json，不在页面里手写业务事实。
"""
import io, json, shutil

B = 'c:/Users/linkz/WorkBuddy/PC办公/'
SRC = B + '国网物资部_标前审阅工作台_W1.html'
DST = B + '国网物资部_标前审阅工作台_W2.html'

shutil.copyfile(SRC, DST)
s = io.open(DST, encoding='utf-8').read()

asset = json.load(io.open(B + '国网Demo_评审全生命周期闭环资产_V1.json', encoding='utf-8'))
stages = asset['stages']

# ---------------------------------------------------------------- 1. 导航
old_nav = '''  <nav class="nav">
    <div class="grp">审阅</div>
    <a class="on" data-v="overview">'''
new_nav = '''  <nav class="nav">
    <div class="grp">全流程</div>
    <a data-v="life">
      <svg class="ic" viewBox="0 0 16 16" fill="none"><circle cx="3.2" cy="8" r="1.7" stroke="currentColor" stroke-width="1.2"/><circle cx="8" cy="8" r="1.7" stroke="currentColor" stroke-width="1.2"/><circle cx="12.8" cy="8" r="1.7" stroke="currentColor" stroke-width="1.2"/><path d="M4.9 8h1.4M9.7 8h1.4" stroke="currentColor" stroke-width="1.2"/></svg>
      生命周期闭环
      <span class="cnt">12</span>
    </a>
    <div class="grp">审阅</div>
    <a class="on" data-v="overview">'''
assert s.count(old_nav) == 1, 'nav anchor not found'
s = s.replace(old_nav, new_nav, 1)

# ---------------------------------------------------------------- 2. 总览页加入口
old_h1 = '''      <div class="h1">批次总览</div>
      <div class="sub">1525K1 · 国网湖北电力 2025 年物资类用户受托工程框架协议公开招标 · 4 个标包（含资格预审 / 资格后审双版）</div>'''
new_h1 = '''      <div class="h1">批次总览</div>
      <div class="sub">1525K1 · 国网湖北电力 2025 年物资类用户受托工程框架协议公开招标 · 4 个标包（含资格预审 / 资格后审双版）</div>

      <div class="card" id="lifeEntry" style="margin-bottom:18px;border-color:#CFE0F5;background:linear-gradient(90deg,#FBFDFF,#FFFFFF);cursor:pointer">
        <div style="display:flex;align-items:center;gap:12px">
          <div style="flex:1">
            <div style="font-size:13px;font-weight:500;margin-bottom:3px">这套东西站在评审全流程的哪一段？</div>
            <div class="mini">按 1358 号文 6 环节拆成 12 个阶段，逐段标注 AI 能做什么、不能做什么、谁在哪儿签字。<b style="color:var(--ink)">12 段中只有 3 段有真跑证据</b>。</div>
          </div>
          <span class="tag t-blu" style="flex:0 0 auto">查看全生命周期 →</span>
        </div>
      </div>'''
assert s.count(old_h1) == 1, 'overview h1 anchor not found'
s = s.replace(old_h1, new_h1, 1)

# ---------------------------------------------------------------- 3. life 视图
STATUS_UI = {
    'VERIFIED': ('t-grn', '真跑验证'),
    'ASSET_ONLY': ('t-amb', '资产就绪'),
    'DESIGN_ONLY': ('t-gry', '设计未实现'),
}
PHASES = ['标前', '招标', '开评标', '定标', '履约', '监督']

# 流程条：按环节分组
flow = ''
for ph in PHASES:
    items = [x for x in stages if x['phase'] == ph]
    chips = ''
    for x in items:
        cls, _ = STATUS_UI[x['demo_status']]
        chips += ('<div class="lchip" data-s="%s"><b>%s</b><span>%s</span><i class="%s"></i></div>'
                  % (x['id'], x['id'], x['name'].split(' · ')[0], cls))
    flow += ('<div class="lphase"><div class="lph">%s</div><div class="lchips">%s</div></div>' % (ph, chips))

# 覆盖热力条
heat = ''
for x in stages:
    color = {'VERIFIED': 'var(--green)', 'ASSET_ONLY': 'var(--amber)', 'DESIGN_ONLY': '#D0D5DD'}[x['demo_status']]
    heat += ('<div class="hcell" title="%s %s" style="background:%s"></div>' % (x['id'], x['name'], color))

life_html = '''
    <!-- ============ 生命周期闭环 ============ -->
    <section class="view" id="v-life">
      <div class="h1">评审全生命周期闭环</div>
      <div class="sub">按 1358 号文 6 环节拆为 12 个可操作阶段 · 逐段标注 AI 能力、法定红线与人工签字点 · 依据 195 号文辅助性定位</div>

      <div class="row k4">
        <div class="card kpi"><div class="lab">阶段总数</div><div class="val num">12<small>段</small></div><div class="foot">标前 3 · 招标 1 · 开评标 3 · 定标 2 · 履约 1 · 监督 2</div></div>
        <div class="card kpi"><div class="lab">有真跑证据</div><div class="val num" style="color:var(--green)">3<small>段</small></div><div class="foot">L3 标前审阅 · L4 澄清 · L6 初评</div></div>
        <div class="card kpi"><div class="lab">资产就绪未跑通</div><div class="val num" style="color:var(--amber)">3<small>段</small></div><div class="foot">有术语/规则，缺真实过程数据</div></div>
        <div class="card kpi"><div class="lab">设计未实现</div><div class="val num" style="color:var(--ink3)">6<small>段</small></div><div class="foot">评分 · 报告核验 · 定标 · 履约 · 监督 · 归档</div></div>
      </div>

      <div class="st">全流程位置<span class="ln"></span><span class="hint">点任一阶段看该段 AI 能力与门禁</span></div>
      <div class="card">
        <div class="lflow">__FLOW__</div>
        <div class="heat">__HEAT__</div>
        <div style="display:flex;gap:18px;flex-wrap:wrap;margin-top:14px;padding-top:12px;border-top:1px solid var(--line2)">
          <span class="mini"><i class="dot" style="background:var(--green)"></i>真跑验证 · 有 turn 与读数可查</span>
          <span class="mini"><i class="dot" style="background:var(--amber)"></i>资产就绪 · 未跑端到端</span>
          <span class="mini"><i class="dot" style="background:#D0D5DD"></i>设计未实现 · 平台侧无实现</span>
        </div>
      </div>

      <div id="lifeDetail"></div>

      <div class="comp">
        <svg width="14" height="14" viewBox="0 0 14 14" fill="none"><circle cx="7" cy="7" r="5.8" stroke="#B54708" stroke-width="1.1"/><path d="M7 4v3.6" stroke="#B54708" stroke-width="1.1" stroke-linecap="round"/><circle cx="7" cy="9.8" r=".65" fill="#B54708"/></svg>
        <span>本图为<b>能力边界说明</b>，不是系统设计承诺。195 号文第十一条：AI 为辅助性工具，不改变法定责任——<b>判定权、赋分权、定标权、签字权一律在人</b>。12 段中只有 3 段有真跑证据，其余为资产级或设计级，<b>不得表述为"全流程已实现"</b>。</span>
      </div>
    </section>

'''

# ---------------------------------------------------------------- 4. 样式
life_css = '''
/* lifecycle */
.lflow{display:flex;gap:10px;flex-wrap:wrap}
.lphase{flex:1 1 150px;min-width:140px}
.lph{font-size:11px;color:var(--ink3);letter-spacing:.3px;margin-bottom:7px;padding-bottom:5px;border-bottom:1px dashed var(--line)}
.lchips{display:flex;flex-direction:column;gap:5px}
.lchip{display:flex;align-items:center;gap:6px;font-size:11.5px;padding:4px 7px;border:1px solid var(--line);border-radius:4px;cursor:pointer;background:#fff;transition:.12s;position:relative}
.lchip:hover{border-color:var(--brand);background:var(--brandsoft)}
.lchip.on{border-color:var(--brand);background:var(--brandsoft);box-shadow:inset 2px 0 0 var(--brand)}
.lchip b{font-weight:500;color:var(--ink3);font-size:10.5px;font-variant-numeric:tabular-nums}
.lchip span{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:var(--ink2)}
.lchip i{width:6px;height:6px;border-radius:50%;flex:0 0 6px;display:inline-block}
.lchip i.t-grn{background:var(--green)}.lchip i.t-amb{background:var(--amber)}.lchip i.t-gry{background:#D0D5DD}
.heat{display:flex;gap:3px;margin-top:14px}
.heat .hcell{flex:1;height:8px;border-radius:2px}
.dot{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:middle}
.ldet{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}
@media(max-width:1100px){.ldet{grid-template-columns:1fr}}
.lbox{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:14px 16px}
.lbox h4{font-size:12.5px;font-weight:500;margin:0 0 10px;color:var(--ink)}
.lkv{display:grid;grid-template-columns:76px 1fr;gap:4px 10px;font-size:11.5px;line-height:1.75}
.lkv .k{color:var(--ink3)}
.lkv .v{color:var(--ink2)}
.llist{margin:0;padding-left:15px;font-size:11.5px;line-height:1.85;color:var(--ink2)}
.llist li{margin-bottom:2px}
.llist.can li::marker{color:var(--green)}
.llist.cannot li::marker{color:var(--red)}
.lgate{background:var(--brandsoft);border:1px solid #CFE0F5;border-radius:4px;padding:8px 11px;font-size:11.5px;color:#1D4A7A;line-height:1.7;margin-top:10px}
.lnote{background:#FFFDF7;border:1px solid #F2E3BF;border-radius:4px;padding:8px 11px;font-size:11.5px;color:#7A5B18;line-height:1.7;margin-top:10px}
'''

s = s.replace('</style>', life_css + '</style>', 1)

# ---------------------------------------------------------------- 5. 插入 section
anchor = '''    <!-- ============ 总览 ============ -->'''
assert s.count(anchor) == 1, 'overview comment anchor not found'
s = s.replace(anchor, life_html.replace('__FLOW__', flow).replace('__HEAT__', heat) + anchor, 1)

# ---------------------------------------------------------------- 6. JS
js_data = json.dumps({
    'stages': [{
        'id': x['id'], 'name': x['name'], 'phase': x['phase'], 'legal': x['legal'],
        'roles': x['roles'], 'artifacts': x['artifacts'], 'pains': x['pains'],
        'can': x['ai_can'], 'cannot': x['ai_cannot'], 'gate': x['gate'],
        'status': x['demo_status'], 'evidence': x['evidence'],
        'note': x['demo_note'], 'platform': x['platform'],
    } for x in stages]
}, ensure_ascii=False)

life_js = '''
// ---------------- lifecycle ----------------
const LIFE = __DATA__;
// 仅这三段有真跑产出，才允许跳转；其余不挂假入口
const LIFE_LINK = {L3:'diff', L4:'clarify', L6:'rules'};
const LSTAT = {VERIFIED:['t-grn','真跑验证'], ASSET_ONLY:['t-amb','资产就绪'], DESIGN_ONLY:['t-gry','设计未实现']};
function esc(t){return String(t).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');}
function renderLife(id){
  const x = LIFE.stages.find(s=>s.id===id) || LIFE.stages[2];
  const [cls,lab] = LSTAT[x.status];
  let h = '';
  h += '<div class="st">'+x.id+' · '+esc(x.name)+'<span class="ln"></span><span class="tag '+cls+'">'+lab+'</span></div>';
  h += '<div class="ldet">';
  // 左：事实
  h += '<div class="lbox"><h4>这一段在做什么</h4>';
  h += '<div class="lkv"><div class="k">法定依据</div><div class="v">'+x.legal.map(esc).join('<br>')+'</div>';
  h += '<div class="k">参与角色</div><div class="v">'+x.roles.map(esc).join(' · ')+'</div>';
  h += '<div class="k">产出物</div><div class="v">'+x.artifacts.map(esc).join(' · ')+'</div>';
  h += '<div class="k">对应痛点</div><div class="v">'+x.pains.map(esc).join(' · ')+'</div>';
  h += '<div class="k">平台支撑</div><div class="v">'+x.platform.map(esc).join(' · ')+'</div>';
  h += '</div>';
  h += '<div class="lgate"><b>人工门禁：</b>'+esc(x.gate)+'</div>';
  h += '</div>';
  // 右：AI 能力
  h += '<div class="lbox"><h4>AI 在这一段的能力边界</h4>';
  h += '<div class="mini" style="margin-bottom:4px">可做</div><ul class="llist can">'+x.can.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul>';
  h += '<div class="mini" style="margin:8px 0 4px">不可做</div><ul class="llist cannot">'+x.cannot.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul>';
  h += '</div>';
  h += '</div>';
  // 证据
  h += '<div class="lbox" style="margin-top:14px"><h4>本段证据与诚实标注</h4>';
  h += '<ul class="llist" style="margin-bottom:8px">'+x.evidence.map(t=>'<li>'+esc(t)+'</li>').join('')+'</ul>';
  h += '<div class="lnote">'+esc(x.note)+'</div>';
  const go = LIFE_LINK[x.id];
  if (go) {
    h += '<div style="margin-top:12px"><span class="tag t-blu" data-go="'+go+'" style="cursor:pointer;padding:4px 12px">查看本段真实产出 →</span></div>';
  } else {
    h += '<div class="mini" style="margin-top:12px">本段尚无真实产出，<b style="color:var(--ink)">不做跳转</b>——避免把设计当成果。</div>';
  }
  h += '</div>';
  document.getElementById('lifeDetail').innerHTML = h;
  document.querySelectorAll('#lifeDetail [data-go]').forEach(b=>{
    b.onclick=()=>{
      const t=b.dataset.go;
      document.querySelectorAll('.nav a').forEach(z=>z.classList.remove('on'));
      document.querySelector('.nav a[data-v="'+t+'"]').classList.add('on');
      document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
      document.getElementById('v-'+t).classList.add('on');
      document.querySelector('.main').scrollTop=0;
    };
  });
}
document.querySelectorAll('.lchip').forEach(c=>{
  c.onclick=()=>{
    document.querySelectorAll('.lchip').forEach(z=>z.classList.remove('on'));
    c.classList.add('on');
    renderLife(c.dataset.s);
  };
});
renderLife('L3');
document.querySelectorAll('.lchip').forEach(c=>{ if(c.dataset.s==='L3') c.classList.add('on'); });
document.getElementById('lifeEntry').onclick=()=>{
  document.querySelectorAll('.nav a').forEach(z=>z.classList.remove('on'));
  document.querySelector('.nav a[data-v="life"]').classList.add('on');
  document.querySelectorAll('.view').forEach(v=>v.classList.remove('on'));
  document.getElementById('v-life').classList.add('on');
  document.querySelector('.main').scrollTop = 0;
};
'''

js_data_block = life_js.replace('__DATA__', js_data)
old_js_anchor = "// nav\n"
assert s.count(old_js_anchor) == 1, 'js anchor not found'
s = s.replace(old_js_anchor, js_data_block + "\n// nav\n", 1)

io.open(DST, 'w', encoding='utf-8').write(s)
print('OK', DST, len(s.encode('utf-8')), 'bytes')
print('sections', s.count('<section class="view'), '| nav items', s.count('data-v="'))
