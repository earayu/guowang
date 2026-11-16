import { writeFileSync, existsSync } from 'node:fs';
import { spawn } from 'node:child_process';
const EDGE=['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe','C:/Program Files/Microsoft/Edge/Application/msedge.exe'].find(p=>existsSync(p));
const PORT=9337,CDP=`http://127.0.0.1:${PORT}`;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const proc=spawn(EDGE,[`--remote-debugging-port=${PORT}`,'--user-data-dir=C:/Users/linkz/WorkBuddy/PC办公/_cdp_ux3','--headless=new','--disable-gpu','--window-size=1440,900','about:blank'],{stdio:'ignore'});
(async()=>{
  let page;
  for(let i=0;i<60;i++){try{const l=await(await fetch(CDP+'/json/list')).json();page=l.find(t=>t.type==='page');if(page?.webSocketDebuggerUrl)break;}catch(e){} await sleep(400);}
  const ws=new WebSocket(page.webSocketDebuggerUrl); let id=0; const pend=new Map();
  const send=(m,p)=>new Promise((res,rej)=>{const mid=++id;pend.set(mid,{res,rej});ws.send(JSON.stringify({id:mid,method:m,params:p||{}}));});
  ws.onmessage=e=>{const m=JSON.parse(e.data); if(m.id&&pend.has(m.id)){const p=pend.get(m.id);pend.delete(m.id);m.error?p.rej(new Error(JSON.stringify(m.error))):p.res(m.result);}};
  const evalJs=async ex=>{const r=await send('Runtime.evaluate',{expression:ex,returnByValue:true,awaitPromise:true,userGesture:true}); if(r.exceptionDetails) throw new Error(r.exceptionDetails.text); return r.result.value;};
  await new Promise(r=>ws.onopen=r);
  await send('Page.enable'); await send('Page.navigate',{url:'http://127.0.0.1:8787/?k=e3ba614e'}); await sleep(2200);
  const out=await evalJs(`(async()=>{
    document.querySelector('.nav a[data-v="bid"]').click(); await new Promise(r=>setTimeout(r,300));
    const rows=[...document.querySelectorAll('#bidCaseTbl tr')].slice(1);
    const tr=rows.find(r=>/恩施/.test(r.innerText));
    tr.querySelector('[data-c]').click(); await new Promise(r=>setTimeout(r,600));
    const b=document.getElementById('btnLiveJudge');
    for(let i=0;i<40&&b.disabled;i++) await new Promise(r=>setTimeout(r,250));
    b.click(); let t='';
    for(let i=0;i<60;i++){await new Promise(r=>setTimeout(r,300)); t=(document.getElementById('liveOut')||{}).innerText||''; if(/合规条件|本条/.test(t)) break;}
    return {hasOld:/判定式不成立/.test(t), snippet:t.split('\\n').filter(x=>/判否|合规条件|共 46|函数 v/.test(x)).slice(0,6)};
  })()`);
  console.log(JSON.stringify(out,null,1));
  proc.kill(); process.exit(0);
})().catch(e=>{console.error('FAIL',e.message);try{proc.kill()}catch(_){};process.exit(1)});
