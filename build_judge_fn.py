# -*- coding: utf-8 -*-
"""把本地判定引擎（sgcc_rule_runner.py）打包成 apemind 平台函数。

为什么用生成器而不是手抄：
  判定引擎里每一条注释都对应一次真跑踩过的坑（含税口径、合计取错行、验签否定优先……）。
  手抄一遍就等于给这些坑开一次「复述漂移」的口子，回归测试也没法证明"平台跑的和本地跑的是同一份"。
  这里直接按行号切 sgcc_rule_runner.py 的引擎段，逐字搬进 main.py，
  再用同一份分派表 V2 生成内嵌规则常量，保证两边同源。

产出：
  sgcc_fn_rule_judge/main.py      函数体（引擎 + 翻译层 + 46 条规则 + 入口）
  sgcc_fn_rule_judge/function.json
用法：python build_judge_fn.py
"""
import hashlib
import io
import json

SRC_RUNNER = "sgcc_rule_runner.py"
DISPATCH = "国网Demo_规则可执行化_46条分派表_V2.json"
OUT_DIR = "sgcc_fn_rule_judge"

# 引擎段：从 MISSING 哨兵到 run_package 之前（含 run_rule）。
# 按标记切而不是按行号——引擎每修一次 bug 行号就漂，行号切片会静默少搬/多搬几行。
ENGINE_START_MARK = "MISSING = object()"
ENGINE_END_MARK = "def run_package("

KEEP = ["rule_id", "row", "category", "subcategory", "rule_text", "exec_path",
        "needs", "check", "optional_needs", "evidence", "human_gate",
        "external_source", "signals", "conclusion_ceiling", "states"]


def slice_engine():
    lines = io.open(SRC_RUNNER, encoding="utf-8").read().split("\n")
    start = next(i for i, ln in enumerate(lines) if ln.startswith(ENGINE_START_MARK))
    end = next(i for i, ln in enumerate(lines) if ln.startswith(ENGINE_END_MARK))
    seg = [ln for ln in lines[start:end]]
    while seg and not seg[-1].strip():
        seg.pop()
    assert seg[-1].strip() == "return base", seg[-1]
    return "\n".join(seg).rstrip() + "\n"


def slim_rules():
    src = json.load(io.open(DISPATCH, encoding="utf-8"))
    rules = [{k: r[k] for k in KEEP if k in r} for r in src["rules"]]
    return rules


def digest_of(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


HEAD = '''# -*- coding: utf-8 -*-
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

'''

TAIL_HEAD = '''

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
    m = re.search(r"\\d{4}-\\d{2}-\\d{2}", str(t or ""))
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
    _sn = re.sub(r"[（(]\\s*电子签章\\s*[)）]", "", _sn).strip()
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


# ================================================================ 规则表（内嵌 V2，{n} 条）

RULES_V2 = json.loads(r"""{rules_json}""")
RULE_SET_VERSION = "V2"
RULE_SET_SHA = "{rule_sha}"

# 参与指纹计算的字段集合与顺序，由 build_judge_fn.py 的 KEEP 注入（单一真相源）。
# 外部规则表按同一口径 slim 后再算 sha，才能与 RULE_SET_SHA 互校。
_KEEP_FIELDS = {keep_fields}


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
'''


def main():
    engine = slice_engine()
    rules = slim_rules()
    rules_json = json.dumps({"meta": {"version": "V2", "n": len(rules)},
                             "rules": rules}, ensure_ascii=False, separators=(",", ":"))
    rule_sha = digest_of(rules_json)

    # 先替换模板里的短占位符，最后才注入规则 JSON：
    # 规则原文里一旦出现 "{n}" 这类字样，反过来替换就会把规则文本改掉。
    tail = (TAIL_HEAD.replace("{n}", str(len(rules)))
            .replace("{rule_sha}", rule_sha)
            .replace("{keep_fields}", repr(KEEP)))
    body = HEAD + engine + tail.replace("{rules_json}", rules_json)

    import os
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    io.open(os.path.join(OUT_DIR, "main.py"), "w", encoding="utf-8", newline="\n").write(body)

    fn = {
        "slug": "sgcc-rule-judge",
        "title": "46 条否决情形判定器（受限 DSL · 可审计）",
        "description": (
            "输入抽取器的原始输出（基准侧 fields + 受审侧 fields），函数内完成「原文 → 判定事实」翻译后"
            "逐条执行 46 条否决情形的受限 DSL 判定式。不用 eval/exec，算子白名单穷举；缺字段一律 UNCERTAIN，"
            "绝不降级成「未见响应」；结论上限 CANDIDATE。逐物料限价对位、逐行算术校验、跨投标人聚合三类算子"
            "各自带对位明细，任何一条判否都能回到原文的哪一行、差多少。"
            "规则可外部注入：传 rules（规则对象数组）即以传入规则为准，无需重新发版；"
            "rule_set_version 为版本名、rule_set_sha 为调用方指纹（与实算不符只写进 notes 留痕，不阻断判定）。"
            "响应里的 rule_source 标明本次用的是 embedded 内嵌集还是 input 传入集，便于对客留证与事故追溯。"),
        "network": False,
        "secret_names": [],
        "permissions": {"functions": "none", "knowledge_base": "none"},
        "access": {"collections": {"mode": "none"}},
        "limits": {"burst": 20, "max_concurrency": 8, "requests_per_second": 10},
        "examples": [{"input": {
            "section_no": "152507-1102002-4004",
            "bidder": "宜昌三峡输变电设备有限公司",
            "rule_ids": ["GW-HB-FJ-010"],
            "bid_fields": [
                {"field": "bid.bidder_name", "value_text": "宜昌三峡输变电设备有限公司", "value_num": None},
                {"field": "bid.tax_rate", "value_text": "13%", "value_num": 0.13},
                {"field": "bid.price_items", "value_text": "分项报价表", "value_num": None,
                 "items": [{"item_no": "100035912200010", "qty": 1.0, "unit_price_yuan": 4070796.46,
                            "amount_yuan": 4070796, "calc_amount_yuan": 4070796.46}]}
            ],
            "tender_fields": [
                {"field": "tender.price_cap", "value_text": "100035912200010:453.31 万元",
                 "value_num": 4533100, "applicable": True, "items_sum_yuan": 4533100,
                 "items": [{"item_no": "100035912200010", "cap_yuan": 4533100}]}
            ]}}],
    }
    io.open(os.path.join(OUT_DIR, "function.json"), "w", encoding="utf-8", newline="\n").write(
        json.dumps(fn, ensure_ascii=False, indent=2) + "\n")

    size = len(body.encode("utf-8"))
    print("engine lines   : %d" % len(engine.split("\n")))
    print("rules          : %d  sha=%s" % (len(rules), rule_sha))
    print("main.py bytes  : %d" % size)
    print("written        : %s/main.py, function.json" % OUT_DIR)


if __name__ == "__main__":
    main()
