// 真浏览器核验：系统 Edge --headless=new + CDP，真导航 / 真点击 / 真输入 / 真截图
// 纪律：不用 DOM 桩、不用源码字符串匹配冒充渲染；先看 DOM 真变化再下结论。
// pass1（保留在 sgcc_console_realcheck_pass1.json）1 条 FAIL 根因：断言把 B2 页的
// "executable = false" 误当成 B3 页契约；源码核实该字串只在 b2 section，属断言写错页面，
// 非页面缺陷。pass2 把 B3 断言改回其真实契约（R1–R6 / 195 号文第十一条 / L1 demo 闭环），
// 并补一条 B2 红线字串检查，不删不改页面来迎合断言。
import { spawn } from 'node:child_process';
import { pathToFileURL } from 'node:url';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const BASE = 'c:/Users/linkz/WorkBuddy/PC办公';
const HTML = path.join(BASE, '国网Demo_演示控制台_V7.html');
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9223;
const PROFILE = path.join(os.tmpdir(), 'sgcc-cdp-' + Date.now());
const URL = pathToFileURL(HTML).href;

const edge = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=' + PORT, '--user-data-dir=' + PROFILE,
  '--window-size=1440,1000', 'about:blank'
], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = { started_at: new Date().toISOString(), url: URL, checks: [], errors: [], screenshot: null };

async function getTarget() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const list = await r.json();
      const page = list.find(t => t.type === 'page');
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
    setTimeout(() => { if (pending.has(id)) { pending.delete(id); reject(new Error('CDP timeout ' + method)); } }, 20000);
  });
}
async function evaluate(expression) {
  const r = await cmd('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error('JS exception: ' + (r.exceptionDetails.text || '') + ' ' + (r.exceptionDetails.exception?.description || ''));
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
    if (m.method === 'Runtime.exceptionThrown') out.errors.push('exception: ' + (m.params.exceptionDetails.text || ''));
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') out.errors.push('console.error: ' + m.params.args.map(a => a.value || a.description).join(' '));
    if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error') out.errors.push('log.error: ' + m.params.entry.text);
  };
  await cmd('Page.enable'); await cmd('Runtime.enable'); await cmd('Log.enable');

  // 真导航（不是同文档改 hash）
  await cmd('Page.navigate', { url: 'about:blank' });
  await sleep(300);
  await cmd('Page.navigate', { url: URL });
  for (let i = 0; i < 60; i++) {
    const ready = await evaluate('document.readyState==="complete" && document.querySelectorAll(".tab").length===12').catch(() => false);
    if (ready) break;
    await sleep(250);
  }
  check('真导航后页签数', await evaluate('document.querySelectorAll(".tab").length'), (await evaluate('document.querySelectorAll(".tab").length')) === 12);
  check('ASSETS 已载入', await evaluate('typeof ASSETS!=="undefined" ? [ASSETS.terms.length,ASSETS.rules.length,ASSETS.provinces.length].join("/") : "missing"'), (await evaluate('typeof ASSETS')) === 'object');
  check('初始 P0 可见', await evaluate('document.getElementById("p0").classList.contains("on")'), await evaluate('document.getElementById("p0").classList.contains("on")'));

  // 真点击 B1
  await evaluate('document.querySelector(\'[data-p="b1"]\').click()');
  await sleep(150);
  check('B1 真渲染并可见', await evaluate('document.getElementById("b1").classList.contains("on")'), await evaluate('document.getElementById("b1").classList.contains("on")'));
  const tRows = await evaluate('document.querySelectorAll("#termBody tr").length');
  check('B1 术语表行数（70 条）', tRows, tRows === 70, 'rows=' + tRows);
  const tHead = await evaluate('document.querySelector("#termBody tr").innerText.slice(0,40)');
  check('B1 首行有真实中文术语', tHead, /[\u4e00-\u9fa5]/.test(tHead));
  // 真输入筛选
  await evaluate('var q=document.getElementById("termQ");q.value="伪命中";q.dispatchEvent(new Event("input",{bubbles:true}))');
  await sleep(120);
  const tq = await evaluate('[document.querySelectorAll("#termBody tr").length, document.getElementById("termCount").innerText, document.querySelector("#termBody tr").innerText.slice(0,30)]');
  check('B1 搜索「伪命中」真收敛', tq, tq[0] > 0 && tq[0] < 68 && /伪命中/.test(tq[2]));
  // 组筛选
  await evaluate('var q=document.getElementById("termQ");q.value="";q.dispatchEvent(new Event("input",{bubbles:true}));var g=document.getElementById("termG");g.value="G7 证据与溯源";g.dispatchEvent(new Event("change",{bubbles:true}))');
  await sleep(120);
  const tg = await evaluate('[document.querySelectorAll("#termBody tr").length, document.getElementById("termCount").innerText]');
  check('B1 组筛选 G7 真收敛', tg, tg[0] === 7);

  // 真点击 B2
  await evaluate('document.querySelector(\'[data-p="b2"]\').click()');
  await sleep(150);
  const rRows = await evaluate('document.querySelectorAll("#ruleBody tr").length');
  check('B2 规则表行数', rRows, rRows === 46);
  const pRows = await evaluate('document.querySelectorAll("#provBody tr").length');
  check('B2 省侧扩展位行数', pRows, pRows === 12);
  check('B2 CANDIDATE 状态数', await evaluate('document.querySelectorAll("#ruleBody .pill.cand").length'), (await evaluate('document.querySelectorAll("#ruleBody .pill.cand").length')) === 46);
  // 真输入规则搜索
  await evaluate('var q=document.getElementById("ruleQ");q.value="不平衡报价";q.dispatchEvent(new Event("input",{bubbles:true}))');
  await sleep(120);
  const rq = await evaluate('[document.querySelectorAll("#ruleBody tr").length, document.getElementById("ruleCount").innerText, document.querySelector("#ruleBody tr").innerText.includes("双版差异")]');
  check('B2 搜索「不平衡报价」命中第46行', rq, rq[0] >= 1 && rq[2] === true);
  // 真展开 details
  await evaluate('var d=document.querySelector("#ruleBody details");d.open=true');
  const full = await evaluate('document.querySelector("#ruleBody details .full").innerText.length');
  check('B2 原文可展开', full, full > 20);
  const b2red = await evaluate('document.getElementById("b2").innerText.includes("executable = false")');
  check('B2 标出 executable=false 红线', b2red, b2red === true);
  // 截图前恢复全量规则库，避免把「搜索后 1 行」当成默认视图
  await evaluate('var q=document.getElementById("ruleQ");q.value="";q.dispatchEvent(new Event("input",{bubbles:true}))');
  await sleep(120);
  const restored = await evaluate('document.querySelectorAll("#ruleBody tr").length');
  check('B2 清空搜索后恢复 46 行', restored, restored === 46);
  // 截图 B2
  const shot = await cmd('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  const shotPath = path.join(BASE, '国网Demo_演示控制台_B2规则库_真浏览器截图.png');
  fs.writeFileSync(shotPath, Buffer.from(shot.data, 'base64'));
  out.screenshot = shotPath;
  check('B2 真浏览器截图', fs.statSync(shotPath).size, fs.statSync(shotPath).size > 10000);

  // 真点击 B3
  await evaluate('document.querySelector(\'[data-p="b3"]\').click()');
  await sleep(120);
  const b3 = await evaluate('(function(){var e=document.getElementById("b3"),t=e.innerText;return [e.classList.contains("on"),t.includes("R1–R6"),t.includes("195 号文第十一条"),t.includes("L1 demo 的标前体检业务闭环")];})()');
  check('B3 闭环页真渲染（按 B3 真实契约断言）', b3, b3.every(Boolean));

  // 零回归：原有 9 页签逐个真点击
  const legacy = ['p0','p1','p2','p3','p4','p5','p6','p7','gate'];
  const regress = [];
  for (const k of legacy) {
    await evaluate(`document.querySelector('[data-p="${k}"]').click()`);
    const ok = await evaluate(`document.getElementById("${k}").classList.contains("on") && document.getElementById("${k}").innerText.length>80`);
    regress.push([k, ok]);
  }
  check('旧 9 页签零回归', regress, regress.every(x => x[1]));

  // 静态禁区：新增页不得有判定按钮、全站不发网络请求
  const buttons = await evaluate('Array.from(document.querySelectorAll("button")).map(b=>b.innerText.replace(/\\s+/g," ")).filter(t=>/通过按钮|否决按钮|赋分按钮|定标按钮|判定为|确认生效/.test(t))');
  check('无自动判定按钮', buttons, buttons.length === 0);
  // 桥接未启动时，页面按设计去探活 127.0.0.1:8765 会失败并被浏览器记一条 log.error。
  // 这是「未连接则保持静态快照」的既定降级，不是缺陷；单列为预期内，其余错误照常报。
  const EXPECTED = /ERR_CONNECTION_REFUSED|127\.0\.0\.1:8765/;
  out.expected_errors = out.errors.filter(e => EXPECTED.test(e));
  out.page_errors = out.errors.filter(e => !EXPECTED.test(e));
  check('桥接未连时的探活失败已归入预期内', out.expected_errors.length + '/' + out.errors.length,
    out.expected_errors.length <= 3, JSON.stringify(out.expected_errors).slice(0, 200));
  const liveTxt = await evaluate('document.getElementById("liveState").innerText + " || " + document.getElementById("liveBody").innerText.slice(0,160)');
  check('未连桥接时保持快照模式且不填猜测数字', liveTxt, /快照模式|未连接/.test(liveTxt) && !/\d{3,}/.test(liveTxt.replace(/127\.0\.0\.1:8765/g, '')), liveTxt.slice(0, 160));
  check('JS 异常与 console.error', out.page_errors.length, out.page_errors.length === 0, out.page_errors.join(' | ').slice(0, 300));

  const failed = out.checks.filter(c => !c.pass);
  out.result = failed.length === 0 ? 'PASS' : 'FAIL';
  out.finished_at = new Date().toISOString();
  fs.writeFileSync(path.join(BASE, 'sgcc_console_realcheck.json'), JSON.stringify(out, null, 2));
  console.log('\nRESULT', out.result, 'checks', out.checks.length, 'failed', failed.length);
} catch (e) {
  out.result = 'ERROR'; out.error = String(e && e.stack || e);
  fs.writeFileSync(path.join(BASE, 'sgcc_console_realcheck.json'), JSON.stringify(out, null, 2));
  console.error('ERROR', out.error);
} finally {
  try { ws && ws.close(); } catch (e) {}
  try { edge.kill('SIGKILL'); } catch (e) {}
  await sleep(300);
  try { fs.rmSync(PROFILE, { recursive: true, force: true }); } catch (e) {}
}
process.exit(out.result === 'PASS' ? 0 : 1);
