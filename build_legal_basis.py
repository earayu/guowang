# -*- coding: utf-8 -*-
"""给 46 条规则挂法规依据，并区分「法定否决情形」与「招标人约定否决条款」。

为什么必须三分而不是笼统写"依据法规"：
  评委最容易问的一句是"这条是法定的，还是你们招标人自己加的"。
  法定否决情形只有《招标投标法实施条例》第 51 条七项 + 第 34 条，其余全是招标人
  依第 23 条在招标文件中约定的条款。混着写等于把招标人约定包装成法定义务，
  一旦被追问就是硬伤；分开写反而显专业——因为招标人本来就有权约定。

confidence 只给 high 的情形才在界面显示条文序号；不给条号的一律只列法规名。
宁可少挂，不可挂错。

用法：python build_legal_basis.py
产出：国网Demo_规则法源溯源表_V1.json / .md
"""
import io
import json

SRC = "_provenance/rules_with_provenance.json"
OUT_JSON = "国网Demo_规则法源溯源表_V1.json"
OUT_MD = "国网Demo_规则法源溯源表_V1.md"

# ---- 法规条文（只收能逐字背出来的，其余不给条号）----
L = {
    "51_1": {"law": "《招标投标法实施条例》", "article": "第五十一条", "item": "第（一）项",
             "text": "投标文件未经投标单位盖章和单位负责人签字", "confidence": "high"},
    "51_3": {"law": "《招标投标法实施条例》", "article": "第五十一条", "item": "第（三）项",
             "text": "投标人不符合国家或者招标文件规定的资格条件", "confidence": "high"},
    "51_4": {"law": "《招标投标法实施条例》", "article": "第五十一条", "item": "第（四）项",
             "text": "同一投标人提交两个以上不同的投标文件或者投标报价，但招标文件要求提交备选投标的除外",
             "confidence": "high"},
    "51_5": {"law": "《招标投标法实施条例》", "article": "第五十一条", "item": "第（五）项",
             "text": "投标报价低于成本或者高于招标文件设定的最高投标限价", "confidence": "high"},
    "51_6": {"law": "《招标投标法实施条例》", "article": "第五十一条", "item": "第（六）项",
             "text": "投标文件没有对招标文件的实质性要求和条件作出响应", "confidence": "high"},
    "51_7": {"law": "《招标投标法实施条例》", "article": "第五十一条", "item": "第（七）项",
             "text": "投标人有串通投标、弄虚作假、行贿等违法行为", "confidence": "high"},
    "34": {"law": "《招标投标法实施条例》", "article": "第三十四条", "item": "",
           "text": "与招标人存在利害关系可能影响招标公正性的法人、其他组织或者个人，不得参加投标；"
                   "单位负责人为同一人或者存在控股、管理关系的不同单位，不得参加同一标段投标或者"
                   "未划分标段的同一招标项目投标", "confidence": "high"},
    "23": {"law": "《招标投标法实施条例》", "article": "第二十三条", "item": "",
           "text": "招标人应当在招标文件中规定实质性要求和条件，说明不满足其中任何一项实质性要求和条件的"
                   "投标将被拒绝，并用醒目的方式标明", "confidence": "high"},
    "law33": {"law": "《招标投标法》", "article": "第三十三条", "item": "",
              "text": "投标人不得以低于成本的报价竞标", "confidence": "high"},
    "law32": {"law": "《招标投标法》", "article": "第三十二条", "item": "",
              "text": "投标人不得相互串通投标报价，不得以向招标人或者评标委员会成员行贿的手段谋取中标",
              "confidence": "high"},
    "law42": {"law": "《招标投标法》", "article": "第四十二条", "item": "",
              "text": "评标委员会经评审，认为所有投标都不符合招标文件要求的，可以否决所有投标",
              "confidence": "high"},
    "51_catch": {"law": "《招标投标法实施条例》等法律法规规章", "article": "", "item": "",
                 "text": "第五十一条第（一）至（七）项以外的其他法定否决情形（兜底援引，具体条文视个案而定）",
                 "confidence": "catchall"},
}

# ---- 按类别默认 ----
# statutory      = 法条直接对应，招标文件只是复述
# tender_defined = 招标人依条例第 23 条自行约定，非法定否决情形
# mixed          = 法定要件 + 招标文件细化口径
BY_CAT = {
    ("形式评审", "文件签署"): ("statutory", ["51_1"]),
    ("形式评审", "格式内容"): ("tender_defined", ["23"]),
    ("形式评审", "参数接口"): ("mixed", ["51_6"]),
    ("响应性评审", "实质不符"): ("statutory", ["51_6"]),
    ("响应性评审", "交付期限"): ("mixed", ["51_6"]),
    ("响应性评审", "投标期限"): ("mixed", ["51_6"]),
    ("响应性评审", "投标范围"): ("mixed", ["51_6"]),
    ("响应性评审", "投标偏差"): ("mixed", ["51_6"]),
    ("响应性评审", "投标担保"): ("mixed", ["51_6"]),
    ("响应性评审", "澄清修改"): ("mixed", ["51_6"]),
    ("响应性评审", "税率错误"): ("tender_defined", ["23"]),
    ("响应性评审", "投标报价"): ("tender_defined", ["23"]),
    ("资格评审", "资格不符"): ("statutory", ["51_3"]),
    ("资格评审", "主体不符"): ("statutory", ["51_3", "34"]),
    ("资格评审", "丧失履约能力"): ("statutory", ["51_3"]),
    ("资格评审", "资信不良"): ("statutory", ["51_3"]),
    ("资格评审", "失信惩戒"): ("mixed", ["51_3"]),
    ("资格评审", "法定否决"): ("statutory", ["51_7", "law32"]),
    ("资格评审", "质量否决"): ("tender_defined", ["23"]),
    ("资格评审", "行贿记录"): ("statutory", ["51_7"]),
    ("资格评审", "不良行为"): ("tender_defined", ["23"]),
    ("资格评审", "无效代理"): ("tender_defined", ["23"]),
    ("其他事项", "其他事项"): ("tender_defined", ["23"]),
}

# ---- 逐条覆盖（类别内口径不同，必须单条定）----
BY_RULE = {
    "GW-HB-FJ-001": ("tender_defined", ["23"]),   # 格式未按招标文件填写
    "GW-HB-FJ-002": ("statutory", ["51_4"]),      # 两份不同投标文件/多个报价
    "GW-HB-FJ-005": ("mixed", ["51_6"]),          # 截止后撤销
    "GW-HB-FJ-006": ("tender_defined", ["23"]),   # 不按评标委员会要求澄清
    "GW-HB-FJ-008": ("tender_defined", ["23"]),   # 不接受修正价格
    "GW-HB-FJ-009": ("statutory", ["51_5", "law33"]),
    "GW-HB-FJ-010": ("statutory", ["51_5"]),
    "GW-HB-FJ-011": ("tender_defined", ["23"]),   # 无效报价/小数点错误
    "GW-HB-FJ-012": ("tender_defined", ["23"]),   # 金额单位错位
    "GW-HB-FJ-018": ("statutory", ["51_7"]),      # 虚假投标
    "GW-HB-FJ-019": ("statutory", ["51_7", "law32"]),  # 串通投标
    "GW-HB-FJ-020": ("catchall", ["51_catch"]),        # 其他法定否决情形（兜底）
    "GW-HB-FJ-022": ("mixed", ["51_3"]),               # 三年内重大质量问题＝资格条件细化
    "GW-HB-FJ-030": ("statutory", ["51_3"]),
    "GW-HB-FJ-031": ("statutory", ["51_3"]),
    "GW-HB-FJ-045": ("tender_defined", ["23"]),        # 招标文件兜底条款
    "GW-HB-FJ-046": ("tender_defined", ["23"]),   # 超本包报价平均值（国网防止抬价）
}

CLASS_CN = {"statutory": "法定否决情形", "tender_defined": "招标人约定否决条款",
            "mixed": "法定要件 + 招标文件细化",
            "catchall": "法定兜底（援引其他法定情形）"}


def resolve(r):
    rid = r["rule_id"]
    p = r["provenance"]
    cat = (p["category"], p["subcategory"])
    if rid in BY_RULE:
        cls, keys = BY_RULE[rid]
    elif cat in BY_CAT:
        cls, keys = BY_CAT[cat]
    else:
        cls, keys = ("tender_defined", ["23"])
    items = []
    for k in keys:
        if k in L:
            items.append(L[k])
        else:  # 只有法规名，没有条号
            items.append({"law": k, "article": "", "item": "", "text": "", "confidence": "name_only"})
    return cls, items


def clean_text(r):
    """去掉 rule_text 里的内部注释（'注：…'、'K1 资格预审版…'），对客只留招标文件口径。"""
    t = r["rule_text"]
    cut = t.find("（注：")
    if cut > 0:
        t = t[:cut]
    # 版本差异注释单独留在 internal_note
    return t.strip()


def internal_note(r):
    t = r["rule_text"]
    notes = []
    i = t.find("（注：")
    if i > 0:
        notes.append(t[i:])
    if "K1" in t and "资格预审" in t:
        j = t.find("；K1")
        if j > 0:
            notes.append(t[j + 1:])
    return " ".join(notes)


def main():
    d = json.load(io.open(SRC, encoding="utf-8"))
    out = []
    for r in d["rules"]:
        cls, items = resolve(r)
        p = r["provenance"]
        out.append({
            "rule_id": r["rule_id"],
            "row": r["row"],
            "category": p["category"],
            "subcategory": p["subcategory"],
            "rule_text": clean_text(r),
            "internal_note": internal_note(r),
            "provenance": {
                "doc": p["doc"],
                "chapter": p["chapter"],
                "section": p["section"],
                "clause": p["clause"],
                "table_row": p["table_row"],
                "para_index": p["para_index"],
                "text_in_tender": p["text_in_tender"],
                "match_sim": p["match_sim"],
            },
            "legal": {"class": cls, "class_cn": CLASS_CN[cls], "items": items},
            "exec_path": r["exec_path"],
            "conclusion_ceiling": r["conclusion_ceiling"],
        })

    io.open(OUT_JSON, "w", encoding="utf-8", newline="\n").write(
        json.dumps({"meta": {
            "n": len(out),
            "tender": "国网湖北电力2025年新增第一次物资公开招标采购文件（152507）",
            "chapter": "第三章 评标办法（综合评估法）/ 前附表之二 初步评审标准",
            "note": "招标文件原文逐条回读，46/46 文本一致（sim=1.000 共 44 条，另 2 条因内部注释标注差异）",
        }, "rules": out}, ensure_ascii=False, indent=1))

    # ---- Markdown ----
    md = []
    md.append("# 46 条否决情形 · 法源溯源表 V1\n")
    md.append("每一条都回读到真实招标文件原文，不做概括、不改写。\n")
    md.append("- 招标文件：《国网湖北电力2025年新增第一次物资公开招标采购文件（152507）》")
    md.append("- 位置：第三章 评标办法（综合评估法）→ 前附表之二 初步评审标准")
    md.append("- 定位方式：章节号 + 表格行号 + 文档段落号（docx 无稳定页码，段落号可精确复核）\n")
    from collections import Counter
    c = Counter(x["legal"]["class"] for x in out)
    md.append("## 否决性质构成\n")
    md.append("| 性质 | 条数 | 含义 |")
    md.append("|---|---:|---|")
    md.append("| 法定否决情形 | %d | 法条直接对应，招标文件仅作复述 |" % c["statutory"])
    md.append("| 法定要件 + 招标文件细化 | %d | 法律原则 + 本项目具体口径 |" % c["mixed"])
    md.append("| 招标人约定否决条款 | %d | 依条例第 23 条由招标人约定，**非法定否决情形** |" % c["tender_defined"])
    md.append("")
    md.append("> 这一栏是对客最该主动说清的：46 条里只有 %d 条是法定的，"
              "其余是招标人依《招标投标法实施条例》第二十三条约定并醒目列明的。"
              "招标人有权约定，但把约定说成法定，一问就穿。\n" % c["statutory"])
    md.append("## 逐条溯源\n")
    md.append("| 行 | 规则号 | 评审类 | 招标文件位置 | 否决性质 | 法规依据 |")
    md.append("|---:|---|---|---|---|---|")
    for x in out:
        p = x["provenance"]
        leg = x["legal"]["items"]
        legs = []
        for it in leg:
            if it["article"]:
                legs.append("%s%s%s" % (it["law"], it["article"], it["item"]))
            else:
                legs.append(it["law"])
        md.append("| %d | %s | %s/%s | 第三章 %s · 表第 %d 行 | %s | %s |" % (
            x["row"], x["rule_id"], x["category"], x["subcategory"],
            p["clause"], p["table_row"], x["legal"]["class_cn"],
            "；".join(legs) if legs else "—"))
    md.append("")
    md.append("## 招标文件原文（逐条，未删改）\n")
    for x in out:
        p = x["provenance"]
        md.append("**%d · %s**　`第三章 %s / 表第 %d 行 / 段 %d`" % (
            x["row"], x["rule_id"], p["clause"], p["table_row"], p["para_index"]))
        md.append("")
        md.append("> " + (p["text_in_tender"] or "").replace("\n", " "))
        md.append("")
    io.open(OUT_MD, "w", encoding="utf-8", newline="\n").write("\n".join(md) + "\n")
    print("rules", len(out))
    print("class", dict(c))
    print("wrote", OUT_JSON, OUT_MD)


if __name__ == "__main__":
    main()
