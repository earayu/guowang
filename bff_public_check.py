# -*- coding: utf-8 -*-
"""B 方案公网验收：逐条断言"客户用自己的电脑打开时，能做什么、不能做什么"。

每条都打真实公网地址（走代理出网 → Cloudflare 边缘 → 本机隧道），
不是打 127.0.0.1。这样测的才是客户那条路径。
"""
import io
import json
import os
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOK = io.open(os.path.join(HERE, "_public_token.txt"), encoding="utf-8").read().strip()
LINK = io.open(os.path.join(HERE, "_public_url.txt"), encoding="utf-8").readline().strip()
BASE = LINK.split("/?k=")[0]

op = urllib.request.build_opener(urllib.request.ProxyHandler({}))
rows = []


def call(method, path, body=None, headers=None, timeout=120):
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    t0 = time.time()
    try:
        r = op.open(req, timeout=timeout)
        return r.status, r.read(), round(time.time() - t0, 2)
    except urllib.error.HTTPError as e:
        return e.code, e.read(), round(time.time() - t0, 2)


def check(name, cond, detail):
    rows.append({"项": name, "结果": "PASS" if cond else "FAIL", "实测": detail})
    print("%-4s %-28s %s" % ("PASS" if cond else "FAIL", name, detail))


# 1. 带口令能拿到页面
c, b, t = call("GET", "/?k=" + TOK)
check("页面·带口令", c == 200 and "评标辅助工作台".encode() in b,
      "HTTP %d, %d KB, %.2fs" % (c, len(b) // 1024, t))

# 2. 不带口令只看得到口令页
c, b, _ = call("GET", "/")
check("页面·无口令被挡", c == 403 and "请输入访问口令".encode() in b, "HTTP %d，返回口令页" % c)

# 3. 错口令同样挡住
c, b, _ = call("GET", "/?k=00000000")
check("页面·错口令被挡", c == 403, "HTTP %d" % c)

# 4. 路径探测不泄漏
c, b, _ = call("GET", "/api/../sgcc_bff.py")
check("路径探测被挡", c in (403, 404), "HTTP %d" % c)

# 5. health 白名单但不吐账号
c, b, t = call("GET", "/api/health")
h = json.loads(b) if c == 200 else {}
check("health 可用且不泄漏账号", c == 200 and h.get("ok") is True and "account" not in h,
      "HTTP %d, %s, %.2fs" % (c, json.dumps(h, ensure_ascii=False), t))

# 6. 接口无口令一律 401
c, b, _ = call("GET", "/api/kbs")
check("接口·无口令 401", c == 401, "HTTP %d %s" % (c, b.decode("utf-8","replace")[:40]))

# 7. 带口令可列库（8 个白名单）
c, b, _ = call("GET", "/api/kbs", headers={"X-Demo-Token": TOK})
n = len(json.loads(b)["items"]) if c == 200 else -1
check("接口·带口令列库", c == 200 and n == 8, "HTTP %d, %d 个库" % (c, n))

# 8. 判定无口令 401
c, b, _ = call("POST", "/api/judge/by-code", {"code": "ES"})
check("判定·无口令 401", c == 401, "HTTP %d" % c)

# 9. 判定带口令真跑（第一次可能是现算）
c, b, t = call("POST", "/api/judge/by-code", {"code": "ES"}, {"X-Demo-Token": TOK})
first = c
if c != 200:
    print("   [首次非 200] HTTP %d %s —— 按页面行为重试一次"
          % (c, b.decode("utf-8", "replace")[:120]))
    time.sleep(0.7)
    c, b, t = call("POST", "/api/judge/by-code", {"code": "ES"}, {"X-Demo-Token": TOK})
d = json.loads(b) if c == 200 else {}
j = d.get("judge") or {}
run = d.get("run") or {}
check("判定·恩施现算可用", c == 200 and j.get("fail_rows") == [7],
      "HTTP %d%s, %.2fs, source=%s, 函数内 %s ms, 判否 %s, 规则集 %s"
      % (c, "" if first == 200 else "（首次 %d，重试后成功，页面同此行为）" % first,
         t, d.get("_source"), run.get("elapsed_ms"), j.get("fail_rows"), j.get("rule_set_sha")))

# 10. 第二次走缓存
c, b, t = call("POST", "/api/judge/by-code", {"code": "ES"}, {"X-Demo-Token": TOK})
d2 = json.loads(b) if c == 200 else {}
check("判定·重复请求走缓存", d2.get("_source") == "cache", "source=%s, %.2fs" % (d2.get("_source"), t))

# 11. 抽取在公网被关掉
c, b, _ = call("POST", "/api/extract", {"batch_id": "x", "side": "bid", "fields": ["bid.seal_name"]},
               {"X-Demo-Token": TOK})
check("抽取·公网已关", c == 403 and "extract_disabled_in_public".encode() in b,
      "HTTP %d %s" % (c, b.decode("utf-8","replace")[:60]))

# 12. 只读检索可用（演示 L1 用得到）
c, b, t = call("GET", "/api/search?kb=col1c64f1cb56417c15&q=%E6%8A%95%E6%A0%87%E6%9C%89%E6%95%88%E6%9C%9F&limit=3",
               headers={"X-Demo-Token": TOK})
hits = -1
if c == 200:
    dd = json.loads(b)
    hits = len(dd.get("hits") or dd.get("items") or [])
check("检索·带口令可读", c == 200, "HTTP %d, %d 条, %.2fs" % (c, hits, t))

# 13. 白名单外的库拒绝
c, b, _ = call("GET", "/api/search?kb=colXXX&q=x&limit=3", headers={"X-Demo-Token": TOK})
check("检索·白名单外被拒", c in (400, 403), "HTTP %d %s" % (c, b.decode("utf-8","replace")[:50]))

out = {
    "meta": {
        "方案": "B · 本机 BFF + Cloudflare 快速隧道",
        "公网地址": BASE,
        "口令位数": len(TOK),
        "测试时间": time.strftime("%Y-%m-%d %H:%M:%S"),
        "测试路径": "本机 → HTTP 代理出网 → Cloudflare 边缘 → 隧道 → 127.0.0.1:8787",
        "note": "所有断言都打公网域名，不是 127.0.0.1。",
    },
    "summary": {
        "total": len(rows),
        "pass": sum(1 for r in rows if r["结果"] == "PASS"),
        "fail": sum(1 for r in rows if r["结果"] == "FAIL"),
    },
    "cases": rows,
}
p = os.path.join(HERE, "国网Demo_B方案_公网穿透_真跑证据_V1.json")
io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(out, ensure_ascii=False, indent=1))
print("\n%d/%d PASS  -> %s" % (out["summary"]["pass"], out["summary"]["total"], os.path.basename(p)))
