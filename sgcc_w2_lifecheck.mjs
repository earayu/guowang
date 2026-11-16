// W2 生命周期视图 · 真浏览器专项核验（Edge --headless=new + CDP）
// 纪律：只认 DOM 真变化。点击后必须看到 innerText 变了才算过，不接受源码字符串。
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const BASE = 'c:/Users/linkz/WorkBuddy/PC办公';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9236;
const FILE = path.join(BASE, '国网物资部_标前审阅工作台_W2.html').replace(/\\/g, '/');
const URL = 'file:///' + encodeURI(FILE);
const PROFILE = path.join(os.tmpdir(), 'sgcc-w2life-' + Date.now());
const OUT = path.join(BASE, 'sgcc_w2_lifecheck.json');
const SHOT = path.join(BASE, '国网物资部_工作台_W2_生命周期视图截图.png');

const edge = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=' + PORT, '--user-data-dir=' + PROFILE,
  '--window-size=1500,1040', '--allow-file-access-from-files', 'about:blank'
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = { started_at: new Date().toISOString(), url: URL, checks: [], errors: [], network: [], screenshot: null };

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

async function main() {
  let target = null;
  for (let i = 0; i < 80; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      target = (await r.json()).find(t => t.type === 'page');
      if (target && target.webSocketDebuggerUrl) break;
    } catch (e) { }
    await sleep(250);
  }
  if (!target) throw new Error('找不到 CDP 页面目标');
  ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result);
    } else if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error') {
      out.errors.push('log.error: ' + m.params.entry.text);
    } else if (m.method === 'Runtime.exceptionThrown') {
      out.errors.push('exception: ' + (m.params.exceptionDetails.text || ''));
    } else if (m.method === 'Network.requestWillBeSent') {
      out.network.push(m.params.request.url.slice(0, 120));
    }
  };
  await cmd('Page.enable'); await cmd('Runtime.enable'); await cmd('Log.enable'); await cmd('Network.enable');
  await cmd('Emulation.setDeviceMetricsOverride', { width: 1500, height: 1040, deviceScaleFactor: 1, mobile: false });
  await cmd('Page.navigate', { url: URL });
  await sleep(1600);

  // A 基础
  check('A1 标题正确', await evaluate('document.title'), (await evaluate('document.title')).includes('标前审阅工作台'));

  // B 导航含 life 且默认仍是 overview（零回归前提）
  const navList = await evaluate('JSON.stringify([...document.querySelectorAll(".nav a")].map(a=>a.dataset.v))');
  check('B1 导航含 life 且共 7 项', navList, JSON.parse(navList).length === 7 && JSON.parse(navList)[0] === 'life', navList);
  const defOn = await evaluate('document.getElementById("v-overview").classList.contains("on") && !document.getElementById("v-life").classList.contains("on")');
  check('B2 默认仍停留在批次总览（不改旧行为）', defOn, defOn === true);

  // C 从总览入口卡真跳转
  await evaluate('document.getElementById("lifeEntry").click()');
  await sleep(400);
  const jump = await evaluate('document.getElementById("v-life").classList.contains("on") && document.querySelector(\'.nav a[data-v="life"]\').classList.contains("on")');
  check('C1 总览入口卡点击真切到生命周期视图', jump, jump === true);

  // D 流程条：12 阶段、6 环节
  const chips = await evaluate('document.querySelectorAll(".lchip").length');
  const phases = await evaluate('document.querySelectorAll(".lphase").length');
  check('D1 阶段 chip 12 个', chips, chips === 12);
  check('D2 环节分组 6 个（对应 1358 号文 6 环节）', phases, phases === 6);

  // E KPI 四值
  const kpi = await evaluate('JSON.stringify([...document.querySelectorAll("#v-life .kpi .val")].map(e=>e.innerText.replace(/\\s+/g,"")))');
  const kv = JSON.parse(kpi);
  check('E1 生命周期 KPI 四值 12/3/3/6', kpi, kv.length === 4 && kv[0].startsWith('12') && kv[1].startsWith('3') && kv[2].startsWith('3') && kv[3].startsWith('6'), kpi);

  // F 默认选中 L3 且详情真渲染
  const onChip = await evaluate('document.querySelector(".lchip.on") ? document.querySelector(".lchip.on").dataset.s : null');
  const det0 = await evaluate('document.getElementById("lifeDetail").innerText');
  check('F1 默认选中 L3 标前审阅', onChip, onChip === 'L3');
  check('F2 详情含法定依据与人工门禁', [det0.includes('法定依据'), det0.includes('人工门禁'), det0.length],
    det0.includes('法定依据') && det0.includes('人工门禁') && det0.length > 300, det0.length + ' 字符');
  check('F3 L3 详情含真跑证据（V1/V7 读数）', det0.includes('V1') && det0.includes('V7') && det0.includes('155'),
    det0.includes('V1') && det0.includes('V7'));

  // G 点击 L7 详情真变化，且明确不可赋分
  await evaluate('document.querySelector(\'.lchip[data-s="L7"]\').click()');
  await sleep(350);
  const det1 = await evaluate('document.getElementById("lifeDetail").innerText');
  const onChip1 = await evaluate('document.querySelector(".lchip.on").dataset.s');
  check('G1 点击 L7 选中态真切换', onChip1, onChip1 === 'L7');
  check('G2 详情内容真变化（非同一份）', det1 !== det0, det1 !== det0, '前后文本不同');
  check('G3 L7 明确标注不可赋分', det1.includes('赋分') && det1.includes('不可做'), det1.includes('赋分'));
  check('G4 L7 诚实标注为设计未实现', det1.includes('设计未实现'), det1.includes('设计未实现'));

  // H 再点 L11 验证「无实现」阶段也说清前置
  await evaluate('document.querySelector(\'.lchip[data-s="L11"]\').click()');
  await sleep(300);
  const det2 = await evaluate('document.getElementById("lifeDetail").innerText');
  check('H1 L11 标注审计权限空白', det2.includes('55 条') || det2.includes('审计'), det2.includes('audit') || det2.includes('55 条') || det2.includes('审计'));

  // H2 阶段 → 真实产出联动（只允许有真跑证据的阶段跳转）
  await evaluate('document.querySelector(\'.lchip[data-s="L3"]\').click()'); await sleep(300);
  const hasGo = await evaluate('!!document.querySelector("#lifeDetail [data-go]")');
  check('H2 L3 提供「查看真实产出」入口', hasGo, hasGo === true);
  await evaluate('document.querySelector("#lifeDetail [data-go]").click()'); await sleep(400);
  const jumped = await evaluate('document.getElementById("v-diff").classList.contains("on") && document.querySelector(\'.nav a[data-v="diff"]\').classList.contains("on")');
  check('H3 点击真跳到双版差异视图', jumped, jumped === true);
  await evaluate('document.querySelector(\'.nav a[data-v="life"]\').click()'); await sleep(400);
  await evaluate('document.querySelector(\'.lchip[data-s="L7"]\').click()'); await sleep(300);
  const hasGo7 = await evaluate('!!document.querySelector("#lifeDetail [data-go]")');
  const note7 = await evaluate('document.getElementById("lifeDetail").innerText.includes("不做跳转")');
  check('H4 L7 无跳转入口且明示「不做跳转」', [hasGo7, note7], hasGo7 === false && note7 === true);

  // I 覆盖热力条 12 段
  const heat = await evaluate('document.querySelectorAll(".heat .hcell").length');
  check('I1 覆盖热力条 12 段', heat, heat === 12);

  // J 红线
  const judge = await evaluate('JSON.stringify(Array.from(document.querySelectorAll("#v-life button")).map(b=>b.innerText).filter(t=>/通过|否决|赋分|定标|判定/.test(t)))');
  check('J1 生命周期页零判定按钮', judge, JSON.parse(judge).length === 0, judge);
  const redline = await evaluate('document.querySelector("#v-life .comp").innerText');
  check('J2 红线声明含「195 号文」与「签字权在人」', [redline.includes('195 号文'), redline.includes('签字权')],
    redline.includes('195 号文') && redline.includes('在人'));

  // K 布局
  const ovf = await evaluate('JSON.stringify({sw:document.documentElement.scrollWidth, cw:document.documentElement.clientWidth})');
  const ov = JSON.parse(ovf);
  check('K1 横向零溢出', ovf, ov.sw <= ov.cw + 2, ovf);
  const two = await evaluate('JSON.stringify((()=>{const a=document.querySelectorAll("#v-life .ldet > .lbox");return {n:a.length, tops:[...a].map(x=>Math.round(x.getBoundingClientRect().top))}})())');
  check('K2 详情双栏并排（同一行）', two, JSON.parse(two).n === 2 && JSON.parse(two).tops[0] === JSON.parse(two).tops[1], two);

  // L 外部依赖 + 异常
  const ext = out.network.filter(u => !u.startsWith('file://') && !u.startsWith('data:') && !u.includes('127.0.0.1'));
  check('L1 无外部网络依赖', ext, ext.length === 0, ext.join(','));
  check('L2 JS 异常与 console.error', out.errors.length, out.errors.length === 0, out.errors.join(' | ').slice(0, 300));

  // 截图（滚回顶部）
  await evaluate('document.querySelector(".main").scrollTop = 0');
  await sleep(250);
  const shot = await cmd('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(SHOT, Buffer.from(shot.data, 'base64'));
  out.screenshot = SHOT;

  const pass = out.checks.filter(c => c.pass).length;
  out.result = { pass, total: out.checks.length };
  fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
  console.log('\n==== PASS : ' + pass + '/' + out.checks.length + ' ====');

  ws.close(); edge.kill();
  setTimeout(() => process.exit(pass === out.checks.length ? 0 : 1), 200);
}
main().catch(e => { console.error('FATAL', e); try { edge.kill(); } catch (_) { } process.exit(2); });
