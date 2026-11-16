# -*- coding: utf-8 -*-
"""
受限 DSL 判定执行器（规则引擎的替代品，约 200 行）。

设计红线：
1. 不使用 eval / exec / compile。算子白名单穷举，未知算子直接抛错。
2. 任何依赖字段缺失 → 该规则返回 UNCERTAIN，绝不降级为 NOT_RESPONDED。
3. 结论上限恒为 CANDIDATE；HUMAN / EXTERNAL / OUT_OF_SCOPE 恒返回 NEED_HUMAN。
4. 每条判定都带证据位置与用到的字段快照，可回读。

用法：python sgcc_rule_runner.py
"""
import io
import json
import re
import sys
from datetime import date, datetime

DISPATCH = "国网Demo_规则可执行化_46条分派表_V1.json"
OUT = "国网Demo_规则执行器_三场景真跑_V1.json"

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


def run_package(tender, bids):
    rules = json.load(io.open(DISPATCH, encoding="utf-8"))["rules"]
    n = len(bids)
    avg = (sum(b.get("bid.price_total", 0) or 0 for b in bids) / n) if n else MISSING
    results = []
    for i, b in enumerate(bids):
        ctx = dict(tender)
        ctx.update(b)
        ctx["peer.price_avg"] = avg if n else MISSING
        ctx["peer.unit_price_median"] = b.get("peer_ref_price_median", MISSING)
        rows = [run_rule(r, ctx, bids) for r in rules]
        results.append({"bidder": b.get("bid.bidder_name"), "rows": rows})
    return results


# ---------------------------------------------------------------- 三场景
# 152507-1102002-4004 限价表的真实 4 条物料（抽取器 table 路径原样取回，单位已由万元换元）
CAP_ITEMS_4004 = [
    {"item_no": "100035912500010", "cap_wan": 34.0, "cap_yuan": 340000},
    {"item_no": "100035917800010", "cap_wan": 182.12, "cap_yuan": 1821200},
    {"item_no": "100035912200010", "cap_wan": 453.31, "cap_yuan": 4533100},
    {"item_no": "100034915900360", "cap_wan": 1000.0, "cap_yuan": 10000000},
]
CAP_SUM_4004 = sum(x["cap_yuan"] for x in CAP_ITEMS_4004)      # 16694300

COMMON_TENDER = {
    "tender.deadline": "2026-10-20T09:00:00",
    "tender.bid_open_date": "2026-10-20",
    "tender.price_cap": CAP_SUM_4004,
    "tender.price_cap_items": CAP_ITEMS_4004,
    "tender.required_delivery_date": "2026-05-10",   # 基准侧现取绝对日期（货物清单首批交货日期）
    "tender.required_validity_days": 90,
    "tender.bond_required": 50000,
    "tender.agent_construction_unit": "湖北某建设管理单位",
    "tender.tender_agency": "湖北某招标代理有限公司",
    "tender.supervisor_legal_rep": "张监理",
    "tender.agency_legal_rep": "李代理",
    "tender.agent_construction_legal_rep": "王代建",
    "tender.affiliate_org_names": ["国网湖北省电力有限公司某某供电公司"],
    "tender.avg_price_threshold_rule": {"base": "peer.price_avg", "mult": 1.2},
    # 技术参数表与专用资格要求尚未结构化 —— 这是当前真实状态（0 项）
    "tender.tech_params_mandatory": {},
    "tender.tech_param_tolerance": {},
    "tender.special_qualification_requirements": {},
    "tender.other_qualification_requirements": {},
    "legal.tax_rate_set": [0.13, 0.09, 0.06, 0.03, 0.01, 0.0],
}

BASE_BID = {
    "bid.bidder_name": "武汉某某电气有限公司",
    "bid.legal_rep_name": "陈某某",
    "bid.license_name": "武汉某某电气有限公司",
    "bid.qualification_cert_name": "武汉某某电气有限公司",
    "bid.name_change_proof_present": False,
    "bid.voucher_index_viewable": True,
    "bid.format_completeness": "complete",
    "bid.file_count_with_diff_content": 1,
    "bid.distinct_price_count": 1,
    "bid.alternative_declared": False,
    "bid.authorization_letter_present": True,
    "bid.authorization_letter_elements_ok": True,
    "bid.legal_rep_seal_present": True,
    "bid.seal_present": True,
    "bid.seal_valid": True,
    "bid.seal_name": "武汉某某电气有限公司",
    "bid.withdrawn_after_deadline": False,
    "bid.committed_delivery_date": "2026-04-30",     # 投标人承诺的交货日期
    "bid.validity_days": 90,
    "bid.tax_rate": 0.13,
    "bid.bond_amount": 50000,
    "bid.bond_form": "bank_transfer",
    "bid.bond_basic_account_proof": True,
    "bid.price_numeric": True,
    "bid.qty": 100,
    "bid.unit_price": 158530,
    "bid.price_total": 15853000,
    "bid.price_total_ex_tax": 15853000,
    # 逐物料报价（第四条 950 万，全部低于各自限价）
    # 每行带数量与单价：行11 要逐行验「数量×单价=合价」，只给合价它无从校验，
    # 会一路降级成 UNCERTAIN（三场景基线就是这么从 22 掉到 21 的）。
    "bid.price_items": [
        {"item_no": "100035912500010", "qty": 1, "unit_price_yuan": 323000,
         "amount_yuan": 323000, "calc_amount_yuan": 323000},
        {"item_no": "100035917800010", "qty": 1, "unit_price_yuan": 1730000,
         "amount_yuan": 1730000, "calc_amount_yuan": 1730000},
        {"item_no": "100035912200010", "qty": 1, "unit_price_yuan": 4300000,
         "amount_yuan": 4300000, "calc_amount_yuan": 4300000},
        {"item_no": "100034915900360", "qty": 1, "unit_price_yuan": 9500000,
         "amount_yuan": 9500000, "calc_amount_yuan": 9500000},
    ],
    "bid.price_items.declared_total_yuan": 15853000,
    "bid.price_unit_ratio_to_ref": 1.05,
    "bid.consortium_agreement_present": True,
    "bid.is_agent": False,
    "bid.manufacturer_name": "武汉某某电气有限公司",
    "bid.agent_of": None,
    "bid.brand_model": "KYN28-12",
    "bid.tech_params": {},
    "bid.qualification_fields": {},
    "bid.peer_ref_price_median": 860000,
}

# 场景二：五处硬违规（只改这五项，其余字段保持合规，便于逐条归因）
BAD = dict(BASE_BID)
BAD.update({
    "bid.bidder_name": "襄阳某某开关有限公司",
    "bid.legal_rep_name": "孙某某",
    "bid.license_name": "襄阳某某开关有限公司",
    "bid.qualification_cert_name": "襄阳某某开关有限公司",
    "bid.seal_name": "襄阳某某电力设备有限公司",     # 违规①：签章名称与投标人不一致
    # 违规②：第 3 条物料报价 460 万 > 该行项目限价 453.31 万。
    # 注意标包总价 1615.3 万 <= 限价合计 1669.43 万——总额没超，
    # 单值比无论如何抓不到这一条，只有逐物料对位能抓到。
    "bid.price_total": 16153000,
    "bid.price_total_ex_tax": 16153000,
    "bid.unit_price": 161530,
    "bid.price_items": [
        {"item_no": "100035912500010", "qty": 1, "unit_price_yuan": 330000,
         "amount_yuan": 330000, "calc_amount_yuan": 330000},
        {"item_no": "100035917800010", "qty": 1, "unit_price_yuan": 1800000,
         "amount_yuan": 1800000, "calc_amount_yuan": 1800000},
        # ← 超限：该行项目限价 453.31 万，此处报 460 万
        {"item_no": "100035912200010", "qty": 1, "unit_price_yuan": 4600000,
         "amount_yuan": 4600000, "calc_amount_yuan": 4600000},
        {"item_no": "100034915900360", "qty": 1, "unit_price_yuan": 9423000,
         "amount_yuan": 9423000, "calc_amount_yuan": 9423000},
    ],
    "bid.price_items.declared_total_yuan": 16153000,
    "bid.validity_days": 60,                          # 违规③：有效期 60 < 90
    "bid.tax_rate": 0.11,                             # 违规④：税率不在法定集合
    "bid.distinct_price_count": 2,                    # 违规⑤：同一内容两个报价
})

# 场景三：只交了三项字段，其余全缺（模拟抽取失败 / 投标文件不全）
THIN = {
    "bid.bidder_name": "宜昌某某输变电有限公司",
    "bid.legal_rep_name": "赵某某",
    "bid.price_total": 15000000,
}


# ---------------------------------------------------------------- 逐物料对位四情形
def run_item_scenarios():
    """行10 逐物料对位的四情形真跑。

    只用 152507-1102002-4004 的真实限价明细（4 条物料、1669.43 万合计），
    只改投标侧报价，其余字段不参与——这样每个结果都能唯一归因到对位逻辑本身。

    A 全物料合规          → RESPONDED
    B 仅第3条超限（总额未超）→ NOT_RESPONDED   ← 单值比抓不到
    C 只有总价且总价超合计  → NOT_RESPONDED   ← 单向判否，无需明细
    D 只有总价且总价未超    → UNCERTAIN       ← 刻意不加绿：可能某条物料超
    E 报价含限价表外行项目  → UNCERTAIN       ← 对不上就不判
    """
    rule = None
    for r in json.load(io.open(DISPATCH, encoding="utf-8"))["rules"]:
        if r["rule_id"] == "GW-HB-FJ-010":
            rule = r
    assert rule is not None, "行10 规则缺失"

    def base_ctx():
        return {"tender.price_cap_items": CAP_ITEMS_4004,
                "tender.price_cap": CAP_SUM_4004}

    cases = [
        ("A 全物料合规", dict(base_ctx(), **{
            "bid.price_items": [
                {"item_no": "100035912500010", "amount_yuan": 323000},
                {"item_no": "100035917800010", "amount_yuan": 1730000},
                {"item_no": "100035912200010", "amount_yuan": 4300000},
                {"item_no": "100034915900360", "amount_yuan": 9500000}],
            "bid.price_total_ex_tax": 15853000})),
        ("B 仅第3条超限（总额未超）", dict(base_ctx(), **{
            "bid.price_items": [
                {"item_no": "100035912500010", "amount_yuan": 330000},
                {"item_no": "100035917800010", "amount_yuan": 1800000},
                {"item_no": "100035912200010", "amount_yuan": 4600000},
                {"item_no": "100034915900360", "amount_yuan": 9423000}],
            "bid.price_total_ex_tax": 16153000})),
        ("C 只有总价且总价超合计", dict(base_ctx(), **{
            "bid.price_total_ex_tax": 17000000})),
        ("D 只有总价且总价未超", dict(base_ctx(), **{
            "bid.price_total_ex_tax": 16000000})),
        ("E 报价含限价表外行项目", dict(base_ctx(), **{
            "bid.price_items": [
                {"item_no": "100035912500010", "amount_yuan": 323000},
                {"item_no": "999999999999999", "amount_yuan": 100000}],
            "bid.price_total_ex_tax": 423000})),
    ]

    out = []
    for name, ctx in cases:
        r = run_rule(rule, ctx, [])
        out.append({"case": name, "state": r["state"], "reason": r["reason"],
                    "item_check": r.get("item_check"),
                    "missing_fields": r.get("missing_fields"),
                    "optional_gaps": r.get("optional_gaps")})
    return out



def main():
    results = run_package(COMMON_TENDER, [BASE_BID, BAD, THIN])
    item_cases = run_item_scenarios()
    out = {"meta": {
        "tender": "152507 同一笔采购（基准 46 条否决情形）",
        "scenarios": ["S1 合规投标", "S2 五处硬违规", "S3 只交三项字段"],
        "note": "机器路径结论恒为候选；缺证恒 UNCERTAIN；人工/外部/超范围恒 NEED_HUMAN",
        "generated_at_rules": DISPATCH,
        "row10_upgrade": "逐物料对位（per_item_within_cap）；限价取 152507-1102002-4004 真实 4 条物料，合计 %d 元"
                         % CAP_SUM_4004,
    }, "packages": results, "item_scenarios": item_cases}

    from collections import Counter
    lines = []
    for pkg in results:
        c = Counter(r["state"] for r in pkg["rows"])
        out.setdefault("summary", {})[pkg["bidder"]] = dict(c)
        lines.append((pkg["bidder"], c))

    # 红线自检
    problems = []
    for pkg in results:
        for r in pkg["rows"]:
            if r["exec_path"] in ("HUMAN", "EXTERNAL", "OUT_OF_SCOPE") and r["state"] != STATE_HUMAN:
                problems.append("越界:" + r["rule_id"])
            if r["state"] == STATE_FAIL and r["missing_fields"]:
                problems.append("缺证判否:" + r["rule_id"])
    out["meta"]["redline_violations"] = problems

    io.open(OUT, "w", encoding="utf-8").write(json.dumps(out, ensure_ascii=False, indent=1))

    print("=" * 78)
    for bidder, c in lines:
        print("%-26s RESPONDED=%2d  NOT_RESPONDED=%2d  UNCERTAIN=%2d  NEED_HUMAN=%2d"
              % (bidder[:26], c[STATE_PASS], c[STATE_FAIL], c[STATE_UNK], c[STATE_HUMAN]))
    print("=" * 78)

    # 场景二逐条列出被机器判否的规则
    print("\n[S2 五处硬违规] 机器判 NOT_RESPONDED 的条目：")
    for r in results[1]["rows"]:
        if r["state"] == STATE_FAIL:
            print("  行%-3s %s  %s/%s  ← %s" % (r["row"], r["rule_id"],
                                                r["category"], r["subcategory"], r["reason"]))

    print("\n[S3 只交三项字段] UNCERTAIN 的条目数：%d（全部转澄清，不判否）"
          % sum(1 for r in results[2]["rows"] if r["state"] == STATE_UNK))
    print("[S3] NOT_RESPONDED 条目数：%d  ← 必须为 0"
          % sum(1 for r in results[2]["rows"] if r["state"] == STATE_FAIL))

    print("\n红线自检：", "通过，0 处越界" if not problems else problems)

    print("\n[行10 逐物料对位] 四情形：")
    want = {"A 全物料合规": STATE_PASS, "B 仅第3条超限（总额未超）": STATE_FAIL,
            "C 只有总价且总价超合计": STATE_FAIL, "D 只有总价且总价未超": STATE_UNK,
            "E 报价含限价表外行项目": STATE_UNK}
    bad_cases = []
    for c in item_cases:
        if c["state"] != want[c["case"]]:
            bad_cases.append("%s 期望 %s 实得 %s" % (c["case"], want[c["case"]], c["state"]))
        ic = c["item_check"] or {}
        extra = ""
        if ic.get("basis") == "item":
            extra = " 超限=%s 未报价=%s" % (ic.get("over") or "无", ic.get("missing_quote") or "无")
        elif ic.get("basis") == "total":
            extra = " 总价=%s 限价合计=%s" % (ic.get("bid_total_yuan"), ic.get("cap_sum_yuan"))
        print("  %-24s %-14s%s" % (c["case"], c["state"], extra))
    print("  期望比对：", "四情形全部命中" if not bad_cases else bad_cases)

    print("输出：", OUT)
    return 0 if (not problems and not bad_cases) else 1


if __name__ == "__main__":
    sys.exit(main())
