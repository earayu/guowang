// W2 布局诊断：热力条取色、文本截断、溢出
import { spawn } from 'node:child_process';
import path from 'node:path'; import os from 'node:os';
const BASE = 'c:/Users/linkz/WorkBuddy/PC办公';
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT = 9237;
const FILE = path.join(BASE, '国网物资部_标前审阅工作台_W2.html').replace(/\\/g, '/');
const URL = 'file:///' + encodeURI(FILE);
const PROFILE = path.join(os.tmpdir(), 'sgcc-w2diag-' + Date.now());
const edge = spawn(EDGE, ['--headless=new', '--disable-gpu', '--no-first-run', '--remote-debugging-port=' + PORT,
  '--user-data-dir=' + PROFILE, '--window-size=1500,1040', 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, seq = 0; const pending = new Map();
function cmd(m, p = {}) { return new Promise((res, rej) => { const id = ++seq; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method: m, params: p })); setTimeout(() => { if (pending.has(id)) { pending.delete(id); rej(new Error('t')); } }, 20000); }); }
async function ev(e) { const r = await cmd('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.text); return r.result.value; }
for (let i = 0; i < 80; i++) { try { const r = await fetch(`http://127.0.0.1:${PORT}/json/list`); const p = (await r.json()).find(t => t.type === 'page'); if (p && p.webSocketDebuggerUrl) { ws = new WebSocket(p.webSocketDebuggerUrl); break; } } catch (e) { } await sleep(250); }
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); } };
await cmd('Page.enable'); await cmd('Runtime.enable');
await cmd('Page.navigate', { url: URL }); await sleep(1500);
await ev('document.querySelector(".nav a[data-v=\\"life\\"]").click()'); await sleep(400);

console.log('--- 热力条 12 段取色 ---');
console.log(await ev(`[...document.querySelectorAll('.heat .hcell')].map((e,i)=>i+':'+getComputedStyle(e).backgroundColor+'|'+(e.title||'')).join('\\n')`));

console.log('--- chip 文字是否被 ellipsis 截断 ---');
console.log(await ev(`[...document.querySelectorAll('.lchip')].map(c=>{const s=c.querySelector('span');return c.dataset.s+' sw='+s.scrollWidth+' cw='+s.clientWidth+(s.scrollWidth>s.clientWidth+1?'  <<截断':'')}).join('\\n')`));

console.log('--- 全流程位置 hint 是否超出主区内容右界 ---');
console.log(await ev(`(()=>{const st=document.querySelector('#v-life .st');const hint=st.querySelector('.hint');const main=document.querySelector('.main');const mr=main.getBoundingClientRect();const cs=getComputedStyle(main);const limit=mr.right-parseFloat(cs.paddingRight);const h=hint.getBoundingClientRect();return JSON.stringify({mainRight:Math.round(mr.right),contentLimit:Math.round(limit),hintRight:Math.round(h.right),overflow:Math.round(h.right-limit),hintText:hint.innerText})})()`));

console.log('--- 6 个环节列宽与 chip 数 ---');
console.log(await ev(`[...document.querySelectorAll('.lphase')].map(p=>{const r=p.getBoundingClientRect();return p.querySelector('.lph').innerText+' w='+Math.round(r.width)+' chips='+p.querySelectorAll('.lchip').length}).join('\\n')`));

console.log('--- 详情卡内部是否有元素溢出 ---');
console.log(await ev(`[...document.querySelectorAll('#lifeDetail .lbox')].map((e,i)=>({i,sw:e.scrollWidth,cw:e.clientWidth,overflow:e.scrollWidth>e.clientWidth+2})).map(o=>JSON.stringify(o)).join('\\n')`));

console.log('--- 页面总高 / 视口 ---');
console.log(await ev(`JSON.stringify({mainScroll:document.querySelector('.main').scrollHeight, mainClient:document.querySelector('.main').clientHeight, winH:innerHeight})`));

ws.close(); edge.kill(); setTimeout(() => process.exit(0), 200);
