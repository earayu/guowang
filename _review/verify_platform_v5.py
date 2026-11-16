# -*- coding: utf-8 -*-
"""平台侧核验：证明线上 v5 真的向后兼容、且注入路径真的生效。

与 _review/regress_v4_v5.py 的分工：
  regress_v4_v5.py  纯本地，证明两份 main.py 行为一致；
  本脚本            走真实 CLI 调线上 v5，把平台出参与「本地 v4 真值」逐字段对比。

A 裸调    六家各调一次（不传 rules）→ 与本地 v4 逐字段一致，rule_source=embedded
B 注入    宜昌把内嵌 V2 原样传回去 → 结论不变、rule_source=input、指纹自洽
C 改规则  宜昌把一条判否行的判定式改恒真 → 该行翻转、指纹变化（线上真的按传入规则判）

网络：apemind.ai 直连不通，只有 Clash(7897) 能到；CLI 只在 no_proxy 未设置时才吃代理，
故这里用 env -u NO_PROXY 的方式调用。

用法：python _review/verify_platform_v5.py [--only A,B,C]
"""
import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import types

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLI = os.path.join(HERE, "apemind-cli", "apemind.exe")
V4 = os.path.join(HERE, "_review", "_bak_main_v4.py")
SLUG = "sgcc-rule-judge"
INPUTS = ["宜昌", "襄阳", "黄石", "荆州", "恩施", "华中"]
PROXY = "http://127.0.0.1:7897"
VOLATILE = {"elapsed_ms"}

ENV = {k: v for k, v in os.environ.items() if k.lower() not in ("no_proxy",)}
ENV.update({"HTTPS_PROXY": PROXY, "https_proxy": PROXY,
            "HTTP_PROXY": PROXY, "http_proxy": PROXY})


# ---------------------------------------------------------------- 本地 v4 真值
class _FakeStep:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


class FakeContext:
    def __init__(self):
        self.state = {}

    def step(self, name, detail=None):
        return _FakeStep()


def load_v4():
    mod = types.ModuleType("apemind_fn")
    mod.Context = FakeContext
    sys.modules["apemind_fn"] = mod
    spec = importlib.util.spec_from_file_location("judge_v4", V4)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------- CLI
def cli(args, tries=6):
    last = ""
    for i in range(tries):
        p = subprocess.run([CLI] + args + ["--format", "json"],
                           capture_output=True, text=True, encoding="utf-8",
                           env=ENV, timeout=300)
        out = (p.stdout or "") + (p.stderr or "")
        try:
            d = json.loads(p.stdout)
        except Exception:
            last = out.strip()[:300]
            time.sleep(2)
            continue
        if d.get("type") == "error" and d.get("error", {}).get("code") == "network_unavailable":
            last = "network_unavailable"
            time.sleep(3)
            continue
        return d
    raise RuntimeError("CLI 多次重试仍失败：%s" % last)


def invoke(payload, tmpdir, tag):
    path = os.path.join(tmpdir, "in_%s.json" % tag)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False)
    d = cli(["function", "invoke", SLUG, "--input", path])
    data = d.get("data") or {}
    if data.get("status") != "succeeded":
        raise RuntimeError("%s 调用未成功：status=%r err=%r %r"
                           % (tag, data.get("status"), data.get("error_code"),
                              (data.get("error_message") or "")[:200]))
    return data


def deep_diff(a, b, path="", leaves=None):
    diffs = []
    if type(a) is not type(b):
        return ["%s: 类型 %s != %s" % (path or "<root>", type(a).__name__, type(b).__name__)]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                diffs.append("%s.%s: 仅 平台 有" % (path, k))
            elif k not in b:
                diffs.append("%s.%s: 仅 本地 有" % (path, k))
            else:
                diffs += deep_diff(a[k], b[k], "%s.%s" % (path, k), leaves)
    elif isinstance(a, list):
        if len(a) != len(b):
            diffs.append("%s: 长度 %d != %d" % (path, len(a), len(b)))
        for i in range(min(len(a), len(b))):
            diffs += deep_diff(a[i], b[i], "%s[%d]" % (path, i), leaves)
    else:
        if leaves is not None:
            leaves[0] += 1
        if a != b:
            diffs.append("%s: %r != %r" % (path, a, b))
    return diffs


def strip(o, extra=()):
    drop = set(VOLATILE) | set(extra)
    return {k: v for k, v in o.items() if k not in drop}


def norm_out(raw):
    """平台出参统一化成与本地 model_dump 同形的 dict。"""
    return json.loads(json.dumps(raw, ensure_ascii=False, default=str))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="A,B,C")
    a = ap.parse_args()
    only = {x.strip().upper() for x in a.only.split(",") if x.strip()}

    m4 = load_v4()
    fails = []
    tmp = tempfile.mkdtemp(prefix="v5plat_")
    plat = {}

    # ------------------------------------------------------------ A 裸调
    if "A" in only:
        print("=== A 裸调：平台 v5（不传 rules）vs 本地 v4 真值 ===")
        leaf_total = 0
        for name in INPUTS:
            p = os.path.join(HERE, "_judge_in_%s.json" % name)
            if not os.path.exists(p):
                print("%-4s 跳过（缺入参）" % name)
                continue
            payload = json.load(open(p, encoding="utf-8"))

            t0 = time.time()
            data = invoke(payload, tmp, "A_" + name)
            wall = (time.time() - t0) * 1000
            out = norm_out(data["output"])
            plat[name] = out

            ref = json.loads(json.dumps(
                m4.main(m4.Input(**payload), FakeContext()).model_dump(),
                ensure_ascii=False, default=str))

            leaves = [0]
            d = deep_diff(strip(ref), strip(out, extra={"rule_source"}), "", leaves)
            leaf_total += leaves[0]
            if d:
                fails.append("A %s 与本地 v4 不一致 %d 处: %s" % (name, len(d), d[:3]))
                print("%-4s 不一致 %d 处: %s" % (name, len(d), d[:3]))
            else:
                print("%-4s 一致 叶子=%d | decided=%d counts=%s | 平台 %dms 墙钟 %dms | sha=%s src=%s"
                      % (name, leaves[0], out["decided"], out["counts"],
                         out["elapsed_ms"], wall, out["rule_set_sha"], out["rule_source"]))
            if out["rule_source"] != "embedded":
                fails.append("A %s rule_source 应为 embedded，实为 %r" % (name, out["rule_source"]))
            if out["rule_set_sha"] != m4.RULE_SET_SHA:
                fails.append("A %s 指纹 %r != 内嵌 %r" % (name, out["rule_set_sha"], m4.RULE_SET_SHA))
        print("A 累计比对叶子数 = %d" % leaf_total)
        if leaf_total < 1500:
            fails.append("A 叶子数仅 %d，比对可能空洞" % leaf_total)

    # ------------------------------------------------------------ B 注入
    if "B" in only:
        print("\n=== B 注入：把内嵌 V2 原样传回平台 → 结论应不变、来源应变成 input ===")
        name = "宜昌"
        if name not in plat:
            payload = json.load(open(os.path.join(HERE, "_judge_in_%s.json" % name), encoding="utf-8"))
            plat[name] = norm_out(invoke(payload, tmp, "B_base")["output"])
        rules = m4.RULES_V2["rules"]
        payload = json.load(open(os.path.join(HERE, "_judge_in_%s.json" % name), encoding="utf-8"))
        p2 = dict(payload)
        p2["rules"] = rules
        p2["rule_set_version"] = "V2"
        p2["rule_set_sha"] = m4.RULE_SET_SHA
        out2 = norm_out(invoke(p2, tmp, "B_inject")["output"])

        d = [x for x in deep_diff(strip(plat[name]), strip(out2), "",
                                  None) if not x.startswith((".rule_set", ".rule_source"))]
        notes = out2.get("notes") or []
        print("rule_source=%s rule_set=%s sha=%s 留痕 %d 条"
              % (out2["rule_source"], out2["rule_set"], out2["rule_set_sha"], len(notes)))
        if d:
            fails.append("B 注入后结论与裸调不一致 %d 处: %s" % (len(d), d[:3]))
            print("  不一致:", d[:3])
        else:
            print("  结论与裸调逐字段一致 | decided=%d counts=%s"
                  % (out2["decided"], out2["counts"]))
        if out2["rule_source"] != "input":
            fails.append("B rule_source 应为 input，实为 %r" % out2["rule_source"])
        if out2["rule_set_sha"] != m4.RULE_SET_SHA:
            fails.append("B 传入 46 条规则后实算指纹 %r != 内嵌 %r（slim 口径不一致）"
                         % (out2["rule_set_sha"], m4.RULE_SET_SHA))

        # C 改规则
        if "C" in only:
            print("\n=== C 改规则：把一条判否行改恒真，线上该行须翻转 ===")
            fail_rows = plat[name]["fail_rows"]
            if not fail_rows:
                fails.append("C 无判否行可改")
            else:
                rn = fail_rows[0]
                mut = [dict(r) for r in rules]
                tgt = next(r for r in mut if r["row"] == rn)
                tgt["check"] = {"op": "eq", "lhs": "bid.bidder_name",
                                "rhs": plat[name]["bidder"]}
                p3 = dict(payload)
                p3["rules"] = mut
                p3["rule_set_version"] = "V3-LIVE"
                out3 = norm_out(invoke(p3, tmp, "C_mutate")["output"])
                ref_row = next(r for r in plat[name]["rows"] if r["row"] == rn)
                new_row = next(r for r in out3["rows"] if r["row"] == rn)
                print("行%d %s → %s | counts %s → %s | sha %s → %s"
                      % (rn, ref_row["state"], new_row["state"],
                         plat[name]["counts"], out3["counts"],
                         plat[name]["rule_set_sha"], out3["rule_set_sha"]))
                if new_row["state"] == ref_row["state"]:
                    fails.append("C 行%d 改规则后结论未变（%s）" % (rn, ref_row["state"]))
                if out3["rule_set_sha"] == plat[name]["rule_set_sha"]:
                    fails.append("C 改规则后指纹未变，指纹闸失效")
                if out3["rule_set"] != "V3-LIVE":
                    fails.append("C 外部版本名未生效：%r" % out3["rule_set"])

    print()
    if fails:
        print("结论：%d 项不通过" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    print("结论：平台 v5 核验全过（A 向后兼容 / B 注入生效 / C 改规则真生效）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
