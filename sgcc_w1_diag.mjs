
import { spawn } from 'node:child_process';
import path from 'node:path'; import os from 'node:os';
const BASE='c:/Users/linkz/WorkBuddy/PC办公';
const EDGE='C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PORT=9233;
const FILE=path.join(BASE,'国网物资部_标前审阅工作台_W1.html').replace(/\\/g,'/');
const URL='file:///'+encodeURI(FILE);
const PROFILE=path.join(os.tmpdir(),'sgcc-w1-diag-'+Date.now());
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
console.log('innerText(可见)    =', await ev('document.body.innerText.length'));
console.log('textContent(全量)  =', await ev('document.body.textContent.length'));
console.log('总览视图可见文本    =', await ev('document.getElementById("v-overview").innerText.length'));
console.log('隐藏视图 innerText =', await ev('[...document.querySelectorAll(".view:not(.on)")].map(v=>v.innerText.length).join(",")'));
console.log('隐藏视图 textContent=', await ev('[...document.querySelectorAll(".view:not(.on)")].map(v=>v.textContent.length).join(",")'));
console.log('总览是否含关键业务词 =', await ev('["1525K1","候选待核","待澄清","155"].every(k=>document.getElementById("v-overview").innerText.includes(k))'));
console.log('总览文本前80字     =', await ev('document.getElementById("v-overview").innerText.replace(/\\s+/g," ").slice(0,80)'));
ws.close();edge.kill();setTimeout(()=>process.exit(0),200);
