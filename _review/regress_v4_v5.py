# -*- coding: utf-8 -*-
"""P0 回归：证明 v5 向后兼容 + 注入路径成立。

四个阶段，任一不过即退出码 1：

  A 兼容  不传 rules 时，v5 与 v4 输出逐字段一致（只容忍 elapsed_ms 计时抖动）
  B 注入  把内嵌 V2 原样当 inp.rules 传入 → 判定结果与 A 完全一致、
          且实算指纹 == RULE_SET_SHA（证明 slim 口径与生成器同源）
  C 改规则 传入被改过的规则（把某条 check 恒真）→ 该条结论确实翻转
          （证明"改规则不用发版"这件事真的生效，不是摆设）
  D 闸门  伪造指纹 → 只留痕不改判；未知 rule_id → 必须抛错

做法：本地注入假的 apemind_fn.Context（只提供 main 用到的 step），
直接 import 两版 main.py 并对同一批入参调用 main()，逐键深比。
不连平台、不发版。

用法：python _review/regress_v4_v5.py
"""
import importlib.util
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4 = os.path.join(HERE, "_review", "_bak_main_v4.py")
V5 = os.path.join(HERE, "sgcc_fn_rule_judge", "main.py")
INPUTS = ["宜昌", "襄阳", "黄石", "荆州", "恩施", "华中"]

# elapsed_ms 是墙钟测量值：同一份代码连跑两次也不会相等（1ms 与 4ms 都出现过）。
# 它是唯一的合法差异项，且下面会单独校验它仍是合理的非负整数，
# 避免把"NoSuchField"这类真问题也一并放过。
VOLATILE = {"elapsed_ms"}


class _FakeStep:
    def __init__(self, *a, **k):
        pass

    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


class FakeContext:
    """只实现 main() 实际用到的那一个方法。"""

    def __init__(self):
        self.state = {}

    def step(self, name, detail=None):
        return _FakeStep()


def install_fake_sdk():
    mod = types.ModuleType("apemind_fn")
    mod.Context = FakeContext
    sys.modules["apemind_fn"] = mod


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(mod, payload):
    out = mod.main(mod.Input(**payload), FakeContext())
    return json.loads(json.dumps(out.model_dump(), ensure_ascii=False, default=str))


def deep_diff(a, b, path="", leaves=None):
    """返回差异路径列表；leaves 累计实际比对过的叶子数（防空洞通过）。"""
    diffs = []
    if type(a) is not type(b):
        return ["%s: 类型 %s != %s" % (path or "<root>", type(a).__name__, type(b).__name__)]
    if isinstance(a, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a:
                diffs.append("%s.%s: 仅 v5 有" % (path, k))
            elif k not in b:
                diffs.append("%s.%s: 仅 v4 有" % (path, k))
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


def strip_volatile(o, extra=()):
    """剔除白名单字段（root 级）。返回 (比对副本, 被剔掉的值)。"""
    drop = set(VOLATILE) | set(extra)
    return ({k: v for k, v in o.items() if k not in drop},
            {k: o[k] for k in drop if k in o})


def drop_prefix(diffs, prefixes):
    """按路径前缀过滤差异。用于剔除"本就该变"的元信息字段，其余一律不许放过。"""
    return [d for d in diffs if not any(d.startswith(p) for p in prefixes)]


def load_payload(name):
    p = os.path.join(HERE, "_judge_in_%s.json" % name)
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def main():
    install_fake_sdk()
    m4 = load(V4, "judge_v4")
    m5 = load(V5, "judge_v5")

    print("v4 sha=%s   v5 sha=%s" % (m4.RULE_SET_SHA, m5.RULE_SET_SHA))
    if m4.RULE_SET_SHA != m5.RULE_SET_SHA:
        print("!! 规则指纹变了，说明规则表被动过，先查这个")
        return 1

    fails = []
    leaf_total = 0

    # ---------------------------------------------------------------- A 兼容
    print("\n=== A 兼容：不传 rules，v5 应与 v4 逐字段一致 ===")
    base = {}
    for name in INPUTS:
        payload = load_payload(name)
        if payload is None:
            print("%-4s 跳过（缺入参）" % name)
            continue
        o4 = run(m4, payload)
        o5 = run(m5, payload)
        base[name] = (payload, o5)

        # v5 新增字段，比对前剔除；除白名单外不应有任何差异
        c5, _ = strip_volatile(o5, extra={"rule_source"})
        c4, t4 = strip_volatile(o4)
        leaves = [0]
        d = deep_diff(c4, c5, "", leaves)
        leaf_total += leaves[0]

        # elapsed_ms 合法差异校验：两边都必须是合理非负整数
        em4, em5 = t4.get("elapsed_ms"), o5.get("elapsed_ms")
        if not (isinstance(em4, int) and isinstance(em5, int) and 0 <= em5 < 60000):
            fails.append("%s elapsed_ms 不是合理测量值：v4=%r v5=%r" % (name, em4, em5))

        if d:
            fails.append("%s 差异 %d 处: %s" % (name, len(d), d[:3]))
            print("%-4s 差异 %d 处: %s" % (name, len(d), d[:3]))
        else:
            print("%-4s 一致 叶子=%d | 46行 decided=%d counts=%s | %dms/%dms | rule_source=%s"
                  % (name, leaves[0], o5["decided"], o5["counts"], em4, em5, o5["rule_source"]))
        if o5.get("rule_source") != "embedded":
            fails.append("%s 未传 rules 时 rule_source 应为 embedded，实为 %r"
                         % (name, o5.get("rule_source")))

    # 防空洞：一共比了多少叶子。46 行 × 十余字段，六家上线应为数千。
    print("\nA 阶段累计比对叶子数 = %d" % leaf_total)
    if leaf_total < 1500:
        fails.append("A 阶段叶子数仅 %d，比对可能空洞，不能算通过" % leaf_total)

    # ---------------------------------------------------------------- B 注入
    print("\n=== B 注入：内嵌 V2 原样传入，结论应不变、指纹应自洽 ===")
    keep = list(m5._KEEP_FIELDS)
    embedded_rules = [{k: r[k] for k in keep if k in r} for r in m5.RULES_V2["rules"]]
    for name in INPUTS:
        if name not in base:
            continue
        payload, o_ref = base[name]
        p2 = dict(payload)
        p2["rules"] = embedded_rules
        p2["rule_set_version"] = "V2"
        p2["rule_set_sha"] = m5.RULE_SET_SHA
        o2 = run(m5, p2)

        c_ref, _ = strip_volatile(o_ref)
        c2, _ = strip_volatile(o2)
        leaves = [0]
        d = deep_diff(c_ref, c2, "", leaves)
        # 注入模式本就会改这三项元信息，按前缀剔除后单独断言（下面 ok_src/ok_sha/ok_ver）。
        meta = (".rule_set", ".rule_set_sha", ".rule_set_version", ".rule_source")
        d = drop_prefix(d, meta)
        if d:
            fails.append("B %s 注入后结论变了 %d 处: %s" % (name, len(d), d[:3]))
            print("%-4s 注入后不一致 %d 处: %s" % (name, len(d), d[:3]))
            continue
        ok_src = o2.get("rule_source") == "input"
        ok_sha = o2.get("rule_set_sha") == m5.RULE_SET_SHA
        ok_ver = o2.get("rule_set") == "V2"
        ok_note = not any("rule_set_sha" in n for n in o2.get("notes") or [])
        print("%-4s rule_source=%s sha=%s ver=%s 无冲突留痕=%s"
              % (name, o2.get("rule_source"), o2.get("rule_set_sha"),
                 o2.get("rule_set"), ok_note))
        if not (ok_src and ok_sha and ok_ver and ok_note):
            fails.append("B %s 注入元信息不对：src=%r sha=%r ver=%r 留痕=%r"
                         % (name, o2.get("rule_source"), o2.get("rule_set_sha"),
                            o2.get("rule_set"), o2.get("notes")))

    # ---------------------------------------------------------------- C 改规则
    print("\n=== C 改规则：把一条判否行的判定式改成恒真，该条结论须翻转 ===")
    # 必须挑「已有明确结论」的行来改：待澄清行是缺字段导致的，改判定式照样缺字段，
    # 结论不会变（第一版脚本挑行1 就踩了这个坑，报了假红）。
    pick = None
    for n in INPUTS:
        if n in base and base[n][1]["fail_rows"]:
            pick = (n, base[n][1])
            break
    if pick:
        name, o_ref = pick
        payload = base[name][0]
        row_no = o_ref["fail_rows"][0]
        row_ref = next(r for r in o_ref["rows"] if r["row"] == row_no)
        mutated = [dict(r) for r in embedded_rules]
        target = next(r for r in mutated if r["row"] == row_no)
        # 恒真式用本家投标人名做等值：bid.bidder_name 一定存在且等于 o_ref["bidder"]，
        # 所以这条判定式在该入参上必然通过，不依赖任何缺字段。
        target["check"] = {"op": "eq", "lhs": "bid.bidder_name", "rhs": o_ref["bidder"]}
        p3 = dict(payload)
        p3["rules"] = mutated
        p3["rule_set_version"] = "V3-TEST"
        o3 = run(m5, p3)
        row_new = next(r for r in o3["rows"] if r["row"] == row_no)
        changed = row_new["state"] != row_ref["state"]
        print("%-4s 行%d %s(%s) → %s(%s) | sha %s → %s"
              % (name, row_no, row_ref["state"], row_ref["reason"][:24],
                 row_new["state"], row_new["reason"][:24],
                 o_ref["rule_set_sha"], o3["rule_set_sha"]))
        print("      counts %s → %s" % (o_ref["counts"], o3["counts"]))
        if not changed:
            fails.append("C 改规则后行%d结论未变，注入路径没生效（%s）"
                         % (row_no, row_ref["state"]))
        if o3["rule_set_sha"] == o_ref["rule_set_sha"]:
            fails.append("C 改了规则但指纹没变，指纹闸失效")
        if o3["rule_set"] != "V3-TEST":
            fails.append("C 外部版本名没生效：%r" % o3["rule_set"])
    else:
        fails.append("C 无可用入参（六家都无判否行）")

    # ---------------------------------------------------------------- D 闸门
    print("\n=== D 闸门：伪造指纹只留痕；未知 rule_id 必炸 ===")
    dname = pick[0] if pick else next((n for n in INPUTS if n in base), None)
    if dname:
        payload, o_ref = base[dname]
        p4 = dict(payload)
        p4["rules"] = embedded_rules
        p4["rule_set_sha"] = "deadbeefdeadbeef"
        o4t = run(m5, p4)
        c_ref, _ = strip_volatile(o_ref)
        c4t, _ = strip_volatile(o4t)
        # rule_source（embedded→input）与 notes（多一条指纹留痕）本就该变，
        # 先剔除再单独断言，避免用"放宽比对"掩盖真问题。
        d = drop_prefix(deep_diff(c_ref, c4t, ""),
                        (".rule_set", ".rule_set_sha", ".rule_source", ".notes"))
        notes4 = o4t.get("notes") or []
        hit = [n for n in notes4 if "rule_set_sha" in n]
        ver_hint = [n for n in notes4 if "rule_set_version" in n]
        extra_notes = [n for n in notes4 if n not in hit and n not in ver_hint]
        print("伪造指纹 → 留痕 %d 条（含未传版本名提示 %d 条）" % (len(notes4), len(ver_hint)))
        for n in notes4:
            print("     · %s" % n[:78])
        if not hit:
            fails.append("D 伪造指纹未写进 notes，留痕缺失")
        if not ver_hint:
            fails.append("D 未传版本名时缺『指纹口径不同』提示，会把口径差异误报成规则被改")
        if extra_notes:
            fails.append("D 伪造指纹带出了无关 note，判定过程被污染：%s" % extra_notes[:2])
        if d:
            fails.append("D 伪造指纹影响了判定结论：%s" % d[:3])

        # D2：同样伪造指纹，但把版本名传对 → 只应剩「指纹不一致」一条，不该再多嘴。
        p5 = dict(p4)
        p5["rule_set_version"] = "V2"
        o5t = run(m5, p5)
        notes5 = o5t.get("notes") or []
        print("伪造指纹+传对版本名 → 留痕 %d 条（应为 1，且无口径提示）" % len(notes5))
        if any("rule_set_version" in n for n in notes5):
            fails.append("D2 版本名已传对却仍提示口径差异，提示逻辑写错了")
        if len(notes5) != 1:
            fails.append("D2 期望恰好 1 条留痕，实为 %d 条：%s" % (len(notes5), notes5[:2]))
    else:
        fails.append("D 无可用入参")

    try:
        run(m5, {"rule_ids": ["GW-HB-FJ-999", "不存在"]})
        fails.append("D 未知 rule_id 没有抛错——这正是最容易出现的假绿")
        print("未知 rule_id → 未抛错（不合格）")
    except ValueError as e:
        print("未知 rule_id → ValueError：%s…" % str(e)[:60])
    except Exception as e:  # noqa: BLE001
        fails.append("D 未知 rule_id 抛了非 ValueError：%s: %s" % (type(e).__name__, e))

    # ---------------------------------------------------------------- 结论
    print()
    if fails:
        print("结论：%d 项不通过 —— 不能发布" % len(fails))
        for f in fails:
            print("  - %s" % f)
        return 1
    print("结论：A/B/C/D 四阶段全过 —— 向后兼容成立，注入路径生效，闸门有效")
    return 0


if __name__ == "__main__":
    sys.exit(main())
