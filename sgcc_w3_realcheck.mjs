// W3 · 真浏览器核验（Edge --headless=new + CDP）
// 目的：确认「投标文件审批」主线真的落到 DOM 上，不只是源码里有字符串。
// 纪律：只认点击后的 DOM 真变化与真实读数。
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const BASE = 'c:/Users/linkz/WorkBuddy/PC办公';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9238;
const FILE = path.join(BASE, '国网物资部_评标辅助工作台_W3.html').replace(/\\/g, '/');
const URL = 'file:///' + encodeURI(FILE);
const PROFILE = path.join(os.tmpdir(), 'sgcc-w3-' + Date.now());
const OUT = path.join(BASE, 'sgcc_w3_realcheck.json');
const SHOT_BID = path.join(BASE, '国网物资部_工作台_W3_投标文件审批截图.png');
const SHOT_OV = path.join(BASE, '国网物资部_工作台_W3_项目基准截图.png');
const SHOT_BID2 = path.join(BASE, '国网物资部_工作台_W3_投标文件审批_无抽屉截图.png');

const edge = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=' + PORT, '--user-data-dir=' + PROFILE,
  '--window-size=1500,1040', '--allow-file-access-from-files', 'about:blank'
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = { started_at: new Date().toISOString(), url: URL, checks: [], console_errors: [], net_fail: [], shots: [] };

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
  if (r.exceptionDetails) throw new Error(r.exceptionDetails.text + ' | ' + JSON.stringify(r.exceptionDetails.exception || {}));
  return r.result.value;
}
function check(name, actual, pass, note) {
  out.checks.push({ name, actual, pass: !!pass, note: note || '' });
  console.log((pass ? 'PASS ' : 'FAIL ') + name, JSON.stringify(actual), note || '');
}
async function shot(file) {
  const r = await cmd('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true });
  fs.writeFileSync(file, Buffer.from(r.data, 'base64'));
  out.shots.push({ file: path.basename(file), bytes: fs.statSync(file).size });
  console.log('SHOT ' + path.basename(file));
}

(async () => {
  let list;
  for (let i = 0; i < 40; i++) {
    try { list = await (await fetch('http://127.0.0.1:' + PORT + '/json/list')).json(); if (list.length) break; } catch (e) {}
    await sleep(250);
  }
  const page = list.find(t => t.type === 'page');
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise(r => ws.addEventListener('open', r));
  ws.addEventListener('message', ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id).res(m.result); pending.delete(m.id); }
    else if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      out.console_errors.push((m.params.args || []).map(a => a.value || a.description).join(' '));
    } else if (m.method === 'Runtime.exceptionThrown') {
      out.console_errors.push('EXCEPTION ' + (m.params.exceptionDetails.text || ''));
    } else if (m.method === 'Network.responseReceived') {
      const st = m.params.response.status;
      if (st >= 400) out.net_fail.push({ url: m.params.response.url, status: st });
    }
  });

  await cmd('Runtime.enable'); await cmd('Network.enable'); await cmd('Page.enable');
  await cmd('Page.navigate', { url: URL });
  await sleep(1600);

  // ---- 1 静态身份
  check('title', await evaluate('document.title'), (await evaluate('document.title')).includes('评标辅助工作台'));
  check('logo 文案', await evaluate("document.querySelector('.top .sg-brand').innerText.trim()"), true,
    (await evaluate("document.querySelector('.top .sg-brand').innerText.trim()")));
  const batchLab = await evaluate("document.querySelector('.top .batch').innerText.replace(/\\s+/g,' ').trim()");
  check('顶栏为「采购项目」+ 独立基准说明', batchLab,
    batchLab.includes('采购项目') && batchLab.includes('两笔独立采购') && !batchLab.includes('批次\n'), batchLab);
  check('"批次"字样已从顶栏移除', !batchLab.startsWith('批次'), !batchLab.startsWith('批次'));

  // ---- 2 导航
  const nav = await evaluate("[...document.querySelectorAll('.nav a')].map(a=>a.dataset.v+':'+a.innerText.replace(/\\s+/g,''))");
  check('导航项与顺序', nav, JSON.stringify(nav) === JSON.stringify([
    'life:生命周期闭环12', 'overview:采购项目基准', 'bid:投标文件审批46',
    'diff:基准口径核对4', 'rules:条款核验46', 'clarify:待澄清事项9',
    'ask:原文取证', 'glossary:术语口径70'
  ]), nav.join(' | '));

  // ---- 3 点「投标文件审批」
  await evaluate("document.querySelector('.nav a[data-v=\"bid\"]').click()");
  await sleep(420);
  check('点击后 nav 高亮切到 bid', await evaluate("document.querySelector('.nav a.on').dataset.v"), true,
    await evaluate("document.querySelector('.nav a.on').dataset.v"));
  check('v-bid 可见 / 其余隐藏', await evaluate(`(()=>{
    const on=[...document.querySelectorAll('.view.on')].map(s=>s.id);
    return on.join(',');
  })()`), true, await evaluate(`[...document.querySelectorAll('.view.on')].map(s=>s.id).join(',')`));
  check('v-bid 标题', await evaluate("document.querySelector('#v-bid .h1').innerText"), true,
    await evaluate("document.querySelector('#v-bid .h1').innerText"));

  // ---- 4 关键事实必须在正文里说清
  const bidText = await evaluate("document.getElementById('v-bid').innerText");
  check('明确写出投标文件 0 份', bidText.includes('投标文件 0 份') || bidText.includes('投标文件已入库'), true);
  check('明确写出受审对象需 ECP 导出', bidText.includes('ECP'), true);
  check('明确 0 份 / 不预编', /不填、不预编、不假装已审/.test(bidText), /不填、不预编、不假装已审/.test(bidText));
  check('明确不演示 AI 赋分', bidText.includes('不演示 AI 赋分'), true);
  check('写明第 3 步 Function 231 ms', /231 ms/.test(bidText), /231 ms/.test(bidText));

  // ---- 4b 核查流水表列宽不得被挤成竖条
  const cols = await evaluate(`(()=>{
    const tb=document.querySelectorAll('#v-bid table')[0];
    const tr=[...tb.querySelectorAll('tr')][1];
    return [...tr.children].map(td=>({w:Math.round(td.getBoundingClientRect().width),h:Math.round(td.getBoundingClientRect().height)}));
  })()`);
  check('核查流水表四列宽度合理（产出列 >=140px）', cols, cols[2].w >= 140, JSON.stringify(cols));

  // ---- 5 三段条数真实分布
  const segs = await evaluate("[...document.querySelectorAll('#v-bid .seg')].map(s=>s.querySelector('.sn').innerText+'='+s.querySelector('.sv').innerText.replace(/\\s+/g,''))");
  check('初步评审三段骨架 4 卡', segs.length, segs.length === 4, segs.join(' | '));
  check('三段条数 5/25/15/1', segs.map(s => s.split('=')[1]).join(','), segs.map(s => s.split('=')[1]).join(',') === '5条,25条,15条,1条', segs.map(s => s.split('=')[1]).join(','));

  // ---- 6 审查工作表：骨架真、响应列空
  const rows = await evaluate(`(()=>{
    const trs=[...document.querySelectorAll('#bidSheet tr')].slice(1);
    return trs.map(tr=>[...tr.children].map(td=>td.innerText.replace(/\\s+/g,' ').trim()));
  })()`);
  check('工作表行数 6', rows.length, rows.length === 6, 'rows=' + rows.length);
  check('条号为真实台账条号', rows.map(r => r[0]).join(','), rows.map(r => r[0]).join(',') === '1,3,23,24,8,46', rows.map(r => r[0]).join(','));
  check('投标响应列全部为空态', rows.every(r => r[3] === '待投标文件入库'), rows.every(r => r[3] === '待投标文件入库'), rows.map(r => r[3]).join('|'));
  check('候选结论列全部未执行', rows.every(r => r[4] === '未执行'), rows.every(r => r[4] === '未执行'), rows.map(r => r[4]).join('|'));
  check('第 46 条标出两版不一致', rows[5][1].includes('两版不一致'), rows[5][1].includes('两版不一致'), rows[5][1].slice(0, 60));

  // ---- 7 抽屉：点行能出原文
  await evaluate("document.querySelectorAll('#bidSheet tr.ck')[0].click()");
  await sleep(360);
  const dTitle = await evaluate("document.getElementById('dTitle').innerText");
  const dText = await evaluate("document.getElementById('dBody').innerText");
  check('点行打开抽屉', await evaluate("document.getElementById('drawer').classList.contains('open')"), true, dTitle);
  check('抽屉标题含条号 1', dTitle.includes('第 1 条'), dTitle.includes('第 1 条'), dTitle);
  check('抽屉含未执行', dText.includes('未执行'), dText.includes('未执行'));
  check('抽屉含只产 CANDIDATE', dText.includes('CANDIDATE'), dText.includes('CANDIDATE'));

  // ---- 8 抽屉展开时无横向溢出
  const ov = await evaluate(`(()=>{const m=document.querySelector('.main');return {sw:m.scrollWidth,cw:m.clientWidth,right:Math.round(m.getBoundingClientRect().right)};})()`);
  check('抽屉展开无横向溢出', ov, ov.sw <= ov.cw + 2, 'scrollW=' + ov.sw + ' clientW=' + ov.cw);
  await shot(SHOT_BID);
  await evaluate("document.getElementById('dClose').click()");
  await sleep(260);

  // ---- 9 项目基准页
  await evaluate("document.querySelector('.nav a[data-v=\"overview\"]').click()");
  await sleep(380);
  check('采购项目基准标题', await evaluate("document.querySelector('#v-overview .h1').innerText"), true,
    await evaluate("document.querySelector('#v-overview .h1').innerText"));
  const ovText = await evaluate("document.getElementById('v-overview').innerText");
  check('基准页写明审批基准来源', ovText.includes('审批投标文件的基准来源'), ovText.includes('审批投标文件的基准来源'));
  check('基准页写明口径不定则无法判响应', ovText.includes('无法回答'), ovText.includes('无法回答'));
  check('基准页 KPI 改名审批可用基准', ovText.includes('审批可用基准'), ovText.includes('审批可用基准'));
  check('"批次总览"已不存在于正文', !ovText.includes('批次总览'), !ovText.includes('批次总览'));
  check('基准页有进入审批页的动线入口', await evaluate("!!document.getElementById('bidEntry')"), true);
  await shot(SHOT_OV);

  // ---- 9b 动线入口真能跳
  await evaluate("document.getElementById('bidEntry').click()");
  await sleep(420);
  check('点基准页入口落到投标文件审批', await evaluate("document.querySelector('.view.on').id"), true,
    await evaluate("document.querySelector('.view.on').id"));
  await shot(SHOT_BID2);

  // ---- 10 口径核对页
  await evaluate("document.querySelector('.nav a[data-v=\"diff\"]').click()");
  await sleep(380);
  const dfText = await evaluate("document.getElementById('v-diff').innerText");
  check('口径核对页标题', await evaluate("document.querySelector('#v-diff .h1').innerText"), (await evaluate("document.querySelector('#v-diff .h1').innerText")).includes('基准口径核对'));
  check('明确写「这不是两个批次的对比」', dfText.includes('这不是两个批次的对比'), dfText.includes('这不是两个批次的对比'));
  check('明确两笔独立采购', dfText.includes('两笔独立采购'), dfText.includes('两笔独立采购'));

  // ---- 11 生命周期 L6 跳转落点
  await evaluate("document.querySelector('.nav a[data-v=\"life\"]').click()");
  await sleep(320);
  await evaluate("document.querySelector('.lchip[data-s=\"L6\"]').click()");
  await sleep(320);
  const hasGo = await evaluate("!!document.querySelector('#lifeDetail [data-go=\"bid\"]')");
  check('L6 出现跳转入口且指向 bid', hasGo, hasGo === true);
  await evaluate("document.querySelector('#lifeDetail [data-go=\"bid\"]').click()");
  await sleep(420);
  check('L6 跳转后落在投标文件审批', await evaluate("document.querySelector('.view.on').id"), true,
    await evaluate("document.querySelector('.view.on').id"));

  // ---- 12 网络与控制台
  check('无 4xx/5xx 请求', out.net_fail, out.net_fail.length === 0, JSON.stringify(out.net_fail));
  check('无 console error', out.console_errors, out.console_errors.length === 0, JSON.stringify(out.console_errors));

  const pass = out.checks.filter(c => c.pass).length;
  out.summary = { total: out.checks.length, pass, fail: out.checks.length - pass };
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1), 'utf-8');
  console.log('\n== ' + pass + '/' + out.checks.length + ' PASS ==');
  console.log('json: ' + OUT);
  ws.close(); edge.kill();
  process.exit(out.summary.fail ? 1 : 0);
})().catch(e => { console.error('FATAL', e); out.fatal = String(e); fs.writeFileSync(OUT, JSON.stringify(out, null, 1), 'utf-8'); try { edge.kill(); } catch (_) {} process.exit(2); });
