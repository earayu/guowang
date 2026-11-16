# -*- coding: utf-8 -*-
"""公网链路稳定性抽样：客户演示最怕的不是慢，是偶尔打不开。

打真实公网地址，统计成功率与耗时分布。--n 控制次数。
"""
import argparse
import io
import json
import os
import statistics
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TOK = io.open(os.path.join(HERE, "_public_token.txt"), encoding="utf-8").read().strip()
LINK = io.open(os.path.join(HERE, "_public_url.txt"), encoding="utf-8").readline().strip()
BASE = LINK.split("/?k=")[0]
op = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def one(path, headers=None, method="GET", body=None):
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(BASE + path, data=data, headers=h, method=method)
    t0 = time.time()
    try:
        r = op.open(req, timeout=40)
        b = r.read()
        return r.status, len(b), round((time.time() - t0) * 1000)
    except urllib.error.HTTPError as e:
        return e.code, 0, round((time.time() - t0) * 1000)
    except Exception as e:
        return 0, 0, round((time.time() - t0) * 1000), type(e).__name__


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return 0
    k = max(0, min(len(xs) - 1, int(round((p / 100.0) * (len(xs) - 1)))))
    return xs[k]


def run(name, path, n, headers=None, ok_bytes=0, method="GET", body=None):
    st, ms, bad = [], [], []
    for i in range(n):
        r = one(path, headers, method, body)
        code, size, t = r[0], r[1], r[2]
        st.append((code, size))
        ms.append(t)
        if code != 200 or (ok_bytes and size < ok_bytes):
            bad.append({"i": i + 1, "code": code, "bytes": size, "ms": t})
        time.sleep(0.3)
    good = sum(1 for c, s in st if c == 200 and (not ok_bytes or s >= ok_bytes))
    print("%-14s 成功 %2d/%2d  P50 %5d ms  P90 %5d ms  max %5d ms"
          % (name, good, n, pct(ms, 50), pct(ms, 90), max(ms)))
    if bad:
        print("   失败样本：%s" % json.dumps(bad[:5], ensure_ascii=False))
    return {"name": name, "n": n, "ok": good, "p50_ms": pct(ms, 50), "p90_ms": pct(ms, 90),
            "max_ms": max(ms), "min_ms": min(ms), "failures": bad}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    a = ap.parse_args()
    print("目标：%s\n" % BASE)
    out = {"meta": {"url": BASE, "at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "path": "本机→代理→Cloudflare→隧道→127.0.0.1:8787"},
           "runs": []}
    out["runs"].append(run("health", "/api/health", a.n))
    out["runs"].append(run("页面", "/?k=" + TOK, max(4, a.n // 3), ok_bytes=100000))
    out["runs"].append(run("judge(现算/缓存)", "/api/judge/by-code", max(3, a.n // 4),
                           headers={"X-Demo-Token": TOK}, method="POST",
                           body={"code": "恩施"}))
    total_ok = sum(r["ok"] for r in out["runs"])
    total_n = sum(r["n"] for r in out["runs"])
    out["summary"] = {"ok": total_ok, "n": total_n, "rate": round(total_ok * 100.0 / total_n, 1)}
    print("\n总计 %d/%d = %.1f%%" % (total_ok, total_n, out["summary"]["rate"]))
    p = os.path.join(HERE, "国网Demo_B方案_链路稳定性抽样.json")
    io.open(p, "w", encoding="utf-8", newline="\n").write(json.dumps(out, ensure_ascii=False, indent=1))
    print("->", os.path.basename(p))


if __name__ == "__main__":
    main()
