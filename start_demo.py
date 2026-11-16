#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""国网 Demo 一键启动。

三种模式：
  默认        直接用系统浏览器打开对客页面（file:// 方式，零进程、断网可用）
  --serve     起本地只读 HTTP 服务（127.0.0.1:8899），给出更像"系统"的地址；
              关闭命令行窗口即停止。
  --live      额外拉起 BFF（127.0.0.1:8787），页面抽屉里的「现场跑 46 条」才真的能跑。
              不起 BFF 时那块会明说"没连上"，不会拿快照冒充实时结果。

只用 Python 标准库，不依赖 requests / flask，任何 python3 都能跑。
"""
import argparse
import http.server
import os
import socketserver
import sys
import threading
import urllib.parse
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))

PAGES = [
    ("国网物资部_评标辅助工作台_W3.html", "对客界面 · 评标辅助工作台 W3",
     "8 个视图；「投标文件审批」= 6 家 × 8 条 48 格；格子里的抽屉可「现场跑 46 条」（需 --live 起 BFF）"),
    ("国网Demo_演示控制台_V7.html", "内部举证 · 演示控制台 V7", "12 个页签：P0-P7 体检流程 + B1-B3 术语/规则库"),
    (os.path.join("demo_pack_v2", "README_怎么讲.md"), "带货说明 · 怎么讲", "页面顺序、口播要点、兜底方案"),
]

INDEX = """<!doctype html><meta charset="utf-8">
<title>国网 Demo 入口</title>
<style>
 body{{font:15px/1.7 -apple-system,"Microsoft YaHei",sans-serif;background:#f5f6f8;color:#1c2430;
      margin:0;padding:48px 24px}}
 .w{{max-width:820px;margin:0 auto}}
 h1{{font-size:22px;margin:0 0 6px}} .sub{{color:#5b6675;margin-bottom:28px}}
 a.card{{display:block;background:#fff;border:1px solid #e2e6ec;border-radius:10px;padding:18px 20px;
        margin-bottom:12px;text-decoration:none;color:inherit}}
 a.card:hover{{border-color:#2f6fed;box-shadow:0 2px 12px rgba(47,111,237,.12)}}
 .t{{font-size:16px;font-weight:600;color:#2f6fed}} .d{{color:#5b6675;font-size:13px;margin-top:4px}}
 .note{{margin-top:22px;padding:14px 16px;background:#fff;border-left:3px solid #f0a020;
        border-radius:4px;font-size:13px;color:#5b6675}}
</style>
<div class="w"><h1>国网招标审核 · 演示入口</h1>
<div class="sub">本地只读服务 · 仅监听 127.0.0.1 · 数据已内嵌，断网可用</div>
{cards}
<div class="note">关掉命令行窗口即停止服务。若只想快速看一眼，直接双击目录里的
「国网物资部_评标辅助工作台_W3.html」更快，效果一样。</div></div>
"""


def build_index():
    cards = []
    for path, title, desc in PAGES:
        if not os.path.exists(os.path.join(HERE, path)):
            continue
        href = urllib.parse.quote(path.replace(os.sep, "/"))
        cards.append('<a class="card" href="%s"><div class="t">%s</div><div class="d">%s</div></a>'
                     % (href, title, desc))
    open(os.path.join(HERE, "_demo_index.html"), "w", encoding="utf-8").write(
        INDEX.format(cards="\n".join(cards)))
    return os.path.join(HERE, "_demo_index.html")


def build_to_bid():
    """生成一份"打开即落在投标文件审批视图"的副本。

    演示时少一次点击就少一次出错机会；副本每次从源页面重新生成，不与源脱钩。
    """
    src = os.path.join(HERE, "国网物资部_评标辅助工作台_W3.html")
    dst = os.path.join(HERE, "演示_直达投标审批.html")
    s = open(src, encoding="utf-8").read()
    inject = (
        "\n<script>window.addEventListener('load',function(){setTimeout(function(){"
        "var a=document.querySelector('.nav a[data-v=\"bid\"]');if(a)a.click();},150);});</script>\n"
        "</body>"
    )
    if "</body>" in s:
        s = s.replace("</body>", inject, 1)
    open(dst, "w", encoding="utf-8").write(s)
    return dst


def serve(port, page=None):
    build_index()
    os.chdir(HERE)

    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("127.0.0.1", port), Q) as httpd:
        # page 指定时直接落到那页（--live 用），否则落到入口页
        target = urllib.parse.quote(page) if page else "_demo_index.html"
        url = "http://127.0.0.1:%d/%s" % (port, target)
        print("服务已启动：%s" % url)
        print("（仅本机可访问；关闭此窗口即停止）")
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n已停止")


def start_bff():
    """起 BFF（127.0.0.1:8787），实时判定要用。

    页面里的「现场跑 46 条」是 HTTP 打到这个进程，再由它调 apemind CLI。
    不起它，页面上那块会明说"没连上"，不会假装跑过。
    """
    import subprocess
    env = dict(os.environ)
    env["BFF_PORT"] = "8787"
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "sgcc_bff.py")],
                         cwd=HERE, env=env)
    print("BFF 已启动（pid %d）→ http://127.0.0.1:8787/" % p.pid)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", action="store_true", help="起本地 HTTP 服务而不是直接开文件")
    ap.add_argument("--live", action="store_true",
                    help="起 BFF:8787 + 静态服务，打开带「实时判定」的业务页面（隐含 --serve）")
    ap.add_argument("--to-bid", action="store_true",
                    help="打开直达页：一打开就停在「投标文件审批」（6 家 × 8 条）")
    ap.add_argument("--port", type=int, default=8899)
    a = ap.parse_args()

    if a.live:
        proc = start_bff()
        try:
            serve(a.port, page="国网物资部_评标辅助工作台_W3.html")
        finally:
            proc.terminate()
            print("BFF 已停止")
        return 0

    if a.serve:
        serve(a.port)
        return 0

    target = os.path.join(HERE, "国网物资部_评标辅助工作台_W3.html")
    if not os.path.exists(target):
        print("找不到对客页面：%s" % target)
        print("请确认 start_demo.py 与页面放在同一目录。")
        return 2

    if a.to_bid:
        target = build_to_bid()
        print("已生成直达页：%s" % target)
        print("打开后直接停在「投标文件审批」：6 家 × 8 条，48 格可点开看算式与原文。")
    uri = "file:///" + urllib.parse.quote(target.replace(os.sep, "/"))
    print("正在打开：%s" % target)
    print("打开后点左侧「投标文件审批」，就是 6 家 × 8 条那张表；任一格可点开看算式与原文。")
    webbrowser.open(uri)
    return 0


if __name__ == "__main__":
    sys.exit(main())
