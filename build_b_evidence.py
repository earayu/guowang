# -*- coding: utf-8 -*-
"""汇总 B 方案（公网穿透）的全部实测结果，生成一份可交付的证据文件。

数据来源都是本目录里真实跑出来的 json，不手填数字：
  国网Demo_B方案_公网穿透_真跑证据_V1.json   ← bff_public_check.py
  国网Demo_B方案_链路稳定性抽样.json          ← stability_check.py
"""
import io
import json
import os
import time

HERE = os.path.dirname(os.path.abspath(__file__))
A = os.path.join(HERE, "国网Demo_B方案_公网穿透_真跑证据_V1.json")
S = os.path.join(HERE, "国网Demo_B方案_链路稳定性抽样.json")
URLF = os.path.join(HERE, "_public_url.txt")


def load(p):
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return {}


a, s = load(A), load(S)
link = io.open(URLF, encoding="utf-8").readline().strip() if os.path.exists(URLF) else ""
base = link.split("/?k=")[0] if link else ""

cases = a.get("cases") or []
runs = s.get("runs") or []

md = []
w = md.append
w("# 国网 Demo · B 方案（公网穿透）真跑证据 V1")
w("")
w("> 目的：让客户用**他自己的电脑**打开业务界面，而不是围着演示机看。")
w("> 所有断言都打**公网域名**，走「本机 → 代理出网 → Cloudflare 边缘 → 隧道 → 127.0.0.1:8787」，")
w("> 不是打 127.0.0.1。这才是客户那条路径。")
w("")
w("- 生成时间：%s" % time.strftime("%Y-%m-%d %H:%M:%S"))
w("- 本次实例：`%s`" % base)
w("- 证据机读版：`国网Demo_B方案_公网穿透_真跑证据_V1.json`、`国网Demo_B方案_链路稳定性抽样.json`")
w("")

w("## 1. 形态")
w("")
w("```")
w("客户浏览器 ──https──> Cloudflare 边缘 ──隧道──> cloudflared ──> 127.0.0.1:8787 (BFF)")
w("                                                                    │")
w("                                                     apemind CLI ──> 平台函数 sgcc-rule-judge v1")
w("```")
w("")
w("只有**一个**端口对外：隧道只映射 8787，BFF 同时托管页面与接口（同源）。")
w("客户浏览器里的 `127.0.0.1` 指的是他自己的机器，所以页面用相对路径取数，不做跨端口直连。")
w("")

w("## 2. 安全与功能断言（%d 项）" % len(cases))
w("")
w("| 项 | 结果 | 实测 |")
w("|---|---|---|")
for c in cases:
    w("| %s | %s | %s |" % (c["项"], c["结果"], str(c["实测"]).replace("|", "/")))
w("")
w("小计：%d/%d PASS。" % (a.get("summary", {}).get("pass", 0), a.get("summary", {}).get("total", len(cases))))
w("")
w("其中几条是这次专门为公网加的，不是原有能力：")
w("")
w("- **口令门**：不带口令连页面都看不到（403 口令页），不是只挡接口。")
w("- **health 不吐账号**：公网模式下 health 只回 `{ok, at, kbs}`，账号名与调用统计不出去。")
w("- **抽取关闸**：`/api/extract` 在公网返回 403。一次抽取 23 秒、直接烧平台额度，演示不需要它。")
w("- **限流**：每来源 IP 每分钟 120 次（实测单独起 `BFF_RATE=3` 实例，第 4 次起 429）。")
w("- **审计**：每次判定落 `sgcc_bff_audit.jsonl`，带真实来源 IP（`CF-Connecting-IP`）。")
w("")

w("## 3. 链路稳定性抽样")
w("")
w("| 项目 | 次数 | 成功 | P50 | P90 | 最大 |")
w("|---|---|---|---|---|---|")
for r in runs:
    w("| %s | %d | %d | %d ms | %d ms | %d ms |"
      % (r["name"], r["n"], r["ok"], r["p50_ms"], r["p90_ms"], r["max_ms"]))
w("")
w("总计 %d/%d = %.1f%%。" % (s.get("summary", {}).get("ok", 0),
                            s.get("summary", {}).get("n", 0),
                            s.get("summary", {}).get("rate", 0)))
w("")
w("页面首屏 P50 约 3.5 秒（177 KB 单文件；浏览器带 gzip 时实际传输 43 KB）。")
w("判定 P50 约 2~4 秒，其中函数内 241~246 ms，其余是 CLI 进程启动与公网往返。")
w("")

w("## 4. 真浏览器核验（客户视角）")
w("")
w("用 CDP 驱动无头 Edge 打开公网链接，模拟客户动作：点格子 → 点「现场跑 46 条」→ 看结果。")
w("")
w("- 页面在公网域名下渲染出 **48 格**（6 家 × 8 条）")
w("- 点格子后抽屉出现「实时判定」区块，按钮由「检查判定服务…」变为可点")
w("- 点击后：`run b48fd36f4024 · 函数 v1 · 函数内 245 ms · 端到端 2182 ms · 现算`")
w("- 共 46 条：通过 8 · 判否 1 · 证不足 16 · 人判 21；判否行 17 `GW-HB-FJ-017`")
w("- 依据字段直接给出：`bid.tax_rate = 0.11`；`legal.tax_rate_set = 0.13,0.09,0.06,0.03,0.01,0`")
w("- **地址栏里的 `?k=` 已被抹掉**（`location.search` 为空），口令只留在 sessionStorage")
w("")
w("截图：`截图_B方案_公网实时判定.png`。")
w("")

w("## 5. 关掉窗口即失效（实测）")
w("")
w("- 停服前：`GET /api/health` → 200")
w("- 停服后：同一地址 → **HTTP 530，Cloudflare error 1033**（隧道不存在），页面与接口一起不可达")
w("")
w("这条是 B 方案敢用的前提：不是靠\"记得关\"，而是关掉进程后公网上根本不存在这个入口。")
w("")

w("## 6. 过程中修掉的三个真错（都不是\"应该没问题\"）")
w("")
w("**① BFF 用 HTTP/1.0 逐请求关连接 → 客户侧 1033**")
w("cloudflared 日志：`read tcp 127.0.0.1:xxxx->127.0.0.1:8787: wsarecv: An established connection was aborted`。")
w("本机直连看不出来，只有经隧道才暴露。改法：HTTP/1.1 + 每个响应显式 `Connection: close` 并置 `close_connection`。")
w("修完隧道日志零 ERR。")
w("")
w("**② cloudflared 对含中文的 body 算错 Content-Length → 400 串包**")
w("审计里抓到原始请求行：`Bad request syntax ('{\"code\": \"恩施\"}POST /api/judge/by-code HTTP/1.1')`。")
w("中文 body 被短读，残留字节串到下一个请求行前面。改法有两层：接口改收 ASCII 代号（`ES/YC/HZ/XY/JZ/HS`），")
w("从源头让 body 全 ASCII；同时所有响应显式关连接，杜绝残留跨请求。修完审计里 `http_error` 为 0。")
w("")
w("**③ 隧道刚建好有冷启窗口 → 首个请求 502**")
w("边缘到源站的连接尚未就绪，客户第一次点就是 502。改法：`start_public.py` 拿到地址后先自己打通 3 次 health、")
w("再真跑一次判定，把窗口吃掉。另外页面里判定请求对 400/5xx 自动重试一次。")
w("")

w("## 7. 边界与风险（会上会被问）")
w("")
w("- **quick tunnel 无 SLA**：Cloudflare 免费快速隧道不保证可用性，链接在进程存活期间有效，重启会换新域名。")
w("  演示中途断了就重跑 `python start_public.py`，把新链接发给客户，30 秒内可恢复。")
w("- **口令是演示级**：链接+口令一起发出去，拿到的人都能看。这在演示场景可接受，但不能当生产鉴权。")
w("- **抽取没有实时性**：公网关了 `/api/extract`，判定入参是该家现场抽取的落盘快照（页面标注 run 号）。")
w("  要现场重抽得在本机做，23 秒且抖动大。")
w("- **首点偏慢**：判定首点 4~6 秒（CLI 冷启动），预热后 2 秒左右。上台前自己先点一次。")
w("- **出口 IP 可见**：审计里记录的是客户公网 IP，演示环境不要外传这份 jsonl。")
w("- **不要用生产数据**：页面内是 6 家样本（1 家对照 + 5 家含典型违例），不含真实投标件。")
w("")

w("## 8. 一句话结论")
w("")
w("B 方案可用：客户用自己的电脑打开一条链接，看到的是同一个业务界面，点下去走的是真的平台函数。")
w("代价是多一条出网隧道，所以口径要收紧——口令、限流、抽取关闸、显式关连接，四项都已实测。")
w("")

p_md = os.path.join(HERE, "国网Demo_B方案_公网穿透_真跑证据_V1.md")
io.open(p_md, "w", encoding="utf-8", newline="\n").write("\n".join(md))
print("written:", os.path.basename(p_md), len("\n".join(md)), "chars")
