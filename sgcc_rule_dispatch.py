# -*- coding: utf-8 -*-
"""
把 46 条否决情形从「自然语言条款」编译成「可执行规则行」。

核心思路：规则引擎的两件事被拆开
  A. 抽取（读得懂）：从投标/招标文件里拿到结构化字段 —— 由 LLM + 检索负责
  B. 判定（比得对）：字段之间比大小 / 比集合 / 比存在性 —— 由纯代码负责

拆分之后，「规则引擎」缩水成一个只认白名单算子的解释器（约 200 行），
规则本身退化成数据行。新增同类规则 = 加一行，不改代码。

执行路径五分类（互斥、穷举）：
  DET           字段已具备，纯比较即可判
  EXTRACT_DET   要先抽取字段，再比较（抽取可失败 → 必须允许 UNCERTAIN）
  HUMAN         需要语义裁量（"明显""不能接受""实质性"）→ 系统只出候选 + 证据
  EXTERNAL      判定依据在系统外部（信用中国 / 工商 / 国网供应商库）
  OUT_OF_SCOPE  条款本身不可穷举或原文不在库
"""
import csv
import json
import io
import sys

RULES_PATH = "国网Demo_专家评审规则库_V1.json"
OUT_JSON = "国网Demo_规则可执行化_46条分派表_V1.json"
OUT_CSV = "国网Demo_规则可执行化_46条分派表_V1.csv"

# exec_path, needs(所需字段), check(受限 DSL 表达式), gate(人工闸门), why(为什么这样分), evidence(证据位置)
D = {}


def add(rid, path, needs, check, why, evidence, gate=None, signals=None, external=None):
    D[rid] = dict(exec_path=path, needs=needs, check=check, why=why,
                  evidence=evidence, gate=gate, signals=signals, external=external)


# ---- 形式评审 ---------------------------------------------------------------
add("GW-HB-FJ-001", "EXTRACT_DET",
    ["bid.voucher_index_viewable", "bid.format_completeness"],
    {"op": "and", "args": [
        {"op": "eq", "lhs": "bid.voucher_index_viewable", "rhs": True},
        {"op": "eq", "lhs": "bid.format_completeness", "rhs": "complete"}]},
    "凭证单可查看是布尔事实（可判）；「内容不全/字迹模糊」需读文件，交抽取给三态",
    "招投标交易平台凭证单 / 投标文件各分册首页")

add("GW-HB-FJ-002", "DET",
    ["bid.file_count_with_diff_content", "bid.distinct_price_count", "bid.alternative_declared"],
    {"op": "and", "args": [
        {"op": "le", "lhs": "bid.file_count_with_diff_content", "rhs": 1},
        {"op": "or", "args": [
            {"op": "le", "lhs": "bid.distinct_price_count", "rhs": 1},
            {"op": "eq", "lhs": "bid.alternative_declared", "rhs": True}]}]},
    "文件份数、报价个数、是否声明备选方案都是可计数量",
    "投标文件封面/目录、开标一览表、投标函")

add("GW-HB-FJ-003", "EXTRACT_DET",
    ["bid.authorization_letter_present", "bid.authorization_letter_elements_ok",
     "bid.legal_rep_seal_present"],
    {"op": "and", "args": [
        {"op": "eq", "lhs": "bid.authorization_letter_present", "rhs": True},
        {"op": "eq", "lhs": "bid.authorization_letter_elements_ok", "rhs": True},
        {"op": "eq", "lhs": "bid.legal_rep_seal_present", "rhs": True}]},
    "「未附授权书」「要素不全」可查；「对格式文件实质性修改」是裁量，另挂人工闸门",
    "法定代表人授权委托书 / 格式文件签署页",
    gate="对格式文件是否构成实质性修改，由评标委员会认定")

add("GW-HB-FJ-004", "DET",
    ["bid.seal_present", "bid.seal_valid", "bid.seal_name"],
    {"op": "and", "args": [
        {"op": "eq", "lhs": "bid.seal_present", "rhs": True},
        {"op": "eq", "lhs": "bid.seal_valid", "rhs": True},
        {"op": "eq", "lhs": "normalize(bid.seal_name)", "rhs": "normalize(bid.bidder_name)"}]},
    "签章有无、有效性、名称一致都是可比对事实",
    "电子投标文件签章页")

add("GW-HB-FJ-005", "DET",
    ["bid.withdrawn_after_deadline"],
    {"op": "eq", "lhs": "bid.withdrawn_after_deadline", "rhs": False},
    "截止时间后是否撤回由平台日志直接给出布尔值，抽取环节负责把时间戳换算成该布尔",
    "招投标交易平台操作日志")

add("GW-HB-FJ-006", "HUMAN", [],
    None,
    "「不按要求澄清」要看评标委员会澄清通知与投标人回函，是过程事实而非文件属性",
    "评标委员会澄清通知 / 投标人澄清回函",
    gate="澄清是否已被要求、是否回应，由评标委员会记录")

# ---- 响应性评审 -------------------------------------------------------------
add("GW-HB-FJ-007", "EXTRACT_DET",
    ["bid.committed_delivery_date", "tender.required_delivery_date"],
    {"op": "le", "lhs": "bid.committed_delivery_date", "rhs": "tender.required_delivery_date"},
    "交货期是数字可直比；「招标人不能接受」是第二段，必须另交人",
    "投标函 / 商务偏差表",
    gate="交货期不满足时，是否接受由招标人决定，系统只报「不满足」")

add("GW-HB-FJ-008", "HUMAN", [],
    None,
    "是否「接受」修正价是投标人的意思表示，只能由评标过程记录证明",
    "评标委员会价格修正记录 / 投标人确认",
    gate="接受与否由评标委员会现场确认")

add("GW-HB-FJ-009", "HUMAN",
    ["bid.price_total", "peer.price_avg"],
    None,
    "「明显低于」「不能合理说明」「低于成本」三重裁量；系统可给偏离信号但不作判定",
    "开标一览表 / 报价说明 / 成本证明材料",
    gate="是否低于成本由评标委员会认定",
    signals=["bid.price_total / peer.price_avg >= 0.8 时不提示",
             "0.5~0.8 提示「显著偏低，建议要求说明」",
             "<0.5 提示「严重偏离，建议重点核查」"])

add("GW-HB-FJ-010", "DET",
    ["bid.price_total_ex_tax", "tender.price_cap"],
    {"op": "le", "lhs": "floor_yuan(bid.price_total_ex_tax)", "rhs": "tender.price_cap"},
    "最高限价是确定数值，剔除角分后直比，零裁量",
    "开标一览表 / 投标函价格表 / 招标文件最高限价条款")

add("GW-HB-FJ-011", "DET",
    ["bid.price_numeric", "bid.qty", "bid.unit_price", "bid.price_total"],
    {"op": "and", "args": [
        {"op": "eq", "lhs": "bid.price_numeric", "rhs": True},
        {"op": "eq", "lhs": "round2(mul(bid.qty, bid.unit_price))", "rhs": "round2(bid.price_total)"}]},
    "算术校验是纯计算，单价×数量≠总价即异常",
    "开标一览表 / 分项报价表")

add("GW-HB-FJ-012", "DET",
    ["bid.price_unit_ratio_to_ref"],
    {"op": "lt", "lhs": "bid.price_unit_ratio_to_ref", "rhs": 100},
    "百倍至万倍是区间比较；比值由抽取环节对同品类参考价求得，判定只做一次区间判断",
    "投标函价格表 / 同标包其他投标人报价")

add("GW-HB-FJ-013", "EXTRACT_DET",
    ["bid.bond_amount", "tender.bond_required", "bid.bond_form",
     "bid.bond_basic_account_proof"],
    {"op": "and", "args": [
        {"op": "ge", "lhs": "bid.bond_amount", "rhs": "tender.bond_required"},
        {"op": "in", "lhs": "bid.bond_form", "rhs": ["bank_transfer", "bank_guarantee", "insurance", "letter"]},
        {"op": "or", "args": [
            {"op": "ne", "lhs": "bid.bond_form", "rhs": "bank_transfer"},
            {"op": "eq", "lhs": "bid.bond_basic_account_proof", "rhs": True}]}]},
    "金额、形式、基本账户证明三项都是可核事实",
    "投标保证金缴纳凭证 / 基本账户开户许可证 / 保函")

add("GW-HB-FJ-014", "HUMAN", [],
    None,
    "「投标范围偏差」需与招标范围逐项对照后判断是否可接受",
    "投标函 / 供货范围表 / 招标范围条款",
    gate="偏差是否可接受由招标人认定")

add("GW-HB-FJ-015", "HUMAN", [],
    None,
    "「不能接受的条件或偏差」与「数据信息不满足规定」均需业务裁量",
    "商务/技术偏差表",
    gate="由评标委员会逐条认定")

add("GW-HB-FJ-016", "DET",
    ["bid.validity_days", "tender.required_validity_days"],
    {"op": "ge", "lhs": "bid.validity_days", "rhs": "tender.required_validity_days"},
    "投标有效期是天数，可直接比",
    "投标函 / 招标文件投标人须知前附表")

add("GW-HB-FJ-017", "DET",
    ["bid.tax_rate", "legal.tax_rate_set"],
    {"op": "in", "lhs": "bid.tax_rate", "rhs": "legal.tax_rate_set"},
    "法定税率为有限枚举集合，可判",
    "开标一览表 / 分项报价表 / 增值税税率栏")

add("GW-HB-FJ-018", "HUMAN",
    ["bid.performance_dates", "bid.invoice_numbers"],
    None,
    "「虚假」需与外部事实核验；系统只能给内部一致性冲突信号",
    "资格证明文件 / 业绩合同 / 验收报告 / 发票",
    gate="是否构成虚假投标由评标委员会认定并可追溯法律责任",
    signals=["业绩合同签订日期晚于验收报告日期",
             "同一发票号在不同业绩中重复出现",
             "业绩金额与合同金额不一致"])

add("GW-HB-FJ-019", "HUMAN",
    ["bid.ip", "bid.mac", "bid.file_author", "bid.contact_phone", "bid.price_pattern"],
    None,
    "串通认定是法律判断；系统只做同源信号聚类，不作结论",
    "平台递交日志 / 投标文件属性 / 报价序列",
    gate="串通投标认定权在评标委员会及行政监督部门",
    signals=["同一标包内两家投标人 IP 相同",
             "投标文件创建者/最后修改者相同",
             "联系人电话或邮箱相同",
             "报价呈规律性等差/等比"])

add("GW-HB-FJ-020", "OUT_OF_SCOPE", [], None,
    "援引外部法律法规的兜底条款，原文不在知识库内，系统无权代为解释",
    "法律法规原文（库外）",
    gate="只能由评标委员会依法认定")

# ---- 技术 / 参数 -----------------------------------------------------------
add("GW-HB-FJ-021", "EXTRACT_DET",
    ["bid.tech_params", "tender.tech_params_mandatory", "tender.tech_param_tolerance"],
    {"op": "and", "args": [
        {"op": "all_satisfy", "lhs": "bid.tech_params", "rhs": "tender.tech_params_mandatory"},
        {"op": "all_within_tolerance", "lhs": "bid.tech_params", "rhs": "tender.tech_param_tolerance"}]},
    "参数表一旦结构化，逐项比对是纯计算；前提是招标文件参数表已结构化（当前 0 项）",
    "技术规范书参数表 / 投标技术响应表")

# ---- 资格评审 --------------------------------------------------------------
add("GW-HB-FJ-022", "EXTERNAL",
    ["bid.major_quality_incident_3y"], None,
    "依据是行政处罚决定或司法文书，须外部数据源",
    "行业主管部门处罚决定 / 司法文书",
    external="国家企业信用信息公示系统 / 信用中国 行政处罚栏")

add("GW-HB-FJ-023", "DET",
    ["bid.is_consortium", "bid.consortium_agreement_present"],
    {"op": "or", "args": [
        {"op": "eq", "lhs": "bid.is_consortium", "rhs": False},
        {"op": "eq", "lhs": "bid.consortium_agreement_present", "rhs": True}]},
    "有无联合体协议是布尔事实；联合体投标时才适用",
    "联合体协议书")

add("GW-HB-FJ-024", "EXTRACT_DET",
    ["bid.bidder_name", "tender.affiliate_org_names"],
    {"op": "not_in", "lhs": "normalize(bid.bidder_name)", "rhs": "normalize_list(tender.affiliate_org_names)"},
    "需招标人提供附属机构名单才可判；名单为空则 UNCERTAIN",
    "营业执照 / 招标人关联单位清单")

add("GW-HB-FJ-025", "EXTERNAL",
    ["bid.liquidation_or_bankrupt"], None,
    "清算/破产状态在司法与工商登记系统",
    "破产裁定书 / 清算公告",
    external="全国企业破产重整案件信息网 / 工商登记")

add("GW-HB-FJ-026", "EXTERNAL",
    ["bid.credit_serious_illegal"], None,
    "严重违法失信名单只能从公示系统实时查",
    "国家企业信用信息公示系统截图",
    external="国家企业信用信息公示系统")

add("GW-HB-FJ-027", "EXTERNAL",
    ["bid.credit_china_dishonest"], None,
    "失信被执行人名单只能从信用中国实时查",
    "信用中国查询截图",
    external="信用中国 www.creditchina.gov.cn")

add("GW-HB-FJ-028", "EXTERNAL",
    ["bid.bribery_record_3y"], None,
    "行贿犯罪记录在司法系统",
    "行贿犯罪档案查询结果",
    external="检察机关行贿犯罪档案查询")

add("GW-HB-FJ-029", "EXTERNAL",
    ["bid.supplier_bad_behavior"], None,
    "国网供应商关系管理内部数据，不在招标文件内",
    "供应商不良行为处理记录",
    external="国网供应商关系管理系统")

add("GW-HB-FJ-030", "EXTRACT_DET",
    ["bid.qualification_fields", "tender.special_qualification_requirements"],
    {"op": "all_satisfy", "lhs": "bid.qualification_fields", "rhs": "tender.special_qualification_requirements"},
    "专用资格要求可结构化（资质等级、业绩数量、注册资本），逐条比对可判",
    "招标公告专用资格要求 / 投标人资格证明文件")

add("GW-HB-FJ-031", "EXTRACT_DET",
    ["bid.qualification_fields", "tender.other_qualification_requirements"],
    {"op": "all_satisfy", "lhs": "bid.qualification_fields", "rhs": "tender.other_qualification_requirements"},
    "同上，取决于招标公告条款能否结构化",
    "招标公告其他资格要求 / 投标人资格证明文件")

add("GW-HB-FJ-032", "DET",
    ["bid.manufacturer_name", "bid.brand_model", "bid.agent_of"],
    {"op": "and", "args": [
        {"op": "group_dup_le", "lhs": "bid.agent_of", "rhs": 1},
        {"op": "group_no_overlap", "lhs": "bid.manufacturer_name", "rhs": "bid.agent_of"}]},
    "同标包内按制造商+品牌型号分组计数，纯集合运算",
    "制造商授权书 / 投标人资格文件")

add("GW-HB-FJ-033", "HUMAN",
    ["bid.factory_capacity_evidence"], None,
    "「是否具有生产能力」需现场核查与专业判断",
    "资质能力核实报告 / 生产场地与设备证明",
    gate="核查结论由招标人组织的核实工作组出具")

add("GW-HB-FJ-034", "HUMAN", [], None,
    "「利害关系且可能影响公正性」是关系判断，无确定判据",
    "投标人关联关系声明 / 评标委员会回避记录",
    gate="由招标人认定")

add("GW-HB-FJ-035", "DET",
    ["bid.bidder_name", "tender.agent_construction_unit"],
    {"op": "ne", "lhs": "normalize(bid.bidder_name)", "rhs": "normalize(tender.agent_construction_unit)"},
    "代建人是确定主体，名称比对即可",
    "招标公告 / 营业执照")

add("GW-HB-FJ-036", "DET",
    ["bid.bidder_name", "tender.tender_agency"],
    {"op": "ne", "lhs": "normalize(bid.bidder_name)", "rhs": "normalize(tender.tender_agency)"},
    "代理机构是确定主体，名称比对即可",
    "招标公告 / 营业执照")

add("GW-HB-FJ-037", "DET",
    ["bid.legal_rep_name", "tender.supervisor_legal_rep", "tender.agency_legal_rep",
     "tender.agent_construction_legal_rep"],
    {"op": "and", "args": [
        {"op": "ne", "lhs": "normalize(bid.legal_rep_name)", "rhs": "normalize(tender.supervisor_legal_rep)"},
        {"op": "ne", "lhs": "normalize(bid.legal_rep_name)", "rhs": "normalize(tender.agency_legal_rep)"},
        {"op": "ne", "lhs": "normalize(bid.legal_rep_name)", "rhs": "normalize(tender.agent_construction_legal_rep)"}]},
    "法定代表人姓名是可比对字符串",
    "营业执照 / 招标公告")

add("GW-HB-FJ-038", "DET",
    ["bid.bidder_name", "bid.license_name", "bid.qualification_cert_name",
     "bid.name_change_proof_present"],
    {"op": "or", "args": [
        {"op": "and", "args": [
            {"op": "eq", "lhs": "normalize(bid.bidder_name)", "rhs": "normalize(bid.license_name)"},
            {"op": "eq", "lhs": "normalize(bid.bidder_name)", "rhs": "normalize(bid.qualification_cert_name)"}]},
        {"op": "eq", "lhs": "bid.name_change_proof_present", "rhs": True}]},
    "名称归一化后比对，纯字符串运算",
    "营业执照 / 资质证书 / 生产许可证 / 名称变更证明")

add("GW-HB-FJ-039", "DET",
    ["bid.legal_rep_name"],
    {"op": "group_dup_le", "lhs": "bid.legal_rep_name", "rhs": 1},
    "同标包内按法定代表人分组计数，纯集合运算",
    "各投标人营业执照")

add("GW-HB-FJ-040", "EXTERNAL",
    ["bid.equity_relation"], None,
    "控股/管理关系要靠工商股权穿透数据",
    "企业信用信息公示系统股权结构",
    external="国家企业信用信息公示系统")

add("GW-HB-FJ-041", "EXTERNAL",
    ["bid.penalty_status"], None,
    "停产停业、吊销、冻结均为行政机关状态记录",
    "行政处罚决定书 / 执行裁定",
    external="信用中国 / 中国执行信息公开网")

add("GW-HB-FJ-042", "DET",
    ["bid.is_agent", "bid.manufacturer_authorization_present",
     "bid.manufacturer_authorization_valid_until", "tender.required_validity_days"],
    {"op": "or", "args": [
        {"op": "eq", "lhs": "bid.is_agent", "rhs": False},
        {"op": "and", "args": [
            {"op": "eq", "lhs": "bid.manufacturer_authorization_present", "rhs": True},
            {"op": "ge", "lhs": "days_until(bid.manufacturer_authorization_valid_until, tender.bid_open_date)",
             "rhs": "tender.required_validity_days"}]}]},
    "是否代理、授权书有无、授权有效期是否覆盖投标有效期，三项均可判",
    "制造商授权书 / 投标人资格声明")

add("GW-HB-FJ-043", "HUMAN", [], None,
    "「实质性要求」的界定本身需要评标委员会解释",
    "评标办法 / 投标文件",
    gate="只能由评标委员会认定")

add("GW-HB-FJ-044", "EXTERNAL",
    ["bid.equity_relation_with_agency"], None,
    "控股/参股关系需工商股权数据",
    "股权结构证明",
    external="国家企业信用信息公示系统")

add("GW-HB-FJ-045", "OUT_OF_SCOPE", [], None,
    "兜底条款，指向招标文件其他章节，无法预先穷举",
    "招标文件其他否决条款",
    gate="逐项由评标委员会对照招标文件认定")

add("GW-HB-FJ-046", "DET",
    ["bid.price_total", "tender.avg_price_threshold_rule"],
    {"op": "le", "lhs": "bid.price_total", "rhs": "eval_threshold(tender.avg_price_threshold_rule, peer.price_avg)"},
    "「超过本包报价平均值规定值」是统计量比较，规定值需从招标文件参数化抽出",
    "招标文件评标办法 / 开标一览表")


def main():
    src = json.load(io.open(RULES_PATH, encoding="utf-8"))
    rules = src["rules"]
    assert len(rules) == 46, len(rules)

    rows = []
    for r in rules:
        rid = r["rule_id"]
        assert rid in D, "未分派: " + rid
        d = D[rid]
        rows.append({
            "rule_id": rid,
            "row": r["row"],
            "category": r["category"],
            "subcategory": r["subcategory"],
            "rule_text": r["rule_text"],
            "source": r.get("source", ""),
            "exec_path": d["exec_path"],
            "needs": d["needs"],
            "check": d["check"],
            "human_gate": d["gate"],
            "signals": d["signals"],
            "external_source": d["external"],
            "evidence": d["evidence"],
            "why_this_path": d["why"],
            # 机器路径的结论上限恒为 CANDIDATE；人工/外部/超范围恒为 NEED_HUMAN
            "conclusion_ceiling": "CANDIDATE" if d["exec_path"] in ("DET", "EXTRACT_DET") else "NEED_HUMAN",
            "states": ({"pass": "RESPONDED", "fail": "NOT_RESPONDED", "missing": "UNCERTAIN"}
                       if d["exec_path"] in ("DET", "EXTRACT_DET")
                       else {"always": "NEED_HUMAN"}),
        })
    assert len(rows) == 46
    assert len(D) == 46, len(D)

    # 分派统计
    from collections import Counter
    c = Counter(r["exec_path"] for r in rows)
    machine = c["DET"] + c["EXTRACT_DET"]
    out = {
        "meta": {
            "title": "国网湖北 46 条否决情形 · 可执行化分派表 V1",
            "generated_from": RULES_PATH,
            "total": 46,
            "dispatch": dict(c),
            "machine_decidable": machine,
            "machine_ratio": round(machine / 46, 4),
            "note": ("判定执行器只做字段比较，不做语义裁量。"
                     "机器路径的结论上限恒为 CANDIDATE（候选），不构成否决结论；"
                     "缺证一律 UNCERTAIN 并转澄清，不得降级为 NOT_RESPONDED。"),
            "dsl_ops": ["and", "or", "eq", "ne", "gt", "ge", "lt", "le", "in", "not_in",
                        "group_dup_le", "group_no_overlap",
                        "all_satisfy", "all_within_tolerance"],
            "dsl_funcs": ["normalize", "normalize_list", "floor_yuan", "round2",
                          "ratio", "mul", "days_until", "eval_threshold"],
            "dsl_total_ops": 14,
            "dsl_total_funcs": 8,
            "semantics": "check 表达式表示「未触发否决」即合规；True=RESPONDED，False=NOT_RESPONDED，缺证=UNCERTAIN",
        },
        "rules": rows,
    }
    io.open(OUT_JSON, "w", encoding="utf-8").write(
        json.dumps(out, ensure_ascii=False, indent=1))

    with io.open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["行号", "规则号", "评审阶段", "子类", "执行路径", "所需字段数",
                    "结论上限", "人工闸门", "证据位置", "规则原文摘要"])
        for r in rows:
            w.writerow([r["row"], r["rule_id"], r["category"], r["subcategory"],
                        r["exec_path"], len(r["needs"]), r["conclusion_ceiling"],
                        r["human_gate"] or "", r["evidence"],
                        r["rule_text"][:90].replace("\n", " ")])

    print("wrote", OUT_JSON, OUT_CSV)
    print("dispatch:", dict(c))
    print("machine_decidable: %d/46 = %.1f%%" % (machine, machine / 46 * 100))
    need_fields = sum(len(r["needs"]) for r in rows)
    print("distinct fields needed:", len({f for r in rows for f in r["needs"]}))


if __name__ == "__main__":
    main()
