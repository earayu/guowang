/* ============ 可用性升级层（行为） ============
   只做呈现与交互改造：不修改任何判定数据、不改变结论口径。
   所有"留痕/角色"均为本地演示级，界面必须标明未接服务端。
   ============================================ */
(function () {
  'use strict';

  var $ = function (s, r) { return (r || document).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || document).querySelectorAll(s)); };
  var K_ROLE = 'sgcc_role_v1', K_FS = 'sgcc_fs_v1', K_DEC = 'sgcc_decision_v1', K_AUD = 'sgcc_audit_v1';
  var BATCH = '1525K1';

  function pad(n) { return String(n).padStart(2, '0'); }
  function stamp(d) {
    d = d || new Date();
    return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' +
      pad(d.getHours()) + ':' + pad(d.getMinutes()) + ':' + pad(d.getSeconds());
  }
  function fileStamp(d) {
    d = d || new Date();
    return '' + d.getFullYear() + pad(d.getMonth() + 1) + pad(d.getDate()) + '_' + pad(d.getHours()) + pad(d.getMinutes());
  }
  var store = {
    get: function (k, dv) { try { var v = localStorage.getItem(k); return v == null ? dv : JSON.parse(v); } catch (e) { return dv; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { } }
  };

  /* ---------- 1. 角色 ---------- */
  var ROLES = {
    expert: { name: '评标专家', decide: true, export: true, judge: true, note: '' },
    owner: { name: '招标人', decide: false, export: true, judge: true, note: '招标人视角：可导出、可看全量，不下评审结论' },
    sup: { name: '监督', decide: false, export: false, judge: false, note: '监督视角：只看不改，报价类摘要脱敏' }
  };
  var role = store.get(K_ROLE, 'expert');
  if (!ROLES[role]) role = 'expert';

  function audit(type, action, detail) {
    var a = store.get(K_AUD, []);
    a.unshift({ t: stamp(), actor: ROLES[role].name, type: type, action: action, detail: detail || '' });
    store.set(K_AUD, a.slice(0, 300));
  }

  function applyRole() {
    var cfg = ROLES[role];
    $$('.ux-seg button').forEach(function (b) { b.classList.toggle('on', b.dataset.role === role); });
    $$('.ux-export').forEach(function (b) {
      b.disabled = !cfg.export;
      b.title = cfg.export ? '' : '当前身份（' + cfg.name + '）无导出权限';
    });
    $$('.ux-decide-wrap').forEach(function (el) { el.style.display = cfg.decide ? '' : 'none'; });
    var jb = $('#btnLiveJudge');
    if (jb) {
      jb.style.pointerEvents = cfg.judge ? '' : 'none';
      jb.style.opacity = cfg.judge ? '' : '.45';
      jb.title = cfg.judge ? '' : '当前身份（' + cfg.name + '）不可触发判定';
    }
    var n = $('#uxRoleNote');
    if (n) { n.textContent = cfg.note; n.style.display = cfg.note ? '' : 'none'; }
    var av = $('.sg-user .sg-ava');
    if (av) av.textContent = cfg.name.slice(0, 1);
    var un = $('.sg-user');
    if (un) {
      var t = un.childNodes[un.childNodes.length - 1];
      if (t && t.nodeType === 3) t.textContent = cfg.name;
    }
  }

  /* ---------- 2. 字号档位 ---------- */
  function applyFs() {
    var v = store.get(K_FS, 'md');
    if (v === 'md') document.documentElement.removeAttribute('data-fs');
    else document.documentElement.setAttribute('data-fs', v);
    $$('.ux-fs button').forEach(function (b) { b.classList.toggle('on', b.dataset.fs === v); });
  }

  /* ---------- 3. 导出 ---------- */
  function csvCell(v) {
    v = String(v == null ? '' : v).replace(/\r?\n/g, ' ').trim();
    return /[",]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v;
  }
  function download(name, lines) {
    var blob = new Blob(['\ufeff' + lines.join('\r\n')], { type: 'text/csv;charset=utf-8' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a); a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 800);
  }
  function head(desc) {
    return [
      ['导出批次', BATCH],
      ['导出时间', stamp()],
      ['导出人', ROLES[role].name],
      ['数据口径', desc],
      ['性质说明', '演示数据；系统只出候选与依据，判定权在评标委员会']
    ].map(function (r) { return r.map(csvCell).join(','); });
  }
  function tableToRows(sel, visibleOnly) {
    var t = $(sel); if (!t) return [];
    return $$('tr', t).filter(function (tr) {
      if (visibleOnly && tr.style.display === 'none') return false;
      return true;
    }).map(function (tr) {
      return $$('th,td', tr).map(function (c) { return c.innerText.replace(/\s+/g, ' ').trim(); });
    });
  }
  function exportTable(sel, fname, desc, visibleOnly) {
    var rows = tableToRows(sel, visibleOnly !== false);
    if (!rows.length) { alert('当前没有可导出的行。'); return; }
    var out = head(desc);
    out.push('');
    rows.forEach(function (r) { out.push(r.map(csvCell).join(',')); });
    download(fname + '_' + fileStamp() + '.csv', out);
    audit('导出', '导出 ' + fname, desc);
  }

  /* ---------- 4. 过滤 ---------- */
  function applyFilter(sel, kw, countEl, unitLabel) {
    var t = $(sel); if (!t) return;
    kw = (kw || '').trim().toLowerCase();
    var rows = $$('tr', t).slice(1);
    var hit = 0;
    rows.forEach(function (tr) {
      var txt = tr.innerText.toLowerCase();
      var ok = !kw || txt.indexOf(kw) >= 0;
      tr.style.display = ok ? '' : 'none';
      if (ok) hit++;
    });
    if (countEl) countEl.innerHTML = '显示 <b>' + hit + '</b> / ' + rows.length + ' ' + (unitLabel || '条');
  }

  function makeToolbar(host, opts) {
    var bar = document.createElement('div');
    bar.className = 'ux-toolbar';
    bar.setAttribute('role', 'search');
    var q = document.createElement('div');
    q.className = 'ux-search';
    q.innerHTML = '<input type="search" id="' + opts.id + '" placeholder="' + opts.ph + '" aria-label="' + opts.ph + '">' +
      '<button class="clr" type="button" aria-label="清除搜索">×</button>';
    var cnt = document.createElement('span');
    cnt.className = 'ux-count';
    cnt.id = opts.id + '_cnt';
    var lb = document.createElement('span');
    lb.className = 'lb'; lb.textContent = opts.label || '检索';
    bar.appendChild(lb); bar.appendChild(q); bar.appendChild(cnt);
    if (opts.exportName) {
      var b = document.createElement('button');
      b.className = 'ux-btn ux-export'; b.type = 'button';
      b.textContent = '导出 CSV';
      b.onclick = function () { exportTable(opts.table, opts.exportName, opts.desc, true); };
      bar.appendChild(b);
    }
    if (opts.printName) {
      var p = document.createElement('button');
      p.className = 'ux-btn'; p.type = 'button'; p.textContent = '打印当前页';
      p.onclick = function () { audit('打印', '打印当前视图', document.title); window.print(); };
      bar.appendChild(p);
    }
    var input = $('input', bar), clr = $('.clr', bar);
    var timer = null;
    function run() {
      applyFilter(opts.table, input.value, cnt, opts.unit);
      if (opts.onFilter) opts.onFilter(input.value);
    }
    input.addEventListener('input', function () { clearTimeout(timer); timer = setTimeout(run, 120); });
    clr.onclick = function () { input.value = ''; run(); input.focus(); };
    host.parentNode.insertBefore(bar, host);
    run();
    return bar;
  }

  /* ---------- 5. 抽屉增强 ---------- */
  var lastFocus = null, drawerEl = $('#drawer');
  var _open = window.openDrawer, _close = window.closeDrawer;

  function decKey() {
    var title = ($('#dTitle') || {}).textContent || '';
    var rule = '';
    $$('#dBody .meta .k').some(function (k) {
      if (/规则号/.test(k.textContent)) { rule = (k.nextElementSibling || {}).textContent || ''; return true; }
      return false;
    });
    return (title + '|' + rule).trim();
  }

  function renderDecide() {
    var wrap = $('#uxDecide'); if (!wrap) return;
    var key = decKey();
    var all = store.get(K_DEC, {});
    var cur = all[key];
    var cfg = ROLES[role];
    var box = wrap.querySelector('.ux-decide-wrap');
    if (!cfg.decide) {
      box.innerHTML = '<div class="ux-decide-wrap" style="display:none"></div>' +
        '<div class="mini" style="color:var(--ink3)">当前身份（' + cfg.name + '）不参与评审结论录入。</div>';
      return;
    }
    if (cur) {
      var cls = cur.verdict === 'accept' ? 'acc' : (cur.verdict === 'reject' ? 'rej' : 'wait');
      var lb = cur.verdict === 'accept' ? '判否成立（采纳机器提示）' : (cur.verdict === 'reject' ? '判否不成立（不采纳）' : '转澄清');
      box.innerHTML = '<div class="done"><span class="ux-chip ' + cls + '">' + lb + '</span>' +
        '<span>已记录 · ' + cur.at + ' · ' + cur.actor + '</span>' +
        '<span class="sp" style="flex:1"></span>' +
        '<button class="ux-btn" type="button" id="uxDecEdit">修改</button>' +
        '<button class="ux-btn" type="button" id="uxDecClear">撤销</button></div>' +
        (cur.reason ? '<div class="mini" style="margin-top:7px">理由：' + cur.reason.replace(/[<>&]/g, function (c) { return { '<': '&lt;', '>': '&gt;', '&': '&amp;' }[c]; }) + '</div>' : '');
      $('#uxDecClear').onclick = function () { var a = store.get(K_DEC, {}); delete a[key]; store.set(K_DEC, a); audit('结论', '撤销核查结论', key); renderDecide(); renderDecideTable(); };
      $('#uxDecEdit').onclick = function () { buildForm(key, cur); };
    } else {
      buildForm(key, null);
    }
  }

  function buildForm(key, cur) {
    var box = $('.ux-decide-wrap');
    box.innerHTML = '<div class="row1"><span class="lbl">专家核查结论</span>' +
      '<button class="ux-btn pri" type="button" data-v="accept">判否成立</button>' +
      '<button class="ux-btn" type="button" data-v="reject">判否不成立</button>' +
      '<button class="ux-btn" type="button" data-v="defer">转澄清</button></div>' +
      '<textarea id="uxDecReason" placeholder="填写理由（写入初步评审表，必填）">' + (cur ? (cur.reason || '') : '') + '</textarea>' +
      '<div class="mini" style="margin-top:5px">结论只记在本机浏览器，用于生成初步评审表；不写回任何服务端。</div>';
    $$('[data-v]', box).forEach(function (b) {
      b.onclick = function () {
        var r = $('#uxDecReason').value.trim();
        if (!r) { $('#uxDecReason').focus(); $('#uxDecReason').style.borderColor = '#C8102E'; return; }
        var all = store.get(K_DEC, {});
        all[key] = { verdict: b.dataset.v, reason: r, at: stamp(), actor: ROLES[role].name };
        store.set(K_DEC, all);
        audit('结论', '录入核查结论：' + b.textContent, key);
        renderDecide(); renderDecideTable();
      };
    });
  }

  window.openDrawer = function (title, meta, quote, foot) {
    lastFocus = document.activeElement;
    _open(title, meta, quote, foot);
    drawerEl.inert = false;
    drawerEl.removeAttribute('aria-hidden');
    drawerEl.setAttribute('role', 'dialog');
    drawerEl.setAttribute('aria-modal', 'false');
    drawerEl.setAttribute('aria-labelledby', 'dTitle');
    var body = $('#dBody');
    var dw = document.createElement('div');
    dw.className = 'ux-decide'; dw.id = 'uxDecide';
    dw.innerHTML = '<div class="row1" style="margin-bottom:6px"><span class="lbl" style="font-weight:500;color:var(--ink)">专家核查结论</span></div><div class="ux-decide-wrap"></div>';
    body.appendChild(dw);
    renderDecide();
    /* 抽屉里的 reason 用同一套业务语言，避免与「本条结论」读起来打架 */
    localizeTerms(body);
    /* 字段旁的「验证通过」指抽取校验，常被读成条款合规；加一句分清 */
    var hasConc = $$('#dBody .meta .k').some(function (k) { return /本条结论/.test(k.textContent); });
    if (hasConc) {
      var mtag = $('#dBody .meta');
      mtag.insertAdjacentHTML('afterend',
        '<div class="mini" style="margin:-6px 0 12px;line-height:1.7">字段旁的「验证通过」指该字段抽取校验通过，' +
        '<b style="color:var(--ink2)">不代表条款合规</b>；是否构成否决以「本条结论」与原文为准。</div>');
    }
    if (role === 'sup') maskMoney();
    var btn = $('#dClose'); if (btn) btn.focus();
    audit('查看', '打开依据抽屉', title);
  };

  window.closeDrawer = function () {
    _close();
    drawerEl.inert = true;
    drawerEl.setAttribute('aria-hidden', 'true');
    if (lastFocus && lastFocus.focus) { try { lastFocus.focus(); } catch (e) { } }
  };

  function maskMoney() {
    $$('#dBody .meta .k').forEach(function (k) {
      if (/报价|金额|价|税率|限价/.test(k.textContent)) {
        var v = k.nextElementSibling;
        if (v) { v.textContent = '——（监督视角脱敏）'; }
      }
    });
  }

  /* ---------- 6. 术语本地化：把内部"判定式"翻成业务话 ----------
     数据层 reason 是"判定式成立/不成立"，指该条款的合规条件是否成立；
     直接给专家看会被读成"判否的理由不成立"。这里只在显示层翻译，不改数据与证据快照。 */
  function localizeTerms(root) {
    if (!root) return 0;
    var w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null, false);
    var n, hits = 0;
    while ((n = w.nextNode())) {
      if (n.nodeValue.indexOf('判定式') >= 0) {
        n.nodeValue = n.nodeValue
          .replace(/判定式不成立/g, '合规条件不成立，本条否决情形成立')
          .replace(/判定式成立/g, '合规条件成立，本条未触发');
        hits++;
      }
    }
    return hits;
  }

  var _live = window.renderLiveResult;
  if (typeof _live === 'function') {
    window.renderLiveResult = function (data) {
      _live(data);
      var out = $('#liveOut'); if (!out) return;
      var hits = localizeTerms(out);
      if (hits) {
        var tip = document.createElement('div');
        tip.className = 'mini';
        tip.style.cssText = 'margin:6px 0 0;line-height:1.7';
        tip.textContent = '判定式＝该条款的合规条件。条件成立即未触发否决；不成立即命中否决情形。最终结论由评标委员会作出。';
        out.appendChild(tip);
      }
    };
  }

  /* ---------- 7. 结论汇总表 ---------- */
  function renderDecideTable() {
    var host = $('#uxDecHost'); if (!host) return;
    var all = store.get(K_DEC, {});
    var keys = Object.keys(all);
    if (!keys.length) {
      host.innerHTML = '<div class="ux-empty">还没有录入核查结论。在「本次受审结果」里点任一格，于右侧抽屉底部填写结论与理由，这里会汇总成初步评审表。</div>';
      return;
    }
    var rows = keys.map(function (k) {
      var d = all[k], p = k.split('|');
      return '<tr><td>' + p[0] + '</td><td class="mono">' + (p[1] || '—') + '</td><td>' +
        (d.verdict === 'accept' ? '<span class="ux-chip acc">判否成立</span>' :
          d.verdict === 'reject' ? '<span class="ux-chip rej">判否不成立</span>' : '<span class="ux-chip wait">转澄清</span>') +
        '</td><td>' + d.reason + '</td><td class="mini">' + d.at + ' · ' + d.actor + '</td>' +
        '<td><button class="ux-btn" type="button" data-del="' + encodeURIComponent(k) + '">删除</button></td></tr>';
    }).join('');
    host.innerHTML = '<div class="card" style="padding:0;overflow:hidden"><table id="decideTable">' +
      '<tr><th style="width:220px">核查对象</th><th style="width:110px">规则号</th><th style="width:110px">专家结论</th><th>理由</th><th style="width:170px">录入</th><th style="width:70px">操作</th></tr>' +
      rows + '</table></div>' +
      '<div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap">' +
      '<button class="ux-btn pri ux-export" type="button" id="uxExpDec">导出初步评审表 CSV</button>' +
      '<button class="ux-btn" type="button" id="uxPrintDec">打印</button>' +
      '<span class="mini" style="align-self:center">结论列由专家填写，系统不代填；导出件含批次、时间、录入人。</span></div>';
    $$('[data-del]', host).forEach(function (b) {
      b.onclick = function () {
        var k = decodeURIComponent(b.dataset.del);
        var a = store.get(K_DEC, {}); delete a[k]; store.set(K_DEC, a);
        audit('结论', '删除核查结论', k); renderDecideTable();
      };
    });
    $('#uxExpDec').onclick = function () {
      var a = store.get(K_DEC, {});
      var ks = Object.keys(a); if (!ks.length) { alert('还没有结论可导出。'); return; }
      var out = head('专家核查结论汇总（初步评审表底稿）');
      out.push('');
      out.push(['核查对象', '规则号', '专家结论', '理由', '录入时间', '录入人'].join(','));
      ks.forEach(function (k) {
        var d = a[k], p = k.split('|');
        var v = d.verdict === 'accept' ? '判否成立' : (d.verdict === 'reject' ? '判否不成立' : '转澄清');
        out.push([p[0], p[1] || '', v, d.reason, d.at, d.actor].map(csvCell).join(','));
      });
      out.push('');
      out.push(['注', '本表为初步评审表底稿；是否存在否决情形、是否赋分、是否定标，由评标委员会依法作出'].map(csvCell).join(','));
      download('初步评审表底稿_' + BATCH + '_' + fileStamp() + '.csv', out);
      audit('导出', '导出初步评审表底稿', ks.length + ' 条结论');
    };
    $('#uxPrintDec').onclick = function () { audit('打印', '打印核查结论', ''); window.print(); };
    applyRole();
  }

  /* ---------- 8. 留痕模态 ---------- */
  function renderAudit() {
    var host = $('#uxAuditBody'); if (!host) return;
    var a = store.get(K_AUD, []);
    if (!a.length) { host.innerHTML = '<div class="ux-empty">暂无操作记录。</div>'; return; }
    host.innerHTML = '<table><tr><th style="width:150px">时间</th><th style="width:90px">身份</th><th style="width:70px">类型</th><th style="width:180px">动作</th><th>对象</th></tr>' +
      a.slice(0, 120).map(function (x) {
        return '<tr><td class="mono">' + x.t + '</td><td>' + x.actor + '</td><td>' + x.type + '</td><td>' + x.action + '</td><td class="mini">' + (x.detail || '—') + '</td></tr>';
      }).join('') + '</table>';
  }
  function openAudit() {
    $('#uxAuditMask').classList.add('on');
    $('#uxAuditModal').classList.add('on');
    renderAudit();
    audit('查看', '打开操作留痕', '');
    $('#uxAuditClose').focus();
  }
  function closeAudit() {
    $('#uxAuditMask').classList.remove('on');
    $('#uxAuditModal').classList.remove('on');
  }

  /* ---------- 9. 键盘与焦点 ---------- */
  function setupKeys() {
    $$('.nav a').forEach(function (a) {
      a.setAttribute('tabindex', '0');
      a.setAttribute('role', 'link');
      a.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); a.click(); }
      });
      a.addEventListener('click', function () {
        var live = $('#uxLive');
        if (live) live.textContent = '已切换到：' + a.textContent.replace(/\s+/g, ' ').trim();
        audit('查看', '切换视图', a.textContent.replace(/\s+/g, ' ').trim());
        applyRole();
      });
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        if ($('#uxAuditModal').classList.contains('on')) { closeAudit(); return; }
        if (drawerEl.classList.contains('open')) { window.closeDrawer(); }
      }
    });

    document.addEventListener('click', function () {
      $$('[data-c]').forEach(function (el) {
        if (!el.hasAttribute('tabindex')) {
          el.setAttribute('tabindex', '0');
          el.setAttribute('role', 'button');
          el.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); el.click(); }
          });
        }
      });
    });
  }

  /* ---------- 10. 初始化 ---------- */
  function boot() {
    /* 抽屉初始态：关闭且不可达 */
    drawerEl.inert = true;
    drawerEl.setAttribute('aria-hidden', 'true');

    /* 顶栏控件事件 */
    $$('.ux-seg button').forEach(function (b) {
      b.onclick = function () {
        role = b.dataset.role; store.set(K_ROLE, role);
        applyRole(); renderDecide(); renderDecideTable();
        audit('身份', '切换身份', ROLES[role].name);
      };
    });
    $$('.ux-fs button').forEach(function (b) {
      b.onclick = function () { store.set(K_FS, b.dataset.fs); applyFs(); };
    });
    /* 原脚本把 × 直接绑到原函数，这里重绑到包装版，否则 Esc/焦点归还走不到 */
    var dc = $('#dClose'); if (dc) dc.onclick = function () { window.closeDrawer(); };
    var ab = $('#uxAuditOpen'); if (ab) ab.onclick = openAudit;
    var ac = $('#uxAuditClose'); if (ac) ac.onclick = closeAudit;
    var am = $('#uxAuditMask'); if (am) am.onclick = closeAudit;
    var ae = $('#uxAuditExport');
    if (ae) ae.onclick = function () {
      var a = store.get(K_AUD, []);
      if (!a.length) { alert('暂无记录。'); return; }
      var out = head('本机操作留痕（演示级，未接服务端审计）');
      out.push(''); out.push(['时间', '身份', '类型', '动作', '对象'].join(','));
      a.forEach(function (x) { out.push([x.t, x.actor, x.type, x.action, x.detail].map(csvCell).join(',')); });
      download('操作留痕_' + BATCH + '_' + fileStamp() + '.csv', out);
    };

    /* 工具条：条款 / 澄清 / 术语 / 48 格 */
    var rulesHost = $('#ruleTable');
    if (rulesHost) {
      makeToolbar(rulesHost, {
        id: 'uxQ1', ph: '搜规则号或条款原文，如 GW-HB-FJ-017、税率',
        label: '条款检索', table: '#ruleTable', unit: '条',
        exportName: '条款台账', desc: '46 条否决情形台账（当前筛选结果）', printName: true,
        onFilter: function () { }
      });
    }
    var clarHost = $('#clarifyTable');
    if (clarHost) {
      makeToolbar(clarHost, {
        id: 'uxQ2', ph: '搜差异项、责任方或仍缺文件',
        label: '检索', table: '#clarifyTable', unit: '项',
        exportName: '待澄清事项表', desc: '9 项待澄清事项（当前筛选结果）', printName: true
      });
    }
    var glosTbl = $('#v-glossary table');
    if (glosTbl) {
      var gw = document.createElement('div');
      gw.className = 'ux-toolbar'; gw.setAttribute('role', 'search');
      gw.innerHTML = '<span class="lb">术语检索</span><div class="ux-search">' +
        '<input type="search" id="uxQ3" placeholder="搜术语或同义叫法，如 后审、废标" aria-label="术语检索">' +
        '<button class="clr" type="button" aria-label="清除搜索">×</button></div><span class="ux-count"></span>';
      glosTbl.parentNode.parentNode.insertBefore(gw, glosTbl.parentNode);
      var gi = $('#uxQ3'), gc = $('.ux-count', gw);
      gi.addEventListener('input', function () { applyFilter('#v-glossary table', gi.value, gc, '条'); });
      $('.clr', gw).onclick = function () { gi.value = ''; applyFilter('#v-glossary table', '', gc, '条'); gi.focus(); };
      applyFilter('#v-glossary table', '', gc, '条');
    }
    var bidHost = $('#bidCaseTbl');
    if (bidHost) {
      makeToolbar(bidHost, {
        id: 'uxQ4', ph: '搜投标人名称',
        label: '检索', table: '#bidCaseTbl', unit: '家',
        exportName: '受审结果矩阵', desc: '6 家 × 8 条机器可判规则（当前筛选结果）', printName: true
      });
    }

    /* 结论汇总区（投标页） */
    var bidView = $('#v-bid');
    if (bidView) {
      var sec = document.createElement('div');
      sec.innerHTML = '<div class="st">我的核查结论<span class="ln"></span><span class="hint">专家录入，系统只汇总，不代填</span></div><div id="uxDecHost"></div>';
      var comp = $('.comp', bidView);
      bidView.insertBefore(sec, comp);
    }

    /* 切换分段时原 renderRules 会重建行，重绘后要把检索词重新套上 */
    var _rr = window.renderRules;
    if (typeof _rr === 'function') {
      window.renderRules = function (cat) {
        _rr(cat);
        var i = $('#uxQ1'), c = $('#uxQ1_cnt');
        if (i) applyFilter('#ruleTable', i.value, c, '条');
      };
    }

    applyFs();
    applyRole();
    renderDecideTable();
    setupKeys();

    /* 落地页：进主线「投标文件审批」而不是说明页 */
    if (!location.hash || location.hash === '#') {
      var target = $('.nav a[data-v="bid"]');
      var overview = $('#v-overview');
      if (target && overview && overview.classList.contains('on')) {
        $$('.nav a').forEach(function (x) { x.classList.remove('on'); });
        target.classList.add('on');
        $$('.view').forEach(function (v) { v.classList.remove('on'); });
        $('#v-bid').classList.add('on');
      }
    }
    audit('查看', '进入工作台', document.title);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

/* ---------- 12. 法源溯源（46 条逐条回读招标文件原文） ---------- */
(function () {
  var el = document.getElementById('uxProvData');
  if (!el) return;
  var PROV = {};
  try { PROV = JSON.parse(el.textContent || '{}'); } catch (e) { return; }
  window.UX_PROV = PROV;

  function openProv(id) {
    var p = PROV[id]; if (!p) return;
    var cls = p.cls || '';
    // 「法定兜底」必须单独措辞：它不是招标文件复述法条，而是援引其他法条。
    // 混进「法定否决情形」里写「仅作复述」，等于把兜底条款说成具体情形，一问就穿。
    var tail = cls.indexOf('兜底') >= 0
      ? '属法定兜底条款：本条本身不列举具体情形，援引其他法律法规规章的否决规定，须逐案对照。'
      : cls.indexOf('法定') === 0
        ? '属法定否决情形，招标文件仅作复述。'
        : cls.indexOf('+') >= 0
          ? '属法定要件加招标文件细化：法律给了原则，本项目给了具体口径。'
          : '属招标人依《招标投标法实施条例》第二十三条约定的否决条款，非法定否决情形。';
    var meta = {
      '招标文件位置': '第三章 ' + p.clause + ' · 前附表之二 · 表第 ' + p.trow + ' 行',
      '文档定位': '段落 ' + p.para + '（docx 无稳定页码，按段落号可精确复核）',
      '否决性质': p.cls,
      '法规依据': (p.laws && p.laws.length) ? p.laws.join('；') : '—'
    };
    openDrawer('法源 · ' + id, meta, p.text,
      '本条从招标文件原文逐字回读，未概括、未改写。' + tail +
      '\n系统只标注法源与条文位置，不解释条款、不判定是否成立。');
  }
  window.uxOpenProv = openProv;

  var _rr = window.renderRules;
  if (typeof _rr !== 'function') return;
  window.renderRules = function () {
    _rr.apply(this, arguments);
    var t = document.getElementById('ruleTable'); if (!t) return;
    var head = t.querySelector('tr:first-child');
    if (head && !head.querySelector('.ux-prov-th')) {
      var th = document.createElement('th');
      th.className = 'ux-prov-th';
      th.style.width = '84px';
      th.textContent = '法源';
      th.title = '回读招标文件原文，并区分法定否决情形与招标人约定条款';
      head.appendChild(th);
    }
    var rows = [].slice.call(t.querySelectorAll('tr')).slice(1);
    rows.forEach(function (tr) {
      if (tr.querySelector('.ux-prov-td')) return;
      var id = ((tr.children[0] || {}).textContent || '').trim();
      var td = document.createElement('td');
      td.className = 'ux-prov-td';
      var p = PROV[id];
      if (!p) {
        td.innerHTML = '<span class="mini">—</span>';
        tr.appendChild(td);
        return;
      }
      var dot = document.createElement('span');
      dot.className = 'ux-prov-dot' + (p.cls.indexOf('法定') === 0 ? ' is-law' : ' is-own');
      dot.title = p.cls;
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'ux-btn ux-prov-btn';
      b.textContent = '原文';
      b.title = '查看招标文件原文与法规依据';
      b.onclick = function (ev) { ev.stopPropagation(); openProv(id); };
      td.appendChild(dot);
      td.appendChild(b);
      tr.appendChild(td);
    });
  };
  // 包装后重绘一次，让初始视图也带上法源列
  try { window.renderRules('all'); } catch (e) {}
})();
