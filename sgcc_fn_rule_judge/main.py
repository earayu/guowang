# -*- coding: utf-8 -*-
"""46 条否决情形判定器（受限 DSL 执行器，平台侧）。

输入是抽取器（sgcc-field-extract）的原始输出：基准侧 fields + 受审侧 fields。
函数内先做「抽取原文 → 判定事实」翻译（签章否定优先、签章名去后缀、逐行报价去重、
日期取 ISO 串），再按分派表 V2 逐条执行判定式。

设计红线（与本仓 sgcc_rule_runner.py 完全一致，引擎段逐字复用）：
  1. 不用 eval/exec/compile；算子白名单穷举，未知算子抛错。
  2. 依赖字段缺失 → UNCERTAIN，绝不降级成 NOT_RESPONDED。
  3. 结论上限恒为 CANDIDATE；HUMAN/EXTERNAL/OUT_OF_SCOPE 恒 NEED_HUMAN。
  4. 每条判定带证据位置 + 用到的字段快照，可回读。

跨投标人聚合（行 39 法定代表人重复）必须传 peer_facts；只给一家时该条返回 UNCERTAIN，
不能拿"组里只有自己"当成"组内无重复"——那是假绿。
"""

import json
import hashlib
import math
import re
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from apemind_fn import Context

MISSING = object()

STATE_PASS = "RESPONDED"          # 已响应（候选）
STATE_FAIL = "NOT_RESPONDED"      # 未见响应（候选）
STATE_UNK = "UNCERTAIN"           # 证不足，转澄清
STATE_HUMAN = "NEED_HUMAN"        # 只能人判


# ---------------------------------------------------------------- 取值与函数
def _norm(v):
    if v is MISSING:
        return MISSING
    s = str(v)
    for a, b in (("（", "("), ("）", ")"), (" ", ""), ("　", ""), ("·", "")):
        s = s.replace(a, b)
    return s.strip().lower()


def _norm_list(v):
    return MISSING if v is MISSING else [_norm(x) for x in v]


def floor_yuan(v):
    if v is MISSING:
        return MISSING
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return MISSING


def round2(v):
    if v is MISSING:
        return MISSING
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return MISSING


def mul(a, b):
    if a is MISSING or b is MISSING:
        return MISSING
    try:
        return float(a) * float(b)
    except (TypeError, ValueError):
        return MISSING


def ratio(a, b):
    if a is MISSING or b is MISSING:
        return MISSING
    try:
        b = float(b)
        return MISSING if b == 0 else float(a) / b
    except (TypeError, ValueError):
        return MISSING


def days_until(target, base):
    """target 日期距 base 还有多少天（base 当天为 0）。"""
    if target is MISSING or base is MISSING:
        return MISSING
    try:
        t = datetime.fromisoformat(str(target)[:10]).date()
        b = datetime.fromisoformat(str(base)[:10]).date()
        return (t - b).days
    except ValueError:
        return MISSING


def eval_threshold(spec, base):
    """把招标文件里的「报价平均值规定值」参数化成阈值（base 由调用方传入）。"""
    if spec is MISSING or not isinstance(spec, dict) or base is MISSING:
        return MISSING
    try:
        if "mult" in spec:
            return float(base) * float(spec["mult"])
        if "add_pct" in spec:
            return float(base) * (1 + float(spec["add_pct"]) / 100.0)
    except (TypeError, ValueError):
        return MISSING
    return MISSING


FUNCS = {
    "normalize": _norm,
    "normalize_list": _norm_list,
    "floor_yuan": floor_yuan,
    "round2": round2,
    "ratio": ratio,
    "mul": mul,
    "days_until": days_until,
    "eval_threshold": eval_threshold,
}

CMP = {
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "gt": lambda a, b: _cmp(a, b, lambda x, y: x > y),
    "ge": lambda a, b: _cmp(a, b, lambda x, y: x >= y),
    "lt": lambda a, b: _cmp(a, b, lambda x, y: x < y),
    "le": lambda a, b: _cmp(a, b, lambda x, y: x <= y),
    "in": lambda a, b: a in b,
    "not_in": lambda a, b: a not in b,
}


def _date_of(v):
    """ISO 日期/日期的宽松识别。真实招标数据里的交货期是绝对日期，不是天数。"""
    if isinstance(v, (date, datetime)):
        return v if isinstance(v, date) and not isinstance(v, datetime) else v.date()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", str(v).strip())
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            return None
    return None


def _cmp(a, b, fn):
    """同类型才比较：日期比日期、数字比数字。类型不一致直接报不可比，不硬转。"""
    da, db = _date_of(a), _date_of(b)
    if da is not None and db is not None:
        return fn(da, db)
    try:
        return fn(float(a), float(b))
    except (TypeError, ValueError):
        raise NeedMissing("不可比较：%r 与 %r 类型不一致" % (a, b))


# ---------------------------------------------------------------- 求值
class NeedMissing(Exception):
    pass


def _operand(spec, ctx, group):
    """解析 lhs / rhs：可能是字面量、字段名、函数调用。"""
    if not isinstance(spec, str):
        if isinstance(spec, list):
            return [(_operand(x, ctx, group) if isinstance(x, str) and x in ctx else x)
                    for x in spec]
        return spec

    # 函数调用形如 normalize(bid.seal_name)
    if "(" in spec and spec.endswith(")"):
        fn = spec[:spec.index("(")]
        inner = spec[spec.index("(") + 1:-1]
        args = []
        for part in _split_args(inner):
            args.append(_operand(part.strip(), ctx, group))
        if fn not in FUNCS:
            raise KeyError("算子未在白名单: " + fn)
        if any(a is MISSING for a in args):
            raise NeedMissing(fn)
        v = FUNCS[fn](*args)
        # 算子自己也可能"算不出来"（floor_yuan(None)、ratio 除零）而返回 MISSING。
        # 让它一路传下去，下一个 float() 就是一记 TypeError，错的是整条链路而不是这条规则。
        if v is MISSING:
            raise NeedMissing("%s(...) 无有效结果" % fn)
        return v

    if spec in ctx:
        v = ctx[spec]
        if v is MISSING:
            raise NeedMissing(spec)
        return v
    if spec.startswith(("bid.", "tender.", "peer.", "legal.")):
        raise NeedMissing(spec)
    return spec  # 字面量


def _item_map(v, amount_key="cap_yuan", key="item_no"):
    """把逐物料明细归一成 {行项目号: 金额(元)}。

    接受两种形状，因为限价明细来自抽取器（list[dict]），而投标明细可能被
    上游给成 dict{item_no: 金额}。两种都要认，否则对位会静默变成空表。
    """
    out = {}
    if isinstance(v, dict):
        for k, val in v.items():
            f = None
            try:
                f = float(val)
            except (TypeError, ValueError):
                f = None
            if f is not None:
                out[str(k)] = f
        return out
    if isinstance(v, (list, tuple)):
        for d in v:
            if not isinstance(d, dict):
                continue
            no = str(d.get(key) or d.get("item_no") or d.get("itemNo") or "").strip()
            if not no:
                continue
            amt = None
            for cand in (amount_key, "cap_yuan", "amount_yuan", "price_yuan", "amount"):
                if d.get(cand) is not None:
                    try:
                        amt = float(d[cand])
                        break
                    except (TypeError, ValueError):
                        continue
            if amt is None and d.get("cap_wan") is not None:
                try:
                    amt = float(d["cap_wan"]) * 10000       # 表头单位是万元
                except (TypeError, ValueError):
                    amt = None
            if amt is not None:
                out[no] = amt
    return out


def _bid_amounts(ctx, node):
    """把投标逐行报价换算成「与限价同口径」的金额，供行10 对位。

    限价表（附表一）列的是**含税**限价，投标分项报价表列的是**未含税**合价。
    两者直接比是拿 407 万去比 453 万，宜昌那行含税 460 万超限价 6.69 万会被判成合规。
    口径由 dispatch 节点的 amount_basis 显式声明，不在代码里按规则号写死：

      ex_tax（默认）  : 直接取未含税行合价
      tax_incl        : 未含税行合价 ×(1+税率)，并按行10 原文「剔除角和分」向下取整到元

    换算不出来的行**不返回**，由调用方按「少行」报缺证——宁可转澄清，不能静默丢行判合规。
    """
    lhs = node.get("lhs")
    raw = ctx.get(lhs) if isinstance(lhs, str) else None
    if not isinstance(raw, (list, dict)):
        return {}
    key = node.get("key", "item_no")
    if (node.get("amount_basis") or "ex_tax") != "tax_incl":
        return _item_map(raw, amount_key="amount_yuan", key=key)

    import math
    ctx_tax = ctx.get("bid.tax_rate")
    out = {}
    rows = (raw.items() if isinstance(raw, dict)
            else [(d.get(key), d) for d in raw if isinstance(d, dict)])
    for no, d in rows:
        try:
            if isinstance(d, dict):
                amt = d.get("amount_yuan")
                tax = d.get("tax_rate", ctx_tax)
            else:
                amt, tax = d, ctx_tax
            if amt is None or tax is None:
                continue
            out[str(no).strip()] = float(math.floor(float(amt) * (1 + float(tax))))
        except (TypeError, ValueError):
            continue
    return out


def _split_args(s):
    out, depth, cur = [], 0, ""
    for ch in s:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def evaluate(node, ctx, group=None):
    """返回 True / False；依赖缺失抛 NeedMissing。"""
    op = node["op"]

    if op in ("and", "or"):
        vals = []
        for a in node["args"]:
            try:
                vals.append(evaluate(a, ctx, group))
            except NeedMissing:
                vals.append(None)
        if op == "and":
            if any(v is False for v in vals):
                return False          # 短路：一项确定不过即不过
            if any(v is None for v in vals):
                raise NeedMissing("and:部分未知")
            return True
        else:
            if any(v is True for v in vals):
                return True
            if any(v is None for v in vals):
                raise NeedMissing("or:部分未知")
            return False

    if op == "per_item_amount_check":
        # 行11：单价×数量与合价是否自洽。
        # 必须逐行比。用「合计数量×合计单价」去比总价是错的——4 行相加后误差互相抵消，
        # 某一行小数点错位（453.31 万写成 45.331 万）会被另外三行掩盖，总额看着还对。
        items = _operand(node["lhs"], ctx, group)
        if not items:
            raise NeedMissing("无分项报价明细")
        bad, checked = [], 0
        # 金额容差：文件里未含税单价带两位小数，合价列在表格化/抽取时常被取整到元
        # （7,892,920.35 读成 7,892,920）。逐行差 0.5 元以内是取整口径，不是「小数点错误」。
        # 真正的错位（4,079,790 写成 407,979）差三个数量级，放宽到 0.5 元也照样抓得住。
        tol = float(node.get("tolerance_yuan") or 0.01)
        for it in items:
            q, up = it.get("qty"), it.get("unit_price_yuan")
            amt, calc = it.get("amount_yuan"), it.get("calc_amount_yuan")
            if q is None or up is None or amt is None:
                continue
            checked += 1
            if calc is None:
                calc = round(float(q) * float(up), 2)
            if abs(float(calc) - float(amt)) > tol:
                bad.append({"item_no": it.get("item_no"), "qty": q, "unit_price": up,
                            "calc": calc, "claimed": amt,
                            "diff": round(float(amt) - float(calc), 2)})
        if checked == 0:
            raise NeedMissing("分项报价表的数量/单价列未解析出数值")
        # 合计行与逐行之和也要对得上（表内自带合计时）
        declared = ctx.get("bid.price_items.declared_total_yuan", MISSING)
        sum_yuan = sum(it.get("amount_yuan") or 0 for it in items)
        sum_diff = None
        total_tol = max(1.0, tol * max(1, len(items)))
        declared_suspect = None
        raw_diff = None
        if isinstance(declared, (int, float)) and declared:
            raw_diff = int(sum_yuan) - int(declared)
            sum_diff = 0 if abs(raw_diff) <= total_tol else raw_diff
            if sum_diff:
                # 合计和逐行和对不上，先排除「合计值其实取到了某一行的合价」。
                # 那是抽取取错行，不是投标人算错；拿它判否等于用错的数当证据。
                # 只有合计值不等于任何单行，才算合计真的不平。
                hit = [it.get("item_no") for it in items
                       if it.get("amount_yuan") is not None
                       and abs(float(declared) - float(it.get("amount_yuan"))) <= total_tol]
                if hit:
                    declared_suspect = {"declared_total_yuan": int(declared),
                                        "equals_row": hit[0],
                                        "why": "合计行疑似取到单行合价，本次不据此判否"}
                    sum_diff = None
        ctx["bid.price_items.sum_check"] = {
            "checked_lines": checked, "bad_lines": bad,
            "items_sum_yuan": int(sum_yuan),
            "declared_total_yuan": (int(declared) if isinstance(declared, (int, float))
                                    and declared else None),
            "sum_diff_yuan": sum_diff,
            "raw_sum_diff_yuan": raw_diff,
            "tolerance_yuan": tol,
            "declared_suspect": declared_suspect,
        }
        if bad:
            return False
        if sum_diff not in (None, 0):
            return False
        return True

    if op == "group_dup_le":
        # 组内同值计数 <= n 视为合规。全空 = 该情形不适用 = 不触发否决。
        field = node["lhs"]
        vals = [g.get(field, MISSING) for g in group]
        vals = [v for v in vals if v is not MISSING and v is not None]
        if not vals:
            return True
        counts = {}
        for v in vals:
            counts[_norm(v)] = counts.get(_norm(v), 0) + 1
        return max(counts.values()) <= int(node["rhs"])

    if op == "group_no_overlap":
        # 「制造商与其授权代理商参加同一标包投标」。
        # 必须逐对跨投标人比：某家的制造商 == 另一家的代理对象。
        # 原实现是「两个集合整体求交」，把「同一家自己 manufacturer==agent_of」
        # （制造商自己投标，正常情形）也算成冲突，两家代理不同制造商时会误判成串标。
        # 实测就是这条：甲代理某制造商、乙代理另一制造商，被判 NOT_RESPONDED。
        lhs, rhs = node["lhs"], node["rhs"]
        for i, gi in enumerate(group):
            maker = gi.get(lhs, MISSING)
            if maker in (MISSING, None):
                continue
            for j, gj in enumerate(group):
                if i == j:
                    continue
                agent = gj.get(rhs, MISSING)
                if agent in (MISSING, None):
                    continue
                if _norm(maker) == _norm(agent):
                    return False
        return True

    if op == "all_satisfy":
        req = _operand(node["rhs"], ctx, group)
        got = _operand(node["lhs"], ctx, group)
        if not req:
            raise NeedMissing("基准未结构化")
        if not got:
            raise NeedMissing("响应未结构化")
        got_map = {k: v for k, v in (got.items() if isinstance(got, dict) else [])}
        for k, need in (req.items() if isinstance(req, dict) else []):
            if k not in got_map:
                raise NeedMissing("缺响应项:" + k)
            if str(got_map[k]) != str(need):
                return False
        return True

    if op == "all_within_tolerance":
        req = _operand(node["rhs"], ctx, group)
        got = _operand(node["lhs"], ctx, group)
        if not req:
            raise NeedMissing("偏差范围未结构化")
        if not got:
            raise NeedMissing("响应未结构化")
        for k, tol in (req.items() if isinstance(req, dict) else []):
            if k not in got:
                raise NeedMissing("缺响应项:" + k)
            try:
                if abs(float(got[k])) > float(tol):
                    return False
            except (TypeError, ValueError):
                raise NeedMissing("非数值:" + k)
        return True

    if op == "per_item_within_cap":
        # 抽取器判定「该标段不在限价表内、且表注写明表外均不设限价」时会置
        # tender.price_cap_applicable=False。此时本条根本不成立，不能因为拿不到
        # 明细就转 UNCERTAIN——那会把「不设限价」这种合规结论误伤成待澄清。
        # 只在严格等于 False 时才走这条；字段缺失一律按原路径处理。
        if ctx.get("tender.price_cap_applicable", MISSING) is False:
            return True
        # 逐物料对位：以行项目号为键，逐条比「投标报价 <= 该行项目最高限价」。
        # 为什么不能单值比：一个标段常有多条物料、各自一个限价，
        # 取最小会把只超其中一条的投标误判成全部超，取最大又会放过超限的那条。
        caps = _item_map(_operand(node["rhs"], ctx, group), key=node.get("key", "item_no"))
        if not caps:
            raise NeedMissing("最高限价未拆到物料级")

        if node.get("amount_basis") == "tax_incl":
            raw0 = ctx.get(node.get("lhs"))
            has_row_tax = isinstance(raw0, (list, tuple)) and any(
                isinstance(d, dict) and d.get("tax_rate") is not None for d in raw0)
            if not has_row_tax and ctx.get("bid.tax_rate") is None:
                # 缺税率时必须说清是缺税率，别让它一路降到「缺总价」的理由上
                raise NeedMissing("缺税率：未含税行价无法换算到含税口径，不得判合规")

        bids = _bid_amounts(ctx, node)
        raw_rows = ctx.get(node.get("lhs")) if isinstance(node.get("lhs"), str) else None
        if isinstance(raw_rows, (list, tuple)) and bids and len(bids) < len(raw_rows):
            # 有行没换算出金额（缺税率等）→ 这部分没证，少一行也算少
            raise NeedMissing("有 %d 行报价无法换算到与限价同口径（缺税率或金额）"
                              % (len(raw_rows) - len(bids)))

        if bids:
            over, uncovered = [], []
            for no, amt in bids.items():
                cap = caps.get(no)
                if cap is None:
                    uncovered.append(no)          # 投标报了限价表里没有的行项目
                    continue
                if amt > cap:
                    over.append(no)
            if over:
                return False
            if uncovered:
                # 有报价行对不上限价行 → 这部分没证，不能判合规，但已比过的都合规，
                # 也不能判否。转澄清是唯一诚实的出口。
                raise NeedMissing("有 %d 条报价行在限价表中无对应行项目：%s"
                                  % (len(uncovered), ",".join(sorted(uncovered)[:3])))
            return True

        # 只有标包总价：只允许单向判否。总价超合计 → 必然超（可以不看明细就判否）；
        # 总价未超合计 → 不能判合规，因为可能某条物料超、另一条拉着总额没超。
        fb = node.get("fallback_total")
        if fb:
            total = _operand(fb, ctx, group)
            # 标包总价缺失时 floor_yuan(None) 返回 MISSING 而不是抛错。
            # 不在这里拦，float(MISSING) 会直接 TypeError，整条规则连带整包判定
            # 一起炸掉（平台侧发布检查就是这么发现的）。缺证就该走 UNCERTAIN。
            if total is MISSING or total is None:
                raise NeedMissing("未取得标包总价，无法与限价合计比较")
            cap_sum = sum(caps.values())
            if float(total) > cap_sum:
                return False
            raise NeedMissing("仅取得标包总价 %s，未超限价合计 %s，无法确认逐物料合规"
                              % (int(float(total)), int(cap_sum)))
        raise NeedMissing("未取得逐物料报价")

    if op in CMP:
        a = _operand(node["lhs"], ctx, group)
        b = _operand(node["rhs"], ctx, group)
        try:
            return CMP[op](a, b)
        except (TypeError, ValueError):
            raise NeedMissing("%s 类型不可比" % op)

    raise KeyError("算子未在白名单: " + op)


# ---------------------------------------------------------------- 逐物料对位明细
def diagnose_items(rule, ctx, group=None):
    """给 per_item_within_cap 类规则补齐可读明细：每条物料对到哪一行、差多少。

    evaluate 只回 True/False，审计时看不出「到底哪条超了」。判定与明细分开算，
    两边各自调用同一个 _item_map，避免为了出明细把判定逻辑复制一遍。
    """
    node = rule.get("check") or {}
    if node.get("op") != "per_item_within_cap":
        return None
    if ctx.get("tender.price_cap_applicable", MISSING) is False:
        return {"basis": "not_applicable", "why": "该标段不在限价表内，表注写明表外不设限价"}
    try:
        caps = _item_map(_operand(node["rhs"], ctx, group), key=node.get("key", "item_no"))
    except (NeedMissing, KeyError):
        return {"basis": "none", "why": "限价明细未取到"}
    if not caps:
        return {"basis": "none", "why": "限价明细为空"}

    lhs = node.get("lhs")
    bids = _bid_amounts(ctx, node)

    if not bids:
        fb = node.get("fallback_total")
        total, cap_sum = None, sum(caps.values())
        if fb:
            try:
                total = float(_operand(fb, ctx, group))
            except (NeedMissing, KeyError, TypeError, ValueError):
                total = None
        return {"basis": "total", "cap_sum_yuan": int(cap_sum),
                "bid_total_yuan": None if total is None else int(total),
                "why": "只有标包总价，逐物料明细缺失；此分支只能单向判否"}

    lines = []
    for no, cap in caps.items():
        amt = bids.get(no)
        lines.append({
            "item_no": no,
            "cap_yuan": int(cap),
            "bid_yuan": None if amt is None else int(amt),
            "delta_yuan": None if amt is None else int(amt - cap),
            "state": ("未报价" if amt is None
                      else ("超限" if amt > cap else "合规")),
        })
    extra = sorted(set(bids) - set(caps))
    return {"basis": "item", "cap_sum_yuan": int(sum(caps.values())),
            "amount_basis": node.get("amount_basis") or "ex_tax",
            "items": lines,
            "over": [x["item_no"] for x in lines if x["state"] == "超限"],
            "missing_quote": [x["item_no"] for x in lines if x["state"] == "未报价"],
            "unmatched_quote": extra}


# ---------------------------------------------------------------- 执行
def run_rule(rule, ctx, group):
    path = rule["exec_path"]
    base = {"rule_id": rule["rule_id"], "row": rule["row"],
            "category": rule["category"], "subcategory": rule["subcategory"],
            "exec_path": path, "evidence": rule["evidence"]}

    if path in ("HUMAN", "EXTERNAL", "OUT_OF_SCOPE"):
        base.update(state=STATE_HUMAN, reason="本路径不作机器判定",
                    gate=rule.get("human_gate") or rule.get("external_source"),
                    used_fields=[], signals=rule.get("signals") or [])
        return base

    used, missing, gaps = [], [], []
    for f in rule["needs"]:
        v = ctx.get(f, MISSING)
        if v is MISSING or v is None:
            missing.append(f)
        else:
            used.append({"field": f, "value": v})

    # 「不适用」不等于「缺证」。招标文件写「本项目免收投标保证金」时，
    # 金额本来就抽不出数——把它当缺证报 UNCERTAIN，等于让一条明确不成立的
    # 否决情形一直挂在待澄清里，白白吃人工复核工时。
    na = [f for f in rule["needs"] if ctx.get(f + ".__na") is True]
    if na:
        base.update(state=STATE_PASS, used_fields=used, missing_fields=[], optional_gaps=gaps,
                    conclusion_ceiling="CANDIDATE",
                    reason="情形不适用：%s 在文件中明确为免收/不设，本条否决情形不成立"
                           % "、".join(na))
        return base

    # optional_needs 只做证据快照，不参与「缺证不判否」的反向保护。
    # 行10 就靠这个：只要限价明细在，哪怕投标侧只有总价，也允许单向判否。
    for f in (rule.get("optional_needs") or []):
        v = ctx.get(f, MISSING)
        if v is MISSING or v is None:
            gaps.append(f)
        else:
            used.append({"field": f, "value": v})

    try:
        ok = evaluate(rule["check"], ctx, group)
        state = STATE_PASS if ok else STATE_FAIL
        # 文案只对客，不改判定：ok 表示该条款的「合规条件」是否成立。
        # 早先写「判定式成立/不成立」，专家会把「判否 + 判定式不成立」读成自相矛盾，
        # 评审 P0-1 已定案，改为业务语义。
        reason = ("合规条件成立，本条未触发" if ok
                  else "合规条件不成立，本条否决情形成立")
        # 反向保护：判 FAIL 却缺字段，视为证不足
        if state == STATE_FAIL and missing:
            state, reason = STATE_UNK, "判否但缺字段：" + ",".join(missing)
            missing = []
    except NeedMissing as e:
        state, reason = STATE_UNK, "缺字段/基准未结构化：%s" % e
    except KeyError as e:
        state, reason = STATE_UNK, "算子异常：%s" % e

    base.update(state=state, reason=reason, used_fields=used,
                missing_fields=missing, optional_gaps=gaps,
                conclusion_ceiling="CANDIDATE")
    # 逐物料类规则补一份对位明细，审计时能直接看出哪条物料超、超多少
    detail = diagnose_items(rule, ctx, group)
    if detail is not None:
        base["item_check"] = detail
        if detail.get("basis") == "not_applicable":
            base["reason"] = ("本标段不在最高限价表内，表注写明「表内以外的其他标段及其涉及的物料"
                              "均不设限价」，本条未触发")
        if detail.get("basis") == "item":
            if detail.get("over"):
                over_txt = "、".join(
                    "%s 报 %d 超限价 %d（超 %d）"
                    % (x["item_no"], x["bid_yuan"], x["cap_yuan"], x["delta_yuan"])
                    for x in detail["items"] if x["state"] == "超限")
                base["reason"] = "逐物料对位：%s" % over_txt
            elif state == STATE_PASS and detail.get("missing_quote"):
                base["reason"] = ("逐物料对位：已报物料全部未超，"
                                  "%d 条物料未报价（漏项归其他规则）"
                                  % len(detail["missing_quote"]))
            elif state == STATE_PASS:
                base["reason"] = ("逐物料对位：%d 条物料全部未超各自限价，"
                                  "报价合计 %d <= 限价合计 %d"
                                  % (len(detail["items"]),
                                     sum(x["bid_yuan"] or 0 for x in detail["items"]),
                                     detail["cap_sum_yuan"]))
        elif detail.get("basis") == "total" and detail.get("bid_total_yuan") is not None:
            if state == STATE_FAIL:
                base["reason"] = ("仅取得标包总价 %d > 限价合计 %d，单向判否"
                                  "（总额已超，无需逐物料即可确认）"
                                  % (detail["bid_total_yuan"], detail["cap_sum_yuan"]))
    return base


# ================================================================ 抽取原文 → 判定事实

LEGAL_TAX = [0.13, 0.09, 0.06, 0.03, 0.01, 0.0]
LEGAL_TAX_SRC = "财税〔2018〕32 号、财政部税务总局海关总署公告 2019 年第 39 号：13%/9%/6%/3%/1%/0"

AGG_OPS = ("group_dup_le", "group_no_overlap")


def parse_seal_present(t):
    """签章是否加盖。否定优先。

    真跑抓到的坑：同一语义模型会给三种表述——
      「是（已加盖电子签章）」（襄阳）、「通过」（宜昌）、「是」（恩施）。
    只认含「加盖/签章」的，后两种会被当成「无法判定」→ 规则按缺字段不判，
    页面却显示字段有值，客户点开就会问「字段明明在，为什么说缺」。
    """
    t = str(t or "").strip()
    if any(x in t for x in ("未加盖", "无电子签章", "未签章", "缺签章", "未盖", "否", "没有")):
        return False
    if any(x in t for x in ("加盖", "签章", "通过", "已签", "是", "有")):
        return True
    return None


def parse_seal_valid(t):
    """签章有效性。否定词优先：襄阳的原文是「验证通过（签章主体与投标人不一致）」，
    只找「通过」二字会判成有效——这正是 v1 误伤过的地方。"""
    t = str(t or "")
    if any(x in t for x in ("不一致", "不符", "无效", "未通过", "失败", "不能验证")):
        return False
    if "通过" in t or "一致" in t:
        return True
    return None


def parse_date(t):
    m = re.search(r"\d{4}-\d{2}-\d{2}", str(t or ""))
    return m.group(0) if m else None


def _field_list(fields):
    """接受 list[dict] 或 dict{field: obj}（两种都是抽取器输出的实际形状）。"""
    if isinstance(fields, dict):
        out = []
        for k, v in fields.items():
            d = dict(v) if isinstance(v, dict) else {"field": k, "value_text": v}
            d.setdefault("field", k)
            out.append(d)
        return out
    return list(fields or [])


def build_tender(fields, notes):
    tf = {f.get("field"): f for f in _field_list(fields) if f.get("field")}
    tender = {}
    for k, f in tf.items():
        if f.get("value_text") == "NOT_FOUND":
            continue
        if k == "tender.price_cap":
            tender["tender.price_cap_items"] = [
                {"item_no": i["item_no"], "cap_yuan": i["cap_yuan"]} for i in (f.get("items") or [])]
            tender["tender.price_cap"] = f.get("items_sum_yuan")
            tender["tender.price_cap_applicable"] = bool(f.get("applicable"))
            if not tender["tender.price_cap_items"]:
                notes.append("基准侧限价明细为空：行10 只能走总价单向判否")
        else:
            # 交货期是 ISO 日期串，value_num 为空；按原文取，别送 None 进判定层
            tender[k] = (f.get("value_text") if k == "tender.required_delivery_date"
                         else f.get("value_num"))
            if f.get("applicable") is False:
                tender[k + ".__na"] = True
    tender["legal.tax_rate_set"] = LEGAL_TAX
    return tender


def build_bid(fields, bidder, notes):
    """把一家投标人的抽取结果翻译成判定层 ctx。"""
    ctx = {}
    fs = {f.get("field"): f for f in _field_list(fields) if f.get("field")}

    def g(name):
        return fs.get(name) or {}

    ctx["bid.bidder_name"] = bidder or g("bid.bidder_name").get("value_text")

    ctx["bid.seal_present"] = parse_seal_present(g("bid.seal_present").get("value_text"))
    if ctx["bid.seal_present"] is None:
        notes.append("seal_present 原文无法判定：%s" % g("bid.seal_present").get("value_text"))

    ctx["bid.seal_valid"] = parse_seal_valid(g("bid.seal_valid").get("value_text"))
    if ctx["bid.seal_valid"] is None:
        notes.append("seal_valid 原文无法判定：%s" % g("bid.seal_valid").get("value_text"))

    # 签章名称做归一：同一字段模型会给「XX有限公司」和「XX有限公司（电子签章）」两种写法，
    # 直接比会把后缀当成「签章主体与投标人不是同一人」→ 恩施被误判（真跑抓到）。
    _sn = str(g("bid.seal_name").get("value_text") or "")
    _sn = re.sub(r"[（(]\s*电子签章\s*[)）]", "", _sn).strip()
    ctx["bid.seal_name"] = _sn or None

    for name in ("bid.validity_days", "bid.tax_rate", "bid.price_total_ex_tax"):
        ctx[name] = g(name).get("value_num")

    ctx["bid.legal_rep_name"] = g("bid.legal_rep_name").get("value_text")
    ctx["bid.committed_delivery_date"] = parse_date(
        g("bid.committed_delivery_date").get("value_text"))

    f = g("bid.bond_amount")
    if f.get("applicable") is False:
        ctx["bid.bond_amount"] = None
        ctx["bid.bond_amount.__na"] = True
    else:
        ctx["bid.bond_amount"] = f.get("value_num")

    f = g("bid.price_items")
    items, seen = [], set()
    for it in (f.get("items") or []):
        no = it.get("item_no")
        if not no or no in seen:          # docx 汇总表与 xlsx 分项表同数据，按行号去重
            continue
        seen.add(no)
        items.append({"item_no": no, "qty": it.get("qty"),
                      "unit_price_yuan": it.get("unit_price_yuan"),
                      "amount_yuan": it.get("amount_yuan"),
                      "calc_amount_yuan": it.get("calc_amount_yuan"),
                      "arith_ok": it.get("arith_ok"),
                      # 只在行内确实带税率时才写这个键：写成 None 会让判定层
                      # 拿到 None 而不是回退到 bid.tax_rate，整表换算不出来。
                      **({"tax_rate": it["tax_rate"]} if it.get("tax_rate") is not None else {})})
    ctx["bid.price_items"] = items
    ctx["bid.price_items.items_sum_yuan"] = sum((i.get("amount_yuan") or 0) for i in items)
    dec = f.get("declared_total_yuan")
    if isinstance(dec, (int, float)) and dec:
        ctx["bid.price_items.declared_total_yuan"] = dec

    # 行46 比的是「投标价格」，口径应与限价表一致（含税）。抽取只给了未含税总价，
    # 这里按本家税率换算出一个含税总价，键名沿用 bid.price_total。
    # 注意：这是**派生值，不是抽取值**。派生只在能拿到税率时才做；
    # 拿不到就不写，绝不默认 13% —— 那会在税率本身就错的家（如 11%）身上造出错数。
    if ctx.get("bid.price_total") is None:
        ex = ctx.get("bid.price_total_ex_tax")
        tr = ctx.get("bid.tax_rate")
        if isinstance(ex, (int, float)) and isinstance(tr, (int, float)):
            ctx["bid.price_total"] = round(ex * (1 + tr), 2)
    return ctx


def _peer_ctx(p):
    """同行事实：可以是 facts 字典，也可以是抽取输出（自动翻译）。"""
    if not isinstance(p, dict):
        return {}
    if any(k.startswith(("bid.", "tender.")) for k in p):
        return dict(p)
    notes = []
    return build_bid(p.get("fields") or p.get("bid_fields") or [], p.get("bidder") or "", notes)


def _has_agg(node):
    if not isinstance(node, dict):
        return False
    if node.get("op") in AGG_OPS:
        return True
    for v in node.values():
        if isinstance(v, dict) and _has_agg(v):
            return True
    return False


# ================================================================ 规则表（内嵌 V2，46 条）

RULES_V2 = json.loads(r"""{"meta":{"version":"V2","n":46},"rules":[{"rule_id":"GW-HB-FJ-001","row":1,"category":"形式评审","subcategory":"格式内容","rule_text":"投标文件未按招标文件规定的格式填写，内容不全或者关键字迹模糊无法辨认的。未按招标文件要求在招标人招投标交易平台信息系统制作并上传凭证单，或因投标人删除了系统文件导致凭证单索引的核实信息无法查看的。","exec_path":"EXTRACT_DET","needs":["bid.voucher_index_viewable","bid.format_completeness"],"check":{"op":"and","args":[{"op":"eq","lhs":"bid.voucher_index_viewable","rhs":true},{"op":"eq","lhs":"bid.format_completeness","rhs":"complete"}]},"evidence":"招投标交易平台凭证单 / 投标文件各分册首页","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-002","row":2,"category":"形式评审","subcategory":"格式内容","rule_text":"投标人递交两份或多份内容不同的投标文件，或在一份投标文件中对同一招标内容报有两个或多个报价，按招标文件规定提交备选投标方案的除外。","exec_path":"DET","needs":["bid.file_count_with_diff_content","bid.distinct_price_count","bid.alternative_declared"],"check":{"op":"and","args":[{"op":"le","lhs":"bid.file_count_with_diff_content","rhs":1},{"op":"or","args":[{"op":"le","lhs":"bid.distinct_price_count","rhs":1},{"op":"eq","lhs":"bid.alternative_declared","rhs":true}]}]},"evidence":"投标文件封面/目录、开标一览表、投标函","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-003","row":3,"category":"形式评审","subcategory":"文件签署","rule_text":"对格式文件进行实质性修改或未按格式进行签署的，如由委托代理人签字的，未附有效的法定代表人（单位负责人）授权委托书的（未提交法定代表人（单位负责人）授权委托书，或法定代表人（单位负责人）授权委托书未经投标单位盖章或法定代表人（单位负责人）签名（或签章）的）；使用投标专用章未附有效的投标专用章与公章具有同等效力说明的。","exec_path":"EXTRACT_DET","needs":["bid.authorization_letter_present","bid.authorization_letter_elements_ok","bid.legal_rep_seal_present"],"check":{"op":"and","args":[{"op":"eq","lhs":"bid.authorization_letter_present","rhs":true},{"op":"eq","lhs":"bid.authorization_letter_elements_ok","rhs":true},{"op":"eq","lhs":"bid.legal_rep_seal_present","rhs":true}]},"evidence":"法定代表人授权委托书 / 格式文件签署页","human_gate":"对格式文件是否构成实质性修改，由评标委员会认定","external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-004","row":4,"category":"形式评审","subcategory":"文件签署","rule_text":"上传招标人招投标交易平台信息系统的电子投标文件无电子签章，或者电子签章无效的，或者电子签章名称与投标人不是同一人的。","exec_path":"DET","needs":["bid.seal_present","bid.seal_valid","bid.seal_name"],"check":{"op":"and","args":[{"op":"eq","lhs":"bid.seal_present","rhs":true},{"op":"eq","lhs":"bid.seal_valid","rhs":true},{"op":"eq","lhs":"normalize(bid.seal_name)","rhs":"normalize(bid.bidder_name)"}]},"evidence":"电子投标文件签章页","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-005","row":5,"category":"响应性评审","subcategory":"澄清修改","rule_text":"提交投标文件截止时间后主动撤销投标文件或对投标文件提出实质性修改的。","exec_path":"DET","needs":["bid.withdrawn_after_deadline"],"check":{"op":"eq","lhs":"bid.withdrawn_after_deadline","rhs":false},"evidence":"招投标交易平台操作日志","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-006","row":6,"category":"响应性评审","subcategory":"澄清修改","rule_text":"不按评标委员会要求对投标文件进行澄清、说明或补正的。","exec_path":"HUMAN","needs":[],"check":null,"evidence":"评标委员会澄清通知 / 投标人澄清回函","human_gate":"澄清是否已被要求、是否回应，由评标委员会记录","external_source":null,"signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-007","row":7,"category":"响应性评审","subcategory":"交付期限","rule_text":"投标文件所承诺的交货期不满足招标文件要求的，且招标人不能接受的。","exec_path":"EXTRACT_DET","needs":["bid.committed_delivery_date","tender.required_delivery_date"],"check":{"op":"le","lhs":"bid.committed_delivery_date","rhs":"tender.required_delivery_date"},"evidence":"投标函 / 商务偏差表","human_gate":"交货期不满足时，是否接受由招标人决定，系统只报「不满足」","external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-008","row":8,"category":"响应性评审","subcategory":"投标报价","rule_text":"投标人不接受评标委员会依法所作的修正价格的。","exec_path":"HUMAN","needs":[],"check":null,"evidence":"评标委员会价格修正记录 / 投标人确认","human_gate":"接受与否由评标委员会现场确认","external_source":null,"signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-009","row":9,"category":"响应性评审","subcategory":"投标报价","rule_text":"报价明显低于其他投标报价，且投标人不能合理说明或者提供相关证明材料，评标委员会认定该投标人以低于成本报价竞标的。","exec_path":"HUMAN","needs":["bid.price_total","peer.price_avg"],"check":null,"evidence":"开标一览表 / 报价说明 / 成本证明材料","human_gate":"是否低于成本由评标委员会认定","external_source":null,"signals":["bid.price_total / peer.price_avg >= 0.8 时不提示","0.5~0.8 提示「显著偏低，建议要求说明」","<0.5 提示「严重偏离，建议重点核查」"],"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-010","row":10,"category":"响应性评审","subcategory":"投标报价","rule_text":"招标文件中明确规定了最高限价（包括具体金额、计算方式），投标人的投标价格剔除角和分（单价限价不剔除）的数值后超过最高限价的。","exec_path":"DET","needs":["tender.price_cap_items"],"check":{"op":"per_item_within_cap","lhs":"bid.price_items","rhs":"tender.price_cap_items","fallback_total":"floor_yuan(bid.price_total_ex_tax)","key":"item_no","amount_basis":"tax_incl","amount_basis_why":"限价表（附表一）为含税限价，投标分项报价表为未含税合价；不同口径直接比会把含税超限的行判成合规（宜昌行含税 460 万 > 限价 453.31 万，未含税仅 407.08 万）。按行10 原文「剔除角和分」向下取整到元。"},"optional_needs":["bid.price_items","bid.price_total_ex_tax","tender.price_cap_applicable"],"evidence":"开标一览表 / 投标函价格表 / 招标文件最高限价条款","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-011","row":11,"category":"响应性评审","subcategory":"投标报价","rule_text":"投标报价构成招标文件规定为无效报价的；开标一览表中显示为非报价数值的。投标报价小数点错误导致单价总价都出现明显错误的。","exec_path":"DET","needs":["bid.price_items"],"check":{"op":"per_item_amount_check","lhs":"bid.price_items","tolerance_yuan":0.5,"tolerance_why":"合价列在文件里带两位小数，表格化/抽取时常取整到元（7,892,920.35 → 7,892,920），逐行差 0.5 元以内是取整口径，不构成行11 的「小数点错误」；真正的错位差 3 个数量级，容差放宽不影响判否。合计行若恰好等于某一单行，视为抽取取错行，不据此判否。"},"optional_needs":["bid.price_total_ex_tax"],"evidence":"开标一览表 / 分项报价表","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-012","row":12,"category":"响应性评审","subcategory":"投标报价","rule_text":"投标价格出现数值与货币单位不对应，即出现了明显的百倍至万倍高于正常水平的报价（如把“投标函价格表”中的“万元”当成“元”进行报价）。","exec_path":"DET","needs":["bid.price_unit_ratio_to_ref"],"check":{"op":"lt","lhs":"bid.price_unit_ratio_to_ref","rhs":100},"evidence":"投标函价格表 / 同标包其他投标人报价","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-013","row":13,"category":"响应性评审","subcategory":"投标担保","rule_text":"未按招标文件要求提交投标保证金的；以银行汇款形式提供的投标保证金未提供从投标人基本账户转出有效证明的（未提供有效证明是指未提供企业银行基本账户开户许可证复印件，也未提供投标人基本账户开户行通过账户管理系统打印的《基本存款账户信息》扫描件）；以投标保证保险形式提交的投标保证金，保单保费未从投标人基本账户转出或保单未体现保费是否由投标人基本账户支付的相关信息或未提供保单查询途径或提供的查询途径招标人无法查询的；以银行保函、投标保证保险形式提交的投标保证金不满足招标文件要求的（如对上述格式文件进行实质性修改或未按格式进行签署）。**（本批不适用）**","exec_path":"EXTRACT_DET","needs":["bid.bond_amount","tender.bond_required"],"check":{"op":"and","args":[{"op":"ge","lhs":"bid.bond_amount","rhs":"tender.bond_required"},{"op":"in","lhs":"bid.bond_form","rhs":["bank_transfer","bank_guarantee","insurance","letter"]},{"op":"or","args":[{"op":"ne","lhs":"bid.bond_form","rhs":"bank_transfer"},{"op":"eq","lhs":"bid.bond_basic_account_proof","rhs":true}]}]},"optional_needs":["bid.bond_form","bid.bond_basic_account_proof"],"evidence":"投标保证金缴纳凭证 / 基本账户开户许可证 / 保函","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-014","row":14,"category":"响应性评审","subcategory":"投标范围","rule_text":"投标范围与招标文件要求存在偏差的，且招标人不能接受的。","exec_path":"HUMAN","needs":[],"check":null,"evidence":"投标函 / 供货范围表 / 招标范围条款","human_gate":"偏差是否可接受由招标人认定","external_source":null,"signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-015","row":15,"category":"响应性评审","subcategory":"投标偏差","rule_text":"投标人提出招标人不能接受的条件或偏差的；未按要求填写具体数据信息以及填写的数据信息不满足招标文件规定的。","exec_path":"HUMAN","needs":[],"check":null,"evidence":"商务/技术偏差表","human_gate":"由评标委员会逐条认定","external_source":null,"signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-016","row":16,"category":"响应性评审","subcategory":"投标期限","rule_text":"投标有效期不满足招标文件要求的。","exec_path":"DET","needs":["bid.validity_days","tender.required_validity_days"],"check":{"op":"ge","lhs":"bid.validity_days","rhs":"tender.required_validity_days"},"evidence":"投标函 / 招标文件投标人须知前附表","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-017","row":17,"category":"响应性评审","subcategory":"税率错误","rule_text":"不按国家法律法规规定填报增值税税率或征收率的。","exec_path":"DET","needs":["bid.tax_rate","legal.tax_rate_set"],"check":{"op":"in","lhs":"bid.tax_rate","rhs":"legal.tax_rate_set"},"evidence":"开标一览表 / 分项报价表 / 增值税税率栏","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-018","row":18,"category":"资格评审","subcategory":"法定否决","rule_text":"投标文件响应与事实不符或虚假投标的（虚假投标包括但不限于投标人在其投标文件中提供虚假的资格证明文件、业绩证明文件、验收报告、故意修改招标文件明确列明的技术要求并对其进行响应等），该投标人参与本次投标的所有标包将均被否决，且该投标人在今后一段时间内参与国家电网有限公司及其所属单位招标活动的任何投标也将被否决。","exec_path":"HUMAN","needs":["bid.performance_dates","bid.invoice_numbers"],"check":null,"evidence":"资格证明文件 / 业绩合同 / 验收报告 / 发票","human_gate":"是否构成虚假投标由评标委员会认定并可追溯法律责任","external_source":null,"signals":["业绩合同签订日期晚于验收报告日期","同一发票号在不同业绩中重复出现","业绩金额与合同金额不一致"],"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-019","row":19,"category":"资格评审","subcategory":"法定否决","rule_text":"串通投标或视为串通投标或根据投诉举报经核实认定为串通投标或联合围标或有其他违法行为的，该投标人参与本次招标活动的所有标包将均被否决。同时招标人将依据《国家电网有限公司供应商关系管理办法》规定进行后续处理。","exec_path":"HUMAN","needs":["bid.ip","bid.mac","bid.file_author","bid.contact_phone","bid.price_pattern"],"check":null,"evidence":"平台递交日志 / 投标文件属性 / 报价序列","human_gate":"串通投标认定权在评标委员会及行政监督部门","external_source":null,"signals":["同一标包内两家投标人 IP 相同","投标文件创建者/最后修改者相同","联系人电话或邮箱相同","报价呈规律性等差/等比"],"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-020","row":20,"category":"资格评审","subcategory":"法定否决","rule_text":"《中华人民共和国招标投标法》、《中华人民共和国招标投标法实施条例》、《评标委员会和评标方法暂行规定》等法律法规规章规定的其他否决情形。（注：所引法律法规原文不在知识库内，无法回读其具体内容）","exec_path":"OUT_OF_SCOPE","needs":[],"check":null,"evidence":"法律法规原文（库外）","human_gate":"只能由评标委员会依法认定","external_source":null,"signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-021","row":21,"category":"形式评审","subcategory":"参数接口","rule_text":"投标文件主要技术参数或产品型式不满足招标文件要求的；投标文件一般技术参数超出允许偏差的最大范围的；对于规定接口要求的产品，投标文件对一次接口、二次接口、土建接口的响应与招标文件不符的。","exec_path":"EXTRACT_DET","needs":["bid.tech_params","tender.tech_params_mandatory","tender.tech_param_tolerance"],"check":{"op":"and","args":[{"op":"all_satisfy","lhs":"bid.tech_params","rhs":"tender.tech_params_mandatory"},{"op":"all_within_tolerance","lhs":"bid.tech_params","rhs":"tender.tech_param_tolerance"}]},"evidence":"技术规范书参数表 / 投标技术响应表","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-022","row":22,"category":"资格评审","subcategory":"质量否决","rule_text":"本次投标截止日前三年内发生重大质量问题（以相关行业主管部门的行政处罚决定或司法机关出具的有关法律文书为准）。","exec_path":"EXTERNAL","needs":["bid.major_quality_incident_3y"],"check":null,"evidence":"行业主管部门处罚决定 / 司法文书","human_gate":null,"external_source":"国家企业信用信息公示系统 / 信用中国 行政处罚栏","signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-023","row":23,"category":"资格评审","subcategory":"资格不符","rule_text":"未提供符合招标文件要求的联合体协议书的。","exec_path":"DET","needs":["bid.is_consortium","bid.consortium_agreement_present"],"check":{"op":"or","args":[{"op":"eq","lhs":"bid.is_consortium","rhs":false},{"op":"eq","lhs":"bid.consortium_agreement_present","rhs":true}]},"evidence":"联合体协议书","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-024","row":24,"category":"资格评审","subcategory":"主体不符","rule_text":"为招标人不具有独立法人资格的附属机构（单位）。","exec_path":"EXTRACT_DET","needs":["bid.bidder_name","tender.affiliate_org_names"],"check":{"op":"not_in","lhs":"normalize(bid.bidder_name)","rhs":"normalize_list(tender.affiliate_org_names)"},"evidence":"营业执照 / 招标人关联单位清单","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-025","row":25,"category":"资格评审","subcategory":"丧失履约能力","rule_text":"进入清算程序，或被宣告破产，或其他丧失履约能力的情形。","exec_path":"EXTERNAL","needs":["bid.liquidation_or_bankrupt"],"check":null,"evidence":"破产裁定书 / 清算公告","human_gate":null,"external_source":"全国企业破产重整案件信息网 / 工商登记","signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-026","row":26,"category":"资格评审","subcategory":"失信惩戒","rule_text":"被市场监督管理机关在国家企业信用信息公示系统中列入严重违法失信企业名单或列入经营异常名录信息的。","exec_path":"EXTERNAL","needs":["bid.credit_serious_illegal"],"check":null,"evidence":"国家企业信用信息公示系统截图","human_gate":null,"external_source":"国家企业信用信息公示系统","signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-027","row":27,"category":"资格评审","subcategory":"失信惩戒","rule_text":"被最高人民法院在“信用中国”网站（www.creditchina.gov.cn）中列入严重失信主体名单或列入失信被执行人。（以评标委员会在“信用中国”网站（www.creditchina.gov.cn）查询结果为准）。","exec_path":"EXTERNAL","needs":["bid.credit_china_dishonest"],"check":null,"evidence":"信用中国查询截图","human_gate":null,"external_source":"信用中国 www.creditchina.gov.cn","signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-028","row":28,"category":"资格评审","subcategory":"行贿记录","rule_text":"投标单位或法定代表人（单位负责人）在投标截止日前三年内存在行贿犯罪记录的。","exec_path":"EXTERNAL","needs":["bid.bribery_record_3y"],"check":null,"evidence":"行贿犯罪档案查询结果","human_gate":null,"external_source":"检察机关行贿犯罪档案查询","signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-029","row":29,"category":"资格评审","subcategory":"不良行为","rule_text":"根据《国家电网有限公司供应商关系管理办法》的规定，若投标人为制造商，存在导致其被暂停中标资格或取消中标资格的不良行为且在处理有效期内的，或投标人存在触发《国家电网有限公司供应商关系管理办法》第六十三条安全及质量重大问题“熔断机制”情形的。若投标人为代理商，投标人或其代理产品的制造商存在导致其被暂停中标资格或取消中标资格的不良行为且在处理有效期内的，或投标人存在触发《国家电网有限公司供应商关系管理办法》第六十三条安全及质量重大问题“熔断机制”情形的。","exec_path":"EXTERNAL","needs":["bid.supplier_bad_behavior"],"check":null,"evidence":"供应商不良行为处理记录","human_gate":null,"external_source":"国网供应商关系管理系统","signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-030","row":30,"category":"资格评审","subcategory":"资格不符","rule_text":"不满足本次招标公告要求的投标人专用资格要求的","exec_path":"EXTRACT_DET","needs":["bid.qualification_fields","tender.special_qualification_requirements"],"check":{"op":"all_satisfy","lhs":"bid.qualification_fields","rhs":"tender.special_qualification_requirements"},"evidence":"招标公告专用资格要求 / 投标人资格证明文件","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-031","row":31,"category":"资格评审","subcategory":"资格不符","rule_text":"不满足本次招标公告要求的投标人其他资格要求的","exec_path":"EXTRACT_DET","needs":["bid.qualification_fields","tender.other_qualification_requirements"],"check":{"op":"all_satisfy","lhs":"bid.qualification_fields","rhs":"tender.other_qualification_requirements"},"evidence":"招标公告其他资格要求 / 投标人资格证明文件","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-032","row":32,"category":"资格评审","subcategory":"主体不符","rule_text":"对于接受代理商投标的项目，一个制造商对同一品牌同一型号的货物委托两个及以上代理商参加同一标包投标的；制造商与其授权委托代理商参加同一标包投标的。","exec_path":"DET","needs":["bid.manufacturer_name","bid.brand_model","bid.agent_of"],"check":{"op":"and","args":[{"op":"group_dup_le","lhs":"bid.agent_of","rhs":1},{"op":"group_no_overlap","lhs":"bid.manufacturer_name","rhs":"bid.agent_of"}]},"evidence":"制造商授权书 / 投标人资格文件","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-033","row":33,"category":"资格评审","subcategory":"资格不符","rule_text":"招标人有权对厂商进行资质能力核查，如经核查该厂商不具有生产投标产品所需的生产场地、生产设备及工艺控制、生产人员、元器件及产品检测能力等资质能力，或因厂商自身原因造成核查工作无法进行的，将视厂商不具备生产投标产品所需的资质能力，招标人有权否决其投标。","exec_path":"HUMAN","needs":["bid.factory_capacity_evidence"],"check":null,"evidence":"资质能力核实报告 / 生产场地与设备证明","human_gate":"核查结论由招标人组织的核实工作组出具","external_source":null,"signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-034","row":34,"category":"资格评审","subcategory":"主体不符","rule_text":"与招标人存在利害关系且可能影响招标公正性。","exec_path":"HUMAN","needs":[],"check":null,"evidence":"投标人关联关系声明 / 评标委员会回避记录","human_gate":"由招标人认定","external_source":null,"signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-035","row":35,"category":"资格评审","subcategory":"主体不符","rule_text":"为本招标项目的代建人。","exec_path":"DET","needs":["bid.bidder_name","tender.agent_construction_unit"],"check":{"op":"ne","lhs":"normalize(bid.bidder_name)","rhs":"normalize(tender.agent_construction_unit)"},"evidence":"招标公告 / 营业执照","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-036","row":36,"category":"资格评审","subcategory":"主体不符","rule_text":"为本招标项目的代理机构。","exec_path":"DET","needs":["bid.bidder_name","tender.tender_agency"],"check":{"op":"ne","lhs":"normalize(bid.bidder_name)","rhs":"normalize(tender.tender_agency)"},"evidence":"招标公告 / 营业执照","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-037","row":37,"category":"资格评审","subcategory":"主体不符","rule_text":"与本招标项目的监理人或代建人或招标代理机构同为一个法定代表人（单位负责人）的。","exec_path":"DET","needs":["bid.legal_rep_name","tender.supervisor_legal_rep","tender.agency_legal_rep","tender.agent_construction_legal_rep"],"check":{"op":"and","args":[{"op":"ne","lhs":"normalize(bid.legal_rep_name)","rhs":"normalize(tender.supervisor_legal_rep)"},{"op":"ne","lhs":"normalize(bid.legal_rep_name)","rhs":"normalize(tender.agency_legal_rep)"},{"op":"ne","lhs":"normalize(bid.legal_rep_name)","rhs":"normalize(tender.agent_construction_legal_rep)"}]},"evidence":"营业执照 / 招标公告","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-038","row":38,"category":"资格评审","subcategory":"资格不符","rule_text":"投标人名称与营业执照（或事业单位法人证书）或资质证书或生产许可证不一致，且未提供相关变更证明。","exec_path":"DET","needs":["bid.bidder_name","bid.license_name","bid.qualification_cert_name","bid.name_change_proof_present"],"check":{"op":"or","args":[{"op":"and","args":[{"op":"eq","lhs":"normalize(bid.bidder_name)","rhs":"normalize(bid.license_name)"},{"op":"eq","lhs":"normalize(bid.bidder_name)","rhs":"normalize(bid.qualification_cert_name)"}]},{"op":"eq","lhs":"bid.name_change_proof_present","rhs":true}]},"evidence":"营业执照 / 资质证书 / 生产许可证 / 名称变更证明","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-039","row":39,"category":"资格评审","subcategory":"主体不符","rule_text":"同一标包或者未划分标包的同一招标项目中，与其他投标人的法定代表人（单位负责人）为同一人。","exec_path":"DET","needs":["bid.legal_rep_name"],"check":{"op":"group_dup_le","lhs":"bid.legal_rep_name","rhs":1},"evidence":"各投标人营业执照","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-040","row":40,"category":"资格评审","subcategory":"主体不符","rule_text":"同一标包或者未划分标包的同一招标项目中，与其他投标人存在控股、管理关系。","exec_path":"EXTERNAL","needs":["bid.equity_relation"],"check":null,"evidence":"企业信用信息公示系统股权结构","human_gate":null,"external_source":"国家企业信用信息公示系统","signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-041","row":41,"category":"资格评审","subcategory":"资信不良","rule_text":"被责令停产停业、暂扣或者吊销许可证、暂扣或者吊销执照的；被招投标活动政府行政监督部门暂停、取消投标资格的；财产被接管或冻结的。","exec_path":"EXTERNAL","needs":["bid.penalty_status"],"check":null,"evidence":"行政处罚决定书 / 执行裁定","human_gate":null,"external_source":"信用中国 / 中国执行信息公开网","signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-042","row":42,"category":"资格评审","subcategory":"无效代理","rule_text":"对于代理商投标，未取得投标产品制造商有效授权的。","exec_path":"DET","needs":["bid.is_agent","bid.manufacturer_authorization_present","bid.manufacturer_authorization_valid_until","tender.required_validity_days"],"check":{"op":"or","args":[{"op":"eq","lhs":"bid.is_agent","rhs":false},{"op":"and","args":[{"op":"eq","lhs":"bid.manufacturer_authorization_present","rhs":true},{"op":"ge","lhs":"days_until(bid.manufacturer_authorization_valid_until, tender.bid_open_date)","rhs":"tender.required_validity_days"}]}]},"evidence":"制造商授权书 / 投标人资格声明","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}},{"rule_id":"GW-HB-FJ-043","row":43,"category":"响应性评审","subcategory":"实质不符","rule_text":"不符合招标文件实质性要求的投标文件。","exec_path":"HUMAN","needs":[],"check":null,"evidence":"评标办法 / 投标文件","human_gate":"只能由评标委员会认定","external_source":null,"signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-044","row":44,"category":"资格评审","subcategory":"主体不符","rule_text":"与本招标项目的监理人或代建人或招标代理机构存在控股或参股关系","exec_path":"EXTERNAL","needs":["bid.equity_relation_with_agency"],"check":null,"evidence":"股权结构证明","human_gate":null,"external_source":"国家企业信用信息公示系统","signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-045","row":45,"category":"其他事项","subcategory":"其他事项","rule_text":"投标人或投标文件符合招标文件中规定否决投标的其他条款的","exec_path":"OUT_OF_SCOPE","needs":[],"check":null,"evidence":"招标文件其他否决条款","human_gate":"逐项由评标委员会对照招标文件认定","external_source":null,"signals":null,"conclusion_ceiling":"NEED_HUMAN","states":{"always":"NEED_HUMAN"}},{"rule_id":"GW-HB-FJ-046","row":46,"category":"响应性评审","subcategory":"投标报价","rule_text":"152507 及 K1 资格后审：「根据招标文件规定，因投标人投标价格超过本包规定投标人报价平均值规定值的。」；K1 资格预审版：「根据招标文件规定，因投标人投标价格超过本包规定投标人报价平均值规定值的**或不平衡报价的**。」（版本差异见第三部分）","exec_path":"DET","needs":["bid.price_total","tender.avg_price_threshold_rule"],"check":{"op":"le","lhs":"bid.price_total","rhs":"eval_threshold(tender.avg_price_threshold_rule, peer.price_avg)"},"evidence":"招标文件评标办法 / 开标一览表","human_gate":null,"external_source":null,"signals":null,"conclusion_ceiling":"CANDIDATE","states":{"pass":"RESPONDED","fail":"NOT_RESPONDED","missing":"UNCERTAIN"}}]}""")
RULE_SET_VERSION = "V2"
RULE_SET_SHA = "e80fd7b21492dc44"

# 参与指纹计算的字段集合与顺序，由 build_judge_fn.py 的 KEEP 注入（单一真相源）。
# 外部规则表按同一口径 slim 后再算 sha，才能与 RULE_SET_SHA 互校。
_KEEP_FIELDS = ['rule_id', 'row', 'category', 'subcategory', 'rule_text', 'exec_path', 'needs', 'check', 'optional_needs', 'evidence', 'human_gate', 'external_source', 'signals', 'conclusion_ceiling', 'states']


# ================================================================ 入口

class Input(BaseModel):
    section_no: str = Field(default="", description="标段号，仅用于回填与留痕")
    bidder: str = Field(default="", description="受审投标人名称；留空则取 bid_fields 里的 bid.bidder_name")
    tender_fields: List[Dict[str, Any]] = Field(
        default_factory=list, description="基准侧抽取输出（sgcc-field-extract 的 fields 数组，原样传入）")
    bid_fields: List[Dict[str, Any]] = Field(
        default_factory=list, description="受审侧抽取输出（fields 数组，原样传入）")
    facts: Dict[str, Any] = Field(
        default_factory=dict, description="直通判定事实（已翻译好的扁平字段，键形如 bid.seal_name）；与 *_fields 二选一")
    peer_facts: List[Dict[str, Any]] = Field(
        default_factory=list, description="同标包其他投标人的事实或抽取输出；行39（法定代表人重复）必须给，否则该条 UNCERTAIN")
    rule_ids: List[str] = Field(default_factory=list, description="只跑这些规则；空=全部 46 条")
    rules: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="外部规则表（规则对象数组）。传了则以传入为准、不再用内嵌 V2；不传行为与旧版完全一致")
    rule_set_version: str = Field(
        default="", description="外部规则表的版本名（如 V3）。空则记为 EXTERNAL；内嵌模式下忽略")
    rule_set_sha: str = Field(
        default="", description="外部规则表的指纹（调用方算法）。与函数实算不一致时写进 notes 留痕，不阻断判定")


class RuleRow(BaseModel):
    rule_id: str
    row: int
    category: str
    subcategory: str
    rule_text: str = ""
    exec_path: str
    state: str = Field(description="RESPONDED 已响应 / NOT_RESPONDED 未见响应 / UNCERTAIN 证不足 / NEED_HUMAN 只能人判")
    reason: str
    conclusion_ceiling: str = "CANDIDATE"
    evidence: str = ""
    used_fields: List[Dict[str, Any]] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    item_check: Optional[Dict[str, Any]] = None


class BlockedBy(BaseModel):
    field: str = Field(description="卡住的字段名，如 tender.avg_price_threshold_rule")
    side: str = Field(description="该字段该由谁补：bid 投标侧 / tender 招标侧 / legal 法规名单 / platform 平台外数据")
    rows: List[int] = Field(description="被这个字段卡住的行号")
    hint: str = Field(description="补数口径的一句话说明")


class Output(BaseModel):
    section_no: str
    bidder: str
    rule_set: str
    rule_set_sha: str
    total: int
    decided: int = Field(description="机器给出结论的条数（不含 NEED_HUMAN）")
    counts: Dict[str, int]
    fail_rows: List[int] = Field(description="判否（NOT_RESPONDED）的行号，按行号升序")
    uncertain_rows: List[int]
    blocked_by: List[BlockedBy] = Field(
        default_factory=list,
        description="待澄清按「缺哪个字段、该谁补」聚合。uncertain_rows 只有行号，前端按行号逐条展示时看不出 16 条其实是 3 类问题")
    warnings: List[str] = Field(default_factory=list,
                                description="输入侧的降级提示（未传 peer_facts、双向 facts 冲突等），不影响判定")
    rows: List[RuleRow]
    notes: List[str]
    elapsed_ms: int
    rule_source: str = Field(
        description="规则来源：embedded=内嵌 V2；input=调用方传入。对客报告与事故追溯都要看这个字段")


def main(inp: Input, ctx: Context) -> Output:
    t0 = time.perf_counter()
    notes = []

    # ---- 规则来源：外部注入优先，未注入则用内嵌 V2 --------------------------
    # 不传 inp.rules 时，走的分支与旧版逐字节一致（rules=RULES_V2["rules"]、
    # rule_set_sha=RULE_SET_SHA），所以六家基线回归结果必须完全相同。
    if inp.rules:
        rules = inp.rules
        rule_source = "input"
        rule_set = inp.rule_set_version or "EXTERNAL"
        # 指纹口径必须与 build_judge_fn.py 的 slim_rules() 一致（同样 15 个字段、同序），
        # 否则外部表哪怕内容相同也永远对不上 RULE_SET_SHA，指纹闸形同失效。
        _slim = [{k: r[k] for k in _KEEP_FIELDS if k in r} for r in rules]
        _payload = json.dumps({"meta": {"version": rule_set, "n": len(_slim)}, "rules": _slim},
                              ensure_ascii=False, separators=(",", ":"))
        rule_sha = hashlib.sha256(_payload.encode("utf-8")).hexdigest()[:16]
        if inp.rule_set_sha and inp.rule_set_sha != rule_sha:
            notes.append(
                "传入 rule_set_sha=%s 与函数实算 %s 不一致：可能用了不同指纹算法，"
                "或规则表在传输/保存中被改动。判定按传入内容执行，此处如实留痕。"
                % (inp.rule_set_sha, rule_sha))
            # 指纹把版本名也算进哈希（见上面的 payload），所以只传规则、不传版本名时
            # 必然对不上内嵌集的 RULE_SET_SHA。这属于口径差异，不是规则被改，
            # 必须单独说清楚，否则调用方会照着"规则被改"去排查，白烧半天。
            if not inp.rule_set_version:
                notes.append(
                    "本次未传 rule_set_version，指纹按 EXTERNAL 计算；而版本名参与哈希，"
                    "所以它与内嵌 %s 的 RULE_SET_SHA=%s 天然不同，不代表规则内容被改。"
                    "要比对内容指纹，请把 rule_set_version 一并传入。"
                    % (RULE_SET_VERSION, RULE_SET_SHA))
    else:
        rules = RULES_V2["rules"]
        rule_source = "embedded"
        rule_set = RULE_SET_VERSION
        rule_sha = RULE_SET_SHA

    if inp.rule_ids:
        want = {str(x).strip() for x in inp.rule_ids if str(x).strip()}
        known = {r["rule_id"] for r in rules} | {str(r.get("row")) for r in rules}
        unknown = sorted(want - known)
        # 早先这里只做过滤：传错一个 rule_id，函数照样 succeeded、total=0、counts 全 0。
        # 调用方（尤其是把规则号写死在配置里的前端 / 上层函数）会拿到一份"零命中且成功"
        # 的结论，看着像"这个标包没有否决情形"——是最难被发现的一种假绿。
        # 规则号写错属于调用方 bug，必须炸出来，不能静默返空。
        if unknown:
            raise ValueError(
                "未知的 rule_id / 行号：%s。本规则集 %s 共 %d 条，可用取值见 rule_set 字段或 "
                "GET 函数说明" % ("、".join(unknown), rule_set, len(rules)))
        rules = [r for r in rules if r["rule_id"] in want or str(r.get("row")) in want]

    with ctx.step("抽取原文 → 判定事实", detail={"tender_fields": len(inp.tender_fields),
                                                "bid_fields": len(inp.bid_fields)}):
        facts = dict(inp.facts or {})
        if inp.tender_fields:
            facts.update(build_tender(inp.tender_fields, notes))
        if inp.bid_fields:
            facts.update(build_bid(inp.bid_fields, inp.bidder, notes))
        elif inp.bidder:
            facts["bid.bidder_name"] = inp.bidder

    group = [facts] + [_peer_ctx(p) for p in (inp.peer_facts or [])]
    group = [g for g in group if g]

    # 行46「报价超过本包平均值规定值」的判定式依赖 peer.price_avg。
    # run_package()（本地三场景）算过这个均值，但平台走的是这个 main()，
    # 早先漏了这一段 —— 结果该条在线上恒为「待澄清」，一条永远判不出来的死规则。
    # 口径与 run_package() 保持一致：含本家，按各家 bid.price_total 取算术平均；
    # 一家总价都拿不到时不写入，让它自然落到「缺证」，不许用 0 兜底造出假均值。
    _pt = [g.get("bid.price_total") for g in group
           if isinstance(g.get("bid.price_total"), (int, float))]
    if _pt:
        facts["peer.price_avg"] = sum(_pt) / len(_pt)

    rows, bucket = [], {"RESPONDED": 0, "NOT_RESPONDED": 0, "UNCERTAIN": 0, "NEED_HUMAN": 0}
    with ctx.step("逐条执行判定式", detail={"rules": len(rules), "peer_group": len(group)}):
        for r in rules:
            # 跨投标人聚合算子在小样本上会"看起来通过"：组里只有自己时必然无重复。
            # 这种事不能给它 RESPONDED，必须显式转为证不足。
            if _has_agg(r.get("check")) and len(group) < 2:
                rows.append(RuleRow(
                    rule_id=r["rule_id"], row=r["row"], category=r["category"],
                    subcategory=r["subcategory"], rule_text=r.get("rule_text", ""),
                    exec_path=r["exec_path"], state=STATE_UNK,
                    reason="跨投标人聚合规则：本次只传入 1 家，无法判断组内是否重复（需同标包全部投标人）",
                    evidence=r.get("evidence", "")))
                bucket[STATE_UNK] += 1
                continue
            try:
                res = run_rule(r, facts, group)
            except Exception as exc:  # noqa: BLE001
                # run_rule 内部只兜 NeedMissing / KeyError。类型、属性、除零这些一旦出现，
                # 早先会直接抛穿 main()，整个请求失败 —— 一条规则写错，其余 45 条的结论
                # 一起拿不到。规则表后续由业务方维护，这个爆炸半径不能留。
                rows.append(RuleRow(
                    rule_id=r["rule_id"], row=r["row"], category=r["category"],
                    subcategory=r["subcategory"], rule_text=r.get("rule_text", ""),
                    exec_path=r["exec_path"], state=STATE_UNK,
                    reason="规则执行异常（%s: %s）；本条不产出结论，其余规则照常"
                           % (type(exc).__name__, exc),
                    evidence=r.get("evidence", "")))
                bucket[STATE_UNK] += 1
                notes.append("%s（行%s）执行异常：%s: %s"
                             % (r["rule_id"], r["row"], type(exc).__name__, exc))
                continue
            item_check = res.pop("item_check", None)
            rows.append(RuleRow(
                rule_id=res["rule_id"], row=res["row"], category=res["category"],
                subcategory=res["subcategory"], rule_text=r.get("rule_text", ""),
                exec_path=res["exec_path"], state=res["state"], reason=res["reason"],
                conclusion_ceiling=res.get("conclusion_ceiling", "CANDIDATE"),
                evidence=res.get("evidence", ""),
                used_fields=res.get("used_fields") or [],
                missing_fields=res.get("missing_fields") or [],
                item_check=item_check))
            bucket[res["state"]] = bucket.get(res["state"], 0) + 1

    decided = bucket["RESPONDED"] + bucket["NOT_RESPONDED"]
    fail_rows = sorted({x.row for x in rows if x.state == STATE_FAIL})
    uncertain_rows = sorted({x.row for x in rows if x.state == STATE_UNK})

    # 待澄清按「缺哪个字段」聚合。uncertain_rows 给的是一串行号，前端逐条列出来时
    # 16 条看着像 16 个互不相干的问题；实际往往是 3 个字段没补上。对客演示时这个
    # 差别很大：前者是"系统看不出东西"，后者是"补这 3 个数就能再判 9 条"。
    _HINT = {
        "bid": "投标文件没抽到这个字段：重抽该字段，或人工核对投标文件对应页",
        "tender": "招标文件未给出该参数（或该表未结构化）：只能人工对照原文补录，补不上就只能是待澄清",
        "legal": "法规/名单类外部依据，库内通常没有：按外部渠道人工核验",
        "platform": "需要库外数据（平台递交日志、同包全量投标人等）：系统内取不到",
    }

    def _side_of(field):
        head = field.split(".", 1)[0] if "." in field else ""
        return head if head in ("bid", "tender", "legal") else "platform"

    blocked = {}
    for x in rows:
        if x.state != STATE_UNK:
            continue
        miss = list(x.missing_fields or [])
        if not miss:
            # 两类没有 missing_fields 的待澄清：跨投标人聚合只给 1 家、以及运行期异常。
            miss = ["peer_facts"] if "跨投标人聚合" in x.reason else ["rule_exec_error"]
        for f in miss:
            blocked.setdefault(f, []).append(x.row)
    blocked_by = [
        BlockedBy(field=f, side=_side_of(f), rows=sorted(v),
                  hint=_HINT.get(_side_of(f), _HINT["platform"]))
        for f, v in sorted(blocked.items(), key=lambda kv: (-len(kv[1]), kv[0]))]

    warnings = []
    if not inp.tender_fields and not any(str(k).startswith("tender.") for k in (inp.facts or {})):
        warnings.append("未传基准侧（tender_fields / facts）：凡依赖招标侧字段的规则都会落到待澄清")
    if not inp.peer_facts:
        warnings.append("未传 peer_facts：行32 / 行39 这类跨投标人聚合规则无法判断组内是否重复，"
                        "一律转待澄清（这是设计如此，不是漏判）")
    if inp.bid_fields and inp.facts:
        warnings.append("bid_fields 与 facts 同时传入：facts 中的同名 bid.* 会被 bid_fields 覆盖")

    with ctx.step("汇总", detail={"decided": decided, "fail_rows": fail_rows,
                                  "blocked_fields": len(blocked_by)}):
        elapsed = int((time.perf_counter() - t0) * 1000)

    return Output(
        section_no=inp.section_no,
        bidder=facts.get("bid.bidder_name") or inp.bidder,
        rule_set=rule_set,
        rule_set_sha=rule_sha,
        total=len(rows),
        decided=decided,
        counts=bucket,
        fail_rows=fail_rows,
        uncertain_rows=uncertain_rows,
        blocked_by=blocked_by,
        warnings=warnings,
        rows=rows,
        notes=notes,
        elapsed_ms=elapsed,
        rule_source=rule_source,
    )
