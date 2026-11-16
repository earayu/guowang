"""46 条否决情形的判定执行器（受限 DSL）。

输入一个标包的基准参数与若干投标人字段，输出逐条四态结论。
只做字段比较，不做语义裁量；结论上限恒为 CANDIDATE。
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from apemind_fn import Context

MISSING = object()

STATE_PASS = "RESPONDED"
STATE_FAIL = "NOT_RESPONDED"
STATE_UNK = "UNCERTAIN"
STATE_HUMAN = "NEED_HUMAN"

# 规则表内嵌：平台只部署 main.py 与 function.json，旁挂文件不会被打包。
# 改规则 = 改这段 + function apply（有 history / rollback 可回退）。
RULES_JSON = r"""{
 "meta": {
  "title": "国网湖北 46 条否决情形 · 可执行化分派表 V1",
  "generated_from": "国网Demo_专家评审规则库_V1.json",
  "total": 46,
  "dispatch": {
   "EXTRACT_DET": 8,
   "DET": 17,
   "HUMAN": 10,
   "OUT_OF_SCOPE": 2,
   "EXTERNAL": 9
  },
  "machine_decidable": 25,
  "machine_ratio": 0.5435,
  "note": "判定执行器只做字段比较，不做语义裁量。机器路径的结论上限恒为 CANDIDATE（候选），不构成否决结论；缺证一律 UNCERTAIN 并转澄清，不得降级为 NOT_RESPONDED。",
  "dsl_ops": [
   "and",
   "or",
   "eq",
   "ne",
   "gt",
   "ge",
   "lt",
   "le",
   "in",
   "not_in",
   "group_dup_le",
   "group_no_overlap",
   "all_satisfy",
   "all_within_tolerance"
  ],
  "dsl_funcs": [
   "normalize",
   "normalize_list",
   "floor_yuan",
   "round2",
   "ratio",
   "mul",
   "days_until",
   "eval_threshold"
  ],
  "dsl_total_ops": 14,
  "dsl_total_funcs": 8,
  "semantics": "check 表达式表示「未触发否决」即合规；True=RESPONDED，False=NOT_RESPONDED，缺证=UNCERTAIN"
 },
 "rules": [
  {
   "rule_id": "GW-HB-FJ-001",
   "row": 1,
   "category": "形式评审",
   "subcategory": "格式内容",
   "rule_text": "投标文件未按招标文件规定的格式填写，内容不全或者关键字迹模糊无法辨认的。未按招标文件要求在招标人招投标交易平台信息系统制作并上传凭证单，或因投标人删除了系统文件导致凭证单索引的核实信息无法查看的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTRACT_DET",
   "needs": [
    "bid.voucher_index_viewable",
    "bid.format_completeness"
   ],
   "check": {
    "op": "and",
    "args": [
     {
      "op": "eq",
      "lhs": "bid.voucher_index_viewable",
      "rhs": true
     },
     {
      "op": "eq",
      "lhs": "bid.format_completeness",
      "rhs": "complete"
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "招投标交易平台凭证单 / 投标文件各分册首页",
   "why_this_path": "凭证单可查看是布尔事实（可判）；「内容不全/字迹模糊」需读文件，交抽取给三态",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-002",
   "row": 2,
   "category": "形式评审",
   "subcategory": "格式内容",
   "rule_text": "投标人递交两份或多份内容不同的投标文件，或在一份投标文件中对同一招标内容报有两个或多个报价，按招标文件规定提交备选投标方案的除外。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.file_count_with_diff_content",
    "bid.distinct_price_count",
    "bid.alternative_declared"
   ],
   "check": {
    "op": "and",
    "args": [
     {
      "op": "le",
      "lhs": "bid.file_count_with_diff_content",
      "rhs": 1
     },
     {
      "op": "or",
      "args": [
       {
        "op": "le",
        "lhs": "bid.distinct_price_count",
        "rhs": 1
       },
       {
        "op": "eq",
        "lhs": "bid.alternative_declared",
        "rhs": true
       }
      ]
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "投标文件封面/目录、开标一览表、投标函",
   "why_this_path": "文件份数、报价个数、是否声明备选方案都是可计数量",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-003",
   "row": 3,
   "category": "形式评审",
   "subcategory": "文件签署",
   "rule_text": "对格式文件进行实质性修改或未按格式进行签署的，如由委托代理人签字的，未附有效的法定代表人（单位负责人）授权委托书的（未提交法定代表人（单位负责人）授权委托书，或法定代表人（单位负责人）授权委托书未经投标单位盖章或法定代表人（单位负责人）签名（或签章）的）；使用投标专用章未附有效的投标专用章与公章具有同等效力说明的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTRACT_DET",
   "needs": [
    "bid.authorization_letter_present",
    "bid.authorization_letter_elements_ok",
    "bid.legal_rep_seal_present"
   ],
   "check": {
    "op": "and",
    "args": [
     {
      "op": "eq",
      "lhs": "bid.authorization_letter_present",
      "rhs": true
     },
     {
      "op": "eq",
      "lhs": "bid.authorization_letter_elements_ok",
      "rhs": true
     },
     {
      "op": "eq",
      "lhs": "bid.legal_rep_seal_present",
      "rhs": true
     }
    ]
   },
   "human_gate": "对格式文件是否构成实质性修改，由评标委员会认定",
   "signals": null,
   "external_source": null,
   "evidence": "法定代表人授权委托书 / 格式文件签署页",
   "why_this_path": "「未附授权书」「要素不全」可查；「对格式文件实质性修改」是裁量，另挂人工闸门",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-004",
   "row": 4,
   "category": "形式评审",
   "subcategory": "文件签署",
   "rule_text": "上传招标人招投标交易平台信息系统的电子投标文件无电子签章，或者电子签章无效的，或者电子签章名称与投标人不是同一人的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.seal_present",
    "bid.seal_valid",
    "bid.seal_name"
   ],
   "check": {
    "op": "and",
    "args": [
     {
      "op": "eq",
      "lhs": "bid.seal_present",
      "rhs": true
     },
     {
      "op": "eq",
      "lhs": "bid.seal_valid",
      "rhs": true
     },
     {
      "op": "eq",
      "lhs": "normalize(bid.seal_name)",
      "rhs": "normalize(bid.bidder_name)"
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "电子投标文件签章页",
   "why_this_path": "签章有无、有效性、名称一致都是可比对事实",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-005",
   "row": 5,
   "category": "响应性评审",
   "subcategory": "澄清修改",
   "rule_text": "提交投标文件截止时间后主动撤销投标文件或对投标文件提出实质性修改的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.withdrawn_after_deadline"
   ],
   "check": {
    "op": "eq",
    "lhs": "bid.withdrawn_after_deadline",
    "rhs": false
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "招投标交易平台操作日志",
   "why_this_path": "截止时间后是否撤回由平台日志直接给出布尔值，抽取环节负责把时间戳换算成该布尔",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-006",
   "row": 6,
   "category": "响应性评审",
   "subcategory": "澄清修改",
   "rule_text": "不按评标委员会要求对投标文件进行澄清、说明或补正的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [],
   "check": null,
   "human_gate": "澄清是否已被要求、是否回应，由评标委员会记录",
   "signals": null,
   "external_source": null,
   "evidence": "评标委员会澄清通知 / 投标人澄清回函",
   "why_this_path": "「不按要求澄清」要看评标委员会澄清通知与投标人回函，是过程事实而非文件属性",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-007",
   "row": 7,
   "category": "响应性评审",
   "subcategory": "交付期限",
   "rule_text": "投标文件所承诺的交货期不满足招标文件要求的，且招标人不能接受的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTRACT_DET",
   "needs": [
    "bid.delivery_days",
    "tender.required_delivery_days"
   ],
   "check": {
    "op": "le",
    "lhs": "bid.delivery_days",
    "rhs": "tender.required_delivery_days"
   },
   "human_gate": "交货期不满足时，是否接受由招标人决定，系统只报「不满足」",
   "signals": null,
   "external_source": null,
   "evidence": "投标函 / 商务偏差表",
   "why_this_path": "交货期是数字可直比；「招标人不能接受」是第二段，必须另交人",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-008",
   "row": 8,
   "category": "响应性评审",
   "subcategory": "投标报价",
   "rule_text": "投标人不接受评标委员会依法所作的修正价格的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [],
   "check": null,
   "human_gate": "接受与否由评标委员会现场确认",
   "signals": null,
   "external_source": null,
   "evidence": "评标委员会价格修正记录 / 投标人确认",
   "why_this_path": "是否「接受」修正价是投标人的意思表示，只能由评标过程记录证明",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-009",
   "row": 9,
   "category": "响应性评审",
   "subcategory": "投标报价",
   "rule_text": "报价明显低于其他投标报价，且投标人不能合理说明或者提供相关证明材料，评标委员会认定该投标人以低于成本报价竞标的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [
    "bid.price_total",
    "peer.price_avg"
   ],
   "check": null,
   "human_gate": "是否低于成本由评标委员会认定",
   "signals": [
    "bid.price_total / peer.price_avg >= 0.8 时不提示",
    "0.5~0.8 提示「显著偏低，建议要求说明」",
    "<0.5 提示「严重偏离，建议重点核查」"
   ],
   "external_source": null,
   "evidence": "开标一览表 / 报价说明 / 成本证明材料",
   "why_this_path": "「明显低于」「不能合理说明」「低于成本」三重裁量；系统可给偏离信号但不作判定",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-010",
   "row": 10,
   "category": "响应性评审",
   "subcategory": "投标报价",
   "rule_text": "招标文件中明确规定了最高限价（包括具体金额、计算方式），投标人的投标价格剔除角和分（单价限价不剔除）的数值后超过最高限价的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.price_total_ex_tax",
    "tender.price_cap"
   ],
   "check": {
    "op": "le",
    "lhs": "floor_yuan(bid.price_total_ex_tax)",
    "rhs": "tender.price_cap"
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "开标一览表 / 投标函价格表 / 招标文件最高限价条款",
   "why_this_path": "最高限价是确定数值，剔除角分后直比，零裁量",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-011",
   "row": 11,
   "category": "响应性评审",
   "subcategory": "投标报价",
   "rule_text": "投标报价构成招标文件规定为无效报价的；开标一览表中显示为非报价数值的。投标报价小数点错误导致单价总价都出现明显错误的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.price_numeric",
    "bid.qty",
    "bid.unit_price",
    "bid.price_total"
   ],
   "check": {
    "op": "and",
    "args": [
     {
      "op": "eq",
      "lhs": "bid.price_numeric",
      "rhs": true
     },
     {
      "op": "eq",
      "lhs": "round2(mul(bid.qty, bid.unit_price))",
      "rhs": "round2(bid.price_total)"
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "开标一览表 / 分项报价表",
   "why_this_path": "算术校验是纯计算，单价×数量≠总价即异常",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-012",
   "row": 12,
   "category": "响应性评审",
   "subcategory": "投标报价",
   "rule_text": "投标价格出现数值与货币单位不对应，即出现了明显的百倍至万倍高于正常水平的报价（如把“投标函价格表”中的“万元”当成“元”进行报价）。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.price_unit_ratio_to_ref"
   ],
   "check": {
    "op": "lt",
    "lhs": "bid.price_unit_ratio_to_ref",
    "rhs": 100
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "投标函价格表 / 同标包其他投标人报价",
   "why_this_path": "百倍至万倍是区间比较；比值由抽取环节对同品类参考价求得，判定只做一次区间判断",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-013",
   "row": 13,
   "category": "响应性评审",
   "subcategory": "投标担保",
   "rule_text": "未按招标文件要求提交投标保证金的；以银行汇款形式提供的投标保证金未提供从投标人基本账户转出有效证明的（未提供有效证明是指未提供企业银行基本账户开户许可证复印件，也未提供投标人基本账户开户行通过账户管理系统打印的《基本存款账户信息》扫描件）；以投标保证保险形式提交的投标保证金，保单保费未从投标人基本账户转出或保单未体现保费是否由投标人基本账户支付的相关信息或未提供保单查询途径或提供的查询途径招标人无法查询的；以银行保函、投标保证保险形式提交的投标保证金不满足招标文件要求的（如对上述格式文件进行实质性修改或未按格式进行签署）。**（本批不适用）**",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTRACT_DET",
   "needs": [
    "bid.bond_amount",
    "tender.bond_required",
    "bid.bond_form",
    "bid.bond_basic_account_proof"
   ],
   "check": {
    "op": "and",
    "args": [
     {
      "op": "ge",
      "lhs": "bid.bond_amount",
      "rhs": "tender.bond_required"
     },
     {
      "op": "in",
      "lhs": "bid.bond_form",
      "rhs": [
       "bank_transfer",
       "bank_guarantee",
       "insurance",
       "letter"
      ]
     },
     {
      "op": "or",
      "args": [
       {
        "op": "ne",
        "lhs": "bid.bond_form",
        "rhs": "bank_transfer"
       },
       {
        "op": "eq",
        "lhs": "bid.bond_basic_account_proof",
        "rhs": true
       }
      ]
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "投标保证金缴纳凭证 / 基本账户开户许可证 / 保函",
   "why_this_path": "金额、形式、基本账户证明三项都是可核事实",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-014",
   "row": 14,
   "category": "响应性评审",
   "subcategory": "投标范围",
   "rule_text": "投标范围与招标文件要求存在偏差的，且招标人不能接受的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [],
   "check": null,
   "human_gate": "偏差是否可接受由招标人认定",
   "signals": null,
   "external_source": null,
   "evidence": "投标函 / 供货范围表 / 招标范围条款",
   "why_this_path": "「投标范围偏差」需与招标范围逐项对照后判断是否可接受",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-015",
   "row": 15,
   "category": "响应性评审",
   "subcategory": "投标偏差",
   "rule_text": "投标人提出招标人不能接受的条件或偏差的；未按要求填写具体数据信息以及填写的数据信息不满足招标文件规定的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [],
   "check": null,
   "human_gate": "由评标委员会逐条认定",
   "signals": null,
   "external_source": null,
   "evidence": "商务/技术偏差表",
   "why_this_path": "「不能接受的条件或偏差」与「数据信息不满足规定」均需业务裁量",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-016",
   "row": 16,
   "category": "响应性评审",
   "subcategory": "投标期限",
   "rule_text": "投标有效期不满足招标文件要求的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.validity_days",
    "tender.required_validity_days"
   ],
   "check": {
    "op": "ge",
    "lhs": "bid.validity_days",
    "rhs": "tender.required_validity_days"
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "投标函 / 招标文件投标人须知前附表",
   "why_this_path": "投标有效期是天数，可直接比",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-017",
   "row": 17,
   "category": "响应性评审",
   "subcategory": "税率错误",
   "rule_text": "不按国家法律法规规定填报增值税税率或征收率的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.tax_rate",
    "legal.tax_rate_set"
   ],
   "check": {
    "op": "in",
    "lhs": "bid.tax_rate",
    "rhs": "legal.tax_rate_set"
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "开标一览表 / 分项报价表 / 增值税税率栏",
   "why_this_path": "法定税率为有限枚举集合，可判",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-018",
   "row": 18,
   "category": "资格评审",
   "subcategory": "法定否决",
   "rule_text": "投标文件响应与事实不符或虚假投标的（虚假投标包括但不限于投标人在其投标文件中提供虚假的资格证明文件、业绩证明文件、验收报告、故意修改招标文件明确列明的技术要求并对其进行响应等），该投标人参与本次投标的所有标包将均被否决，且该投标人在今后一段时间内参与国家电网有限公司及其所属单位招标活动的任何投标也将被否决。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [
    "bid.performance_dates",
    "bid.invoice_numbers"
   ],
   "check": null,
   "human_gate": "是否构成虚假投标由评标委员会认定并可追溯法律责任",
   "signals": [
    "业绩合同签订日期晚于验收报告日期",
    "同一发票号在不同业绩中重复出现",
    "业绩金额与合同金额不一致"
   ],
   "external_source": null,
   "evidence": "资格证明文件 / 业绩合同 / 验收报告 / 发票",
   "why_this_path": "「虚假」需与外部事实核验；系统只能给内部一致性冲突信号",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-019",
   "row": 19,
   "category": "资格评审",
   "subcategory": "法定否决",
   "rule_text": "串通投标或视为串通投标或根据投诉举报经核实认定为串通投标或联合围标或有其他违法行为的，该投标人参与本次招标活动的所有标包将均被否决。同时招标人将依据《国家电网有限公司供应商关系管理办法》规定进行后续处理。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [
    "bid.ip",
    "bid.mac",
    "bid.file_author",
    "bid.contact_phone",
    "bid.price_pattern"
   ],
   "check": null,
   "human_gate": "串通投标认定权在评标委员会及行政监督部门",
   "signals": [
    "同一标包内两家投标人 IP 相同",
    "投标文件创建者/最后修改者相同",
    "联系人电话或邮箱相同",
    "报价呈规律性等差/等比"
   ],
   "external_source": null,
   "evidence": "平台递交日志 / 投标文件属性 / 报价序列",
   "why_this_path": "串通认定是法律判断；系统只做同源信号聚类，不作结论",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-020",
   "row": 20,
   "category": "资格评审",
   "subcategory": "法定否决",
   "rule_text": "《中华人民共和国招标投标法》、《中华人民共和国招标投标法实施条例》、《评标委员会和评标方法暂行规定》等法律法规规章规定的其他否决情形。（注：所引法律法规原文不在知识库内，无法回读其具体内容）",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "OUT_OF_SCOPE",
   "needs": [],
   "check": null,
   "human_gate": "只能由评标委员会依法认定",
   "signals": null,
   "external_source": null,
   "evidence": "法律法规原文（库外）",
   "why_this_path": "援引外部法律法规的兜底条款，原文不在知识库内，系统无权代为解释",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-021",
   "row": 21,
   "category": "形式评审",
   "subcategory": "参数接口",
   "rule_text": "投标文件主要技术参数或产品型式不满足招标文件要求的；投标文件一般技术参数超出允许偏差的最大范围的；对于规定接口要求的产品，投标文件对一次接口、二次接口、土建接口的响应与招标文件不符的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTRACT_DET",
   "needs": [
    "bid.tech_params",
    "tender.tech_params_mandatory",
    "tender.tech_param_tolerance"
   ],
   "check": {
    "op": "and",
    "args": [
     {
      "op": "all_satisfy",
      "lhs": "bid.tech_params",
      "rhs": "tender.tech_params_mandatory"
     },
     {
      "op": "all_within_tolerance",
      "lhs": "bid.tech_params",
      "rhs": "tender.tech_param_tolerance"
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "技术规范书参数表 / 投标技术响应表",
   "why_this_path": "参数表一旦结构化，逐项比对是纯计算；前提是招标文件参数表已结构化（当前 0 项）",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-022",
   "row": 22,
   "category": "资格评审",
   "subcategory": "质量否决",
   "rule_text": "本次投标截止日前三年内发生重大质量问题（以相关行业主管部门的行政处罚决定或司法机关出具的有关法律文书为准）。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTERNAL",
   "needs": [
    "bid.major_quality_incident_3y"
   ],
   "check": null,
   "human_gate": null,
   "signals": null,
   "external_source": "国家企业信用信息公示系统 / 信用中国 行政处罚栏",
   "evidence": "行业主管部门处罚决定 / 司法文书",
   "why_this_path": "依据是行政处罚决定或司法文书，须外部数据源",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-023",
   "row": 23,
   "category": "资格评审",
   "subcategory": "资格不符",
   "rule_text": "未提供符合招标文件要求的联合体协议书的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.is_consortium",
    "bid.consortium_agreement_present"
   ],
   "check": {
    "op": "or",
    "args": [
     {
      "op": "eq",
      "lhs": "bid.is_consortium",
      "rhs": false
     },
     {
      "op": "eq",
      "lhs": "bid.consortium_agreement_present",
      "rhs": true
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "联合体协议书",
   "why_this_path": "有无联合体协议是布尔事实；联合体投标时才适用",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-024",
   "row": 24,
   "category": "资格评审",
   "subcategory": "主体不符",
   "rule_text": "为招标人不具有独立法人资格的附属机构（单位）。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTRACT_DET",
   "needs": [
    "bid.bidder_name",
    "tender.affiliate_org_names"
   ],
   "check": {
    "op": "not_in",
    "lhs": "normalize(bid.bidder_name)",
    "rhs": "normalize_list(tender.affiliate_org_names)"
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "营业执照 / 招标人关联单位清单",
   "why_this_path": "需招标人提供附属机构名单才可判；名单为空则 UNCERTAIN",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-025",
   "row": 25,
   "category": "资格评审",
   "subcategory": "丧失履约能力",
   "rule_text": "进入清算程序，或被宣告破产，或其他丧失履约能力的情形。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTERNAL",
   "needs": [
    "bid.liquidation_or_bankrupt"
   ],
   "check": null,
   "human_gate": null,
   "signals": null,
   "external_source": "全国企业破产重整案件信息网 / 工商登记",
   "evidence": "破产裁定书 / 清算公告",
   "why_this_path": "清算/破产状态在司法与工商登记系统",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-026",
   "row": 26,
   "category": "资格评审",
   "subcategory": "失信惩戒",
   "rule_text": "被市场监督管理机关在国家企业信用信息公示系统中列入严重违法失信企业名单或列入经营异常名录信息的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTERNAL",
   "needs": [
    "bid.credit_serious_illegal"
   ],
   "check": null,
   "human_gate": null,
   "signals": null,
   "external_source": "国家企业信用信息公示系统",
   "evidence": "国家企业信用信息公示系统截图",
   "why_this_path": "严重违法失信名单只能从公示系统实时查",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-027",
   "row": 27,
   "category": "资格评审",
   "subcategory": "失信惩戒",
   "rule_text": "被最高人民法院在“信用中国”网站（www.creditchina.gov.cn）中列入严重失信主体名单或列入失信被执行人。（以评标委员会在“信用中国”网站（www.creditchina.gov.cn）查询结果为准）。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTERNAL",
   "needs": [
    "bid.credit_china_dishonest"
   ],
   "check": null,
   "human_gate": null,
   "signals": null,
   "external_source": "信用中国 www.creditchina.gov.cn",
   "evidence": "信用中国查询截图",
   "why_this_path": "失信被执行人名单只能从信用中国实时查",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-028",
   "row": 28,
   "category": "资格评审",
   "subcategory": "行贿记录",
   "rule_text": "投标单位或法定代表人（单位负责人）在投标截止日前三年内存在行贿犯罪记录的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTERNAL",
   "needs": [
    "bid.bribery_record_3y"
   ],
   "check": null,
   "human_gate": null,
   "signals": null,
   "external_source": "检察机关行贿犯罪档案查询",
   "evidence": "行贿犯罪档案查询结果",
   "why_this_path": "行贿犯罪记录在司法系统",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-029",
   "row": 29,
   "category": "资格评审",
   "subcategory": "不良行为",
   "rule_text": "根据《国家电网有限公司供应商关系管理办法》的规定，若投标人为制造商，存在导致其被暂停中标资格或取消中标资格的不良行为且在处理有效期内的，或投标人存在触发《国家电网有限公司供应商关系管理办法》第六十三条安全及质量重大问题“熔断机制”情形的。若投标人为代理商，投标人或其代理产品的制造商存在导致其被暂停中标资格或取消中标资格的不良行为且在处理有效期内的，或投标人存在触发《国家电网有限公司供应商关系管理办法》第六十三条安全及质量重大问题“熔断机制”情形的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTERNAL",
   "needs": [
    "bid.supplier_bad_behavior"
   ],
   "check": null,
   "human_gate": null,
   "signals": null,
   "external_source": "国网供应商关系管理系统",
   "evidence": "供应商不良行为处理记录",
   "why_this_path": "国网供应商关系管理内部数据，不在招标文件内",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-030",
   "row": 30,
   "category": "资格评审",
   "subcategory": "资格不符",
   "rule_text": "不满足本次招标公告要求的投标人专用资格要求的",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTRACT_DET",
   "needs": [
    "bid.qualification_fields",
    "tender.special_qualification_requirements"
   ],
   "check": {
    "op": "all_satisfy",
    "lhs": "bid.qualification_fields",
    "rhs": "tender.special_qualification_requirements"
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "招标公告专用资格要求 / 投标人资格证明文件",
   "why_this_path": "专用资格要求可结构化（资质等级、业绩数量、注册资本），逐条比对可判",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-031",
   "row": 31,
   "category": "资格评审",
   "subcategory": "资格不符",
   "rule_text": "不满足本次招标公告要求的投标人其他资格要求的",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTRACT_DET",
   "needs": [
    "bid.qualification_fields",
    "tender.other_qualification_requirements"
   ],
   "check": {
    "op": "all_satisfy",
    "lhs": "bid.qualification_fields",
    "rhs": "tender.other_qualification_requirements"
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "招标公告其他资格要求 / 投标人资格证明文件",
   "why_this_path": "同上，取决于招标公告条款能否结构化",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-032",
   "row": 32,
   "category": "资格评审",
   "subcategory": "主体不符",
   "rule_text": "对于接受代理商投标的项目，一个制造商对同一品牌同一型号的货物委托两个及以上代理商参加同一标包投标的；制造商与其授权委托代理商参加同一标包投标的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.manufacturer_name",
    "bid.brand_model",
    "bid.agent_of"
   ],
   "check": {
    "op": "and",
    "args": [
     {
      "op": "group_dup_le",
      "lhs": "bid.agent_of",
      "rhs": 1
     },
     {
      "op": "group_no_overlap",
      "lhs": "bid.manufacturer_name",
      "rhs": "bid.agent_of"
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "制造商授权书 / 投标人资格文件",
   "why_this_path": "同标包内按制造商+品牌型号分组计数，纯集合运算",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-033",
   "row": 33,
   "category": "资格评审",
   "subcategory": "资格不符",
   "rule_text": "招标人有权对厂商进行资质能力核查，如经核查该厂商不具有生产投标产品所需的生产场地、生产设备及工艺控制、生产人员、元器件及产品检测能力等资质能力，或因厂商自身原因造成核查工作无法进行的，将视厂商不具备生产投标产品所需的资质能力，招标人有权否决其投标。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [
    "bid.factory_capacity_evidence"
   ],
   "check": null,
   "human_gate": "核查结论由招标人组织的核实工作组出具",
   "signals": null,
   "external_source": null,
   "evidence": "资质能力核实报告 / 生产场地与设备证明",
   "why_this_path": "「是否具有生产能力」需现场核查与专业判断",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-034",
   "row": 34,
   "category": "资格评审",
   "subcategory": "主体不符",
   "rule_text": "与招标人存在利害关系且可能影响招标公正性。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [],
   "check": null,
   "human_gate": "由招标人认定",
   "signals": null,
   "external_source": null,
   "evidence": "投标人关联关系声明 / 评标委员会回避记录",
   "why_this_path": "「利害关系且可能影响公正性」是关系判断，无确定判据",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-035",
   "row": 35,
   "category": "资格评审",
   "subcategory": "主体不符",
   "rule_text": "为本招标项目的代建人。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.bidder_name",
    "tender.agent_construction_unit"
   ],
   "check": {
    "op": "ne",
    "lhs": "normalize(bid.bidder_name)",
    "rhs": "normalize(tender.agent_construction_unit)"
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "招标公告 / 营业执照",
   "why_this_path": "代建人是确定主体，名称比对即可",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-036",
   "row": 36,
   "category": "资格评审",
   "subcategory": "主体不符",
   "rule_text": "为本招标项目的代理机构。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.bidder_name",
    "tender.tender_agency"
   ],
   "check": {
    "op": "ne",
    "lhs": "normalize(bid.bidder_name)",
    "rhs": "normalize(tender.tender_agency)"
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "招标公告 / 营业执照",
   "why_this_path": "代理机构是确定主体，名称比对即可",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-037",
   "row": 37,
   "category": "资格评审",
   "subcategory": "主体不符",
   "rule_text": "与本招标项目的监理人或代建人或招标代理机构同为一个法定代表人（单位负责人）的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.legal_rep_name",
    "tender.supervisor_legal_rep",
    "tender.agency_legal_rep",
    "tender.agent_construction_legal_rep"
   ],
   "check": {
    "op": "and",
    "args": [
     {
      "op": "ne",
      "lhs": "normalize(bid.legal_rep_name)",
      "rhs": "normalize(tender.supervisor_legal_rep)"
     },
     {
      "op": "ne",
      "lhs": "normalize(bid.legal_rep_name)",
      "rhs": "normalize(tender.agency_legal_rep)"
     },
     {
      "op": "ne",
      "lhs": "normalize(bid.legal_rep_name)",
      "rhs": "normalize(tender.agent_construction_legal_rep)"
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "营业执照 / 招标公告",
   "why_this_path": "法定代表人姓名是可比对字符串",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-038",
   "row": 38,
   "category": "资格评审",
   "subcategory": "资格不符",
   "rule_text": "投标人名称与营业执照（或事业单位法人证书）或资质证书或生产许可证不一致，且未提供相关变更证明。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.bidder_name",
    "bid.license_name",
    "bid.qualification_cert_name",
    "bid.name_change_proof_present"
   ],
   "check": {
    "op": "or",
    "args": [
     {
      "op": "and",
      "args": [
       {
        "op": "eq",
        "lhs": "normalize(bid.bidder_name)",
        "rhs": "normalize(bid.license_name)"
       },
       {
        "op": "eq",
        "lhs": "normalize(bid.bidder_name)",
        "rhs": "normalize(bid.qualification_cert_name)"
       }
      ]
     },
     {
      "op": "eq",
      "lhs": "bid.name_change_proof_present",
      "rhs": true
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "营业执照 / 资质证书 / 生产许可证 / 名称变更证明",
   "why_this_path": "名称归一化后比对，纯字符串运算",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-039",
   "row": 39,
   "category": "资格评审",
   "subcategory": "主体不符",
   "rule_text": "同一标包或者未划分标包的同一招标项目中，与其他投标人的法定代表人（单位负责人）为同一人。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.legal_rep_name"
   ],
   "check": {
    "op": "group_dup_le",
    "lhs": "bid.legal_rep_name",
    "rhs": 1
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "各投标人营业执照",
   "why_this_path": "同标包内按法定代表人分组计数，纯集合运算",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-040",
   "row": 40,
   "category": "资格评审",
   "subcategory": "主体不符",
   "rule_text": "同一标包或者未划分标包的同一招标项目中，与其他投标人存在控股、管理关系。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTERNAL",
   "needs": [
    "bid.equity_relation"
   ],
   "check": null,
   "human_gate": null,
   "signals": null,
   "external_source": "国家企业信用信息公示系统",
   "evidence": "企业信用信息公示系统股权结构",
   "why_this_path": "控股/管理关系要靠工商股权穿透数据",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-041",
   "row": 41,
   "category": "资格评审",
   "subcategory": "资信不良",
   "rule_text": "被责令停产停业、暂扣或者吊销许可证、暂扣或者吊销执照的；被招投标活动政府行政监督部门暂停、取消投标资格的；财产被接管或冻结的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTERNAL",
   "needs": [
    "bid.penalty_status"
   ],
   "check": null,
   "human_gate": null,
   "signals": null,
   "external_source": "信用中国 / 中国执行信息公开网",
   "evidence": "行政处罚决定书 / 执行裁定",
   "why_this_path": "停产停业、吊销、冻结均为行政机关状态记录",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-042",
   "row": 42,
   "category": "资格评审",
   "subcategory": "无效代理",
   "rule_text": "对于代理商投标，未取得投标产品制造商有效授权的。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.is_agent",
    "bid.manufacturer_authorization_present",
    "bid.manufacturer_authorization_valid_until",
    "tender.required_validity_days"
   ],
   "check": {
    "op": "or",
    "args": [
     {
      "op": "eq",
      "lhs": "bid.is_agent",
      "rhs": false
     },
     {
      "op": "and",
      "args": [
       {
        "op": "eq",
        "lhs": "bid.manufacturer_authorization_present",
        "rhs": true
       },
       {
        "op": "ge",
        "lhs": "days_until(bid.manufacturer_authorization_valid_until, tender.bid_open_date)",
        "rhs": "tender.required_validity_days"
       }
      ]
     }
    ]
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "制造商授权书 / 投标人资格声明",
   "why_this_path": "是否代理、授权书有无、授权有效期是否覆盖投标有效期，三项均可判",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-043",
   "row": 43,
   "category": "响应性评审",
   "subcategory": "实质不符",
   "rule_text": "不符合招标文件实质性要求的投标文件。",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "HUMAN",
   "needs": [],
   "check": null,
   "human_gate": "只能由评标委员会认定",
   "signals": null,
   "external_source": null,
   "evidence": "评标办法 / 投标文件",
   "why_this_path": "「实质性要求」的界定本身需要评标委员会解释",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-044",
   "row": 44,
   "category": "资格评审",
   "subcategory": "主体不符",
   "rule_text": "与本招标项目的监理人或代建人或招标代理机构存在控股或参股关系",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "EXTERNAL",
   "needs": [
    "bid.equity_relation_with_agency"
   ],
   "check": null,
   "human_gate": null,
   "signals": null,
   "external_source": "国家企业信用信息公示系统",
   "evidence": "股权结构证明",
   "why_this_path": "控股/参股关系需工商股权数据",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-045",
   "row": 45,
   "category": "其他事项",
   "subcategory": "其他事项",
   "rule_text": "投标人或投标文件符合招标文件中规定否决投标的其他条款的",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "OUT_OF_SCOPE",
   "needs": [],
   "check": null,
   "human_gate": "逐项由评标委员会对照招标文件认定",
   "signals": null,
   "external_source": null,
   "evidence": "招标文件其他否决条款",
   "why_this_path": "兜底条款，指向招标文件其他章节，无法预先穷举",
   "conclusion_ceiling": "NEED_HUMAN",
   "states": {
    "always": "NEED_HUMAN"
   }
  },
  {
   "rule_id": "GW-HB-FJ-046",
   "row": 46,
   "category": "响应性评审",
   "subcategory": "投标报价",
   "rule_text": "152507 及 K1 资格后审：「根据招标文件规定，因投标人投标价格超过本包规定投标人报价平均值规定值的。」；K1 资格预审版：「根据招标文件规定，因投标人投标价格超过本包规定投标人报价平均值规定值的**或不平衡报价的**。」（版本差异见第三部分）",
   "source": "sgcc_l1_results.json → V5 答案（turn turn2b0c5bc86a956549）逐条回读原文",
   "exec_path": "DET",
   "needs": [
    "bid.price_total",
    "tender.avg_price_threshold_rule"
   ],
   "check": {
    "op": "le",
    "lhs": "bid.price_total",
    "rhs": "eval_threshold(tender.avg_price_threshold_rule, peer.price_avg)"
   },
   "human_gate": null,
   "signals": null,
   "external_source": null,
   "evidence": "招标文件评标办法 / 开标一览表",
   "why_this_path": "「超过本包报价平均值规定值」是统计量比较，规定值需从招标文件参数化抽出",
   "conclusion_ceiling": "CANDIDATE",
   "states": {
    "pass": "RESPONDED",
    "fail": "NOT_RESPONDED",
    "missing": "UNCERTAIN"
   }
  }
 ]
}"""


def _rules():
    return json.loads(RULES_JSON)["rules"]


def _norm(v):
    if v is MISSING:
        return MISSING
    s = str(v)
    for a, b in (("（", "("), ("）", ")"), (" ", ""), ("　", ""), ("·", "")):
        s = s.replace(a, b)
    return s.strip().lower()


def _norm_list(v):
    return MISSING if v is MISSING else [_norm(x) for x in v]


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return MISSING


def floor_yuan(v):
    v = _num(v)
    return MISSING if v is MISSING else int(v)


def round2(v):
    v = _num(v)
    return MISSING if v is MISSING else round(v, 2)


def mul(a, b):
    a, b = _num(a), _num(b)
    return MISSING if a is MISSING or b is MISSING else a * b


def ratio(a, b):
    a, b = _num(a), _num(b)
    return MISSING if a is MISSING or b is MISSING or b == 0 else a / b


def days_until(target, base):
    if target is MISSING or base is MISSING:
        return MISSING
    try:
        t = datetime.fromisoformat(str(target)[:10]).date()
        b = datetime.fromisoformat(str(base)[:10]).date()
        return (t - b).days
    except ValueError:
        return MISSING


def eval_threshold(spec, base):
    if spec is MISSING or not isinstance(spec, dict):
        return MISSING
    base = _num(base)
    if base is MISSING:
        return MISSING
    if "mult" in spec:
        return base * float(spec["mult"])
    if "add_pct" in spec:
        return base * (1 + float(spec["add_pct"]) / 100.0)
    return MISSING


FUNCS = {"normalize": _norm, "normalize_list": _norm_list, "floor_yuan": floor_yuan,
         "round2": round2, "mul": mul, "ratio": ratio, "days_until": days_until,
         "eval_threshold": eval_threshold}

CMP = {"eq": lambda a, b: a == b, "ne": lambda a, b: a != b,
       "gt": lambda a, b: _num(a) > _num(b), "ge": lambda a, b: _num(a) >= _num(b),
       "lt": lambda a, b: _num(a) < _num(b), "le": lambda a, b: _num(a) <= _num(b),
       "in": lambda a, b: a in b, "not_in": lambda a, b: a not in b}


class NeedMissing(Exception):
    pass


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


def _operand(spec, ctx, group):
    if not isinstance(spec, str):
        if isinstance(spec, list):
            return [ctx.get(x, x) if isinstance(x, str) else x for x in spec]
        return spec
    if "(" in spec and spec.endswith(")"):
        fn = spec[:spec.index("(")]
        if fn not in FUNCS:
            raise KeyError("算子未在白名单: " + fn)
        args = [_operand(p.strip(), ctx, group) for p in _split_args(spec[spec.index("(") + 1:-1])]
        if any(a is MISSING for a in args):
            raise NeedMissing(fn)
        return FUNCS[fn](*args)
    if spec in ctx:
        v = ctx[spec]
        if v is MISSING:
            raise NeedMissing(spec)
        return v
    if spec.startswith(("bid.", "tender.", "peer.", "legal.")):
        raise NeedMissing(spec)
    return spec


def evaluate(node, ctx, group=None):
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
                return False
            if any(v is None for v in vals):
                raise NeedMissing("and:部分未知")
            return True
        if any(v is True for v in vals):
            return True
        if any(v is None for v in vals):
            raise NeedMissing("or:部分未知")
        return False

    if op == "group_dup_le":
        vals = [g.get(node["lhs"], MISSING) for g in group]
        vals = [v for v in vals if v is not MISSING and v is not None]
        if not vals:
            return True
        counts = {}
        for v in vals:
            counts[_norm(v)] = counts.get(_norm(v), 0) + 1
        return max(counts.values()) <= int(node["rhs"])

    if op == "group_no_overlap":
        a = {_norm(x) for x in (g.get(node["lhs"], MISSING) for g in group)
             if x is not MISSING and x is not None}
        b = {_norm(x) for x in (g.get(node["rhs"], MISSING) for g in group)
             if x is not MISSING and x is not None}
        if not a or not b:
            return True
        return not (a & b)

    if op == "all_satisfy":
        req = _operand(node["rhs"], ctx, group)
        got = _operand(node["lhs"], ctx, group)
        if not req:
            raise NeedMissing("基准未结构化")
        if not got:
            raise NeedMissing("响应未结构化")
        for k, need in req.items():
            if k not in got:
                raise NeedMissing("缺响应项:" + k)
            if str(got[k]) != str(need):
                return False
        return True

    if op == "all_within_tolerance":
        req = _operand(node["rhs"], ctx, group)
        got = _operand(node["lhs"], ctx, group)
        if not req or not got:
            raise NeedMissing("偏差范围或响应未结构化")
        for k, tol in req.items():
            if k not in got:
                raise NeedMissing("缺响应项:" + k)
            v = _num(got[k])
            if v is MISSING:
                raise NeedMissing("非数值:" + k)
            if abs(v) > float(tol):
                return False
        return True

    if op in CMP:
        a = _operand(node["lhs"], ctx, group)
        b = _operand(node["rhs"], ctx, group)
        try:
            return CMP[op](a, b)
        except (TypeError, ValueError):
            raise NeedMissing("%s 类型不可比" % op)

    raise KeyError("算子未在白名单: " + op)


class TenderIn(BaseModel):
    fields: Dict[str, Any] = Field(default_factory=dict, description="基准字段，键以 tender. / legal. 开头")


class BidIn(BaseModel):
    bidder: str = Field(description="投标人名称")
    fields: Dict[str, Any] = Field(default_factory=dict, description="受审字段，键以 bid. 开头")


class Input(BaseModel):
    batch_id: str = Field(description="采购批次号，如 152507")
    tender: TenderIn
    bids: List[BidIn] = Field(description="同一标包的全部投标人")


class RuleResult(BaseModel):
    rule_id: str
    row: int
    category: str
    subcategory: str
    exec_path: str
    state: str
    reason: str
    evidence: str
    used_fields: List[Dict[str, Any]] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    gate: Optional[str] = None
    conclusion_ceiling: str = "CANDIDATE"


class BidResult(BaseModel):
    bidder: str
    rows: List[RuleResult]
    count: Dict[str, int]


class Output(BaseModel):
    batch_id: str
    rules_total: int
    by_bidder: List[BidResult]
    redline_violations: List[str]
    disclaimer: str


DISCLAIMER = ("本表为候选待核事项，不构成违规或投标有效性的终局判定；"
              "依 195 号文辅助性定位，判定权在招标人与评标委员会。")


def _run_rule(rule, ctx, group):
    path = rule["exec_path"]
    base = dict(rule_id=rule["rule_id"], row=rule["row"], category=rule["category"],
                subcategory=rule["subcategory"], exec_path=path, evidence=rule["evidence"])

    if path in ("HUMAN", "EXTERNAL", "OUT_OF_SCOPE"):
        base.update(state=STATE_HUMAN, reason="本路径不作机器判定",
                    gate=rule.get("human_gate") or rule.get("external_source"),
                    used_fields=[], missing_fields=[])
        return base

    used, missing = [], []
    for f in rule["needs"]:
        v = ctx.get(f, MISSING)
        if v is MISSING or v is None:
            missing.append(f)
        else:
            used.append({"field": f, "value": v})

    try:
        ok = evaluate(rule["check"], ctx, group)
        state = STATE_PASS if ok else STATE_FAIL
        reason = "判定式成立" if ok else "判定式不成立"
        if state == STATE_FAIL and missing:
            state, reason = STATE_UNK, "判否但缺字段：" + ",".join(missing)
            missing = []
    except NeedMissing as e:
        state, reason = STATE_UNK, "缺字段或基准未结构化：%s" % e
    except KeyError as e:
        state, reason = STATE_UNK, "算子异常：%s" % e

    base.update(state=state, reason=reason, used_fields=used, missing_fields=missing)
    return base


def main(inp: Input, ctx: Context) -> Output:
    rules = _rules()
    bids = [b.fields for b in inp.bids]

    with ctx.step("统计同包参数", detail={"bids": len(bids)}):
        prices = [_num(b.get("bid.price_total")) for b in bids]
        prices = [p for p in prices if p is not MISSING]
        avg = sum(prices) / len(prices) if prices else MISSING

    out, violations = [], []
    for b, bid in zip(inp.bids, bids):
        c = dict(inp.tender.fields)
        c.update(bid)
        c["peer.price_avg"] = avg
        with ctx.step("判定：" + b.bidder, detail={"rules": len(rules)}):
            rows = [_run_rule(r, c, bids) for r in rules]
        for r in rows:
            if r["exec_path"] in ("HUMAN", "EXTERNAL", "OUT_OF_SCOPE") and r["state"] != STATE_HUMAN:
                violations.append("越界:" + r["rule_id"])
            if r["state"] == STATE_FAIL and r["missing_fields"]:
                violations.append("缺证判否:" + r["rule_id"])
        count = {k: sum(1 for r in rows if r["state"] == k)
                 for k in (STATE_PASS, STATE_FAIL, STATE_UNK, STATE_HUMAN)}
        out.append(BidResult(bidder=b.bidder,
                             rows=[RuleResult(**r) for r in rows], count=count))

    return Output(batch_id=inp.batch_id, rules_total=len(rules),
                  by_bidder=out, redline_violations=violations, disclaimer=DISCLAIMER)
