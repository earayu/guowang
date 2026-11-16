// W1 工作台 · 真浏览器核验：系统 Edge --headless=new + CDP
// 纪律：不用 DOM 桩、不用源码字符串匹配冒充渲染；先看 DOM 真变化再下结论。
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';

const BASE = 'c:/Users/linkz/WorkBuddy/PC办公';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9231;
// 目标文件可切换（W1 基线 / W2 升版），避免为通过而改断言数字
const TARGET = process.env.WB ? process.env.WB : '国网物资部_标前审阅工作台_W1.html';
const TAG = process.env.TAG ? process.env.TAG : 'w1';
const EXPECT_VIEWS = process.env.VIEWS ? parseInt(process.env.VIEWS, 10) : 6;
const FILE = path.join(BASE, TARGET).replace(/\\/g, '/');
const URL = 'file:///' + encodeURI(FILE);
const PROFILE = path.join(os.tmpdir(), 'sgcc-w1-cdp-' + Date.now());
const OUT = path.join(BASE, 'sgcc_' + TAG + '_realcheck.json');
const SHOT = path.join(BASE, '国网物资部_工作台_' + TAG.toUpperCase() + '_真浏览器截图.png');
const SHOT2 = path.join(BASE, '国网物资部_工作台_' + TAG.toUpperCase() + '_证据抽屉截图.png');

const edge = spawn(EDGE, [
  '--headless=new', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-port=' + PORT, '--user-data-dir=' + PROFILE,
  '--window-size=1500,1040', '--allow-file-access-from-files', 'about:blank'
], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
const out = { started_at: new Date().toISOString(), url: URL, checks: [], errors: [], network: [], screenshot: null, screenshot2: null };

async function getTarget() {
  for (let i = 0; i < 60; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${PORT}/json/list`);
      const page = (await r.json()).find(t => t.type === 'page');
      if (page && page.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch (e) { /* not up */ }
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
  };
  await cmd('Page.enable'); await cmd('Runtime.enable'); await cmd('Network.enable');
  await cmd('Page.navigate', { url: URL });
  await sleep(1400);

  // A 页面加载
  check('A1 标题正确', await evaluate('document.title'), (await evaluate('document.title')).includes('标前审阅工作台'));
  // innerText 只返回可见文本（首屏为总览视图），故按可见语义断言；另用 textContent 证明全部视图均在 DOM
  const visLen = await evaluate('document.body.innerText.length');
  const allLen = await evaluate('document.body.textContent.length');
  const hasBiz = await evaluate('["1525K1","候选待核","待澄清","155"].every(k=>document.getElementById("v-overview").innerText.includes(k))');
  check('A2 首屏可见正文已渲染', visLen, visLen > 800, visLen + ' 字符（可见）');
  check('A3 全部视图均在 DOM（非空白/懒加载失败）', allLen, allLen > 20000, allLen + ' 字符（全量）');
  check('A4 首屏含关键业务词', hasBiz, hasBiz === true, '1525K1 / 候选待核 / 待澄清 / 155');

  // B 导航
  const navN = await evaluate('document.querySelectorAll(".nav a").length');
  check('B1 导航项数量', navN, navN === EXPECT_VIEWS, '期望 ' + EXPECT_VIEWS);
  const viewN = await evaluate('document.querySelectorAll(".view").length');
  check('B2 视图数量', viewN, viewN === EXPECT_VIEWS, '与导航一一对应，期望 ' + EXPECT_VIEWS);
  const navMatch = await evaluate('JSON.stringify([...document.querySelectorAll(".nav a")].map(a=>a.dataset.v)) === JSON.stringify([...document.querySelectorAll(".view")].map(v=>v.id.replace("v-","")))');
  check('B3 导航与视图 id 全匹配', navMatch, navMatch === true);

  // C 总览 KPI
  const kpi = await evaluate('[...document.querySelectorAll("#v-overview .kpi .val")].map(e=>e.innerText.replace(/\\s/g,""))');
  check('C1 总览 KPI 四值', kpi, kpi.length === 4 && kpi[0].startsWith('155') && kpi[1].startsWith('18') && kpi[2].startsWith('46') && kpi[3].startsWith('9'));
  const stage = await evaluate('document.querySelectorAll("#v-overview .stage .s").length');
  check('C2 审阅链路六段', stage, stage === 6);

  // D 切到双版差异
  await evaluate('document.querySelector(\'[data-v="diff"]\').click()');
  await sleep(280);
  const diffOn = await evaluate('document.getElementById("v-diff").classList.contains("on")');
  check('D1 双版差异视图真切换', diffOn, diffOn === true);
  const vsCards = await evaluate('document.querySelectorAll("#v-diff .vcard").length');
  const vsBytes = await evaluate('document.getElementById("v-diff").innerText.includes("9,706,361") && document.getElementById("v-diff").innerText.includes("9,763,974")');
  check('D2 两版文件卡与字节数', [vsCards, vsBytes], vsCards === 2 && vsBytes === true);
  const dRows0 = await evaluate('document.querySelectorAll("#diffBody tr").length');
  check('D3 型式试验维度行数', dRows0, dRows0 >= 4, dRows0 + ' 行（含表头）');

  // 切 tab 看是否真重渲染
  const preSnap = await evaluate('document.getElementById("diffBody").innerText.slice(0,80)');
  await evaluate('document.querySelector(\'[data-tab="2"]\').click()');
  await sleep(250);
  const postSnap = await evaluate('document.getElementById("diffBody").innerText.slice(0,80)');
  const tabOn = await evaluate('document.querySelector(\'[data-tab="2"]\').classList.contains("on")');
  check('D4 Tab 切换真重渲染', [tabOn, preSnap !== postSnap], tabOn === true && preSnap !== postSnap, '业绩页与型式试验页内容不同');

  // 点击"查看原文"打开抽屉
  await evaluate('document.querySelector("#diffBody [data-ev]").click()');
  await sleep(300);
  const drawerOpen = await evaluate('document.getElementById("drawer").classList.contains("open")');
  const drawerHas = await evaluate('document.getElementById("dBody").innerText.length');
  check('D5 点击依据抽屉真打开且有内容', [drawerOpen, drawerHas], drawerOpen === true && drawerHas > 120, drawerHas + ' 字符');
  // 抽屉打开时主区必须让位（否则正好遮住对比页右列），且不得撑出横向溢出
  const pushState = await evaluate(`(()=>{
    const m=document.querySelector('.main');
    return JSON.stringify({
      pushed:m.classList.contains('pushed'),
      padR:getComputedStyle(m).paddingRight,
      sw:document.documentElement.scrollWidth,
      cw:document.documentElement.clientWidth
    });
  })()`);
  const ps = JSON.parse(pushState);
  check('D5b 抽屉打开时主区让位且零溢出', pushState, ps.pushed === true && parseInt(ps.padR) >= 420 && ps.sw <= ps.cw + 2, pushState);
  const shot2 = await cmd('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(SHOT2, Buffer.from(shot2.data, 'base64'));
  out.screenshot2 = SHOT2;
  await evaluate('document.getElementById("dClose").click()');
  await sleep(200);
  check('D6 抽屉可关闭', await evaluate('document.getElementById("drawer").classList.contains("open")'), (await evaluate('document.getElementById("drawer").classList.contains("open")')) === false);

  // E 条款核验
  await evaluate('document.querySelector(\'[data-v="rules"]\').click()');
  await sleep(280);
  const ruleRows = await evaluate('document.querySelectorAll("#ruleTable tr").length');
  check('E1 规则表 46 行', ruleRows, ruleRows === 47, (ruleRows - 1) + ' 条 + 表头');
  const ruleIds = await evaluate('document.querySelectorAll("#ruleTable td:first-child").length');
  check('E2 规则编号列', ruleIds, ruleIds === 46);
  const gw046 = await evaluate('document.getElementById("ruleTable").innerText.includes("GW-HB-FJ-046")');
  check('E3 末条规则在位（非截断）', gw046, gw046 === true);
  // 分类筛选真过滤
  await evaluate('document.querySelector(\'[data-rtab="资格评审"]\').click()');
  await sleep(220);
  const zgRows = await evaluate('document.querySelectorAll("#ruleTable tr").length - 1');
  check('E4 资格评审筛选真过滤', zgRows, zgRows === 25, zgRows + ' 条');
  await evaluate('document.querySelector(\'[data-rtab="all"]\').click()');
  await sleep(180);
  // 点规则开抽屉
  await evaluate('document.querySelector("#ruleTable tr.ck").click()');
  await sleep(280);
  const rDrawer = await evaluate('document.getElementById("dBody").innerText');
  check('E5 规则抽屉含可做/不可做边界', rDrawer.includes('系统可做') && rDrawer.includes('系统不可做'), rDrawer.includes('系统可做'));
  await evaluate('document.getElementById("dClose").click()');
  await sleep(150);

  // F 待澄清
  await evaluate('document.querySelector(\'[data-v="clarify"]\').click()');
  await sleep(280);
  const clRows = await evaluate('document.querySelectorAll("#clarifyTable tr").length - 1');
  check('F1 待澄清 9 项', clRows, clRows === 9, clRows + ' 项');
  const clMissing = await evaluate('document.getElementById("clarifyTable").innerText.includes("仍缺文件")');
  check('F2 含"仍缺文件"列', clMissing, clMissing === true);

  // G 问答页
  await evaluate('document.querySelector(\'[data-v="ask"]\').click()');
  await sleep(280);
  const cites = await evaluate('document.querySelectorAll("#v-ask .cite").length');
  check('G1 答案引用条数', cites, cites === 3);
  const sampleN = await evaluate('document.querySelectorAll("#v-ask .sample span").length');
  check('G2 示例问题可点', sampleN, sampleN === 5);
  await evaluate('document.querySelectorAll("#v-ask .sample span")[2].click()');
  await sleep(150);
  const qv = await evaluate('document.getElementById("qbox").value');
  check('G3 点示例真填入输入框', qv.slice(0, 12), qv.includes('保证金'));

  // H 术语
  await evaluate('document.querySelector(\'[data-v="glossary"]\').click()');
  await sleep(250);
  const gRows = await evaluate('document.querySelectorAll("#v-glossary table tr").length - 1');
  check('H1 术语展示行数', gRows, gRows === 10);

  // I 静态禁区：不得有判定动作控件
  const judgeBtns = await evaluate(`Array.from(document.querySelectorAll('button')).map(b=>b.innerText).filter(t=>/通过|否决|赋分|定标|中标|判定为/.test(t))`);
  check('I1 无判定动作按钮', judgeBtns, judgeBtns.length === 0);

  // J 合规声明常驻
  const compN = await evaluate('document.querySelectorAll(".comp").length');
  const compHas = await evaluate('[...document.querySelectorAll(".comp")].every(e=>e.innerText.includes("不")||e.innerText.includes("仅"))');
  check('J1 每个视图都有合规声明', [compN, compHas], compN === EXPECT_VIEWS && compHas === true);

  // J2 横向零溢出：抽屉用 translateX 移出视口时不得撑大页面（曾溢出 420px）
  const ovf = await evaluate('JSON.stringify([document.documentElement.scrollWidth, document.documentElement.clientWidth])');
  const [sw, cw] = JSON.parse(ovf);
  check('J2 横向零溢出', ovf, sw <= cw + 2, 'scrollWidth ' + sw + ' / clientWidth ' + cw);

  // J3 合规条不得遮挡上方内容（曾因 sticky 盖住表格第 3 行）
  await evaluate('document.querySelector(\'[data-v="overview"]\').click()');
  await sleep(250);
  await evaluate('document.querySelector(".main").scrollTop = 0');
  await sleep(150);
  const overlap = await evaluate(`(()=>{
    const c=document.querySelector('#v-overview .comp').getBoundingClientRect();
    const t=document.querySelector('#v-overview table');
    if(!t) return 'no-table';
    const tr=t.getBoundingClientRect();
    const covered = c.top < tr.bottom - 1 && c.bottom > tr.top + 1;
    return JSON.stringify({covered, compTop:Math.round(c.top), tableBottom:Math.round(tr.bottom), position:getComputedStyle(document.querySelector('#v-overview .comp')).position});
  })()`);
  const ov = JSON.parse(overlap);
  check('J3 合规条在文档流内不遮挡内容', overlap, ov.covered === false && ov.position === 'static', overlap);

  // J4 顶栏常驻合规标签存在且可见
  await evaluate('document.querySelector(".main").scrollTop = 900');
  await sleep(200);
  const pillBox = await evaluate(`(()=>{const p=document.querySelector('.pill-gov');if(!p)return null;const r=p.getBoundingClientRect();return JSON.stringify({text:p.innerText,top:Math.round(r.top),visible:r.top>=0&&r.top<60})})()`);
  check('J4 顶栏合规标签滚动后仍可见', pillBox, pillBox !== null && JSON.parse(pillBox).visible === true, pillBox || '');
  await evaluate('document.querySelector(".main").scrollTop = 0');
  await sleep(150);

  // K 无外部网络请求
  const ext = out.network.filter(u => !u.startsWith('file://') && !u.startsWith('data:'));
  check('K1 无外部网络依赖', ext, ext.length === 0, ext.join(','));

  // L JS 异常
  check('L1 JS 异常与 console.error', out.errors.length, out.errors.length === 0, out.errors.join(' | ').slice(0, 300));

  // 截图（回到总览）
  await evaluate('document.querySelector(\'[data-v="overview"]\').click()');
  await sleep(350);
  const shot = await cmd('Page.captureScreenshot', { format: 'png' });
  fs.writeFileSync(SHOT, Buffer.from(shot.data, 'base64'));
  out.screenshot = SHOT;

  const fails = out.checks.filter(c => !c.pass);
  out.result = fails.length === 0 ? 'PASS' : 'FAIL';
  out.failed = fails.map(f => f.name);
  console.log('\n==== ' + out.result + ' : ' + (out.checks.length - fails.length) + '/' + out.checks.length + ' ====');
  if (fails.length) console.log('FAILED:', fails.map(f => f.name + ' => ' + JSON.stringify(f.value)).join(' ; '));
} catch (e) {
  out.error = String(e && e.message || e);
  console.log('SCRIPT ERROR', out.error);
} finally {
  fs.writeFileSync(OUT, JSON.stringify(out, null, 2));
  try { ws && ws.close(); } catch (e) {}
  try { edge.kill(); } catch (e) {}
  setTimeout(() => process.exit(0), 300);
}
