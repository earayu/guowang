"""字段抽取器：按字段白名单从知识库抽结构化值，并强制出处回读。

两条确定性能力（不经过模型，可逐字节复现）：
  A. 表格行匹配   —— 限价表 / 货物清单这类「一个标段一行」的表，按标段号锁定整行取值。
  B. 引用跳转链   —— 「见招标公告」→「详见货物清单」这类指引，最多跳 2 跳，逐跳留痕。

通用路径（模型抽取 + 逐字回读）只用于文本型条款；抽不到返回 NOT_FOUND，绝不猜。

行4/10/16/17 所需字段：
  受审侧 bid.seal_*              行4  电子签章
  受审侧 bid.price_total_ex_tax  行10 超最高限价
  受审侧 bid.validity_days       行16 投标有效期
  受审侧 bid.tax_rate            行17 税率
  基准侧 tender.price_cap / required_validity_days / required_delivery_date
"""

import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from apemind_fn import Context

# 字段白名单：字段名 -> (检索问句, 单位说明, 是否为数值, 取值方式)
# 取值方式：table=表格行匹配；chain=引用跳转链；llm=模型抽取+回读
# 每个字段给多个检索问句，合并后交给模型。单问句召回不稳：同一份文件里
# 「投标有效期」既能被条款词召回，也能被前附表标题召回，给一条就漏一条。
FIELDS = {
    "tender.price_cap": (["最高限价 网省采购申请行项目号 标段号",
                          "最高限价 万元 数量 单位 物料描述 含税总价"], "元", True, "table"),
    "tender.required_validity_days": (["投标有效期 日历天 自投标截止日起",
                                       "投标人须知前附表 投标有效期 编列内容"],
                                      "天", True, "llm"),
    "tender.bond_required": (["投标保证金 金额 缴纳形式",
                              "投标人须知前附表 投标保证金"], "元", True, "llm"),
    "tender.required_delivery_date": (["交货期 首批交货日期"], "日期", False, "chain"),
    "bid.bidder_name": (["投标人名称 投标人基本情况"], "文本", False, "llm"),
    "bid.seal_present": (["电子签章 签章页 投标文件签署"], "布尔", False, "llm"),
    "bid.seal_valid": (["电子签章 有效性 验证"], "布尔", False, "llm"),
    "bid.seal_name": (["电子签章 签章名称 投标人名称"], "文本", False, "llm"),
    "bid.price_items": (["分项报价表 行项目号 不含税合价"],
                        "元", True, "bid_table"),
    "bid.price_total_ex_tax": (["投标总价 不含税 人民币"], "元", True, "llm"),
    "bid.committed_delivery_date": (["首批交货日期 交货期承诺"], "日期", False, "llm"),
    "bid.validity_days": (["投标有效期 承诺 日历天"], "天", True, "llm"),
    "bid.tax_rate": (["增值税 税率 征收率 报价表"], "%", True, "llm"),
    # 下面这几项在投标文件正文/报价表里本来就有，之前只是没声明，导致行11/13/39 全部卡住。
    "bid.legal_rep_name": (["法定代表人 投标人基本情况",
                            "单位负责人 法定代表人身份证明"], "文本", False, "llm"),
    "bid.bond_amount": (["投标保证金 金额 缴纳", "投标保证金 免收"], "元", True, "llm"),
}


# 知识库隔离：函数同时挂在基准库和受审库上，ctx.search 默认跨库检索。
# 不指定 kb_ids 的话，查投标人名称时 top12 会被 155 份基准库文档占满，
# 本家投标包排在十几名开外，过滤后一条不剩（实测黄石这家就是这样丢的）。
# 按侧指定库，比事后靠文件名猜可靠得多——score 目前恒为 0，不能拿来区分。
TENDER_KBS = ["col0cd75b81b6b47b74", "colcf0af5d45fd7ef6b"]
# 兜底：只在不认识投标人时走（正常路径必命中 BIDDER_KBS）。
# 旧混库 cold848aad8f57412ce（v1 五家同库）已从 allowlist 移除，不再指向它——
# 实测混库时检索 top20 里本家只占 1 条，其余被别家块挤满，字段抽取靠排序运气。
BID_KBS = [
    "col2de7406a4c8a6e56", "col4020b47c9984bbbb", "col2894640b355a1b11",
    "col8fe7f3d2e3d2dac5", "cold98e481541486cc5", "col1c64f1cb56417c15",
]

# 每家一个库（v2：6 家 × 4 份，三册 docx + 分项报价表 xlsx）。
# 单库只放本家文件，limit=20 即覆盖全文，
# 「这次排序对我有利」这个前提被消掉了。
BIDDER_KBS = {
    "华中电力监测技术（湖北）有限公司": "col2de7406a4c8a6e56",
    "襄阳汉江开关设备有限公司": "col4020b47c9984bbbb",
    "宜昌三峡输变电设备有限公司": "col2894640b355a1b11",
    "荆州楚元智能装备有限公司": "col8fe7f3d2e3d2dac5",
    "黄石磁湖电力科技有限公司": "cold98e481541486cc5",
    "恩施清江自动化设备有限公司": "col1c64f1cb56417c15",
}


def _kbs_for(side: str, bidder: str = "") -> List[str]:
    if side != "bid":
        return TENDER_KBS
    kb = BIDDER_KBS.get(bidder)
    return [kb] if kb else BID_KBS


BID_FILE_PREFIXES = ("投标文件_", "分项报价表_", "投标函_", "开标一览表_")


def _is_own(h: Any, bidder: str) -> bool:
    """这份命中是不是「本次受审的那家」的投标文件。

    受审侧最大的坑不是抽不到，是抽到别人的：函数同时挂在基准库和受审库上，
    ctx.search 是跨库检索，召回里混着招标文件、也混着另外四家的投标包。
    实测踩到过——查「投标人名称」返回的 source 是基准库某份技术规范书，
    因为文件名里有「宜昌运维分部」，简称「宜昌」就匹配上了，结果把招标人
    「国网湖北省电力有限公司」当成投标人。

    所以这里只认两种：source 含投标人全名；或 source 是本家投标包文件名。
    不再用裸简称去猜，也不再拿 content 兜底。
    """
    if not bidder:
        return True
    src = str(h.get("source", ""))
    if bidder in src:
        return True
    short = bidder[:2]
    return bool(short) and src.startswith(BID_FILE_PREFIXES) and short in src


def _is_tender_side(h: Any) -> bool:
    """基准侧只认招标/采购文件，把投标包挡在外面。

    这是上一条的镜像：受审库建好之后，基准侧查「最高限价 行项目号」
    会把投标人的分项报价表也召回来，表头签名和列数都像，很容易读串。
    靠文件名前缀隔开，比靠 score 排序可靠——score 目前恒为 0，不能依赖。
    """
    return not str(h.get("source", "")).startswith(BID_FILE_PREFIXES)


def _search_multi(ctx: Context, queries: List[str], scope_hint: str,
                  section_no: str = "", limit: int = 8,
                  bidder: str = "", side: str = "tender") -> List[Any]:
    """多问句召回 + 合并去重 + 按是否属本范围重排。

    检索词保持裸，不拼批次号/标包名：任何额外词都会改变排序，把目标块挤出 top。
    范围控制放在取回之后，按来源与内容是否含本标段号/标包名排序。
    """

    hits, seen = [], set()
    for q in queries:
        for h in ctx.search(q, _kbs_for(side, bidder), limit=limit):
            k = (str(h.get("source", "")), str(h.get("content", ""))[:160])
            if k in seen:
                continue
            seen.add(k)
            hits.append(h)
    if side == "bid":
        hits = [h for h in hits if _is_own(h, bidder)]
    else:
        hits = [h for h in hits if _is_tender_side(h)]
    if scope_hint or section_no:
        def rank(h):
            blob = str(h.get("source", "")) + str(h.get("content", ""))[:400]
            if section_no and _squash(section_no) in _squash(blob):
                return 0
            if scope_hint and scope_hint in blob:
                return 1
            return 2
        hits.sort(key=rank)
    return hits

# 表格签名：靠表头关键字认出是哪张表。
# 值是「别名组」列表——表头命中任一组即可，组内关键字须全部出现。
# 国网货物清单的真实列名是「网省采购申请号」（152507 货物清单 xlsx 第 1 行即为该名），
# 投标报价表照抄招标清单列名，只有部分模板才叫「行项目号」。
# 只认「行项目号」会把真实件整表漏掉——实测 v2 报价表就因此 price_items 全 NOT_FOUND。
TABLE_SIGS = {
    "price_cap": [["标段号", "最高限价"]],
    "goods_list": [["首批交货日期", "分标编号"]],
    "bid_price": [["行项目号", "合价"], ["网省采购申请号", "合价"],
                  ["采购申请号", "合价"], ["项目号", "合价"]],
}

# 引用跳转：最多 2 跳，每跳一个检索问句 + 一个终点表签名
# 每跳给多个问句、结果合并后再扫。单问句召回不稳：同一个「交货期」条款，
# 只有带上「交货地点 / 技术性能指标」这些邻条款词时才会被切到同一块里返回。
CHAIN_DELIVERY = [
    {"hop": 1, "queries": ["交货期 交货地点 技术性能指标 见招标公告 见第五章",
                            "投标人须知前附表 1.3.2 交货期 编列内容"],
     "anchor": "交货期", "target": "招标公告"},
    # 第 2 跳不限定关键词：公告里那句是「详见货物清单」，本身不含「交货」二字，
    # 若沿用「交货」做锚点会永远匹配不到。
    {"hop": 2, "queries": ["招标公告 交货时间 详见货物清单",
                            "项目概况与招标范围 货物清单 交货时间"],
     "anchor": None, "target": "货物清单"},
    # 第 3 跳落在货物清单表上。这里有三重坑，逐个踩过：
    # ① 152507 的货物清单是 23 列宽表，一张表会被切成多块，单个问句只召回其中一块
    #    （实测只回来 2 行，全表 4 行 → 误判「表中无该标段行」）；
    # ② 全批 18 份货物清单表头一模一样，纯表头检索时 4004 排不进前 10，回来的全是别家标包
    #    （表行数 9 却无一本标段 → 同样报「无该标段行」）；
    # ③ 只有把标段号带进查询，才能把本标包那份压到第 1 位（实测 4004 排 1~4 位）。
    # 所以末跳给三条并行问句 + 带标段号的定向问句，limit 提到 20 才够覆盖全表。
    {"hop": 3, "queries": ["首批交货日期 最后一批交货日期 交货地点",
                            "货物清单 分标编号 包名称 首批交货日期 交货方式",
                            "分标编号 项目单位 首批交货日期 物料编码",
                            "{section_no} 货物清单 首批交货日期 最后一批交货日期 交货地点"],
     "limit": 20, "table": "goods_list"},
]


class Input(BaseModel):
    batch_id: str = Field(description="采购批次号，用于限定检索范围")
    side: str = Field(description="tender=基准侧（招标文件）；bid=受审侧（投标文件）")
    fields: List[str] = Field(description="要抽取的字段名，必须在白名单内")
    scope_hint: str = Field(default="", description="标包关键词（如 2005智能终端），用于把检索限定到具体标包")
    section_no: str = Field(default="", description="标段号（如 152507-1102003-2005），表格行匹配的定位键")
    bidder: str = Field(default="", description="受审侧必填：投标人名称。受审库里有多家投标包，"
                                                "不指定就会把别家的报价/有效期当成本家的")


class OneField(BaseModel):
    field: str
    value_text: str = Field(description="原文中的取值原文，抽不到写 NOT_FOUND")
    quoted_span: str = Field(description="逐字摘录的原文片段，不得改写")
    source: str = Field(description="该片段出自哪个文件，必须是给定来源之一")


class Extraction(BaseModel):
    items: List[OneField]


class FieldOut(BaseModel):
    field: str
    value_text: str
    value_num: Optional[float] = None
    unit: str
    source: str
    quoted_span: str
    method: str = Field(description="table=表格行匹配；chain=引用跳转链；llm=模型抽取；none=未取到")
    applicable: bool = Field(description="该条款对本标包是否适用（免收保证金、不设限价等为不适用）")
    readback_ok: bool = Field(description="quoted_span 是否逐字出现在该来源原文中")
    value_valid: bool = Field(description="数值字段是否真的解析出了数字")
    verified: bool = Field(description="回读通过且取值有效")
    trace: List[Dict[str, Any]] = Field(default_factory=list, description="引用跳转痕迹")
    items: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="逐物料明细（限价表按行项目号一行一条）：item_no/desc/cap_wan/cap_yuan。"
                    "判定层必须按行项目号逐条对位，不得用 value_num 单值比")
    items_sum_yuan: Optional[float] = Field(
        default=None, description="逐物料限价合计（元，两位小数），仅用于「总价超合计」单向判否兜底")
    declared_total_yuan: Optional[float] = Field(
        default=None,
        description="表格自带的合计行数值（元）。与 items_sum_yuan 不等即说明表内算术不通，"
                    "这是行11「小数点错误导致单价总价都出现明显错误」的直接证据")
    reason: str


class Output(BaseModel):
    batch_id: str
    side: str
    requested: int
    found: int
    verified: int
    readback_pass_rate: float
    value_valid_rate: float
    fields: List[FieldOut]
    note: str


# ------------------------------------------------------------------ 基础工具

def _squash(s: str) -> str:
    """去掉所有空白与常见不可见字符，用于回读比对（不改字，只去空白）。"""
    return re.sub(r"[\s\u3000\xa0]+", "", str(s))


def _num(text: str) -> Optional[float]:
    if not text or text.upper() == "NOT_FOUND":
        return None
    # 报价表里的金额是带千分位的（15,024,870.00）。不去逗号，正则会先匹配到 15，
    # 整个投标总价就变成 15 元——这种错不报异常，只会安静地判错。
    text = re.sub(r"(?<=\d),(?=\d{3})", "", str(text))
    m = re.search(r"(\d+(?:\.\d+)?)\s*(万元|亿元|万|元|天|%|％)?", text)
    if not m:
        return None
    v = float(m.group(1))
    unit = m.group(2) or ""
    if unit in ("万元", "万"):
        v *= 10000
    elif unit == "亿元":
        v *= 100000000
    return v


def Q(v: Optional[float]) -> float:
    """金额/数量转两位小数浮点。逐行算术校验要一个确定的比较口径。"""
    if v is None:
        return 0.0
    return round(float(v) + 1e-9, 2)


def _rate_of(text: str) -> Optional[float]:
    """税率原文 → 小数。报价表写「13%」得 0.13；写「0.13」原样保留。

    法定税率集合是 [0.13, 0.09, 0.06, 0.03, 0.01, 0]，单位错一位就是误杀。
    """
    if not text:
        return None
    raw = str(text).strip()
    v = _num(raw)
    if v is None:
        return None
    if "%" in raw or "％" in raw:
        return round(v / 100.0, 6)
    return round(v, 6) if v <= 1 else round(v / 100.0, 6)


def _md_rows(content: str) -> List[List[str]]:
    """把 Markdown 表格行拆成单元格；跳过分隔行（全由 - : 空格组成）。"""
    rows = []
    for ln in str(content).split("\n"):
        ln = ln.strip()
        if not ln.startswith("|"):
            continue
        cells = [c.strip().strip("*").strip() for c in ln.strip("|").split("|")]
        if not cells:
            continue
        body = [c for c in cells if c]
        if body and all(re.fullmatch(r"[-: ]+", c) for c in body):
            continue
        rows.append(cells)
    return rows


def _col(header: List[str], *keys: str) -> Optional[int]:
    for i, c in enumerate(header):
        n = re.sub(r"\s+", "", c)
        for k in keys:
            if k in n:
                return i
    return None


def _find_header(hits: List[Any], sig: str) -> Optional[List[str]]:
    """在所有命中块里找指定表的表头。表头与数据行常被切到不同块，所以单独扫一遍。"""
    groups = TABLE_SIGS[sig]
    for h in hits:
        for cells in _md_rows(str(h.get("content", ""))):
            joined = [_squash(c) for c in cells]
            for keys in groups:
                if all(any(k in c for c in joined) for k in keys):
                    return cells
    return None


def _row_span(cells: List[str]) -> str:
    """把整行还原成 Markdown 行文本，作为回读用的 quoted_span（逐字，不改写）。"""
    return "| " + " | ".join(cells) + " |"


# ------------------------------------------------------------------ 能力 A：表格行匹配

SECTION_RE = re.compile(r"\d{6}-\d{3,}-\d{3,}")


ITEM_RE = re.compile(r"^\d{10,20}$")


def _value_ok(sig: str, raw: str) -> bool:
    """取值列的格式校验。比列数更可靠——被截断的行会伪装成短行，值格式骗不了人。"""
    v = raw.strip()
    if sig == "price_cap":
        return bool(re.fullmatch(r"\d+(?:\.\d+)?", v))          # 限价：纯数字（万元）
    if sig == "bid_price":
        return bool(re.fullmatch(r"[\d,]+(?:\.\d+)?", v))       # 报价：可能带千分位
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v))          # 货物清单：首批交货日期


def _is_data_row(cells: List[str], key_idx: int, ncol: int, sig: str = "") -> bool:
    """判一行的形状是否像数据行：列数与表头一致，且定位列符合该表的键格式。

    限价表/货物清单的键是标段号（152507-1102002-4004）；
    分项报价表的键是行项目号（100035912500010，纯数字长号），不能用同一个判据。
    """
    if abs(len(cells) - ncol) > 1:
        return False
    if key_idx >= len(cells):
        return False
    key = _squash(cells[key_idx])
    if sig == "bid_price":
        return bool(ITEM_RE.match(key))
    return bool(SECTION_RE.search(key))


def _match_table(hits: List[Any], section_no: str, sig: str) -> Dict[str, Any]:
    """按标段号锁定表格行。

    两个关键约束（不加会把别的表当成这张表）：
      1. 数据行列数必须与表头一致 —— 限价表 6 列、货物清单 23 列，混了就会读错列；
      2. 返回 table_rows（全表数据行数），用于判断表是否被完整召回。
         「表里没有该标段」只有在表完整时才等于「不适用」；表没召回全，只能说不知道。
    """
    header = _find_header(hits, sig)
    if header is None:
        return {"found": False, "table_rows": 0, "complete": False,
                "why": "未找到目标表的表头"}

    ncol = len(header)
    if sig == "price_cap":
        val_idx = _col(header, "最高限价", "限价")
        key_idx = _col(header, "标段号", "分标编号")
    elif sig == "bid_price":
        val_idx = _col(header, "合价", "金额")
        # 顺序有讲究：「网省采购申请号」必须排在「采购申请号」前面，
        # 否则同一行里「总部采购申请号」也会被当成定位列，串到另一个号上。
        key_idx = _col(header, "行项目号", "网省采购申请号", "采购申请号", "项目号")
    else:
        val_idx = _col(header, "首批交货日期")
        key_idx = _col(header, "分标编号", "标段号")

    if val_idx is None or key_idx is None:
        return {"found": False, "table_rows": 0, "complete": False,
                "why": "表头缺少定位列或取值列"}

    # 数据行可能不在同一块，扫全部命中；列数不符的一律不认
    # 同一行会被多个查询、多个块反复返回，必须按行文本去重，
    # 否则「命中 N 行」和逐行明细都会虚高数倍。
    all_rows, matched = [], []
    seen_rows = set()
    for h in hits:
        for cells in _md_rows(str(h.get("content", ""))):
            if not _is_data_row(cells, key_idx, ncol, sig):
                continue
            row_key = _squash("|".join(cells))
            if row_key in seen_rows:
                continue
            seen_rows.add(row_key)
            all_rows.append(cells)
            if section_no and _squash(section_no) not in _squash(cells[key_idx]):
                continue
            v = cells[val_idx] if val_idx < len(cells) else ""
            if not _value_ok(sig, v):
                continue
            matched.append({"cells": cells, "value": v,
                            "source": str(h.get("source", "")),
                            "span": _row_span(cells)})

    # 完整阈值：限价表/货物清单全表约 30 行，只召回个位数时判「不设限价」是不负责任的；
    # 分项报价表就几行物料，阈值按 3 行（低于 3 行说明这份报价表没读全）。
    need = 15 if sig in ("price_cap", "goods_list") else 3
    body = {"header": header, "table_rows": len(all_rows),
            "complete": len(all_rows) >= need}
    if not matched:
        return dict(body, found=False, why="表中无该标段行（全表共 %d 行）" % len(all_rows))
    return dict(body, found=True, rows=matched, count=len(matched),
                val_idx=val_idx, key_idx=key_idx)


def _extract_price_cap(hits: List[Any], section_no: str) -> FieldOut:
    r = _match_table(hits, section_no, "price_cap")
    if not r["found"]:
        # 「表里没有这个标段」只有在整张表被完整召回时，才等于「不设限价」。
        # 表没召回全就下这个结论，等于把「没看见」当成「不存在」——不可以。
        if r["complete"]:
            na_note, src = "", ""
            for h in hits:
                c = str(h.get("content", ""))
                if "最高限价" in c and "不设限价" in c:
                    m = re.search(r"注：[^。]*不设限价[^。]*。", c)
                    if m:
                        na_note, src = m.group(0), str(h.get("source", ""))
                        break
            if na_note:
                return FieldOut(field="tender.price_cap", value_text="不设最高限价", unit="元",
                                source=src, quoted_span=na_note, method="table",
                                applicable=False, readback_ok=True, value_valid=True,
                                verified=True, trace=[],
                                reason="限价表已完整召回（%d 行），本标段不在表内；表注写明"
                                       "「表内以外的其他标段及其涉及的物料均不设限价」，"
                                       "判定为不设限价（有效结论，非抽取失败）"
                                       % r["table_rows"])
        why2 = r.get("why", "未匹配到限价行")
        if not r["complete"]:
            why2 += "；限价表仅召回 %d 行，不足 15 行判不了「不设限价」，转澄清" % r["table_rows"]
        return FieldOut(field="tender.price_cap", value_text="NOT_FOUND", unit="元",
                        source="", quoted_span="", method="none", applicable=True,
                        readback_ok=False, value_valid=False, verified=False, trace=[],
                        reason=why2)

    rows = r["rows"]
    vals = []
    for row in rows:
        v = _num(row["value"])
        if v is not None:
            vals.append(v)
    if not vals:
        return FieldOut(field="tender.price_cap", value_text="NOT_FOUND", unit="元",
                        source="", quoted_span="", method="table", applicable=True,
                        readback_ok=False, value_valid=False, verified=False, trace=[],
                        reason="命中表格行但限价列未解析出数值")

    # 同一标段常有多条物料、各自一个限价。不能只留一个数：
    # 取最小值会过严、取最大值会过松，正确做法是逐行列出，让判定层按行项目号对位。
    header = r["header"]
    key_idx = r["key_idx"]
    item_idx = _col(header, "行项目号", "项目号", "物料号")
    desc_idx = _col(header, "物料描述", "物料名称", "物资名称")
    detail = []
    for row in rows:
        c = row["cells"]
        cap_wan = _num(row["value"])
        detail.append({
            # 列位置不再硬编码（原来写死 c[1]/c[4]，换个表头就串列）：
            # 先用表头定位，定位不到再退回原位。
            "item_no": (c[item_idx] if item_idx is not None and item_idx < len(c)
                        else (c[key_idx] if key_idx < len(c) else "")),
            "desc": (c[desc_idx] if desc_idx is not None and desc_idx < len(c) else ""),
            "cap_wan": cap_wan,
            "cap_yuan": (int(round(cap_wan * 10000)) if cap_wan is not None else None),
            "quoted_span": row["span"][:160],
            "source": row["source"],
        })
    # 按行项目号升序，保证顺序稳定。
    # 不能靠「召回顺序」当表序：同一条表行会被多个查询、多个块返回，
    # 扫描顺序本来就≠原表顺序，排一下才能让两次运行、两份报告对得上。
    detail.sort(key=lambda d: (d["item_no"] or ""))

    # value_num 必须和 unit 同口径。原来这里直接取 _num(限价列) = 34.0（万元数值），
    # unit 却写「元」，判定层一旦用 value_num 就是 1 万倍误差。改取 cap_yuan。
    yuans = [(d["cap_yuan"], d) for d in detail if d["cap_yuan"] is not None]
    if not yuans:
        return FieldOut(field="tender.price_cap", value_text="NOT_FOUND", unit="元",
                        source="", quoted_span="", method="table", applicable=True,
                        readback_ok=False, value_valid=False, verified=False, trace=[],
                        reason="命中表格行但限价列未解析出数值")
    pick, pick_d = min(yuans, key=lambda x: x[0])
    # 摘要带行项目号：只列「34.0、182.12…」看不出哪个数对哪条物料，逐条对位时还得回去翻
    value_text = "、".join("%s:%s" % (d["item_no"], d["cap_wan"]) for d in detail) + " 万元"
    why = "表格行匹配：标段号 %s 命中 %d 条物料行" % (section_no, len(rows))
    if len(rows) > 1:
        why += ("，各物料限价不同，已按行项目号逐条列入 items；"
                "value_num 只是最严（最小）值，仅供粗筛，不得作为判定依据")
    return FieldOut(field="tender.price_cap", value_text=value_text, value_num=pick,
                    unit="元", source=pick_d["source"], quoted_span=pick_d["quoted_span"],
                    method="table", applicable=True, readback_ok=True,
                    value_valid=True, verified=True, trace=detail, items=detail,
                    items_sum_yuan=sum(int(d["cap_yuan"]) for d in detail
                                       if d["cap_yuan"] is not None),
                    reason=why + "；单位由表头「最高限价（万元）」换算为元")


# ------------------------------------------------------------------ 能力 B：引用跳转链

# 原文既有「详见货物清单」也有「见招标公告」，所以「详」必须是可选的，
# 写成 详见? 会要求必须先有「详」字，把「见招标公告」整类漏掉。
REF_PATTERNS = [
    (r"(?:详见|见)\s*货物清单", "货物清单"),
    (r"(?:详见|见)\s*招标公告", "招标公告"),
]


def _scan_ref(hits: List[Any], anchor: Optional[str],
              target: Optional[str] = None) -> tuple:
    """在一跳的命中里找「<条款> | 见XXX」这样的指引行，返回 (目标, 原文行, 来源)。

    anchor 为 None 时不限定条款关键词，只看引用模式（用于「详见货物清单」这类
    不含条款名的指引句）。target 指定只认某一跳目标——公告正文里自己也会写
    「详见招标公告附件」，若不限目标就会把这句话误当成交货期的下一跳。
    """
    for h in hits:
        for ln in str(h.get("content", "")).split("\n"):
            if anchor is not None and anchor not in ln:
                continue
            for pat, tgt in REF_PATTERNS:
                if target is not None and tgt != target:
                    continue
                if re.search(pat, ln):
                    return tgt, ln.strip(), str(h.get("source", ""))
    return None, None, None


def _extract_delivery(ctx: Context, batch_id: str, scope_hint: str,
                      section_no: str) -> FieldOut:
    trace: List[Dict[str, Any]] = []
    hits: List[Any] = []
    for step in CHAIN_DELIVERY:
        hits, seen = [], set()
        for qs in step["queries"]:
            # 检索问句保持「裸」，不拼批次号也不拼标包名：任何额外词都会改变排序，
            # 把「交货期」那一块挤出 top10（实测过三种前缀，全部召回不到）。
            # 例外只有末跳货物清单：18 份清单表头完全相同，不带标段号就永远排不进前 10。
            q = qs.replace("{section_no}", section_no or "").replace(
                "{scope_hint}", scope_hint or "").strip()
            got = [h for h in ctx.search(q, TENDER_KBS, limit=step.get("limit", 10))
                   if _is_tender_side(h)]
            for h in got:
                k = (str(h.get("source", "")), str(h.get("content", ""))[:160])
                if k in seen:
                    continue
                seen.add(k)
                hits.append(h)
            trace.append({"hop": step["hop"], "query": q, "hits": len(got)})
        # 取回后再收范围：来源属本标包的排前面，其余保序垫后
        if scope_hint:
            hits.sort(key=lambda h: 0 if scope_hint in str(h.get("source", "")) else 1)
        trace.append({"hop": step["hop"], "merged_hits": len(hits),
                      "in_scope": sum(1 for h in hits
                                      if scope_hint and scope_hint in str(h.get("source", "")))})

        if "table" in step:
            r = _match_table(hits, section_no, step["table"])
            if r["found"]:
                # 同标段多行时取最早的首批交货日期，即最紧的交期
                dates = []
                for row in r["rows"]:
                    m = re.search(r"\d{4}-\d{2}-\d{2}", row["value"])
                    if m:
                        dates.append((m.group(0), row))
                if dates:
                    dates.sort(key=lambda x: x[0])
                    d, row = dates[0]
                    trace.append({"hop": step["hop"], "match": "table_row",
                                  "rows": r["count"], "picked": d})
                    return FieldOut(
                        field="tender.required_delivery_date", value_text=d, unit="日期",
                        source=row["source"], quoted_span=row["span"][:200],
                        method="chain", applicable=True, readback_ok=True,
                        value_valid=True, verified=True, trace=trace,
                        reason="引用跳转 2 跳后由货物清单表格行匹配取得首批交货日期"
                               "（同标段 %d 行取最早）" % r["count"])
            trace.append({"hop": step["hop"], "match": "table_row_failed",
                          "why": r.get("why")})
            break

        tgt, line, src = _scan_ref(hits, step.get("anchor"), step.get("target"))
        trace.append({"hop": step["hop"], "ref": tgt, "line": (line or "")[:120], "source": src})
        if not tgt:
            break

    return FieldOut(field="tender.required_delivery_date", value_text="NOT_FOUND", unit="日期",
                    source="", quoted_span="", method="chain", applicable=True,
                    readback_ok=False, value_valid=False, verified=False, trace=trace,
                    reason="引用链未走通到取值表")


# ------------------------------------------------------------------ 受审侧：分项报价表

def _extract_bid_price_items(hits: List[Any], bidder: str) -> FieldOut:
    """从投标人的分项报价表抽逐行项目报价，形状与基准侧限价 items 对齐，便于逐条对位。

    不按标段号过滤：分项报价表里没有「标段号」列，且每家投标包只投一个标段，
    隔离靠 source（投标人）而不是靠表内容。
    """
    r = _match_table(hits, "", "bid_price")
    if not r["found"]:
        why = r.get("why", "未匹配到分项报价表")
        if not r["complete"]:
            why += "；报价表仅召回 %d 行，不足 3 行，视为未读全" % r["table_rows"]
        return FieldOut(field="bid.price_items", value_text="NOT_FOUND", unit="元",
                        source="", quoted_span="", method="none", applicable=True,
                        readback_ok=False, value_valid=False, verified=False, trace=[],
                        reason="%s：%s" % (bidder or "受审方", why))

    hdr = r["header"]
    qty_idx = _col(hdr, "数量")
    up_idx = _col(hdr, "不含税单价", "单价")
    rate_idx = _col(hdr, "税率")

    items = []
    for row in r["rows"]:
        c = row["cells"]
        amt = _num(row["value"])

        def at(i: Optional[int]) -> str:
            return c[i] if i is not None and i < len(c) else ""

        qty = _num(at(qty_idx)) if qty_idx is not None else None
        up = _num(at(up_idx)) if up_idx is not None else None
        rate = _rate_of(at(rate_idx)) if rate_idx is not None else None

        # 逐行算术自校验：数量 × 不含税单价 应等于不含税合价。
        # 这不是「顺手多抽两个字段」，行11 的否决情形就是「小数点错误导致单价总价都出现明显错误」，
        # 判它必须逐行比，用「合计数量 × 合计单价」去比总价是错的——多行相加后误差互相抵消。
        line_calc = (round(Q(qty) * Q(up), 2) if qty is not None and up is not None else None)
        amt_num = round(Q(amt), 2) if amt is not None else None
        ok_line = (line_calc == amt_num) if (line_calc is not None and amt_num is not None) else None

        items.append({
            "item_no": at(r["key_idx"]),
            "qty": qty,
            "unit_price_yuan": up,
            # 金额保留两位小数（审计口径）：7,949,557.52 不能存成 7949558
            "amount_yuan": (round(float(amt), 2) if amt is not None else None),
            "tax_rate": rate,
            "calc_amount_yuan": line_calc,
            "arith_ok": ok_line,
            "desc": at(1),
            "quoted_span": row["span"][:160],
            "source": row["source"],
        })
    if not items:
        return FieldOut(field="bid.price_items", value_text="NOT_FOUND", unit="元",
                        source="", quoted_span="", method="bid_table", applicable=True,
                        readback_ok=False, value_valid=False, verified=False, trace=[],
                        reason="命中报价表但合价列未解析出数值")

    # 合计行不是数据行（首列是「合计」不是行项目号），_is_data_row 会把它滤掉，单独扫。
    declared_total, total_span = None, ""
    for h in hits:
        for cells in _md_rows(str(h.get("content", ""))):
            if not cells or "合计" not in _squash(cells[0]):
                continue
            for cell in cells[1:]:
                v = _num(cell)
                if v is not None and v > 1000:      # 排除「合计 4 项」这类计数
                    declared_total = round(v, 2)
                    total_span = _row_span(cells)
                    break
            if declared_total is not None:
                break
        if declared_total is not None:
            break

    # 同一行项目号会在两处各出现一次：价格册的「已标价货物清单行报价汇总表」和
    # 随附的 xlsx「分项报价表」，是同一份数据的两种呈现。按行文本去重挡不住——
    # 两份表列名不同（xlsx 多「项目名称」列）、行文本不同，于是逐行合价之和正好翻倍，
    # 还会被误判成「表内合计与明细不符」。按 item_no 去重，先到先得。
    # 本标段一行项目一号（各包号下唯一），不存在同一号多行的情形；
    # 若将来出现一包一号多行，这里要改成按 (item_no, 包号) 去重。
    _uniq, _seen = [], set()
    for _it in items:
        _no = (_it.get("item_no") or "").strip()
        if _no and _no in _seen:
            continue
        if _no:
            _seen.add(_no)
        _uniq.append(_it)
    items = _uniq

    items.sort(key=lambda d: d["item_no"] or "")
    total = round(sum(i["amount_yuan"] for i in items if i["amount_yuan"] is not None), 2)
    bad_lines = [i["item_no"] for i in items if i["arith_ok"] is False]
    sum_ok = (declared_total is not None and abs(declared_total - total) < 0.005
              if declared_total is not None else None)

    note = "分项报价表逐行项目号取值：%d 条物料，逐行合价之和 %.2f 元" % (len(items), total)
    if declared_total is not None:
        note += "，表内合计行 %.2f 元（%s）" % (
            declared_total, "一致" if sum_ok else "不一致，差 %.2f 元" % (total - declared_total))
    else:
        note += "，未召回到合计行"
    if bad_lines:
        note += "；%d 条物料单价×数量与合价不符：%s" % (len(bad_lines), "、".join(bad_lines))

    return FieldOut(
        field="bid.price_items", value_text="、".join(
            "%s:%s×%s=%.2f" % (i["item_no"], i["qty"], i["unit_price_yuan"], i["amount_yuan"])
            for i in items),
        value_num=float(total), unit="元", source=items[0]["source"],
        quoted_span=(total_span or items[0]["quoted_span"]), method="bid_table",
        applicable=True, readback_ok=True, value_valid=True, verified=True,
        trace=items, items=items, items_sum_yuan=total,
        declared_total_yuan=declared_total,
        reason=note + "（受审方：%s）" % (bidder or "未指定"))


# ------------------------------------------------------------------ 通用路径：模型抽取

def _extract_llm(ctx: Context, name: str, hits: List[Any],
                 unit: str, is_num: bool) -> FieldOut:
    sources = [str(h.get("source", "")) for h in hits]
    blocks = []
    for i, h in enumerate(hits, 1):
        blocks.append("[%d] 来源：%s\n%s" % (i, h.get("source", ""),
                                            str(h.get("content", ""))[:900]))

    ext = ctx.llm(
        "任务：从下列招标文件片段中抽取字段「%s」的取值。\n"
        "硬性要求：\n"
        "1. quoted_span 必须是从片段里**逐字复制**的一小段原文（10~60 字），不得改写、不得拼接。\n"
        "2. source 必须原样填写该片段标注的来源。\n"
        "3. 片段里没有明确写出，就填 NOT_FOUND，不要推测。\n\n"
        "片段：\n%s\n\n只输出一个 item。" % (name, "\n\n".join(blocks)),
        system="你是招标文件字段抽取器。只做摘录，不做推理；宁可返回 NOT_FOUND 也不猜。",
        output=Extraction)

    item = ext.items[0] if ext.items else None
    if item is None:
        return FieldOut(field=name, value_text="NOT_FOUND", unit=unit, source="",
                        quoted_span="", method="none", applicable=True,
                        readback_ok=False, value_valid=False, verified=False, trace=[],
                        reason="模型未返回结果")

    readback_ok, why = False, ""
    span = _squash(item.quoted_span)
    # 同一份文件会被切成多个块，回读必须在该来源的**全部块**里找。
    # 只取第一个同源块是错的：证据落在别的块里就会被误判成回读失败。
    targets = [h for h in hits if str(h.get("source", "")) == item.source]
    if item.value_text.upper() == "NOT_FOUND" or not span:
        why = "标注为未找到"
    elif not targets:
        why = "来源不在本次检索命中内"
    elif any(span in _squash(h.get("content", "")) for h in targets):
        readback_ok, why = True, "回读通过"
    else:
        why = "回读失败：片段未出现在该来源原文中"

    num = _num(item.value_text) if is_num else None
    # 税率统一成小数：原文写「13%」，_num 得 13.0，而法定税率集合是 [0.13, 0.09 …]。
    # 两边口径不一致，行17 会把 13% 判成「不在法定集合」——合规投标被误杀。
    # 归一放在抽取侧做一次，比让每个消费方各自记得除 100 可靠。
    if name.endswith("tax_rate") and num is not None and num > 1:
        num = round(num / 100.0, 6)
    na_words = ("不适用", "免收", "不设", "不收取", "无需")
    applicable = not any(w in item.value_text for w in na_words)
    # 不适用类取值没有金额可言，但原文常带条款号「（前附表 3.4.1）」，
    # _num 会把 3.4.1 抓成 3.4，凭空多出一笔「保证金 3.4 元」的假金额。
    # 实测襄阳这家就是这样：value_text「本项目免收（前附表 3.4.1）」→ value_num=3.4。
    # 不适用时一律置空，宁可没有数，也不给一个会被下游当真的数。
    if not applicable:
        num = None
    value_valid = (not is_num) or (num is not None) or (not applicable)
    if readback_ok and not value_valid:
        why = "回读通过但未解析出数值（疑似套话条款，非具体取值）"
    elif readback_ok and not applicable:
        why = "回读通过，条款对本标包不适用"

    return FieldOut(field=name, value_text=item.value_text, value_num=num, unit=unit,
                    source=item.source, quoted_span=item.quoted_span[:200],
                    method="llm", applicable=applicable, readback_ok=readback_ok,
                    value_valid=value_valid, verified=readback_ok and value_valid,
                    trace=[], reason=why)


# ------------------------------------------------------------------ 主流程

def main(inp: Input, ctx: Context) -> Output:
    bad = [f for f in inp.fields if f not in FIELDS]
    if bad:
        raise ValueError("字段不在白名单: " + ",".join(bad))

    prefix = "tender." if inp.side == "tender" else "bid."
    if any(not f.startswith(prefix) for f in inp.fields):
        raise ValueError("side 与字段前缀不一致，受审侧字段以 bid. 开头")

    # 受审侧必须点名是哪一家。受审库里同时躺着多家投标包，缺了 bidder
    # 就会把别家的报价、有效期抽成这家的——错得很安静，事后极难发现。
    if inp.side == "bid" and not inp.bidder:
        raise ValueError("受审侧必须提供 bidder（投标人名称），否则会跨家取数")

    results: List[FieldOut] = []

    for name in inp.fields:
        q, unit, is_num, how = FIELDS[name]

        if how == "bid_table":
            with ctx.step("分项报价表：" + name):
                # 多问句是并集，多给一路只会增加命中、不会挤掉原有排序：
                # 受审库里同标段躺着多家投标包，裸问句召回的 top10 常被先入库那家占满，
                # 本家的报价表反而进不来。补一路「投标人 + 分项报价表」把它捞回来。
                qs = list(q) + [inp.bidder + " 分项报价表"]
                if inp.section_no:
                    qs.append(inp.section_no)
                hits = _search_multi(ctx, qs, inp.scope_hint, "", limit=12,
                                     bidder=inp.bidder, side="bid")
            if not hits:
                results.append(FieldOut(field=name, value_text="NOT_FOUND", unit=unit,
                                        source="", quoted_span="", method="none",
                                        applicable=True, readback_ok=False,
                                        value_valid=False, verified=False, trace=[],
                                        reason="受审库里没有 %s 的命中（不会跨家取数）" % inp.bidder))
                continue
            results.append(_extract_bid_price_items(hits, inp.bidder))
            continue

        if how == "table":
            if not inp.section_no:
                results.append(FieldOut(field=name, value_text="NOT_FOUND", unit=unit,
                                        source="", quoted_span="", method="none",
                                        applicable=True, readback_ok=False,
                                        value_valid=False, verified=False, trace=[],
                                        reason="表格行匹配必须提供 section_no（标段号）"))
                continue
            with ctx.step("表格行匹配：" + name):
                # 再加一路「标段号本身」：表行按语义检索常常召不回来，
                # 但用标段号精确命中时几乎必回（实测同一标段从 0 行变 4 行）。
                hits = _search_multi(ctx, list(q) + [inp.section_no],
                                     inp.scope_hint, inp.section_no, limit=10)
            if not hits:
                results.append(FieldOut(field=name, value_text="NOT_FOUND", unit=unit,
                                        source="", quoted_span="", method="none",
                                        applicable=True, readback_ok=False,
                                        value_valid=False, verified=False, trace=[],
                                        reason=("受审库中未召回到 %s 的文件（跨库召回经本家过滤后为空）" % inp.bidder)
                                        if inp.side == "bid" and inp.bidder
                                        else "知识库无命中"))
                continue
            results.append(_extract_price_cap(hits, inp.section_no))
            continue

        if how == "chain":
            if not inp.section_no:
                results.append(FieldOut(field=name, value_text="NOT_FOUND", unit=unit,
                                        source="", quoted_span="", method="none",
                                        applicable=True, readback_ok=False,
                                        value_valid=False, verified=False, trace=[],
                                        reason="引用跳转链必须提供 section_no（标段号）"))
                continue
            with ctx.step("引用跳转：" + name):
                results.append(_extract_delivery(ctx, inp.batch_id, inp.scope_hint,
                                                 inp.section_no))
            continue

        with ctx.step("检索：" + name):
            # 受审侧补两路：光给「投标人名称」这种泛问句，在 155 份基准库 + 5 家投标包
            # 的混合召回里挤不进 top8，过滤掉别家之后就一条不剩（实测就是这个原因）：
            # 补一路纯人名、一路「人名 + 字段词」，同时把 limit 放宽，取回后再筛本家。
            if inp.side == "bid" and inp.bidder:
                qs = list(q) + [inp.bidder, inp.bidder + " " + q[0]]
                # limit 提到平台上限 20。受审库存着 10 个文件、几十个块，
                # 12 条只够覆盖少数文件的少数块——实测黄石那家的「六、投标保证金」
                # 就始终进不来，而同句式的另外四家能进，纯粹是排序运气。
                lim = 20
            else:
                qs = list(q)
                lim = 8
            hits = _search_multi(ctx, qs, inp.scope_hint, inp.section_no, limit=lim,
                                 bidder=inp.bidder, side=inp.side)
        if not hits:
            results.append(FieldOut(field=name, value_text="NOT_FOUND", unit=unit,
                                    source="", quoted_span="", method="none",
                                    applicable=True, readback_ok=False,
                                    value_valid=False, verified=False, trace=[],
                                    reason=("受审库中未召回到 %s 的文件（跨库召回经本家过滤后为空）" % inp.bidder)
                                        if inp.side == "bid" and inp.bidder
                                        else "知识库无命中"))
            continue
        with ctx.step("抽取：" + name):
            results.append(_extract_llm(ctx, name, hits, unit, is_num))

    found = sum(1 for r in results if r.value_text.upper() != "NOT_FOUND")
    verified = sum(1 for r in results if r.verified)
    rb = sum(1 for r in results if r.readback_ok)
    vv = sum(1 for r in results if r.value_valid)
    rate = round(rb / len(results), 4) if results else 0.0
    vrate = round(vv / len(results), 4) if results else 0.0

    return Output(
        batch_id=inp.batch_id, side=inp.side, requested=len(results),
        found=found, verified=verified, readback_pass_rate=rate, value_valid_rate=vrate,
        fields=results,
        note="未通过回读的字段不得进入判定层；判定层会因此输出 UNCERTAIN 并转澄清。"
             "method=table/chain 的字段由确定性代码取值，不经模型，可逐字节复现。")
