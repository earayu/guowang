// 补测：点准热区（span[data-c]）→ 抽屉 → 现场跑 46 条 → 结果；并测「抽屉关闭态是否仍可被键盘聚焦」。
import { writeFileSync, existsSync } from 'node:fs';
import { spawn } from 'node:child_process';

const EDGE = ['C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
  'C:/Program Files/Microsoft/Edge/Application/msedge.exe'].find(p => existsSync(p));
const PORT = 9334, CDP = `http://127.0.0.1:${PORT}`;
const URL = process.argv[2] || 'http://127.0.0.1:8787/?k=e3ba614e';
const sleep = ms => new Promise(r => setTimeout(r, ms));
const proc = spawn(EDGE, [`--remote-debugging-port=${PORT}`, '--user-data-dir=C:/Users/linkz/WorkBuddy/PC办公/_cdp_review2',
  '--headless=new', '--disable-gpu', '--window-size=1440,900', 'about:blank'], { stdio: 'ignore' });

async function findPage() {
  for (let i = 0; i < 60; i++) {
    try { const l = await (await fetch(CDP + '/json/list')).json(); const p = l.find(t => t.type === 'page'); if (p?.webSocketDebuggerUrl) return p; } catch (e) { }
    await sleep(400);
  } throw new Error('CDP 未就绪');
}
function connect(page) {
  return new Promise((res0, rej) => {
    const ws = new WebSocket(page.webSocketDebuggerUrl); let id = 0; const pending = new Map();
    ws.onmessage = ev => { const m = JSON.parse(ev.data); if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); } };
    ws.onerror = () => rej(new Error('ws'));
    ws.onopen = () => {
      const send = (method, params) => new Promise((res, rej2) => { const mid = ++id; pending.set(mid, { res, rej: rej2 }); ws.send(JSON.stringify({ id: mid, method, params: params || {} })); });
      const evalJs = async e => { const r = await send('Runtime.evaluate', { expression: e, returnByValue: true, awaitPromise: true, userGesture: true }); if (r.exceptionDetails) throw new Error(r.exceptionDetails.text); return r.result.value; };
      res0({ send, evalJs });
    };
  });
}

(async () => {
  const page = await findPage(); const { send, evalJs } = await connect(page);
  await send('Page.enable');
  await send('Page.navigate', { url: URL }); await sleep(1500);
  await evalJs(`document.querySelector('.nav a[data-v="bid"]')?.click()`); await sleep(400);

  const out = {};
  // 1) 关闭态：抽屉里的关闭按钮能否被聚焦/被读到
  out.closedState = await evalJs(`(() => {
    const d=document.getElementById('drawer');
    const btn=document.getElementById('dClose');
    return { open:d.classList.contains('open'),
      closedOpacityOrOffscreen: getComputedStyle(d).transform,
      closeBtnInTabOrder: btn.tabIndex, closeBtnVisible: btn.getBoundingClientRect().width>0,
      drawerAriaHidden: d.getAttribute('aria-hidden'), focusableInsideClosedDrawer:
        [...d.querySelectorAll('button,a,input,[tabindex]')].length };
  })()`);

  // 2) 点准 span[data-c]
  out.click = await evalJs(`(async () => {
    const spans=[...document.querySelectorAll('#bidCaseTbl [data-c]')];
    const pick=spans.find(s=>/判否/.test(s.innerText))||spans[0];
    const t=performance.now(); pick.click(); await new Promise(r=>setTimeout(r,500));
    const d=document.getElementById('drawer');
    return { cells:spans.length, picked:pick.innerText, cellKey:pick.dataset.c,
      open:d.classList.contains('open'), ms:Math.round(performance.now()-t),
      title:(document.getElementById('dTitle')||{}).innerText,
      bodyLen:(document.getElementById('dBody')||{}).innerText.length,
      hasLive:!!document.getElementById('liveJudge'),
      liveBtn:(document.getElementById('btnLiveJudge')||{}).innerText };
  })()`);

  // 3) 现场跑 46 条
  out.live = await evalJs(`(async () => {
    const b=document.getElementById('btnLiveJudge');
    if(!b) return {err:'not injected'};
    for(let i=0;i<40 && b.disabled;i++) await new Promise(r=>setTimeout(r,200));
    if(b.disabled) return {skipped:true, text:b.innerText};
    const t=performance.now(); b.click();
    let txt='';
    for(let i=0;i<60;i++){ await new Promise(r=>setTimeout(r,250)); txt=b.innerText;
      if(/通过|不成立|失败|判定不出/.test(txt) && !/正在|跑…|检查判定服务/.test(txt)) break; }
    const box=document.getElementById('liveJudge');
    return { ms:Math.round(performance.now()-t), btnAfter:txt,
      blockLen:(box||{}).innerText?.length||0,
      blockText:((box||{}).innerText||'').slice(0,400) };
  })()`);

  // 4) 抽屉内滚动是否需要（长内容）
  out.scroll = await evalJs(`(() => { const b=document.querySelector('#drawer .db');
    const r=b.getBoundingClientRect(); return { clientH:b.clientHeight, scrollH:b.scrollHeight,
      overflowY:getComputedStyle(b).overflowY, ratio:+(b.scrollHeight/b.clientHeight).toFixed(2),
      visibleAreaPct:+(r.height/window.innerHeight*100).toFixed(0) }; })()`);

  // 5) 键盘 Tab 顺序（抽屉打开态）
  const seq = [];
  for (let i = 0; i < 8; i++) {
    await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
    await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Tab', code: 'Tab', windowsVirtualKeyCode: 9 });
    await sleep(80);
    seq.push(await evalJs(`(() => { const a=document.activeElement; return a? a.tagName+'|'+(a.innerText||a.id||'').replace(/\\s+/g,' ').slice(0,18) : 'none'; })()`));
  }
  out.tabSeqOpen = seq;

  // 6) Esc 是否关闭抽屉
  await send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 });
  await sleep(250);
  out.escCloses = await evalJs(`!document.getElementById('drawer').classList.contains('open')`);

  const shot = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync('_review_probe_drawer.png', Buffer.from(shot.data, 'base64'));

  writeFileSync('_review_probe2.json', JSON.stringify(out, null, 2));
  console.log(JSON.stringify(out, null, 1));
  proc.kill(); process.exit(0);
})().catch(e => { console.error('FAIL', e.message); try { proc.kill(); } catch (_) { } process.exit(1); });
