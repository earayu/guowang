# -*- coding: utf-8 -*-
"""从判定函数导出「规则源」JSON，供 BFF 注入与客户侧维护共用。

规则源格式（与函数入参 inp.rules 完全同形）：
  {"version": "V2", "rules": [ {15 个 KEEP 字段} ... ]}

为什么只保留 15 个字段：函数的指纹口径就是对这 15 个字段做的（build_judge_fn.py 的
slim_rules）。多带字段不会影响判定，但会让 BFF 算出的指纹与函数实算对不上，
每次调用都多一条"指纹不一致"留痕，演示时看着像出了问题。

用法：
  python _review/make_rules_source.py                 # 写 _review/rules_source_v2.json
  python _review/make_rules_source.py --out X.json    # 指定输出
"""
import argparse
import hashlib
import importlib.util
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAIN = os.path.join(HERE, "sgcc_fn_rule_judge", "main.py")


def load_fn():
    class _S:
        def __enter__(self):
            return None

        def __exit__(self, *a):
            return False

    class Ctx:
        def __init__(self):
            self.state = {}

        def step(self, name, detail=None):
            return _S()

    mod = types.ModuleType("apemind_fn")
    mod.Context = Ctx
    sys.modules["apemind_fn"] = mod
    spec = importlib.util.spec_from_file_location("judge_v5", MAIN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "_review", "rules_source_v2.json"))
    a = ap.parse_args()

    m = load_fn()
    keep = list(m._KEEP_FIELDS)
    rules = [{k: r[k] for k in keep if k in r} for r in m.RULES_V2["rules"]]
    version = m.RULE_SET_VERSION
    doc = {"version": version, "rules": rules}

    sha = hashlib.sha256(json.dumps(
        {"meta": {"version": version, "n": len(rules)}, "rules": rules},
        ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()[:16]

    print("rules          : %d" % len(rules))
    print("导出指纹       : %s" % sha)
    print("函数内嵌指纹   : %s  %s" % (m.RULE_SET_SHA, "一致" if sha == m.RULE_SET_SHA else "不一致！"))
    if sha != m.RULE_SET_SHA:
        print("导出内容与函数内嵌集不同源，拒绝写出", file=sys.stderr)
        return 1

    with open(a.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print("written        : %s  %d bytes" % (a.out, os.path.getsize(a.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
