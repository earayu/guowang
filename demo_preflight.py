# -*- coding: utf-8 -*-
"""演示前 60 秒一键自检（P0-3 现场零依赖）。

只用标准库 + 本地 CLI，不 import requests——
所以任何 python 都能跑，不挑解释器。

用法：
    python demo_preflight.py            # 全检查
    python demo_preflight.py --quick    # 只查页面与离线数据（不碰网络）

退出码：0 = 可以上台；1 = 有阻断项；2 = 只有警告
"""
import io
import json
import os
import socket
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
CLI = os.path.join(ROOT, "apemind-cli", "apemind.exe")
W3 = os.path.join(ROOT, "国网物资部_评标辅助工作台_W3.html")
V7 = os.path.join(ROOT, "国网Demo_演示控制台_V7.html")
PAGE_DATA = os.path.join(ROOT, "国网Demo_W3v2_页面数据_6家8条.json")
EV = [os.path.join(ROOT, f) for f in (
    "国网Demo_F2受审侧抽取v2_真跑证据.json",
    "国网Demo_F3_46条规则端到端_真跑证据_V2.json",
    "国网Demo_F4规则算子边界_验证_V2.json",
    "国网Demo_F4跨家聚合规则_算子验证_V2.json",
)]
KBS = [("colcf0af5d45fd7ef6b", "招标主库"),
       ("col0cd75b81b6b47b74", "招标质量验证库"),
       ("col2de7406a4c8a6e56", "受审 HZ"),
       ("col4020b47c9984bbbb", "受审 XY"),
       ("col2894640b355a1b11", "受审 YC"),
       ("col8fe7f3d2e3d2dac5", "受审 JZ"),
       ("cold98e481541486cc5", "受审 HS"),
       ("col1c64f1cb56417c15", "受审 ES")]

rows = []


def add(level, name, detail):
    rows.append((level, name, detail))


def run_cli(args, timeout=60):
    try:
        p = subprocess.run([CLI] + args, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return p.returncode, (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return -1, "EXC %s" % e


def main():
    quick = "--quick" in sys.argv

    # ---- 1 文件齐备 ----
    need = [("对客主界面 W3", W3), ("内部举证壳 V7", V7), ("页面数据", PAGE_DATA)] + \
           [("证据 " + os.path.basename(p)[:24], p) for p in EV]
    miss = [n for n, p in need if not os.path.exists(p)]
    if miss:
        add("FAIL", "文件齐备", "缺 " + "、".join(miss))
    else:
        add("PASS", "文件齐备", "W3 + V7 + 页面数据 + 4 份证据均在")

    # ---- 2 页面是不是 v2 ----
    if os.path.exists(W3):
        h = io.open(W3, encoding="utf-8", errors="replace").read()
        marks = {
            "六家八条标题": "6 家 × 8 条机器可判规则" in h,
            "行7 列": "行7 交货期" in h,
            "字段对位 66/66": "66<small>/66</small>" in h,
            "机器跑通 8/25": "8<small>/25 条</small>" in h,
            "抽屉算式": "【算式】" in h,
            "无 v1 家名脱敏": "某某" not in h,
            "无 v1 七条文案": "七条规则" not in h,
        }
        bad = [k for k, v in marks.items() if not v]
        if bad:
            add("FAIL", "W3 是 v2 版", "不合格项：" + "、".join(bad))
        else:
            add("PASS", "W3 是 v2 版", "7 项标记全中（含行7 列与算式抽屉）")
        add("INFO", "W3 体积", "%.0f KB" % (len(h.encode("utf-8")) / 1024))

    # ---- 3 离线数据自检 ----
    if os.path.exists(PAGE_DATA):
        d = json.load(io.open(PAGE_DATA, encoding="utf-8"))
        nrow = len(d.get("rows", []))
        ncol = len(d.get("cols", []))
        ncells = sum(len(r.get("cells", {})) for r in d.get("rows", []))
        ncalc = sum(1 for r in d.get("rows", []) for c in r["cells"].values() if c.get("calc"))
        nquote = sum(1 for r in d.get("rows", []) for c in r["cells"].values()
                     for f in (c.get("fields") or []) if f.get("quote"))
        nfail = sum(r.get("fail", 0) for r in d.get("rows", []))
        ok = (nrow == 6 and ncol == 8 and ncells == 48 and nfail == 5)
        add("PASS" if ok else "FAIL", "离线判定矩阵",
            "6 家 × 8 条 = %d 格；判否合计 %d 处；算式 %d 条；原文引用 %d 条" % (ncells, nfail, ncalc, nquote))
        if nfail != 5:
            add("FAIL", "判否数", "期望 5（5 家各 1 处），实得 %d" % nfail)

    # ---- 4 CLI 与登录态 ----
    if quick:
        add("SKIP", "CLI 登录态", "--quick 模式跳过")
    elif not os.path.exists(CLI):
        add("FAIL", "CLI 存在", "找不到 " + CLI)
    else:
        rc, out = run_cli(["auth", "status", "--json"])
        if rc != 0 or "access_expires_at" not in out:
            add("FAIL", "CLI 登录态", "auth status 失败：%s" % out.strip()[:120])
        else:
            try:
                j = json.loads(out)
                exp = (j.get("data") or {}).get("access_expires_at") or ""
                left = None
                if exp:
                    t = time.mktime(time.strptime(exp[:19], "%Y-%m-%dT%H:%M:%S")) - time.time() + 8 * 3600
                    left = int(t / 60)
                if left is None:
                    add("WARN", "CLI 登录态", "读不到到期时间：%s" % exp)
                elif left <= 0:
                    add("FAIL", "CLI 登录态", "access token 已过期 → 先跑复登")
                elif left < 15:
                    add("WARN", "CLI 登录态", "只剩 %d 分钟（平台约 9 分钟一过）→ 上台前先复登" % left)
                else:
                    add("PASS", "CLI 登录态", "剩余 %d 分钟" % left)
            except Exception as e:
                add("WARN", "CLI 登录态", "解析失败：%s" % e)

        # ---- 5 八个库在不在 ----
        miss_kb, total_doc = [], 0
        for kid, label in KBS:
            rc, out = run_cli(["knowledge", "get", kid, "--json"], timeout=45)
            if rc != 0 or '"id"' not in out:
                miss_kb.append("%s(%s)" % (label, kid))
        if miss_kb:
            add("FAIL", "八个库", "缺：" + "、".join(miss_kb))
        else:
            add("PASS", "八个库", "招标 2 + 受审 6 全部在")

    # ---- 6 桥接（可选） ----
    s = socket.socket()
    s.settimeout(0.6)
    try:
        s.connect(("127.0.0.1", 8765))
        add("PASS", "桥接 8765", "在听（可用实时取数模式）")
    except Exception:
        add("INFO", "桥接 8765", "未启动 → 今天是快照模式，讲的时候要说清")
    finally:
        s.close()

    # ---- 7 解释器 ----
    has_req = True
    try:
        import requests  # noqa: F401
    except Exception:
        has_req = False
    add("INFO" if has_req else "WARN", "当前解释器",
        ("%s（有 requests，可跑 status_check / 复登）" % sys.version.split()[0]) if has_req
        else "%s 无 requests → 复登请用 .workbuddy/binaries/python/envs/default/Scripts/python.exe" %
             sys.version.split()[0])

    # ---- 输出 ----
    W = 74
    print("=" * W)
    print("国网 Demo 演示前自检  |  %s  |  %s" % (time.strftime("%Y-%m-%d %H:%M:%S"), ROOT))
    print("=" * W)
    icon = {"PASS": "[ OK ]", "FAIL": "[FAIL]", "WARN": "[WARN]", "INFO": "[INFO]", "SKIP": "[SKIP]"}
    for level, name, detail in rows:
        print("%s %-14s %s" % (icon.get(level, "[    ]"), name, detail))
    nf = sum(1 for r in rows if r[0] == "FAIL")
    nw = sum(1 for r in rows if r[0] == "WARN")
    print("-" * W)
    if nf:
        print("结论：NO-GO —— %d 项阻断。修完再上台。" % nf)
    elif nw:
        print("结论：GO（带 %d 条提醒）。按提醒处置后上台。" % nw)
    else:
        print("结论：GO —— 页面、数据、库、登录态都齐。")
    print("=" * W)
    return 0 if not nf else 1


if __name__ == "__main__":
    sys.exit(main())
