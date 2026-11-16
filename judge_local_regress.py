# -*- coding: utf-8 -*-
"""判定函数本地回归：把平台侧 main.py 当普通模块跑，逐条对比 F3 真跑基线。

为什么要单独做这一步：函数一旦上了平台，回归就只剩"看上去对"。
这里在**发布之前**用同一份现场抽取原文（_f3v2_bid_live.json + F3 证据里的基准侧 fields）
跑 6 家 × 46 条，逐条比 state 与 F3 证据是否一致；不一致就不许发。

stub 说明：pydantic / apemind_fn 只在平台沙箱里存在，本地用最小替身，
只实现 BaseModel 的 kwargs 构造与 Context.step 的上下文管理器，不模拟校验逻辑。
"""
import contextlib
import importlib.util
import io
import json
import sys
import types

F3 = "国网Demo_F3_46条规则端到端_真跑证据_V2.json"
LIVE = "_f3v2_bid_live.json"
TENDER_OUT = "_f3v2_tender_out.json"
OUT = "_judge_local_regress.json"


def _install_stubs():
    if "pydantic" not in sys.modules:
        class _FieldInfo:
            def __init__(self, default=None, default_factory=None, **_):
                self.default = default
                self.default_factory = default_factory

        class BaseModel:
            def __init__(self, **kw):
                ann = {}
                for cls in reversed(type(self).__mro__):
                    ann.update(getattr(cls, "__annotations__", {}) or {})
                for k in ann:
                    if k in kw:
                        setattr(self, k, kw[k])
                    elif isinstance(getattr(type(self), k, None), _FieldInfo):
                        fi = getattr(type(self), k)
                        setattr(self, k, fi.default_factory() if fi.default_factory else fi.default)
                    elif hasattr(type(self), k):
                        setattr(self, k, getattr(type(self), k))
                    else:
                        setattr(self, k, None)
                for k, v in kw.items():
                    setattr(self, k, v)

        m = types.ModuleType("pydantic")
        m.BaseModel = BaseModel
        m.Field = lambda default=None, **kw: _FieldInfo(default=default, **kw)
        sys.modules["pydantic"] = m

    if "apemind_fn" not in sys.modules:
        class Context:
            def step(self, name, detail=None):
                return contextlib.nullcontext()

        m = types.ModuleType("apemind_fn")
        m.Context = Context
        sys.modules["apemind_fn"] = m


def load_judge():
    spec = importlib.util.spec_from_file_location("judge_fn", "sgcc_fn_rule_judge/main.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    _install_stubs()
    J = load_judge()

    f3 = json.load(io.open(F3, encoding="utf-8"))
    live = json.load(io.open(LIVE, encoding="utf-8"))

    # 基准侧用现场的完整输出（_f3v2_tender_out.json）。F3 证据里只摘了 value_text/source，
    # 丢了 value_num 与 items 明细——拿它重跑会把行10 判成"限价未拆到物料级"、
    # 行16 判成"90 与 None 不可比"，看着像引擎坏了，其实是输入被削过。
    import os
    if os.path.exists(TENDER_OUT):
        tender_fields = json.load(io.open(TENDER_OUT, encoding="utf-8"))["fields"]
        # _f3v2_tender_out.json 落盘于 v26 那一轮，交货期还是 NOT_FOUND；
        # F3 最终跑的是 v27（带标段号定向问句后抽到 2026-04-20）。
        # 两份必须合并：items/value_num 只有 out 里有，交货期只有证据 meta 里是 v27 的值。
        # 不合并就会把 row7 判成 UNCERTAIN，白丢一条已跑通的判否。
        meta_fields = f3["meta"]["tender_extract"]["fields"]
        merged = []
        for f in tender_fields:
            m = meta_fields.get(f["field"]) if isinstance(meta_fields, dict) else None
            if m and m.get("value_text") not in (None, "NOT_FOUND"):
                f = dict(f, value_text=m["value_text"])
            merged.append(f)
        tender_fields = merged
    else:
        tender_fields = f3["meta"]["tender_extract"]["fields"]
        if isinstance(tender_fields, dict):
            tender_fields = [dict(v, field=k) for k, v in tender_fields.items()]
        print("[warn] 未找到 %s，退回证据摘要（items/value_num 会缺）" % TENDER_OUT)

    bids = live["bidders"]
    # 每家 facts 先翻译一次，作为其他家的 peer（行39 法定代表人重复要跨家比）
    facts_by = {}
    for b in bids:
        notes = []
        f = {}
        f.update(J.build_tender(tender_fields, notes))
        f.update(J.build_bid(b["fields"], b["bidder"], notes))
        facts_by[b["bidder"]] = f

    report = {"generated": None, "cases": [], "summary": {}}
    import time
    report["generated"] = time.strftime("%Y-%m-%d %H:%M:%S")

    total_cmp, total_bad = 0, 0
    for m in f3["matrix"]:
        bidder = m["bidder"]
        peers = [v for k, v in facts_by.items() if k != bidder]
        out = J.main(J.Input(section_no=f3["meta"]["section_no"], bidder=bidder,
                             tender_fields=tender_fields,
                             bid_fields=next(b["fields"] for b in bids if b["bidder"] == bidder),
                             peer_facts=peers), sys.modules["apemind_fn"].Context())

        got = {r.rule_id: r for r in out.rows}
        diffs = []
        for d in m["decided"]:
            total_cmp += 1
            g = got.get(d["rule_id"])
            if g is None:
                diffs.append({"rule_id": d["rule_id"], "row": d["row"],
                              "base": d["state"], "now": "MISSING_RULE"})
            elif g.state != d["state"]:
                diffs.append({"rule_id": d["rule_id"], "row": d["row"],
                              "base": d["state"], "now": g.state,
                              "base_reason": d.get("reason"), "now_reason": g.reason})
        total_bad += len(diffs)
        report["cases"].append({
            "bidder": bidder, "code": m["code"], "expect": m["expect"],
            "decided_in_evidence": len(m["decided"]),
            "rows_out": out.total, "counts": out.counts, "fail_rows": out.fail_rows,
            "uncertain_rows": out.uncertain_rows,
            "rule_set_sha": out.rule_set_sha, "elapsed_ms": out.elapsed_ms,
            "diffs": diffs,
            "key_rows": {str(k): next((r.state for r in out.rows if r.row == k), None)
                         for k in (4, 7, 10, 11, 13, 16, 17, 39)},
        })

    report["summary"] = {"compared": total_cmp, "mismatch": total_bad,
                         "cases": len(report["cases"])}
    io.open(OUT, "w", encoding="utf-8").write(json.dumps(report, ensure_ascii=False, indent=1))

    print("对比条目 : %d" % total_cmp)
    print("不一致   : %d" % total_bad)
    for c in report["cases"]:
        print("  %-4s %-6s fail=%s unc=%s diff=%d  %s"
              % (c["code"], c["bidder"][:6], c["fail_rows"], c["uncertain_rows"],
                 len(c["diffs"]), c["key_rows"]))
    if total_bad:
        print("\n不一致明细：")
        for c in report["cases"]:
            for d in c["diffs"]:
                print("  %s row%s %s → %s | %s → %s"
                      % (c["code"], d["row"], d["base"], d["now"],
                         str(d.get("base_reason"))[:60], str(d.get("now_reason"))[:60]))
        raise SystemExit(1)
    print("\n回归通过：平台侧判定与 F3 真跑基线逐条一致")


if __name__ == "__main__":
    main()
