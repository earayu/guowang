# -*- coding: utf-8 -*-
"""量三段耗时：CLI 进程开销、平台函数自报耗时、出参体积。

为什么要分段：BFF 每来一次判定请求就 spawn 一次 apemind.exe。
"慢"到底慢在进程启动、慢在网络、还是慢在函数里的 46 条判定，不量清楚就优化等于猜。
"""
import json
import subprocess
import sys
import time

CLI = r"./apemind-cli/apemind.exe"
INP = "_judge_in_宜昌.json"


def run(n=3):
    rows = []
    for _ in range(n):
        t0 = time.perf_counter()
        p = subprocess.run([CLI, "function", "invoke", "sgcc-rule-judge",
                            "--input", INP, "--json"],
                           capture_output=True)
        wall = (time.perf_counter() - t0) * 1000
        try:
            d = json.loads(p.stdout.decode("utf-8"))["data"]
        except Exception:
            print("FAIL", p.stdout[:200], p.stderr[:300])
            sys.exit(1)
        out_bytes = len(json.dumps(d["output"], ensure_ascii=False).encode("utf-8"))
        rows.append((wall, d["elapsed_ms"], out_bytes, d["id"]))
        print("  wall=%7.1f ms  fn=%5d ms  out=%6d B  run=%s"
              % (wall, d["elapsed_ms"], out_bytes, d["id"]))
    cli_overhead = sum(w - f for w, f, _, _ in rows) / len(rows)
    print("\n  CLI 进程+网络开销（wall - fn）均值：%.1f ms" % cli_overhead)
    print("  出参平均：%.1f KB" % (sum(b for _, _, b, _ in rows) / len(rows) / 1024))


if __name__ == "__main__":
    print("判定函数逐次调用：")
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 3)
