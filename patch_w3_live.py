# -*- coding: utf-8 -*-
"""给 W3 评标工作台加「实时判定」入口：抽屉里一键现场跑 46 条。

设计取舍：
  - 不动 renderBidCase 内部逻辑，只在矩阵渲染完**之后**给每个格子补一层监听。
    原 onclick 先触发（渲染抽屉），新监听后触发（往抽屉里挂实时判定块），
    这样 W3 既有的快照展示零回归，实时能力是叠加而不是替换。
  - 实时块只认 BFF（127.0.0.1:8787）。拿不到就明说"没连上"，不回退成假结果。
  - 抽屉里写清两段来源：入参是哪一次现场抽取（run_id 来自页面数据），
    判定是此刻调用的平台函数。客户问"这是录好的还是现算的"，页面自己答得上来。

用法：python patch_w3_live.py   （幂等，可重复执行）
产出：国网物资部_评标辅助工作台_W3.html（就地打补丁）
"""
import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "国网物资部_评标辅助工作台_W3.html")
MARK = "/*__LIVE_JUDGE__*/"
ANCHOR = "renderBidCase();"

LIVE_JS = MARK + r"""
/* ================= 实时判定：一键调用平台函数 sgcc-rule-judge =================
   入参用页面里已落盘的现场抽取结果（judge_live_check.py 落的那一份），
   判定本身是此刻的 HTTP 调用，不预置任何结论。
   连不上 BFF 就照实说"没连上"——不拿快照充当实时结果。 */
/* 同源优先。file:// 双击 → 回落本机 8787；经隧道用域名打开 → 走相对路径。
   关键：客户浏览器里的 127.0.0.1 是他自己的笔记本，不是演示机。 */
const BFF_BASE = (function(){
  if(location.protocol === 'file:') return 'http://127.0.0.1:8787';
  if(!/^(127\.0\.0\.1|localhost|\[::1\])$/i.test(location.hostname)) return '';
  return location.port === '8787' ? '' : 'http://127.0.0.1:8787';
})();
/* 公网演示口令：?k= 只取一次，转存 sessionStorage，再把地址栏抹干净——
   客户投屏或截图时不该把口令一起带走。 */
const DEMO_K = (function(){
  let q = '';
  try{ q = new URLSearchParams(location.search).get('k') || ''; }catch(e){}
  if(q){
    try{ sessionStorage.setItem('demo_k', q); }catch(e){}
    try{ history.replaceState(null, '', location.pathname + location.hash); }catch(e){}
    return q;
  }
  try{ return sessionStorage.getItem('demo_k') || ''; }catch(e){ return ''; }
})();
function apiHeaders(extra){
  const h = Object.assign({}, extra || {});
  if(DEMO_K) h['X-Demo-Token'] = DEMO_K;
  return h;
}
/* 请求体一律走 ASCII 代号。cloudflared 在 h2→HTTP/1.1 转换时按字符数给
   Content-Length，中文 body 会被短读、残留字节串到下一个请求行（审计里抓过现场）。
   全 ASCII 的 body 从源头避开这个问题。 */
const CODE_ASCII = {'华中':'HZ','襄阳':'XY','宜昌':'YC','荆州':'JZ','黄石':'HS','恩施':'ES'};
let LIVE_CTX = null;
const LIVE_SEEN = {};

function mountLiveJudge(){
  if(!LIVE_CTX) return;
  const body = document.getElementById('dBody');
  if(!body || document.getElementById('liveJudge')) return;
  const wrap = document.createElement('div');
  wrap.id = 'liveJudge';
  wrap.style.cssText = 'margin-top:18px;border-top:1px dashed var(--line);padding-top:12px';
  wrap.innerHTML =
    '<div class="mini" style="margin-bottom:7px;line-height:1.7">' +
      '<b style="color:var(--ink)">实时判定</b> · 平台函数 sgcc-rule-judge<br>' +
      '<span style="color:var(--ink3)">入参＝该家现场抽取结果（'+esc(LIVE_CTX.runId||'—')+'）；判定＝此刻现算</span>' +
    '</div>' +
    '<button class="btn pri" id="btnLiveJudge" style="width:100%" disabled>检查判定服务…</button>' +
    '<div id="liveOut" class="mini" style="margin-top:10px;line-height:1.7"></div>';
  body.appendChild(wrap);
  const btn = document.getElementById('btnLiveJudge');
  const out = document.getElementById('liveOut');
  btn.onclick = runLiveJudge;
  if(LIVE_SEEN[LIVE_CTX.code]){
    btn.disabled = false; btn.textContent = '▶ 现场跑 46 条否决判定';
    renderLiveResult(LIVE_SEEN[LIVE_CTX.code]);
    return;
  }
  out.innerHTML = '<span style="color:var(--ink3)">正在确认判定服务…</span>';
  // 先探活：离线包拷到别人机器上时没有 BFF，按钮必须干脆置灰说清原因，
  // 而不是让人点一下再报错——那看起来像系统坏了，其实是这份页面本来就没接服务。
  fetch(BFF_BASE + '/api/health', {cache:'no-store', headers: apiHeaders()}).then(r=>{
    if(!r.ok) throw new Error('health ' + r.status);
    return r.json();
  }).then(()=>{
    btn.disabled = false;
    btn.textContent = '▶ 现场跑 46 条否决判定';
    out.innerHTML = '<span style="color:var(--ink3)">点上面的按钮，会真的走一次 HTTP：浏览器 → BFF → apemind CLI → 平台函数，约 2~4 秒。</span>';
  }).catch(()=>{
    btn.textContent = '实时判定：当前未连入系统';
    out.innerHTML = '<span style="color:var(--ink3)">这一份是离线页面，没有可连的判定服务。' +
      '格子里的结论是预计算快照，可照常查看算式与原文；要现场现算，请在有服务的机器上打开。</span>';
  });
}

async function runLiveJudge(){
  const out = document.getElementById('liveOut');
  const btn = document.getElementById('btnLiveJudge');
  const code = LIVE_CTX.code;
  btn.disabled = true;
  btn.style.opacity = .6;
  const t0 = performance.now();
  out.innerHTML = '<span style="color:var(--brand2)">调用中…</span>' +
    '<br><span style="color:var(--ink3)">POST '+(BFF_BASE||location.origin)+'/api/judge/by-code → 平台函数执行</span>';
  try{
    const once = async () => {
      const resp = await fetch(BFF_BASE + '/api/judge/by-code', {
        method: 'POST',
        headers: apiHeaders({'Content-Type': 'application/json'}),
        body: JSON.stringify({code: CODE_ASCII[code] || code})
      });
      let d = null;
      try{ d = await resp.json(); }catch(e){}
      if(!resp.ok){
        const err = new Error((d && (d.error || d.code)) || ('HTTP '+resp.status));
        err.status = resp.status;
        throw err;
      }
      if(!d || !d.judge) throw new Error('返回内容不完整');
      return d;
    };
    let data;
    try{
      data = await once();
    }catch(e1){
      // 公网链路上真出现过一次：隧道刚接上时首个 POST 被上游转成畸形请求，
      // 返回 400 且是 http.server 的 HTML 错误页。重试一次就好，不必让客户看见。
      if(e1.status && e1.status !== 400 && e1.status < 500) throw e1;
      out.innerHTML += '<br><span style="color:var(--ink3)">首次未成功，自动重试一次…</span>';
      await new Promise(r => setTimeout(r, 700));
      data = await once();
    }
    data._client_ms = Math.round(performance.now() - t0);
    LIVE_SEEN[code] = data;
    renderLiveResult(data);
  }catch(e){
    const local = location.protocol === 'file:' ||
                  /^(127\.0\.0\.1|localhost|\[::1\])$/i.test(location.hostname);
    out.innerHTML = '<span style="color:var(--red)">调用失败：'+esc(e.message)+'</span>' +
      '<br><span style="color:var(--ink3)">' +
      (local ? '检查 BFF 是否在跑（python sgcc_bff.py）。'
             : '演示服务可能已停止，或网络中断。') +
      '这一格现在没有实时结果，不拿快照补——补上去就等于说谎。</span>';
  }finally{
    btn.disabled = false;
    btn.style.opacity = 1;
  }
}

const LIVE_LABEL = {
  RESPONDED:     {t:'通过',   c:'t-grn', d:'判定式不成立，本条未触发'},
  NOT_RESPONDED: {t:'判否',   c:'t-red', d:'判定式成立，候选否决项'},
  UNCERTAIN:     {t:'证不足', c:'t-amb', d:'缺字段/基准未结构化，转澄清'},
  NEED_HUMAN:    {t:'人判',   c:'t-gry', d:'本路径不作机器判定'}
};

function renderLiveResult(data){
  const out = document.getElementById('liveOut');
  if(!out) return;
  const j = data.judge || {};
  const run = data.run || {};
  if(!j.rows){ out.innerHTML = '<span style="color:var(--red)">返回体里没有判定结果：'+esc(JSON.stringify(data).slice(0,200))+'</span>'; return; }
  const c = j.counts || {};
  const keyRows = [4,7,10,11,13,16,17,39];
  const ordered = j.rows.slice().sort((a,b)=>{
    const rank = {NOT_RESPONDED:0, RESPONDED:1, UNCERTAIN:2, NEED_HUMAN:3};
    return (rank[a.state]-rank[b.state]) || (a.row-b.row);
  });
  let h = '<div style="background:var(--bg2,#F6F8FB);border-radius:4px;padding:8px 10px;margin-bottom:8px">' +
    '<div><b style="color:var(--ink)">'+esc(j.bidder||'')+'</b> · 规则集 '+esc(j.rule_set||'')+'/'+esc(j.rule_set_sha||'')+'</div>' +
    '<div style="color:var(--ink3)">run ' + esc(String(run.run_id||'').slice(-12)) +
      ' · 函数 v'+esc(String(run.version)) + ' · 函数内 ' + (run.elapsed_ms!=null?run.elapsed_ms:'—') + ' ms' +
      ' · ' + ((data._source==='cache')
                ? '命中缓存（同输入 5 分钟内复用，未重算）'
                : '端到端 ' + (data.wall_ms!=null?data.wall_ms:'—') + ' ms · 现算') + '</div>' +
    '<div style="color:var(--ink2);margin-top:3px">共 '+j.total+' 条：通过 '+((c.RESPONDED)||0)+
      ' · 判否 '+((c.NOT_RESPONDED)||0)+' · 证不足 '+((c.UNCERTAIN)||0)+' · 人判 '+((c.NEED_HUMAN)||0)+'</div>' +
    '</div>';
  // 判否要说清"凭什么"：只给一句「判定式不成立」，客户第一反应就是「你凭什么」。
  // 把这条判定实际用到的字段值摆出来（税率 0.07 对法定集合 [0.13,0.09,…]），
  // 判否才有据可查，也经得起当场质疑。
  const fails = j.rows.filter(x=>x.state==='NOT_RESPONDED');
  if(fails.length){
    h += '<div style="background:#FEF3F2;border-left:2px solid var(--red);padding:7px 9px;margin-bottom:8px;line-height:1.65">';
    fails.forEach(f=>{
      h += '<div><b style="color:var(--red)">行'+f.row+' 判否</b> <span style="color:var(--ink3)">'+esc(f.rule_id)+'</span></div>';
      h += '<div style="color:var(--ink2)">'+esc(f.reason||'')+'</div>';
      const uf = (f.used_fields||[]).map(u=>u.field+' = '+String(u.value)).join('；');
      if(uf) h += '<div style="color:var(--ink3);word-break:break-all">依据字段：'+esc(uf.slice(0,220))+'</div>';
    });
    h += '</div>';
  }
  h += '<div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">';
  keyRows.forEach(k=>{
    const r = j.rows.filter(x=>x.row===k)[0];
    h += '<span class="tag '+(r?LIVE_LABEL[r.state].c:'t-gry')+'" style="cursor:default">行'+k+' '+(r?LIVE_LABEL[r.state].t:'—')+'</span>';
  });
  h += '</div>';
  h += '<div style="max-height:260px;overflow:auto;border:1px solid var(--line);border-radius:4px">' +
       '<table style="width:100%;font-size:11.5px"><tr style="background:var(--bg2,#F6F8FB)">' +
       '<th style="width:34px;text-align:left;padding:4px 6px">条</th>' +
       '<th style="width:52px;text-align:left;padding:4px 6px">结论</th>' +
       '<th style="text-align:left;padding:4px 6px">判据</th></tr>';
  ordered.forEach(r=>{
    const L = LIVE_LABEL[r.state] || {t:r.state,c:'t-gry'};
    const dim = r.state==='NEED_HUMAN' ? 'opacity:.62' : '';
    h += '<tr style="'+dim+';border-top:1px solid var(--line)">' +
         '<td style="padding:4px 6px;color:var(--ink3)">'+r.row+'</td>' +
         '<td style="padding:4px 6px"><span class="tag '+L.c+'" style="cursor:default">'+L.t+'</span></td>' +
         '<td style="padding:4px 6px" title="'+esc(r.rule_text||'')+'">'+esc(String(r.reason||'').slice(0,46))+'</td></tr>';
  });
  h += '</table></div>';
  h += '<div style="color:var(--ink3);margin-top:6px">按结论排序。鼠标悬停可看条款原文；判否只给候选项与依据，认定权在评标委员会。</div>';
  out.innerHTML = h;
}

document.querySelectorAll('#bidCaseTbl [data-c]').forEach(el=>{
  el.addEventListener('click', ()=>{
    const p = el.dataset.c.split(':');
    const r = BID_CASE.rows[parseInt(p[0],10)];
    if(!r) return;
    LIVE_CTX = {code:r.code, bidder:r.bidder, runId:r.runId, row:p[1]};
    mountLiveJudge();
  });
});
"""


def main():
    src = io.open(TARGET, encoding="utf-8").read()
    if MARK in src:
        # 幂等：先摘掉旧补丁，再按最新版本重打。
        # 补丁区间 = MARK 到原始锚点 "\n// diff tabs" 之前，摘除后页面回到补丁前状态。
        i = src.find(MARK)
        j = src.find("\n// diff tabs", i)
        if j < 0:
            raise SystemExit("找到旧补丁但找不到区间终点，请手工检查")
        src = src[:i] + src[j:]
        print("检测到旧补丁，已摘除")
    if ANCHOR not in src:
        raise SystemExit("找不到锚点 %r，页面结构变了，先别打补丁" % ANCHOR)
    src = src.replace(ANCHOR, ANCHOR + "\n" + LIVE_JS, 1)
    io.open(TARGET, "w", encoding="utf-8", newline="\n").write(src)
    print("已打补丁：%s" % os.path.basename(TARGET))
    print("按钮位置：「受审结果矩阵」任意格子 → 抽屉底部")


if __name__ == "__main__":
    main()
