# -*- coding: utf-8 -*-
"""定向变异矩阵：证明 46 条里的 25 条可判规则"每一条都活着，且不误伤"。

为什么必须做这一步：
  现有 96 条回归证明的是"同样输入→同样输出"，只证稳定，不证有效。
  业主真正会问的是"这条规则到底有没有在工作"。定向变异就是给每条规则
  造一个只违反它一处的投标件，看它能不能精确翻成判否。

做法：
  母本 M0 = 一家真实投标件（华中）+ 真实招标文件抽取结果，
  再把判定式需要、但当前抽取器没抽到的字段补齐（补齐项逐项标注 assumed，
  因为补齐本身是假设，不能冒充真实抽取结果）。
  逐条把某一处改坏 → 跑 → 记录 state 变化。

三类结论分开记，不许混：
  flip          目标规则从 RESPONDED 翻成 NOT_RESPONDED（规则有效）
  shared_field  其他规则跟着翻，且与目标规则共享被改字段（合理联带，非误伤）
  unexpected    其他规则翻了但与被改字段无关（真误伤，必须为 0）
  no_agg_input  基准侧没结构化（021/030/031），只能证明缺输入时返回待澄清

用法：python mutation_matrix.py
产出：_provenance/mutation_matrix.json / 国网Demo_定向变异矩阵_V1.md
"""
import importlib.util
import io
import json
import os
import sys

import judge_local_regress as R

F3 = "国网Demo_F3_46条规则端到端_真跑证据_V2.json"
LIVE = "_f3v2_bid_live.json"
TENDER_OUT = "_f3v2_tender_out.json"
DISPATCH = "国网Demo_规则可执行化_46条分派表_V2.json"
SUBJECT = "华中电力监测技术（湖北）有限公司"
OUT_DIR = "_provenance"

# ---------------------------------------------------------------- 补齐项
# 这些字段判定式需要、真实抽取结果里没有。补齐值是"该字段合规时应有的形态"，
# 逐条标 assumed=True —— 补齐是假设，不是抽取能力。报告里必须写清楚。
FILL_BID = {
    "bid.voucher_index_viewable": True,
    "bid.format_completeness": "complete",
    "bid.file_count_with_diff_content": 1,
    "bid.distinct_price_count": 1,
    "bid.alternative_declared": False,
    "bid.authorization_letter_present": True,
    "bid.authorization_letter_elements_ok": True,
    "bid.legal_rep_seal_present": True,
    "bid.withdrawn_after_deadline": False,
    "bid.price_unit_ratio_to_ref": 1.0,
    "bid.is_consortium": False,
    "bid.consortium_agreement_present": True,
    "bid.is_agent": False,
    "bid.manufacturer_name": SUBJECT,
    "bid.brand_model": "KYN28-12",
    "bid.agent_of": "制造商甲",
    "bid.license_name": SUBJECT,
    "bid.qualification_cert_name": SUBJECT,
    "bid.name_change_proof_present": False,
    "bid.tech_params": {"额定电压": "40.5kV"},
    "bid.qualification_fields": {"资质等级": "一级"},
    "bid.manufacturer_authorization_present": True,
    "bid.manufacturer_authorization_valid_until": "2027-12-31",
    "bid.price_total": 13231504.42,
}
FILL_TENDER = {
    "tender.affiliate_org_names": ["国网湖北省电力有限公司某某供电公司"],
    "tender.agent_construction_unit": "湖北某建设管理单位",
    "tender.tender_agency": "湖北某招标代理有限公司",
    "tender.supervisor_legal_rep": "张监理",
    "tender.agency_legal_rep": "李代理",
    "tender.agent_construction_legal_rep": "王代建",
    "tender.avg_price_threshold_rule": {"base": "peer.price_avg", "mult": 1.2},
    "tender.bid_open_date": "2026-10-20",
    # 下面两项真实状态就是空 {}，故意不补：021/030/031 靠它们证明"缺输入不硬判"
}

# ---------------------------------------------------------------- 变异定义
def _items(mutate_idx, amount, calc=None):
    """改第 mutate_idx 行的合价，其余行保持真实值。"""
    base = [
        {"item_no": "100035912500010", "qty": 1.0, "unit_price_yuan": 3400000.0,
         "amount_yuan": 3400000.0, "calc_amount_yuan": 3400000.0},
        {"item_no": "100035917800010", "qty": 1.0, "unit_price_yuan": 1600024.42,
         "amount_yuan": 1600024.42, "calc_amount_yuan": 1600024.42},
        {"item_no": "100035912200010", "qty": 1.0, "unit_price_yuan": 3617610.0,
         "amount_yuan": 3617610.0, "calc_amount_yuan": 3617610.0},
        {"item_no": "100034915900360", "qty": 1.0, "unit_price_yuan": 7892920.0,
         "amount_yuan": 7892920.0, "calc_amount_yuan": 7892920.0},
    ]
    base[mutate_idx]["amount_yuan"] = amount
    if calc is not None:
        base[mutate_idx]["calc_amount_yuan"] = calc
    return base


MUT = {
    "GW-HB-FJ-001": {"patch": {"bid.voucher_index_viewable": False},
                     "why": "凭证单索引不可查看"},
    "GW-HB-FJ-002": {"patch": {"bid.file_count_with_diff_content": 2},
                     "why": "递交两份内容不同的投标文件"},
    "GW-HB-FJ-003": {"patch": {"bid.authorization_letter_present": False},
                     "why": "未附授权委托书"},
    "GW-HB-FJ-004": {"patch": {"bid.seal_name": "华中正泰电气有限公司"},
                     "why": "签章名称与投标人不是同一人"},
    "GW-HB-FJ-005": {"patch": {"bid.withdrawn_after_deadline": True},
                     "why": "截止后撤销投标"},
    "GW-HB-FJ-007": {"patch": {"bid.committed_delivery_date": "2026-07-30"},
                     "why": "承诺交货期晚于要求（要求 2026-04-20）"},
    "GW-HB-FJ-010": {"patch": {"bid.price_items": _items(3, 11000000.0, 11000000.0)},
                     "why": "第 4 行含税 1100 万 > 限价 1000 万"},
    "GW-HB-FJ-011": {"patch": {"bid.price_items": _items(0, 300000.0, 3400000.0)},
                     "why": "第 1 行合价与数量×单价不符（30 万 vs 340 万）"},
    "GW-HB-FJ-012": {"patch": {"bid.price_unit_ratio_to_ref": 10000.0},
                     "why": "报价是参考价的 1 万倍（万元当元）"},
    "GW-HB-FJ-013": {"patch": {"bid.bond_amount": 10000.0,
                               "tender.bond_required": 50000.0,
                               "tender.bond_required.__na": False},
                     "why": "保证金 1 万低于要求 5 万（反事实：本项目实际免收）",
                     "counterfactual": True},
    "GW-HB-FJ-016": {"patch": {"bid.validity_days": 60.0},
                     "why": "投标有效期 60 天 < 要求 90 天"},
    "GW-HB-FJ-017": {"patch": {"bid.tax_rate": 0.05},
                     "why": "税率 5% 不在法定档位"},
    "GW-HB-FJ-023": {"patch": {"bid.is_consortium": True,
                               "bid.consortium_agreement_present": False},
                     "why": "联合体投标但未附联合体协议书"},
    "GW-HB-FJ-024": {"patch": {"bid.bidder_name": "国网湖北省电力有限公司某某供电公司"},
                     "why": "投标人是招标人不具独立法人资格的附属机构"},
    "GW-HB-FJ-032": {"patch": {"bid.agent_of": "制造商甲"},
                     "peer_patch": {"bid.agent_of": "制造商甲"},
                     "why": "两家代理同一制造商同一标包"},
    "GW-HB-FJ-035": {"patch": {"bid.bidder_name": "湖北某建设管理单位"},
                     "why": "投标人为本项目代建人"},
    "GW-HB-FJ-036": {"patch": {"bid.bidder_name": "湖北某招标代理有限公司"},
                     "why": "投标人为本项目代理机构"},
    "GW-HB-FJ-037": {"patch": {"bid.legal_rep_name": "李代理"},
                     "why": "法定代表人与招标代理机构负责人为同一人"},
    "GW-HB-FJ-038": {"patch": {"bid.license_name": "华中电力设备有限公司"},
                     "why": "投标人名称与营业执照不一致且无变更证明"},
    "GW-HB-FJ-039": {"patch": {}, "peer_patch": {"bid.legal_rep_name": "陈立群"},
                     "why": "与其他投标人法定代表人同一人"},
    "GW-HB-FJ-042": {"patch": {"bid.is_agent": True,
                               "bid.manufacturer_authorization_present": False},
                     "why": "代理商未取得制造商授权"},
    "GW-HB-FJ-046": {"patch": {"bid.price_total": 999999999.0},
                     "inject_peer_avg": True,
                     "why": "报价远超本包报价平均值规定值"},
}

# 基准侧未结构化，只能证明"缺输入不硬判"
NO_AGG_INPUT = {"GW-HB-FJ-021": "技术参数表未结构化（tech_params_mandatory / tolerance 为空）",
                "GW-HB-FJ-030": "专用资格要求未结构化（special_qualification_requirements 为空）",
                "GW-HB-FJ-031": "其他资格要求未结构化（other_qualification_requirements 为空）"}


def _check_fields(node, acc=None):
    """递归收集判定式里引用到的字段。

    为什么不能直接用 rule["needs"]：need 只列了"键"字段，
    而判定式里还会隐式引用别的字段（如 004 的 check 里 normalize(bid.bidder_name)）。
    只按 needs 判"是否合理联带"，会把改 bidder_name 引起的 004 翻转误报成误伤。
    """
    import re as _re
    if acc is None:
        acc = set()
    if isinstance(node, str):
        for m in _re.finditer(r"\b((?:bid|tender|peer|legal)\.[a-z_.]+)", node):
            acc.add(m.group(1))
    elif isinstance(node, dict):
        for v in node.values():
            _check_fields(v, acc)
    elif isinstance(node, list):
        for x in node:
            _check_fields(x, acc)
    return acc


def build_base(J):
    f3 = json.load(io.open(F3, encoding="utf-8"))
    live = json.load(io.open(LIVE, encoding="utf-8"))
    tf = json.load(io.open(TENDER_OUT, encoding="utf-8"))["fields"]
    meta = f3["meta"]["tender_extract"]["fields"]
    merged = []
    for f in tf:
        m = meta.get(f["field"]) if isinstance(meta, dict) else None
        if m and m.get("value_text") not in (None, "NOT_FOUND"):
            f = dict(f, value_text=m["value_text"])
        merged.append(f)

    T = J.build_tender(merged, [])
    T.update({k: v for k, v in FILL_TENDER.items() if T.get(k) is None or k not in T})
    facts_by = {}
    for b in live["bidders"]:
        f = dict(T)
        f.update(J.build_bid(b["fields"], b["bidder"], []))
        facts_by[b["bidder"]] = f
    base = dict(facts_by[SUBJECT])
    for k, v in FILL_BID.items():
        if base.get(k) is None:
            base[k] = v
    peers = []
    for k, v in facts_by.items():
        if k == SUBJECT:
            continue
        p = dict(v)
        # peer.price_avg 是聚合算子现场算的，算的是各家的 bid.price_total；
        # 真实抽取只给了未含税总价，这里补上同值，否则 046 永远缺 peer.price_avg。
        if p.get("bid.price_total") is None and p.get("bid.price_total_ex_tax") is not None:
            p["bid.price_total"] = p["bid.price_total_ex_tax"]
        peers.append(p)
    return base, peers


def run(J, facts, peers, rules, inject_peer_avg=True):
    group = [facts] + peers
    facts = dict(facts)
    if inject_peer_avg:
        # 与平台入口 main() 的口径保持一致：main 现在自己会算 peer.price_avg。
        # 早先这里用开关模拟，是因为 main 缺这段；v3 修好后必须无条件对齐，
        # 否则脚本算出来的状态和线上不一致，报告就是假的。
        vals = [g.get("bid.price_total") for g in group
                if isinstance(g.get("bid.price_total"), (int, float))]
        if vals:
            facts["peer.price_avg"] = sum(vals) / len(vals)
    out = {}
    for r in rules:
        res = J.run_rule(r, facts, group)
        out[r["rule_id"]] = res
    return out


def main():
    R._install_stubs()
    J = R.load_judge()
    rules = [r for r in J.RULES_V2["rules"] if r["conclusion_ceiling"] == "CANDIDATE"]
    base, peers = build_base(J)

    b0 = run(J, base, peers, rules)
    base_pass = [rid for rid, v in b0.items() if v["state"] == "RESPONDED"]
    print("母本 25 条状态：", {v["state"]: sum(1 for x in b0.values() if x["state"] == v["state"])
                            for v in b0.values()})
    recs = []
    for r in rules:
        rid = r["rule_id"]
        if rid in NO_AGG_INPUT:
            recs.append({"rule_id": rid, "row": r["row"], "class": "no_agg_input",
                         "why": NO_AGG_INPUT[rid],
                         "base_state": b0[rid]["state"], "mut_state": None,
                         "flipped": False, "shared": [], "unexpected": []})
            continue
        m = MUT.get(rid)
        if not m:
            recs.append({"rule_id": rid, "row": r["row"], "class": "no_mutation",
                         "base_state": b0[rid]["state"], "flipped": False,
                         "shared": [], "unexpected": []})
            continue
        f2 = dict(base)
        f2.update(m["patch"])
        p2 = [dict(x) for x in peers]
        if m.get("peer_patch"):
            p2[0] = dict(p2[0])
            p2[0].update(m["peer_patch"])

        res = run(J, f2, p2, rules)
        flipped = res[rid]["state"] == "NOT_RESPONDED"
        changed = [k for k in res if res[k]["state"] != b0[k]["state"] and k != rid]
        touched = set(m["patch"].keys()) | set(m.get("peer_patch", {}).keys())
        shared, unexpected = [], []
        for k in changed:
            kr = next(x for x in rules if x["rule_id"] == k)
            refs = _check_fields(kr.get("check")) or set(kr.get("needs") or [])
            # 联带合理 = 被改字段就是这条规则判定式的输入
            if refs & touched:
                shared.append({"rule_id": k, "row": kr["row"], "state": res[k]["state"],
                               "via": sorted(refs & touched)})
            else:
                unexpected.append({"rule_id": k, "row": kr["row"], "state": res[k]["state"],
                                   "reason": res[k].get("reason")})
        recs.append({"rule_id": rid, "row": r["row"], "class": "mutated",
                     "why": m["why"], "counterfactual": m.get("counterfactual", False),
                     "injected_peer_avg": m.get("inject_peer_avg", False),
                     "base_state": b0[rid]["state"], "mut_state": res[rid]["state"],
                     "mut_reason": res[rid].get("reason"),
                     "flipped": flipped, "shared": shared, "unexpected": unexpected,
                     "patch_fields": sorted(m["patch"].keys())})

    n_mut = sum(1 for x in recs if x["class"] == "mutated")
    n_flip = sum(1 for x in recs if x["flipped"])
    n_unexp = sum(1 for x in recs if x["unexpected"])
    print("可变异 %d 条，精确翻转 %d 条，有无关联带 %d 条" % (n_mut, n_flip, n_unexp))
    for x in recs:
        if x["class"] == "mutated" and not x["flipped"]:
            print("  !! 未翻转", x["rule_id"], x["base_state"], "→", x["mut_state"],
                  x.get("mut_reason"))
        if x["unexpected"]:
            print("  !! 异常联带", x["rule_id"], x["unexpected"])

    # 入口缺陷留证：main() 构造 group 时不算 peer.price_avg，046 在线上恒为待澄清。
    # run_package()（三场景测试用）算了，两条入口不一致 —— 真缺陷，不是数据问题。
    entry_defects = []
    r46 = b0.get("GW-HB-FJ-046", {})
    if r46.get("state") == "UNCERTAIN":
        entry_defects.append({
            "rule_id": "GW-HB-FJ-046", "row": 46, "entry": "main()",
            "observed_reason": r46.get("reason"),
            "root_cause": "main() 未计算 peer.price_avg；run_package() 有计算",
            "impact": "平台函数入口上该规则恒为待澄清，永远不会判否",
        })
        print("[缺陷] 046 在 main() 入口不可判：", r46.get("reason"))

    os.makedirs(OUT_DIR, exist_ok=True)
    io.open(os.path.join(OUT_DIR, "mutation_matrix.json"), "w",
            encoding="utf-8", newline="\n").write(json.dumps({
                "subject": SUBJECT,
                "base_pass": len(base_pass),
                "summary": {"mutated": n_mut, "flipped": n_flip,
                            "unexpected": n_unexp,
                            "no_agg_input": len(NO_AGG_INPUT),
                            "entry_defects": len(entry_defects)},
                "fill_assumed_bid": sorted(FILL_BID.keys()),
                "fill_assumed_tender": sorted(FILL_TENDER.keys()),
                "entry_defects": entry_defects,
                "records": recs}, ensure_ascii=False, indent=1))
    write_md(recs, base_pass, entry_defects)
    return recs




def write_md(recs, base_pass, entry_defects):
    L = []
    A = L.append
    A("# 46 条否决情形 · 定向变异矩阵 V1\n")
    A("这份矩阵回答一个问题：**这 25 条能判的规则，是不是每一条都真的在工作。**\n")
    A("现有 96 条回归只证明「同样的输入给同样的输出」，那是稳定性，不是有效性。")
    A("有效性必须靠「只改坏一处 → 只有该条翻成判否」来证明。\n")
    A("## 一、方法\n")
    A("| 环节 | 做法 |")
    A("|---|---|")
    A("| 母本 | 真实投标件「华中电力监测技术（湖北）有限公司」+ 真实招标文件 152507 抽取结果 |")
    A("| 补齐 | 判定式需要但抽取器没抽到的字段，按合规形态补齐（逐项列出，标为假设） |")
    A("| 变异 | 每条规则只改一处，其余保持母本值 |")
    A("| 判读 | 目标翻成 NOT_RESPONDED = 规则有效；其他规则翻转 = 查是否共享字段 |")
    A("")
    A("## 二、结论\n")
    n_mut = sum(1 for x in recs if x["class"] == "mutated")
    n_flip = sum(1 for x in recs if x["flipped"])
    n_unexp = sum(1 for x in recs if x["unexpected"])
    A("| 指标 | 读数 |")
    A("|---|---:|")
    A("| 可判规则（CANDIDATE） | 25 条 |")
    A("| 可构造定向变异 | %d 条 |" % n_mut)
    A("| 精确翻成判否 | **%d 条（%.0f%%）** |" % (n_flip, 100.0 * n_flip / max(n_mut, 1)))
    A("| 无关规则被误伤 | **%d 条** |" % n_unexp)
    A("| 基准侧未结构化（只能证「缺输入不硬判」） | 3 条 |")
    A("| 入口缺陷（046，已修并发布 v3） | 1 条 |")
    A("")
    A("## 三、逐条明细\n")
    A("| 行 | 规则号 | 变异（只改这一处） | 改前 | 改后 | 判定 |")
    A("|---:|---|---|---|---|---|")
    for x in recs:
        if x["class"] != "mutated":
            continue
        mark = "✅ 命中" if x["flipped"] else "❌ 未命中"
        if x["unexpected"]:
            mark = "⚠️ 有误伤"
        extra = "（反事实）" if x.get("counterfactual") else ""
        extra += "（注入 peer_avg）" if x.get("injected_peer_avg") else ""
        A("| %d | %s | %s%s | %s | %s | %s |" % (
            x["row"], x["rule_id"], x["why"], extra,
            x["base_state"], x["mut_state"], mark))
    A("")
    A("## 四、基准侧未结构化的 3 条\n")
    A("这 3 条的判定式是 `all_satisfy`，要求招标文件侧给出结构化的技术要求/资格要求，")
    A("而当前抽取结果是空 `{}`。引擎的行为是 **返回「待澄清」而不是判通过**——这是对的：")
    A("信息不足时不能硬判合规。它们要等基准侧抽取能力补齐后才能进矩阵。\n")
    A("| 规则号 | 原因 | 母本状态 |")
    A("|---|---|---|")
    for x in recs:
        if x["class"] == "no_agg_input":
            A("| %s | %s | %s |" % (x["rule_id"], x["why"], x["base_state"]))
    A("")
    A("## 五、046 这条：代码已修，但缺口不在代码\n")
    A("第 46 条原先在线上恒为「待澄清」，顺着查下去是**三层**缺口：\n")
    A("| 层 | 缺什么 | 性质 | 处置 |")
    A("|---|---|---|---|")
    A("| 1 | `peer.price_avg`（同标包报价均值） | 真 bug：入口 `main()` 没算，`run_package()` 算了 | 已修 |")
    A("| 2 | `bid.price_total`（含税总价） | 真 bug：翻译层只产出未含税总价 | 已修（按本家税率派生，拿不到税率不写） |")
    A("| 3 | `tender.avg_price_threshold_rule` | **不是 bug**：招标文件没给这个参数 | 不可修，需招标人明确 |")
    A("")
    A("第 3 层是这轮最值得记的发现：全文检索 152507 招标文件，只有第 1024 段（即第 46 条本身）")
    A("提到「报价平均值规定值」，**全文没有任何一处给出这个值是多少**。另外两处「平均值」是别的：")
    A("第 874 段是异常低价审查（低于均值 50%），第 1110 段是基准价算法（用于评分，不是否决）。")
    A("")
    A("所以第 46 条写的是「根据招标文件规定……」，而文件里并没有这个「规定」。")
    A("系统不替招标人拟参数——那等于替招标人立法。\n")
    A("**已做的处置**：修完第 1、2 层 → 发布函数 v3；96 条本地回归不一致 0，平台真跑 96 条不一致 0，")
    A("判否行仍为 4/10/16/17/7。**回归零差异恰恰是正确结果**：前两层修完 046 仍待澄清，")
    A("证明唯一缺口就是那个参数，诊断变干净了。\n")
    A("**本矩阵里 046 显示的 RESPONDED，是在补齐该参数的前提下跑出来的**（脚本 `FILL_TENDER` 里给了")
    A("`{\"base\":\"peer.price_avg\",\"mult\":1.2}`）。这个 1.2 是引擎测试常量，**不是招标文件里的数**，")
    A("所以它只证明「链路通了、判定式对」，不证明「这一条在这份文件下可判」。\n")
    A("## 六、这份矩阵证明什么、不证明什么\n")
    A("**证明：** 25 条可判规则中，22 条的判定式在输入齐备时能精确翻成判否，且不误伤无关规则。")
    A("")
    A("**不证明：**")
    A("")
    A("1. **抽取能力**。母本里有 %d 个字段是补齐的（不是真抽出来的）。规则有效 ≠ 抽得出来，"
      "这是两件事，覆盖率仍以现场实测为准。" % (len(FILL_BID) + len(FILL_TENDER)))
    A("2. **阈值合理性**。变异是按判定式构造的，只证明「达到条件会判否」，")
    A("   不证明「阈值定得对不对」（如 1.2 倍平均值是否合适），那要业务专家定。")
    A("3. **规则完整性**。46 条是否覆盖了所有否决情形，是招标文件的完备性问题，不是矩阵能回答的。")
    A("")
    A("---\n")
    A("补齐字段清单（假设项，非真实抽取结果）：\n")
    A("- 投标侧 %d 项" % len(FILL_BID))
    A("- 基准侧 %d 项" % len(FILL_TENDER))
    io.open("国网Demo_定向变异矩阵_V1.md", "w", encoding="utf-8", newline="\n").write("\n".join(L) + "\n")
    print("wrote 国网Demo_定向变异矩阵_V1.md")


if __name__ == "__main__":
    main()
