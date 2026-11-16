// C8 · 真浏览器核验：系统 Edge --headless=new + CDP
// 与 sgcc_console_realcheck.mjs 的区别：从 http://127.0.0.1:8765/ 真导航（不是 file://），
// 真点击实时按钮，监听 Network 域证明「页面只请求本地桥接、不直连 apemind.ai」。
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const BASE = 'c:/Users/linkz/WorkBuddy/PC办公';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9224;
const URL = 'http://127.0.0.1:8765/';
const PROFILE = path.join(os.tmpdir(), 'sgcc-c8-cdp-' + Date.now());
const OUT = path.join(BASE, 'sgcc_c8_realcheck.json');
const SHOT = path.join(BASE, '国网Demo_演示控制台_C8实时读数_真浏览器截图.png');

const edge = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=' + PORT, '--user-data-dir=' + PROFILE,
  '--window-size=1440,1000', 'about:blank'
], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = { started_at: new Date().toISOString(), url: URL, checks: [], errors: [], expected_rejections: [], network: [], screenshot: null };

async function getTarget() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const page = (await r.json()).find(t => t.type === 'page');
      if (page && page.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch (e) { /* not up yet */ }
    await sleep(250);
  }
  throw new Error('Edge CDP 未就绪');
}
let ws, seq = 0;
const pending = new Map();
function cmd(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++seq;
    pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error('CDP timeout ' + method)); } }, 30000);
  });
}
async function evaluate(expression) {
  const r = await cmd('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error('JS exception: ' + (r.exceptionDetails.text || ''));
  return r.result.value;
}
function check(name, value, pass, detail) {
  out.checks.push({ name, value, pass: !!pass, detail: detail || '' });
  console.log((pass ? 'PASS' : 'FAIL'), name, JSON.stringify(value), detail || '');
}

try {
  const wsUrl = await getTarget();
  ws = new WebSocket(wsUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
  ws.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id); pending.delete(m.id);
      m.error ? p.reject(new Error(JSON.stringify(m.error))) : p.resolve(m.result);
    }
    if (m.method === 'Network.requestWillBeSent') out.network.push(m.params.request.url);
    if (m.method === 'Runtime.exceptionThrown') out.errors.push('exception: ' + (m.params.exceptionDetails.text || ''));
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') out.errors.push('console.error: ' + m.params.args.map(a => a.value || a.description).join(' '));
    if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error') {
      const e = m.params.entry;
      const msg = 'log.error: ' + e.text + ' @ ' + (e.url || '');
      if ((e.url || '').includes('/bridge/invoke') && e.text.includes('403')) out.expected_rejections.push(msg);
      else out.errors.push(msg);
    }
  };
  await cmd('Page.enable'); await cmd('Runtime.enable'); await cmd('Log.enable'); await cmd('Network.enable');

  await cmd('Page.navigate', { url: 'about:blank' });
  await sleep(300);
  await cmd('Page.navigate', { url: URL });
  for (let i = 0; i < 60; i++) {
    const ready = await evaluate('document.readyState==="complete" && document.querySelectorAll(".tab").length===12').catch(() => false);
    if (ready) break;
    await sleep(250);
  }
  check('HTTP 同源真导航', await evaluate('location.protocol+"//"+location.host'), (await evaluate('location.protocol+"//"+location.host')) === 'http://127.0.0.1:8765');
  check('12 页签零回归', await evaluate('document.querySelectorAll(".tab").length'), (await evaluate('document.querySelectorAll(".tab").length')) === 12);
  await sleep(500);
  check('启动探测判定桥接已连接', await evaluate('document.getElementById("liveState").innerText'), (await evaluate('document.getElementById("liveState").innerText')).includes('桥接已连接'));

  // 真点击 P1 与实时按钮
  await evaluate('document.querySelector(\'[data-p="p1"]\').click()');
  await sleep(180);
  check('P1 页面真可见', await evaluate('document.getElementById("p1").classList.contains("on")'), await evaluate('document.getElementById("p1").classList.contains("on")'));
  await evaluate('document.getElementById("btnLive").click()');
  for (let i = 0; i < 80; i++) {
    const done = await evaluate('document.getElementById("liveBody").innerText.includes("CLI 原始状态字段")').catch(() => false);
    if (done) break;
    await sleep(250);
  }
  const body = await evaluate('document.getElementById("liveBody").innerText');
  check('实时读数真渲染（CLI v0.7.56）', body.includes('v0.7.56'), body.includes('v0.7.56'));
  check('实时读数含 155 份与四类 ACTIVE 155',
    [body.includes('155'), body.includes('ACTIVE'), body.includes('graph_index_status'), body.includes('COMPLETE')],
    body.includes('155') && body.includes('ACTIVE') && body.includes('graph_index_status') && body.includes('COMPLETE'));
  check('实时读数带 CLI request_id', /[0-9a-f]{28,}/.test(body), /[0-9a-f]{28,}/.test(body));
  check('徽标变为实时读数', await evaluate('document.getElementById("liveState").innerText'), (await evaluate('document.getElementById("liveState").innerText')).includes('实时读数'));

  // 浏览器侧真发一次越权请求，验证桥接拒绝（不是源码断言）
  const neg = await evaluate(`fetch('/bridge/invoke',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({path:'document list',args:['--confirm']})}).then(r=>r.status)`);
  check('前端越权试探被桥接 403 拒绝', neg, neg === 403);

  // 网络栈证据：页面只请求 127.0.0.1:8765
  const external = out.network.filter(u => !u.startsWith('http://127.0.0.1:8765') && !u.startsWith('about:') && !u.startsWith('data:'));
  check('浏览器网络栈无 apemind.ai 直连', external, external.length === 0, external.slice(0, 5).join(' | '));
  check('浏览器网络栈含桥接 status/allowlist/health',
    ['/bridge/status', '/bridge/allowlist', '/bridge/health'].map(p => out.network.some(u => u.includes(p))),
    ['/bridge/status', '/bridge/allowlist', '/bridge/health'].every(p => out.network.some(u => u.includes(p))));
  // 与旧 20 项核验同一语义：只查判定「动作」按钮，不把静态禁区页签的说明文字当控件
  const judgeBtns = await evaluate(`Array.from(document.querySelectorAll('button')).map(b=>b.innerText).filter(t=>/通过按钮|否决按钮|赋分按钮|定标按钮|判定为|确认生效/.test(t))`);
  check('无自动判定按钮（对齐旧核验语义）', judgeBtns, judgeBtns.length === 0);
  check('预期越权拒绝已单列（不计页面错误）', out.expected_rejections.length, out.expected_rejections.length === 1, out.expected_rejections.join(' | ').slice(0, 300));
  check('JS 异常与 console.error', out.errors.length, out.errors.length === 0, out.errors.join(' | ').slice(0, 300));

  await evaluate("document.getElementById('liveCard').scrollIntoView()");
  await sleep(300);
  const shot = await cmd('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  fs.writeFileSync(SHOT, Buffer.from(shot.data, 'base64'));
  out.screenshot = SHOT;
  check('真浏览器截图', fs.statSync(SHOT).size, fs.statSync(SHOT).size > 20000);

  const failed = out.checks.filter(c => !c.pass);
  out.result = failed.length === 0 ? 'PASS' : 'FAIL';
  out.failed = failed.length;
  console.log('\nRESULT', out.result, 'checks', out.checks.length, 'failed', failed.length);
} catch (e) {
  out.result = 'ERROR'; out.error = String(e && e.stack || e);
  console.log('ERROR', out.error);
} finally {
  fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
  try { edge.kill(); } catch (e) { /* ignore */ }
}
