# -*- coding: utf-8 -*-
"""C8 · fe-evidence-bridge 本地桥接服务（唯一实时取数面）

约束（fe-evidence-bridge 取数契约 v1.2）：
  1. 只绑定 127.0.0.1:8765，页面只 fetch 本服务，绝不直连 apemind.ai；
  2. 桥接只执行 allowlist 内的 apemind CLI 命令，CLI 负责认证 / workspace header；
  3. 最小集全部只读：禁止 --confirm / --idempotency-key / --header / --server / --account / 写字段；
  4. apemind api 仅允许 GET 且路径限定在样本知识库文档列表；
  5. CLI 版本与 allowlist 版本不一致时阻断发问；
  6. CLI 输出信封原样回传，日志只记 path/exit/request_id，不记凭据与正文。
"""
import io
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__)) + os.sep
CLI = BASE + 'apemind-cli' + os.sep + 'apemind.exe'
HTML = BASE + '国网Demo_演示控制台_V7.html'
CAPS = BASE + 'sgcc_capabilities_present.json'
ALLOWLIST = BASE + 'bridge' + os.sep + 'allowlist.json'
LOG = BASE + 'sgcc_bridge_calls.jsonl'
CID = 'colcf0af5d45fd7ef6b'
PORT = 8765

READ_COMMANDS = [
    'auth status', 'knowledge list', 'document list', 'document get',
    'search', 'grep', 'read', 'outline',
    'turn list', 'turn get', 'skill list', 'dataset list',
    'function get', 'agent kb list', 'api',
]
FORBIDDEN_FLAGS = {
    '--confirm', '--idempotency-key', '--header', '--server', '--account',
    '--input', '--field', '--raw-field', '--force', '--accept-breaking',
    '--secret-file',
}
COMMON_FLAGS = {'--json', '--jq', '--format', '--template', '--workspace', '--paginate'}
API_PATH_RE = re.compile(r'^/api/v2/collections/' + re.escape(CID) + r'/documents(\?[A-Za-z0-9_=&%.-]*)?$')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def build_allowlist():
    caps = json.load(io.open(CAPS, encoding='utf-8'))
    data = caps['data']
    by_path = {c['path']: c for c in data['command_details']}
    cmds = {}
    for p in READ_COMMANDS:
        c = by_path.get(p)
        assert c, 'capabilities missing ' + p
        flags = set()
        for f in c.get('flags') or []:
            name = f if isinstance(f, str) else f.get('name')
            flags.add('--' + name)
        flags |= COMMON_FLAGS
        flags -= FORBIDDEN_FLAGS
        cmds[p] = {
            'mode': 'read',
            'flags': sorted(flags),
            'scopes': c.get('required_oauth_scopes') or [],
            'use': c.get('use', ''),
        }
    out = {
        'contract': 'fe-evidence-bridge v1.2',
        'cli_version': data['version'],
        'fetched_at': caps.get('fetched_at'),
        'request_id': caps.get('request_id'),
        'collection_id': CID,
        'commands': cmds,
        'forbidden_flags': sorted(FORBIDDEN_FLAGS),
        'api_get_path_pattern': API_PATH_RE.pattern,
        'rules': [
            '前端只请求 127.0.0.1 桥接，不直连 /api/v2 或 apemind.ai',
            '桥接只执行 allowlist 内的 apemind CLI 命令，认证由 CLI 管',
            '最小集全部只读，前端不得自动拼 --confirm',
            'CLI 版本与 allowlist 版本不一致时阻断发问',
            'CLI 输出信封原样回传，日志不记凭据与正文',
        ],
    }
    os.makedirs(os.path.dirname(ALLOWLIST), exist_ok=True)
    io.open(ALLOWLIST, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def cli(args, timeout=150):
    t0 = time.time()
    try:
        p = subprocess.run([CLI] + args, capture_output=True, text=True,
                           encoding='utf-8', errors='replace', timeout=timeout)
        raw = (p.stdout or '').strip()
        try:
            env = json.loads(raw)
        except Exception:
            env = {'type': 'raw', 'stdout': raw[:4000], 'stderr': (p.stderr or '')[-800:]}
        rc = p.returncode
    except subprocess.TimeoutExpired:
        rc, env = 124, {'error': {'code': 'bridge_timeout', 'message': 'CLI 超时'}}
    log({'path': args[0] if args else '', 'args': args[1:], 'exit_code': rc,
         'request_id': (env.get('request_id') if isinstance(env, dict) else None),
         'ms': int((time.time() - t0) * 1000), 'at': now()})
    return rc, env


def cli_text(args, timeout=30):
    p = subprocess.run([CLI] + args, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout)
    return p.returncode, (p.stdout or '').strip()


def log(rec):
    with io.open(LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(rec, ensure_ascii=False) + '\n')


def validate(path, args):
    """返回 (ok, reason)。严格白名单：命令名、flag、位置参数、api 路径、写操作一律拒绝。"""
    if path not in AL['commands']:
        return False, 'command_not_in_allowlist'
    if not isinstance(args, list) or len(args) > 24:
        return False, 'bad_args'
    allowed = set(AL['commands'][path]['flags'])
    positional = []
    for i, a in enumerate(args):
        if not isinstance(a, str) or len(a) > 400 or any(ch in a for ch in ('\x00', '\n', '\r')):
            return False, 'bad_arg_value'
        if a.startswith('--'):
            flag = a.split('=', 1)[0]
            if flag in FORBIDDEN_FLAGS or flag not in allowed:
                return False, 'flag_not_allowed:' + flag
            if flag == '--method' and (i + 1 >= len(args) or args[i + 1].upper() != 'GET'):
                return False, 'api_method_must_be_get'
            if flag == '--jq' and ('request_id' in a.lower() or 'token' in a.lower()):
                return False, 'jq_probe_forbidden'
        else:
            positional.append(a)
    if path == 'api':
        if not positional or not API_PATH_RE.match(positional[0]):
            return False, 'api_path_not_allowed'
        if len(positional) > 1:
            return False, 'api_extra_positional'
    return True, ''


class Handler(BaseHTTPRequestHandler):
    server_version = 'SGCCBridge/1.2'

    def _send(self, code, obj, ctype='application/json; charset=utf-8'):
        body = obj if isinstance(obj, bytes) else json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(body)

    def _local_only(self):
        host = (self.headers.get('Host') or '').split(':')[0]
        if host not in ('127.0.0.1', 'localhost'):
            self._send(403, {'error': {'code': 'local_only'}})
            return False
        return True

    def do_OPTIONS(self):
        self._send(204, b'')

    def do_GET(self):
        if not self._local_only():
            return
        p = self.path.split('?', 1)[0]
        if p == '/favicon.ico':
            self._send(204, b'')
            return
        if p in ('/', '/index.html'):
            try:
                self._send(200, io.open(HTML, 'rb').read(), 'text/html; charset=utf-8')
            except OSError:
                self._send(404, {'error': {'code': 'console_html_missing'}})
            return
        if p == '/bridge/version':
            self._send(200, self.health())
            return
        if p == '/bridge/health':
            h = self.health()
            self._send(200 if h['data']['version_match'] else 423, h)
            return
        if p == '/bridge/allowlist':
            self._send(200, {'data': {
                'contract': AL['contract'], 'cli_version': AL['cli_version'],
                'request_id': AL['request_id'], 'fetched_at': AL['fetched_at'],
                'commands': sorted(AL['commands']), 'command_count': len(AL['commands']),
                'forbidden_flags': AL['forbidden_flags'], 'rules': AL['rules'],
            }, 'bridge': {'at': now()}})
            return
        if p == '/bridge/status':
            if not self.health()['data']['version_match']:
                self._send(423, {'error': {'code': 'cli_version_drift'}})
                return
            self._send(200, self.status())
            return
        self._send(404, {'error': {'code': 'not_found', 'path': p}})

    def do_POST(self):
        if not self._local_only():
            return
        if self.path.split('?', 1)[0] != '/bridge/invoke':
            self._send(404, {'error': {'code': 'not_found'}})
            return
        if not self.health()['data']['version_match']:
            self._send(423, {'error': {'code': 'cli_version_drift'}})
            return
        try:
            n = int(self.headers.get('Content-Length') or '0')
            body = json.loads(self.rfile.read(n).decode('utf-8'))
        except Exception:
            self._send(400, {'error': {'code': 'bad_json'}})
            return
        path, args = body.get('path'), body.get('args') or []
        ok, reason = validate(path, args)
        if not ok:
            log({'path': path, 'args': args, 'rejected': reason, 'at': now()})
            self._send(403, {'error': {'code': 'allowlist_rejected', 'reason': reason}})
            return
        rc, env = cli(path.split(' ') + args)
        self._send(200, {'cli': env, 'exit_code': rc,
                         'bridge': {'path': path, 'at': now(), 'contract': AL['contract']}})

    def health(self):
        rc, ver = cli_text(['--version'])
        rc2, env = cli(['auth', 'status', '--json'], timeout=40)
        acct = (env.get('data') or {}).get('account') or {}
        return {'data': {
            'cli_version': ver.strip(),
            'allowlist_version': AL['cli_version'],
            'version_match': ver.strip() == AL['cli_version'],
            'account': acct.get('name'),
            'token_cached': bool((env.get('data') or {}).get('access_token_cached')),
            'auth_exit': rc2,
            'contract': AL['contract'],
            'allowlist_request_id': AL['request_id'],
            'at': now(),
        }}

    def status(self):
        rows, rids, pages = [], [], 0
        for page in (1, 2, 3, 4):
            rc, env = cli(['api', '/api/v2/collections/%s/documents?page=%d&page_size=100' % (CID, page),
                           '--method', 'GET', '--json'])
            d = env.get('data') or {}
            items = d.get('items') or []
            if rc != 0 or not items:
                return {'error': {'code': 'cli_api_failed', 'exit_code': rc,
                                 'message': (env.get('error') or {}).get('message', 'no items')},
                        'bridge': {'at': now()}}
            rows.extend(items)
            rids.append(env.get('request_id'))
            pages += 1
            if not d.get('has_next'):
                break
        keys = ('status', 'vector_index_status', 'fulltext_index_status', 'graph_index_status')
        return {'data': {
            'collection_id': CID,
            'documents': len(rows),
            'counters': {k: dict(Counter(str(x.get(k)) for x in rows)) for k in keys},
            'pages': pages,
            'cli_request_ids': rids,
            'source': 'apemind api (CLI, GET only)',
        }, 'bridge': {'at': now(), 'contract': AL['contract'], 'mode': 'read-only'}}

    def log_message(self, fmt, *a):
        sys.stderr.write('[%s] %s\n' % (now(), fmt % a))


if __name__ == '__main__':
    AL = build_allowlist()
    print('BRIDGE allowlist built:', AL['contract'], AL['cli_version'],
          len(AL['commands']), 'commands, request_id', AL['request_id'])
    print('BRIDGE listening http://127.0.0.1:%d/ (Ctrl+C to stop)' % PORT)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
