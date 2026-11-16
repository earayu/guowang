// W3 · 受审侧结果矩阵 · 真浏览器核验（Edge --headless=new + CDP）
// 只认点击后 DOM 的真实变化：矩阵行数、四色标签计数、抽屉里出现的真实金额、
// 以及控制台有没有报错。源码里有字符串不算通过。
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const BASE = 'c:/Users/linkz/WorkBuddy/PC办公';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9246;
const FILE = path.join(BASE, '国网物资部_评标辅助工作台_W3.html').replace(/\\/g, '/');
const URL = 'file:///' + encodeURI(FILE);
const PROFILE = path.join(os.tmpdir(), 'sgcc-bid-' + Date.now());
const OUT = path.join(BASE, 'sgcc_w3_bid_realcheck.json');
const SHOT = path.join(BASE, '国网物资部_工作台_W3_受审结果截图.png');

const edge = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=' + PORT, '--user-data-dir=' + PROFILE,
  '--window-size=1500,1100', '--allow-file-access-from-files', 'about:blank'
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = { started_at: new Date().toISOString(), url: URL, checks: [], console_errors: [] };
const add = (name, ok, detail) => { out.checks.push({ name, ok, detail }); };

let ws, seq = 0;
const pending = new Map();
function cmd(method, params = {}) {
  return new Promise((res, rej) => {
    const id = ++seq;
    pending.set(id, { res, rej });
    ws.send(JSON.stringify({ id, method, params }));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error('timeout ' + method)); } }, 30000);
  });
}
async function evaluate(expr) {
  const r = await cmd('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails).slice(0, 300));
  return r.result.value;
}

async function connect() {
  for (let i = 0; i < 40; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
      const page = list.find(t => t.type === 'page');
      if (page) {
        const WebSocket = (await import('node:worker_threads'), globalThis.WebSocket);
        ws = new WebSocket(page.webSocketDebuggerUrl);
        await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
        ws.onmessage = ev => {
          const m = JSON.parse(ev.data);
          if (m.id && pending.has(m.id)) { pending.get(m.id).res(m.result); pending.delete(m.id); }
        };
        return true;
      }
    } catch { }
    await sleep(250);
  }
  return false;
}

(async () => {
  try {
    if (!await connect()) throw new Error('CDP 连接失败');
    await cmd('Runtime.enable');
    await cmd('Page.enable');
    await cmd('Log.enable');
    ws.onmessage = (ev => {
      const m = JSON.parse(ev.data);
      if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
        out.console_errors.push(m.params.args.map(a => a.value || a.description).join(' '));
      }
      if (m.method === 'Runtime.exceptionThrown') {
        out.console_errors.push('EXCEPTION ' + JSON.stringify(m.params.exceptionDetails).slice(0, 200));
      }
      if (m.id && pending.has(m.id)) { pending.get(m.id).res(m.result); pending.delete(m.id); }
    });

    await cmd('Page.navigate', { url: URL });
    await sleep(2200);

    // 1. 切到「投标文件审批」
    const nav = await evaluate(`(()=>{
      const a=document.querySelector('.nav a[data-v="bid"]');
      if(!a) return 'no-nav';
      a.click(); return 'clicked';
    })()`);
    add('切到投标文件审批视图', nav === 'clicked', nav);
    await sleep(900);

    const visible = await evaluate(`document.querySelector('#v-bid').classList.contains('on') || getComputedStyle(document.querySelector('#v-bid')).display!=='none'`);
    add('视图已显示', visible === true, String(visible));

    // 2. 顶部说明块
    const warn = await evaluate(`(()=>{const e=document.querySelector('#v-bid .block-warn');return e?e.innerText.replace(/\\s+/g,' '):'';})()`);
    add('说明块写明已入库 5 份', /5 份受控合成投标包/.test(warn), warn.slice(0, 60));
    add('说明块写明合成数据', /合成演示数据/.test(warn), '');
    add('说明块不再写「0 份」空态', !/投标文件 0 份/.test(warn), '');

    // 3. KPI
    const kpi = await evaluate(`(()=>Array.from(document.querySelectorAll('#v-bid .card.kpi')).map(e=>e.innerText.replace(/\\s+/g,' ')))()`);
    add('KPI 4 张', kpi.length === 4, String(kpi.length));
    add('KPI 受审投标包=5', kpi.some(x => /受审投标包\s*5/.test(x)), kpi[1] || '');
    add('KPI 字段对位 55/55', kpi.some(x => /55\s*\/\s*55/.test(x)), kpi[2] || '');
    add('KPI 机器判定 7/25', kpi.some(x => /7\s*\/\s*25\s*条/.test(x)), kpi[3] || '');

    // 4. 矩阵结构
    const tbl = await evaluate(`(()=>{
      const t=document.getElementById('bidCaseTbl');
      if(!t) return null;
      const rows=Array.from(t.querySelectorAll('tr'));
      return {rows:rows.length, head:rows[0]?rows[0].children.length:0,
              body:rows.slice(1).map(r=>Array.from(r.children).map(c=>c.innerText.replace(/\\s+/g,' ').trim()))};
    })()`);
    add('矩阵表存在', !!tbl, tbl ? 'ok' : 'null');
    if (tbl) {
      // 投标人 + 剧本 + 7 条规则 + 判否 = 10 列
      add('表头 10 列（7 条规则）', tbl.head === 10, String(tbl.head));
      add('数据 5 行', tbl.rows === 6, String(tbl.rows));
      const body = tbl.body;
      add('5 家全在', body.length === 5, body.map(r => r[0]).join('|').slice(0, 80));
      const ruleCells = body.flatMap(r => r.slice(2, 9));
      const bad = ruleCells.filter(x => x.includes('判否')).length;
      const pass = ruleCells.filter(x => x.includes('通过')).length;
      add('判否 4 格（每家一条）', bad === 4, '判否=' + bad);
      add('通过 31 格（5×7-4）', pass === 31, '通过=' + pass);
      add('宜昌行10 标注超 1 条', body.some(r => r[0].includes('宜昌') && /超1条/.test(r[3])), '');
      add('襄阳行4 判否', body.some(r => r[0].includes('襄阳') && r[2].includes('判否')), '');
      add('荆州行16 判否', body.some(r => r[0].includes('荆州') && r[6].includes('判否')), '');
      add('黄石行17 判否', body.some(r => r[0].includes('黄石') && r[7].includes('判否')), '');
      // 新增的三列要真出结果，不能是「未跑」
      add('行11 报价算术全部出结论', body.every(r => r[4] && !r[4].includes('未跑')), '');
      add('行13 保证金全部出结论', body.every(r => r[5] && !r[5].includes('未跑')), '');
      add('行39 法人不重全部出结论', body.every(r => r[8] && !r[8].includes('未跑')), '');
    }

    // 4.5 无抽屉先截一张：抽屉会推挤主区，矩阵被挡住就看不到
    await evaluate(`(()=>{const g=document.getElementById('bidCaseTbl');
      if(g) g.scrollIntoView({block:'center'}); return 1;})()`);
    await sleep(500);
    const shotM = await cmd('Page.captureScreenshot', { format: 'png' });
    if (shotM.data) fs.writeFileSync(path.join(BASE,'国网物资部_工作台_W3_受审矩阵截图.png'), Buffer.from(shotM.data,'base64'));

    // 5. 点开宜昌行10 的格子，看抽屉里有没有真实金额
    const clickRes = await evaluate(`(()=>{
      const t=document.getElementById('bidCaseTbl');
      const rows=Array.from(t.querySelectorAll('tr')).slice(1);
      const yc=rows.find(r=>r.children[0].innerText.includes('宜昌'));
      if(!yc) return 'no-yichang';
      const tag=yc.children[3].querySelector('[data-c]');
      if(!tag) return 'no-tag';
      tag.click();
      return 'clicked';
    })()`);
    add('点开宜昌行10 格子', clickRes === 'clicked', clickRes);
    await sleep(600);

    const drawer = await evaluate(`(()=>{const d=document.getElementById('drawer');
      return d&&d.classList.contains('open')?d.innerText.replace(/\\s+/g,' '):'';})()`);
    add('抽屉已打开', drawer.length > 20, drawer.slice(0, 50));
    add('抽屉含超限物料号 100035912200010', drawer.includes('100035912200010'), '');
    add('抽屉含限价 4,533,100', /4,?533,?100/.test(drawer), '');
    add('抽屉含报价 4,600,000', /4,?600,?000/.test(drawer), '');
    add('抽屉含「超限」标记', drawer.includes('超限'), '');

    // 6. 卡字段清单
    const blocked = await evaluate(`(()=>{
      const cards=Array.from(document.querySelectorAll('#v-bid .card table'));
      const t=cards.find(x=>x.innerText.includes('缺的字段'));
      return t?t.innerText.replace(/\\s+/g,' '):'';
    })()`);
    add('卡字段清单已渲染', /bid\.price_total/.test(blocked), blocked.slice(0, 60));

    // 7. 46 条台账仍在
    const sheet = await evaluate(`(()=>{const t=document.getElementById('bidSheet');
      return t?t.querySelectorAll('tr').length:0;})()`);
    add('审查工作表 6 行台账仍在', sheet === 7, '行数=' + sheet);

    // 8. 截图
    const shot = await cmd('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
    if (shot.data) { fs.writeFileSync(SHOT, Buffer.from(shot.data, 'base64')); out.shot = SHOT; }

    add('无控制台错误', out.console_errors.length === 0, out.console_errors.slice(0, 2).join(' | '));
  } catch (e) {
    out.fatal = String(e && e.stack || e).slice(0, 500);
  } finally {
    out.finished_at = new Date().toISOString();
    const ok = out.checks.filter(c => c.ok).length;
    out.summary = { total: out.checks.length, ok, failed: out.checks.length - ok };
    fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
    console.log('='.repeat(70));
    for (const c of out.checks) {
      console.log((c.ok ? 'PASS ' : 'FAIL ') + c.name + (c.ok ? '' : '  ← ' + String(c.detail).slice(0, 90)));
    }
    console.log('='.repeat(70));
    console.log(`${ok}/${out.checks.length} 通过` + (out.fatal ? '  致命：' + out.fatal : ''));
    try { edge.kill(); } catch { }
    process.exit(ok === out.checks.length && !out.fatal ? 0 : 1);
  }
})();
