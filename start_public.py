# -*- coding: utf-8 -*-
"""B 方案一键启动：本机 BFF + Cloudflare 快速隧道，客户用自己电脑打开。

和 A 方案（start_demo.py --live）的差别只有一个：多一条出网隧道。
但多了这条隧道，安全模型就变了——所以本脚本做的每一件事都是因为这个：

  1. 强制口令。端口一挂上隧道，世界上任何人都能敲 /api/judge。
     口令写进 URL 的 ?k=，页面读到后转存 sessionStorage 并抹掉地址栏。
  2. 页面由 BFF 自己托管（同源）。客户浏览器里的 127.0.0.1 是他自己的机器，
     跨端口硬编码必然失败；同源之后前端用相对路径，CORS 问题一并消失。
  3. 限流 + 审计。每个来源 IP 每分钟上限，全部调用落 sgcc_bff_audit.jsonl，
     带真实来源 IP（CF-Connecting-IP）。
  4. 只监听 127.0.0.1:8787。隧道进程在本机连它，不往外绑 0.0.0.0。

用法：
  python start_public.py              # 起服务 + 隧道，打印带口令的链接
  python start_public.py --no-tunnel  # 只起公网模式的 BFF（自己接别的隧道）
  python start_public.py --fresh      # 换一个新口令（旧链接立即失效）
"""
import argparse
import io
import json
import os
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CFD = os.path.join(HERE, "tools", "cloudflared.exe")
TOKEN_FILE = os.path.join(HERE, "_public_token.txt")
URL_FILE = os.path.join(HERE, "_public_url.txt")
PORT = 8787
METRICS = 20199

URL_RE = re.compile(r"https://[a-z0-9][a-z0-9-]*\.trycloudflare\.com")


def get_token(fresh=False):
    """口令只在本地文件里，不进代码、不进日志。"""
    if not fresh and os.path.exists(TOKEN_FILE):
        t = io.open(TOKEN_FILE, encoding="utf-8").read().strip()
        if t:
            return t
    t = secrets.token_hex(4)          # 8 位十六进制，念得出来，猜不出来
    io.open(TOKEN_FILE, "w", encoding="utf-8", newline="\n").write(t + "\n")
    return t


def port_busy(port):
    s = socket.socket()
    s.settimeout(0.6)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def wait_health(timeout=40):
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            r = opener.open("http://127.0.0.1:%d/api/health" % PORT, timeout=3)
            if r.status == 200:
                return True
        except Exception:
            pass
        time.sleep(0.6)
    return False


def start_bff(token):
    env = dict(os.environ)
    env.update({"BFF_PUBLIC": "1", "BFF_TOKEN": token, "BFF_PORT": str(PORT),
                "BFF_RATE": env.get("BFF_RATE", "120")})
    # 公网模式不设 CORS 通配：同源访问，根本不需要跨域放行。
    env.pop("BFF_ORIGIN", None)
    p = subprocess.Popen([sys.executable, "-u", os.path.join(HERE, "sgcc_bff.py")],
                         cwd=HERE, env=env,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         text=True, encoding="utf-8", errors="replace", bufsize=1)
    threading.Thread(target=_pump, args=(p, "[bff] "), daemon=True).start()
    return p


def _pump(proc, tag):
    """把子进程输出带前缀转发，两个进程的日志不混。"""
    try:
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                print(tag + line)
                sys.stdout.flush()
    except Exception:
        pass


def start_tunnel(url):
    """起隧道并拿到公网地址。

    地址不靠解析日志：cloudflared 在 Windows 上把输出重定向到管道时会吞行，
    第一次就是卡在这——进程明明在跑，日志一行读不到。改读它自己的 metrics
    端点 /quicktunnel（官方提供的反查接口），日志另落一份文件备查。
    """
    if not os.path.exists(CFD):
        raise SystemExit("找不到 %s，先下载 cloudflared" % CFD)

    log_path = os.path.join(HERE, "_cloudflared.log")
    logf = io.open(log_path, "w", encoding="utf-8", buffering=1)
    cmd = [CFD, "tunnel", "--url", url, "--no-autoupdate",
           "--metrics", "127.0.0.1:%d" % METRICS]
    if os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"):
        # 本机走 HTTP 代理出网，UDP/7844 不稳；http2 走 443/TCP。
        cmd += ["--protocol", "http2"]
    p = subprocess.Popen(cmd, cwd=HERE, stdout=logf, stderr=subprocess.STDOUT)
    print("隧道进程已起（pid=%d），日志：%s" % (p.pid, os.path.basename(log_path)))

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    t0 = time.time()
    while time.time() - t0 < 90:
        try:
            r = opener.open("http://127.0.0.1:%d/quicktunnel" % METRICS, timeout=2)
            host = (json.loads(r.read().decode("utf-8")) or {}).get("hostname")
            if host:
                return p, "https://" + host
        except Exception:
            pass
        if p.poll() is not None:
            logf.close()
            raise SystemExit("隧道进程退出（exit=%s）。日志尾部：\n%s"
                             % (p.returncode, _tail(log_path)))
        time.sleep(0.5)
    logf.close()
    raise SystemExit("90 秒未拿到公网地址。日志尾部：\n%s" % _tail(log_path))


def _tail(path, n=25):
    try:
        lines = io.open(path, encoding="utf-8", errors="replace").read().splitlines()
        return "\n".join(lines[-n:])
    except OSError:
        return "(无日志)"


def warm_tunnel(link, token):
    """隧道刚建好时有一段窗口：边缘到本机 origin 的连接还没就绪，
    头几个请求会拿到 502 或 Cloudflare 自己的 400。这段不能留给客户——
    他自己点第一次，看到的就是"打不开"。

    做法：连续打通 health，再真跑一次判定，把连接和 CLI 一起预热。
    """
    opener = urllib.request.build_opener()      # 走系统代理出网
    base = link.split("/?k=")[0]
    t0 = time.time()
    hits = 0
    while time.time() - t0 < 90:
        try:
            r = opener.open(base + "/api/health", timeout=20)
            if r.status == 200:
                hits += 1
                if hits >= 3:
                    break
        except Exception:
            hits = 0
        time.sleep(1.5)
    print("公网连通性预热：%d 次连续成功，用时 %.0fs" % (hits, time.time() - t0))

    try:
        req = urllib.request.Request(
            base + "/api/judge/by-code",
            data=json.dumps({"code": "恩施"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Demo-Token": token})
        t1 = time.time()
        d = json.loads(opener.open(req, timeout=120).read().decode("utf-8"))
        j = d.get("judge") or {}
        print("判定链路预热：判否 %s，函数内 %s ms，端到端 %.1fs"
              % (j.get("fail_rows"), (d.get("run") or {}).get("elapsed_ms"), time.time() - t1))
    except Exception as e:
        print("判定预热未成功（不致命，页面首次点击会自动重试一次）：%s" % e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-tunnel", action="store_true", help="只起公网模式的 BFF，不拉隧道")
    ap.add_argument("--fresh", action="store_true", help="换新口令，旧链接立即失效")
    a = ap.parse_args()

    if port_busy(PORT):
        raise SystemExit("端口 %d 已被占用。先关掉正在跑的 start_demo.py --live 或 sgcc_bff.py。" % PORT)

    token = get_token(a.fresh)
    print("=" * 66)
    print(" B 方案：客户用自己的电脑打开（本机服务 + 公网隧道）")
    print("=" * 66)

    bff = start_bff(token)
    if not wait_health():
        bff.terminate()
        raise SystemExit("BFF 没起来，先看 [bff] 日志。")

    local = "http://127.0.0.1:%d/?k=%s" % (PORT, token)
    print("\n本机自检：%s" % local)

    if a.no_tunnel:
        print("\n只起了 BFF。自己接隧道时目标填 http://127.0.0.1:%d" % PORT)
        try:
            bff.wait()
        except KeyboardInterrupt:
            bff.terminate()
        return

    cfd, url = start_tunnel("http://127.0.0.1:%d" % PORT)
    link = "%s/?k=%s" % (url, token)
    io.open(URL_FILE, "w", encoding="utf-8", newline="\n").write(
        "%s\n# 生成于 %s，口令见 _public_token.txt；关掉本窗口即失效\n"
        % (link, time.strftime("%Y-%m-%d %H:%M:%S")))

    warm_tunnel(link, token)

    print("\n" + "-" * 66)
    print(" 给客户的链接（可直接发微信）：")
    print("   " + link)
    print("-" * 66)
    print(" 带口令的完整地址才会打开页面；只发域名会被挡在口令页。")
    print(" 页面里点格子 → 抽屉底部「现场跑 46 条」＝真的走公网回到这台机器。")
    print(" 第一次点约 4~6 秒（CLI 冷启动），上台前自己先点一次会快一半。")
    print(" 这条链接写进了 _public_url.txt；关掉本窗口（Ctrl+C）即失效。")
    print(" 演示完请按 Ctrl+C：隧道一断，公网上就再也敲不到这个端口。")
    print("-" * 66)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n收工，关隧道与 BFF…")
    finally:
        for p in (cfd, bff):
            try:
                p.terminate()
            except Exception:
                pass
        time.sleep(1)
        for p in (cfd, bff):
            try:
                p.kill()
            except Exception:
                pass
        print("已全部停止。")


if __name__ == "__main__":
    main()
