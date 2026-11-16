
import { spawn } from 'node:child_process';
import path from 'node:path'; import os from 'node:os';
const BASE='c:/Users/linkz/WorkBuddy/PC办公';
const EDGE='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT=9235;
const FILE=path.join(BASE,'国网物资部_标前审阅工作台_W1.html').replace(/\\/g,'/');
const URL='file:///'+encodeURI(FILE);
const PROFILE=path.join(os.tmpdir(),'sgcc-w1-ovf-'+Date.now());
const edge=spawn(EDGE,['--headless=new','--disable-gpu','--no-first-run','--remote-debugging-port='+PORT,'--user-data-dir='+PROFILE,'--window-size=1500,1040','about:blank'],{stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let ws,seq=0;const pending=new Map();
function cmd(m,p={}){return new Promise((res,rej)=>{const id=++seq;pending.set(id,{res,rej});ws.send(JSON.stringify({id,method:m,params:p}));setTimeout(()=>{if(pending.has(id)){pending.delete(id);rej(new Error('t'))}},20000)})}
async function ev(e){const r=await cmd('Runtime.evaluate',{expression:e,returnByValue:true,awaitPromise:true});if(r.exceptionDetails)throw new Error(r.exceptionDetails.text);return r.result.value}
for(let i=0;i<60;i++){try{const r=await fetch(`http://127.0.0.1:${PORT}/json/list`);const p=(await r.json()).find(t=>t.type==='page');if(p&&p.webSocketDebuggerUrl){ws=new WebSocket(p.webSocketDebuggerUrl);break}}catch(e){}await sleep(250)}
await new Promise((res,rej)=>{ws.onopen=res;ws.onerror=rej});
ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id&&pending.has(m.id)){const p=pending.get(m.id);pending.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result)}};
await cmd('Page.enable');await cmd('Runtime.enable');
await cmd('Page.navigate',{url:URL});await sleep(1400);
console.log('--- 各容器溢出情况 ---');
console.log(await ev(`JSON.stringify({
  body:[document.body.scrollWidth,document.body.clientWidth],
  html:[document.documentElement.scrollWidth,document.documentElement.clientWidth],
  main:[document.querySelector('.main').scrollWidth,document.querySelector('.main').clientWidth]
})`));
console.log('--- 溢出 .main 宽度的元素 ---');
console.log(await ev(`[...document.querySelectorAll('.main *')].filter(e=>e.scrollWidth>e.clientWidth+2 && e.clientWidth>0).slice(0,10).map(e=>e.className+'|'+e.tagName+'|sw='+e.scrollWidth+' cw='+e.clientWidth).join('\\n')`));
console.log('--- .comp 的定位与尺寸 ---');
console.log(await ev(`(()=>{const c=document.querySelector('.comp');const r=c.getBoundingClientRect();const m=document.querySelector('.main').getBoundingClientRect();return JSON.stringify({position:getComputedStyle(c).position,top:Math.round(r.top),bottom:Math.round(r.bottom),mainBottom:Math.round(m.bottom),h:Math.round(r.height)})})()`));
console.log('--- 视口 ---');
console.log(await ev(`JSON.stringify({innerW:innerWidth,innerH:innerHeight,dpr:devicePixelRatio})`));
ws.close();edge.kill();setTimeout(()=>process.exit(0),200);
