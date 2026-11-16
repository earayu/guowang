# -*- coding: utf-8 -*-
"""造 6 份「按真实招标文件形态」的受控合成投标包（三册制：价格 / 商务 / 技术）。

全部依据取自本地真实招标文件 S2_152507 / 包1_完整招标文件_82077900012222353：
  · 招标文件 3.1.1「投标文件的组成」11 项
  · 投标人须知前附表：投标有效期 90 日、免收投标保证金、财务年份 2022—2024、
    不接受联合体、不允许备选方案与分包、商务与技术文件整体电子签章
  · 前附表之附表一：最高限价 34 / 182.12 / 453.31 / 1000 万元（**含税总价**）
  · 货物清单：包1(HB100) 首批 2026-04-20；包2(HB200) 首批 2026-06-29、末批 2026-06-30
  · 招标公告：投标截止 2026-01-28 09:00，不接受联合体
  · 评标办法前附表之二：46 条否决情形
  · 技术规范书：带 * 的重要技术参数（监测范围 >24km、定位精度 ±1m 等）

与 bid_packs/（v1）的口径差异（这是本轮必须修的地方）：
  v1 拿「未含税金额」直接与「含税限价」比，且未含税 = 限价×0.9。
  换算含税后 15024870×1.13 = 16978103.10 > 含税限价 16694300 ——
  按真实口径 v1 六家其实全部超限价，却被判为「无超限价」。
  v2 改为：含税报价 = 含税限价×折扣，未含税 = 含税÷(1+税率)，
  三处金额（投标函 / 开标一览表 / 分项报价表）互相对得上。

v1 另有两处不真实：签章日期 2026-10-18（晚于投标截止 2026-01-28）、
承诺交货 2026-05-10（晚于包1 要求的 2026-04-20）。v2 一并改正。

产出（bid_packs_v2/）：
  投标文件_<简称>_152507-1102002-4004_价格文件.docx
  投标文件_<简称>_152507-1102002-4004_商务文件.docx
  投标文件_<简称>_152507-1102002-4004_技术文件.docx
  分项报价表_<简称>_152507-1102002-4004.xlsx
  _ground_truth_v3.json   6 家期望值（由文件内容反推，非手填）
  _README_合成包说明.md
"""
import json
import os
import zlib

# ---- 确定性伪随机：v2 全篇用 hash()，带 PYTHONHASHSEED 随机化，
#      每次重跑财务/证件/电话都变，合成件不稳定。改为 crc32 派生。
def sd(*args):
    return zlib.crc32(("|".join(str(a) for x in args for a in (x,))).encode("utf-8"))

# ---- 统一社会信用代码校验位（GB 32100-2015）
_CHARS = "0123456789ABCDEFGHJKLMNPQRTUWXY"
_W = [1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28]

def uscc(p17):
    """由 17 位本体码补出合法校验位，产出 18 位。"""
    tot = sum(_CHARS.index(p17[i]) * _W[i] for i in range(17))
    c = 31 - tot % 31
    return p17 + _CHARS[0 if c == 31 else c]

# ---- 公民身份号码校验位（GB 11643）
_IW = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]

def idno(p17):
    return p17 + "10X98765432"[sum(int(p17[i]) * _IW[i] for i in range(17)) % 11]

def age_of(birth):
    """投标截止日 2026-01-28 时的周岁。"""
    y, m, d = (int(x) for x in birth.split("-"))
    a = 2026 - y - ((1, 28) < (m, d))
    return a

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

OUT = "bid_packs_v2"
SECTION = "152507-1102002-4004"
BATCH = "152507"
TENDER_NO = "国网湖北电力2025年新增第一次物资公开招标采购（152507）"
BUYER = "国网湖北省电力有限公司"
AGENT = "湖北正信电力工程咨询有限公司"
DEADLINE = "2026 年 1 月 28 日 9 时 00 分"
SIGN_DATE = "2026 年 1 月 26 日"
VALIDITY_DAYS = 90
TAX_DEFAULT = 13
WARRANTY_YEARS = 3
DELIVERY_PLACE = "湖北省武汉市江汉区  施工现场地面交货"
# 区号 → 本地号码位数（027 为 8 位，湖北地市为 7 位）
AREA_CODE = {"华中": ("027", 8), "襄阳": ("0710", 7), "宜昌": ("0717", 7),
             "荆州": ("0716", 7), "黄石": ("0714", 7), "恩施": ("0718", 7)}

# 营业执照登记机关（按注册地区级市场监督管理局）
AUTHORITY = {"华中": "武汉市江汉区市场监督管理局", "襄阳": "襄阳市樊城区市场监督管理局",
             "宜昌": "宜昌市伍家岗区市场监督管理局", "荆州": "荆州市沙市区市场监督管理局",
             "黄石": "黄石市下陆区市场监督管理局", "恩施": "恩施市市场监督管理局"}

# 三体系同一家认证机构发证，是制造企业常见做法
CERT_BODY = "中泰联合认证有限公司"

# 项目人员姓名池（按家确定性取用，避免六家人员雷同）
NAMES = ["李承志", "张宏图", "杨立诚", "黄敏行", "徐方正", "高文远", "范启明", "彭书翰",
         "董继先", "傅安然", "卢仲达", "崔亦农", "章守拙", "苏景行", "柯允中", "万澄之",
         "邵维新", "洪长卿", "凌致远", "楼伯谦", "关慕之", "聂连城", "游允升", "滕季平",
         "诸葛明诚", "苗青野", "霍立夫", "蓝景熙", "臧守一", "简仲容"]

# 已完工业绩（按家定制：项目、规模、时间各不相同；单项金额均能支撑本分标体量）
REFS = {
    "HZ": [("220kV 先锋输变电工程电缆隧道在线监测系统", "武汉供电公司", "6 套 / 1,286 万元", "2024-09"),
           ("110kV 王家墩商务区电缆隧道综合监控系统", "武汉供电公司", "4 套 / 936 万元", "2023-12"),
           ("220kV 江北变电缆隧道光纤测温及视频监控", "武汉供电公司", "3 套 / 618 万元", "2025-06")],
    "XY": [("220kV 檀溪变电缆隧道在线监测系统", "襄阳供电公司", "3 套 / 742 万元", "2024-05"),
           ("110kV 长虹路电缆隧道综合监控改造", "襄阳供电公司", "2 套 / 486 万元", "2023-08"),
           ("220kV 邓城变电缆隧道环境监测系统", "襄阳供电公司", "2 套 / 395 万元", "2025-04")],
    "YC": [("220kV 磨基山变电缆隧道在线监测系统", "宜昌供电公司", "8 套 / 1,845 万元", "2024-11"),
           ("220kV 白洋变电缆隧道综合监控系统", "宜昌供电公司", "5 套 / 1,120 万元", "2023-10"),
           ("110kV 东山隧道光纤测温及应急通话系统", "宜昌供电公司", "4 套 / 826 万元", "2025-08")],
    "JZ": [("220kV 沙东变电缆隧道在线监测系统", "荆州供电公司", "3 套 / 936 万元", "2024-07"),
           ("110kV 江津东路电缆隧道综合监控改造", "荆州供电公司", "2 套 / 512 万元", "2025-05"),
           ("110kV 荆州开发区隧道环境监测系统", "荆州供电公司", "2 套 / 368 万元", "2023-11")],
    "HS": [("220kV 磁湖变电缆隧道在线监测系统", "黄石供电公司", "3 套 / 868 万元", "2024-04"),
           ("110kV 团城山隧道光纤测温系统", "黄石供电公司", "2 套 / 445 万元", "2025-07"),
           ("110kV 下陆工业园电缆隧道监控改造", "黄石供电公司", "1 套 / 312 万元", "2023-09")],
    "ES": [("110kV 舞阳变电缆隧道在线监测系统", "恩施供电公司", "3 套 / 786 万元", "2024-09"),
           ("110kV 龙凤坝隧道综合监控系统", "恩施供电公司", "2 套 / 516 万元", "2025-10"),
           ("220kV 旗峰坝变电缆隧道环境监测系统", "恩施供电公司", "2 套 / 438 万元", "2023-12")],
}

# 在建项目（同样按家定制，与已完工业绩不重复）
ONGOING = {
    "HZ": [("220kV 沙东变电站综合监控系统", "荆州供电公司", "2 套 / 452 万元", "2026-03"),
           ("110kV 汉正街隧道环境监测系统", "武汉供电公司", "1 套 / 286 万元", "2026-05")],
    "XY": [("110kV 樊城中心区电缆隧道监控系统", "襄阳供电公司", "1 套 / 238 万元", "2026-04")],
    "YC": [("220kV 顾家店变电缆隧道监控系统", "宜昌供电公司", "3 套 / 675 万元", "2026-05"),
           ("110kV 猇亭隧道在线监测系统", "宜昌供电公司", "2 套 / 418 万元", "2026-06")],
    "JZ": [("220kV 楚都变电缆隧道监控系统", "荆州供电公司", "1 套 / 296 万元", "2026-04")],
    "HS": [("220kV 阳新变电缆隧道监控系统", "黄石供电公司", "1 套 / 236 万元", "2026-03")],
    "ES": [("220kV 恩施东变电缆隧道监控系统", "恩施供电公司", "1 套 / 342 万元", "2026-05")],
}

# 业绩备注按家与序位轮换，避免六家措辞一字不差
REF_NOTE = ["已通过竣工验收，运行正常", "已投运，无质量投诉",
            "验收合格，获业主单位书面认可"]

# 真实货物清单（网省采购申请号 / 包号 / 项目名称 / 单位 / 数量 / 首批交货 / 含税限价元）
ITEMS = [
    {"no": "100034915900360", "pkg": "包1（HB100）", "qty": 1, "unit": "套",
     "desc": "线路在线监测装置,电缆隧道在线监测系统",
     "project": "武汉先锋220千伏输变电工程（江北—王家墩Ⅰ、Ⅱ回π入先锋）",
     "deliver": "2026-04-20", "cap": 10000000},
    {"no": "100035912200010", "pkg": "包2（HB200）", "qty": 1, "unit": "套",
     "desc": "线路在线监测装置,电缆隧道在线监测系统",
     "project": "国网湖北武汉供电公司220kV巡鲇一回隧道综合监控系统升级",
     "deliver": "2026-06-29", "cap": 4533100},
    {"no": "100035912500010", "pkg": "包2（HB200）", "qty": 1, "unit": "套",
     "desc": "线路在线监测装置,电缆隧道在线监测系统",
     "project": "国网湖北武汉供电公司220kV关康等电缆隧道综合监控系统改造",
     "deliver": "2026-06-29", "cap": 340000},
    {"no": "100035917800010", "pkg": "包2（HB200）", "qty": 1, "unit": "套",
     "desc": "线路在线监测装置,电缆隧道在线监测系统",
     "project": "国网湖北武汉供电公司220kV巡鲇一回电缆隧道（黄家湖二期）",
     "deliver": "2026-06-29", "cap": 1821200},
]
CAP_SUM = sum(i["cap"] for i in ITEMS)     # 16694300 含税

# 剧本：每份文件只改该改的项，其余保持一致，保证逐条可归因。
# 单位名称 / 法人 / 代理人 / 地址 / 区划码均为虚构，但形态与真实营业执照一致：
# 名称可连读、区划码对应真实行政区、信用代码与身份号码校验位可验。
BIDDERS = [
    {"code": "HZ", "short": "华中", "name": "华中电力监测技术（湖北）有限公司",
     "legal": "陈立群", "legal_birth": "1968-05-12", "legal_id": idno("42010319680512401"),
     "agent_person": "刘振宇", "agent_birth": "1985-03-19", "agent_id": idno("42010319850319401"),
     "agent_title": "市场部经理",
     "seal_name": "华中电力监测技术（湖北）有限公司",
     "addr": "湖北省武汉市江汉区江兴路 8 号", "region": "420103",
     "uscc": uscc("91420103MA4K8N2P3"), "found": "2006-03-14",
     "capital": "5000 万元", "staff": 268, "tech_staff": 101,
     "tel": "027-8336 7120", "email": "hzjc@hz-powermon.com.cn",
     "bank": "中国工商银行股份有限公司武汉江汉支行",
     "acct": "3202 0031 0920 0186 442",
     "auditor": "湖北中信会计师事务所（特殊普通合伙）",
     "seal_ok": True, "validity": 90, "tax": 13, "ratio": 0.9000,
     "deliver_note": "满足",
     "expect": "全合规（对照组）", "defect": None,
     "note": "无缺陷。用来证明这套判定不是「逢标必否」"},

    {"code": "XY", "short": "襄阳", "name": "襄阳汉江开关设备有限公司",
     "legal": "孙茂林", "legal_birth": "1972-11-03", "legal_id": idno("42060619721103335"),
     "agent_person": "马继东", "agent_birth": "1981-06-27", "agent_id": idno("42060619810627335"),
     "agent_title": "营销部经理",
     "seal_name": "襄阳汉江电力设备有限公司",
     "addr": "湖北省襄阳市樊城区长虹路 156 号", "region": "420606",
     "uscc": uscc("91420606MA48T7QJ6"), "found": "2011-07-05",
     "capital": "3000 万元", "staff": 156, "tech_staff": 58,
     "tel": "0710-3276 480", "email": "xyhj-switch@xyhj-switch.com.cn",
     "bank": "中国建设银行股份有限公司襄阳樊城支行",
     "acct": "4200 1623 5080 5301 8874",
     "auditor": "襄阳正源联合会计师事务所",
     "seal_ok": False, "validity": 90, "tax": 13, "ratio": 0.9315,
     "deliver_note": "满足",
     "expect": "违规-电子签章名称与投标人不是同一人", "defect": "否决情形序号 4",
     "note": "签章名称「襄阳汉江电力设备有限公司」≠ 投标人「襄阳汉江开关设备有限公司」"},

    {"code": "YC", "short": "宜昌", "name": "宜昌三峡输变电设备有限公司",
     "legal": "赵鹏举", "legal_birth": "1975-02-28", "legal_id": idno("42050319750228401"),
     "agent_person": "何晓峰", "agent_birth": "1983-09-14", "agent_id": idno("42050319830914401"),
     "agent_title": "项目部经理",
     "seal_name": "宜昌三峡输变电设备有限公司",
     "addr": "湖北省宜昌市伍家岗区东山大道 92 号", "region": "420503",
     "uscc": uscc("91420503MA48K3XL2"), "found": "2009-11-20",
     "capital": "8000 万元", "staff": 412, "tech_staff": 163,
     "tel": "0717-6351 902", "email": "yc-business@sxpower-sb.com.cn",
     "bank": "中国银行股份有限公司宜昌伍家岗支行",
     "acct": "5713 5806 2891 0043 77",
     "auditor": "宜昌三峡会计师事务有限责任公司",
     "seal_ok": True, "validity": 90, "tax": 13, "ratio": 0.8950,
     "deliver_note": "满足",
     "override": {"100035912200010": 4600000},
     "expect": "违规-单条行项目含税报价超最高限价", "defect": "否决情形序号 10",
     "note": "巡鲇一回行报含税 4600000，超该行限价 4533100 共 66900；"
             "但标包合计仍低于限价合计，只比总额抓不到"},

    {"code": "JZ", "short": "荆州", "name": "荆州楚元智能装备有限公司",
     "legal": "周文彬", "legal_birth": "1980-07-16", "legal_id": idno("42100219800716401"),
     "agent_person": "邹立新", "agent_birth": "1979-12-05", "agent_id": idno("42100219791205401"),
     "agent_title": "商务部经理",
     "seal_name": "荆州楚元智能装备有限公司",
     "addr": "湖北省荆州市沙市区江津东路 41 号", "region": "421002",
     "uscc": uscc("91421002MA48W6FJ0"), "found": "2013-05-28",
     "capital": "2000 万元", "staff": 98, "tech_staff": 39,
     "tel": "0716-8214 733", "email": "jzcy-bid@chuyuan-ie.com.cn",
     "bank": "中国农业银行股份有限公司荆州沙市支行",
     "acct": "1702 0104 0018 926",
     "auditor": "荆州楚信会计师事务所（普通合伙）",
     "seal_ok": True, "validity": 60, "tax": 13, "ratio": 0.8630,
     "deliver_note": "满足",
     "expect": "违规-投标有效期不足 90 日", "defect": "否决情形序号 16",
     "note": "投标函附录承诺有效期 60 日历天，前附表 3.3.1 要求 90 日"},

    {"code": "HS", "short": "黄石", "name": "黄石磁湖电力科技有限公司",
     "legal": "吴兴国", "legal_birth": "1971-09-24", "legal_id": idno("42020419710924401"),
     "agent_person": "郑海涛", "agent_birth": "1987-01-30", "agent_id": idno("42020419870130401"),
     "agent_title": "销售部经理",
     "seal_name": "黄石磁湖电力科技有限公司",
     "addr": "湖北省黄石市下陆区杭州东路 22 号", "region": "420204",
     "uscc": uscc("91420204MA48Y2RD9"), "found": "2015-09-02",
     "capital": "1200 万元", "staff": 74, "tech_staff": 31,
     "tel": "0714-6318 425", "email": "hs-cihu@cihupower.com.cn",
     "bank": "中国邮政储蓄银行股份有限公司黄石下陆支行",
     "acct": "9430 0201 0089 761 28",
     "auditor": "黄石华信联合会计师事务所",
     "seal_ok": True, "validity": 90, "tax": 11, "ratio": 0.9180,
     "deliver_note": "满足",
     "expect": "违规-增值税税率不在法定税率集合", "defect": "否决情形序号 17",
     "note": "填报增值税税率 11%，不在 13/9/6/3/1/0 之内"},

    {"code": "ES", "short": "恩施", "name": "恩施清江自动化设备有限公司",
     "legal": "王世昌", "legal_birth": "1983-04-08", "legal_id": idno("42280119830408401"),
     "agent_person": "覃永福", "agent_birth": "1976-10-11", "agent_id": idno("42280119761011401"),
     "agent_title": "区域经理",
     "seal_name": "恩施清江自动化设备有限公司",
     "addr": "湖北省恩施市舞阳大道 178 号", "region": "422801",
     "uscc": uscc("91422801MA48P5GH7"), "found": "2017-04-11",
     "capital": "1000 万元", "staff": 63, "tech_staff": 26,
     "tel": "0718-8216 509", "email": "es-qj@qjauto-en.com.cn",
     "bank": "中国农业银行股份有限公司恩施舞阳支行",
     "acct": "1780 0104 0021 335",
     "auditor": "恩施清源会计师事务所",
     "seal_ok": True, "validity": 90, "tax": 13, "ratio": 0.8470,
     "deliver_note": "偏差", "deliver_first": "2026-07-15",
     "expect": "违规-包1 交货期不满足且招标人不能接受", "defect": "否决情形序号 7",
     "note": "承诺包1 首批交货 2026-07-15，货物清单要求 2026-04-20，逾期 86 天；"
             "同时在技术偏差表中如实列明该偏差（未隐瞒，属响应性不符而非虚假投标）"},
]

# 技术规范书真实参数（逐条取自规范书 T01~T06 表；带 * 为重要参数，共 21 项，
# 上一版只覆盖 12 项，漏了存储温度/工作温度/硬件接口/录像分辨率/网络安全/双 BIOS/
# 存储模式/人数统计/智能分析/视频内容保护——漏项在评标中是直接扣分点。）
TECH_PARAMS = [
    ("1", "监测范围*", ">24km", "≥ 32km"),
    ("2", "电缆导体温度计算精度*", "≤±2.0℃", "≤±1.5℃"),
    ("3", "上位机系统响应时间*", "<400ms", "≤ 280ms"),
    ("4", "电缆动态瓶颈点跟踪数", "≥24 个", "≥ 32 个"),
    ("5", "报警级数", "≥3", "4 级（预警/告警/严重/紧急）"),
    ("6", "DTS 测量距离*", "8km/2km", "10km/4km"),
    ("7", "DTS 单通道测量时间*", "10s（20km、温度分辨率＜1℃）", "8.6s"),
    ("8", "DTS 通道数*", "8 通道/2 通道", "12 通道/4 通道"),
    ("9", "DTS 定位精度*", "±1m", "±0.8m"),
    ("10", "DTS 存储温度*", "-10℃～+85℃", "-20℃～+85℃"),
    ("11", "DTS 工作温度*", "-10℃～+60℃", "-20℃～+70℃"),
    ("12", "测温光缆纤芯数*", "2", "2"),
    ("13", "测温光缆模式*", "62.5/125μm 多模", "62.5/125μm 多模"),
    ("14", "测温光缆衰减", "＜2.4dB/km@850nm；＜0.6dB/km@1330nm",
     "2.1dB/km@850nm；0.52dB/km@1330nm"),
    ("15", "网络视频输入*", "可接入≥64 路 1080P", "72 路 1080P"),
    ("16", "设备硬件接口*",
     "16 个硬盘一对一指示灯、RUN/ALM/NET 指示灯、两个解码卡指示灯",
     "完全具备：16 路硬盘一对一指示灯、RUN/ALM/NET 指示灯、2 个解码卡指示灯"),
    ("17", "录像分辨率*", "5MP/3MP/1080p/UXGA/720p/VGA/4CIF/DCIF/2CIF/CIF/QCIF",
     "全部支持，最高 5MP"),
    ("18", "网络安全*", "支持 UNP 内外网穿越，支持 IPv6",
     "支持 UNP 内外网穿越，支持 IPv6"),
    ("19", "设备可靠性*", "支持双 BIOS 模式，主 BIOS 失效可从备份启动",
     "支持双 BIOS，主 BIOS 失效自动切换备份启动"),
    ("20", "摄像机有效像素*", "≥400 万", "400 万（2688×1520）"),
    ("21", "摄像机存储模式*", "支持 IPSAN 或 ISCSI 直存双路传输",
     "支持 IPSAN 与 ISCSI 直存双路传输"),
    ("22", "摄像机人数统计*", "支持不规则区域实时人数统计并经 OSD 显示、按间隔上报",
     "支持，可设置不规则区域并按 1~60min 间隔上报"),
    ("23", "摄像机智能分析功能*", "支持区域入侵检测，可设阈值与滞留报警",
     "支持区域入侵、越界、滞留检测，可设阈值"),
    ("24", "摄像机视频内容保护*", "码流随机混淆，非授权终端无法正常播放",
     "支持码流随机混淆与加密存储"),
    ("25", "环境温度（使用条件）", "最高 +40℃ / 最低 -20℃",
     "设备适应 -20℃～+70℃，覆盖工程所在地 -20℃～+40℃"),
    ("26", "环境相对湿度（使用条件）", "≤90%（25℃）",
     "设备工作湿度 0%～95%（无凝露），覆盖 ≤90% 要求"),
]

# 非关键数值按家微调（三家以上取值不同），避免六家技术册一个模子；
# 微调后仍全部满足规范书要求，不引入新的负偏差。
TECH_ADJ = {
    "1": ["≥ 28km", "≥ 32km", "≥ 36km", "≥ 40km"],
    "4": ["≥ 28 个", "≥ 32 个", "≥ 36 个"],
    "6": ["10km/4km", "12km/4km", "8km/3km"],
    "8": ["12 通道/4 通道", "16 通道/4 通道", "10 通道/2 通道"],
    "15": ["64 路 1080P", "72 路 1080P", "80 路 1080P"],
}

BID_ORDER = ["HZ", "XY", "YC", "JZ", "HS", "ES"]


def tech_rows(b):
    """技术参数响应表：带 * 项全部覆盖，非关键数值按家轮换取值。"""
    k = BID_ORDER.index(b["code"]) if b["code"] in BID_ORDER else 0
    out = []
    for no, name, req, resp in TECH_PARAMS:
        if no in TECH_ADJ:
            cand = TECH_ADJ[no]
            resp = cand[(k + len(no)) % len(cand)]
        out.append([no, name, req, resp])
    return out


# 单价分析表成本构成（占未含税单价比例）
# 六家用同一组比例，等于自认同一套成本模型 —— 评标专家对照六份就能看出来。
# 按家扰动后归一化到 100%，末项金额兜底，保证逐项相加严格等于未含税单价。
COST_MIX = [
    ("设备本体", 0.52), ("配套附件与材料", 0.14), ("系统软件与组态", 0.09),
    ("运输与仓储", 0.03), ("现场安装与调试", 0.11), ("技术服务与培训", 0.04),
    ("检验试验与验收", 0.03), ("其他（管理、财务费用等）", 0.04),
]


def cost_mix(code):
    """返回 [(项名, 占比)]，占比合计恰为 1.0000。"""
    raw = []
    for k, (name, r) in enumerate(COST_MIX):
        if k == 0:
            raw.append([name, r])
        else:
            raw.append([name, r * (1 + (sd(code, "cm", k) % 81 - 40) / 1000.0)])
    tot = sum(x[1] for x in raw)
    out, acc = [], 0.0
    for i, (name, r) in enumerate(raw):
        v = round(1.0 - acc, 4) if i == len(raw) - 1 else round(r / tot, 4)
        acc = round(acc + v, 4)
        out.append((name, v))
    return out


# ---------------------------------------------------------------- 排版工具
def cn(run, name="宋体", size=None, bold=None):
    run.font.name = name
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = rpr.makeelement(qn("w:rFonts"), {})
        rpr.append(rfonts)
    rfonts.set(qn("w:eastAsia"), name)
    rfonts.set(qn("w:ascii"), name)
    rfonts.set(qn("w:hAnsi"), name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    return run


def para(doc, text="", size=10.5, bold=False, align=None, first_indent=True,
         space_after=4, name="宋体"):
    p = doc.add_paragraph()
    r = p.add_run(text)
    cn(r, name, size, bold)
    if align is not None:
        p.alignment = align
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.line_spacing = 1.5
    if first_indent and text:
        pf.first_line_indent = Pt(21)
    return p


def h1(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    cn(r, "黑体", 14, True)
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(6)
    return p


def h2(doc, text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    cn(r, "黑体", 11.5, True)
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(4)
    return p


def kv(doc, k, v, w=14):
    p = doc.add_paragraph()
    r1 = p.add_run(k + "：")
    cn(r1, "宋体", 10.5, True)
    r2 = p.add_run(str(v))
    cn(r2, "宋体", 10.5)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.line_spacing = 1.4
    return p


def table(doc, header, rows, size=8.5, aligns=None, header_fill="DDEBF7"):
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, hd in enumerate(header):
        cell = t.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cn(p.add_run(hd), "宋体", size, True)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            cn(p.add_run(str(v)), "宋体", size)
            if aligns and i < len(aligns):
                p.alignment = aligns[i]
            elif i > 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return t


def money(v):
    return "{:,.2f}".format(v)


DIGITS = "零壹贰叁肆伍陆柒捌玖"
UNITS = ["", "拾", "佰", "仟"]
BIG = ["", "万", "亿", "万亿"]


def rmb_upper(amount):
    """人民币大写。整数到亿级，角分到分。"""
    amount = round(float(amount) + 1e-9, 2)
    int_part = int(amount)
    cent = int(round((amount - int_part) * 100))
    jiao, fen = divmod(cent, 10)

    if int_part == 0:
        head = "零元"
    else:
        groups, n = [], int_part
        while n > 0:
            groups.append(n % 10000)
            n //= 10000
        out = ""
        for idx in range(len(groups) - 1, -1, -1):
            g = groups[idx]
            if g == 0:
                if out and not out.endswith("零"):
                    out += "零"
                continue
            seg, zero = "", False
            for pos in range(3, -1, -1):
                d = (g // (10 ** pos)) % 10
                if d == 0:
                    zero = True
                else:
                    if zero and seg:
                        seg += "零"
                    zero = False
                    seg += DIGITS[d] + UNITS[pos]
            out += seg + BIG[idx]
        head = out.rstrip("零") + "元"

    if jiao == 0 and fen == 0:
        tail = "整"
    else:
        tail = ""
        if jiao:
            tail += DIGITS[jiao] + "角"
        elif int_part:
            tail += "零"
        if fen:
            tail += DIGITS[fen] + "分"
        else:
            tail += "整" if not jiao else ""
    return head + tail


# ---------------------------------------------------------------- 报价计算
def price_rows(b):
    """含税报价 = 含税限价×折扣；未含税 = 含税÷(1+税率)。三处金额同源。"""
    rate = b["tax"] / 100.0
    out = []
    for it in ITEMS:
        cap = it["cap"] * it["qty"]
        override = (b.get("override") or {}).get(it["no"])
        if override:
            inc_unit = override
        else:
            # 真实报价不会把总下浮率等比例摊到每一行：行级在 -0.9%~+0.9% 内浮动，
            # 且报到百元位（投标工具按元录入，实务上按整数报）。
            d = (sd(b["code"], it["no"]) % 181 - 90) / 10000.0
            inc_unit = int(round(it["cap"] * (b["ratio"] + d) / 100.0)) * 100
        inc_amt = inc_unit * it["qty"]
        exc_unit = round(inc_unit / (1 + rate), 2)
        exc_amt = round(exc_unit * it["qty"], 2)
        out.append({"no": it["no"], "desc": it["desc"], "project": it["project"],
                    "pkg": it["pkg"], "qty": it["qty"], "unit": it["unit"],
                    "cap": it["cap"], "inc_unit": inc_unit, "inc_amt": inc_amt,
                    "exc_unit": exc_unit, "exc_amt": exc_amt, "rate": b["tax"]})
    return out


def totals(rows):
    return (round(sum(r["exc_amt"] for r in rows), 2),
            round(sum(r["inc_amt"] for r in rows), 2))


# ---------------------------------------------------------------- 封面 / 页眉页脚
def cover(doc, b, volume, subtitle, note):
    warn = doc.add_paragraph()
    warn.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = warn.add_run("【合成演示数据 · 非真实投标文件 · 仅用于系统验证】")
    cn(r, "宋体", 9, True)
    r.font.color.rgb = RGBColor(0xC0, 0x00, 0x00)

    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p.add_run(BATCH), "宋体", 16, True)
    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p2.add_run(TENDER_NO), "宋体", 13, True)

    for _ in range(2):
        doc.add_paragraph()
    p3 = doc.add_paragraph()
    p3.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p3.add_run("投 标 文 件"), "黑体", 30, True)
    p4 = doc.add_paragraph()
    p4.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(p4.add_run("（%s）" % volume), "黑体", 20, True)

    for _ in range(2):
        doc.add_paragraph()
    for line in subtitle:
        pp = doc.add_paragraph()
        pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cn(pp.add_run(line), "宋体", 12)

    for _ in range(4):
        doc.add_paragraph()
    for k, v in (("投 标 人", b["name"] + "（电子签章）"),
                 ("法定代表人", b["legal"]),
                 ("日    期", SIGN_DATE)):
        pp = doc.add_paragraph()
        pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cn(pp.add_run("%s：%s" % (k, v)), "宋体", 12, True)

    doc.add_page_break()
    pn = doc.add_paragraph()
    pn.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cn(pn.add_run(note), "宋体", 9)
    pn.runs[0].font.color.rgb = RGBColor(0x80, 0x80, 0x80)


def _field(paragraph, code):
    """插入 Word 域（PAGE / NUMPAGES），保证页码在 Word 中随分页变化。"""
    from docx.oxml import OxmlElement
    run = paragraph.add_run()
    f1 = OxmlElement("w:fldChar")
    f1.set(qn("w:fldCharType"), "begin")
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = code
    f2 = OxmlElement("w:fldChar")
    f2.set(qn("w:fldCharType"), "end")
    run._r.append(f1)
    run._r.append(it)
    run._r.append(f2)
    cn(run, "宋体", 8)


def add_header(doc, b, volume):
    sec = doc.sections[0]
    hp = sec.header.paragraphs[0]
    hp.text = ""
    cn(hp.add_run("%s   %s  %s   %s" % (BATCH, SECTION, b["name"], volume)), "宋体", 8)
    hp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp = sec.footer.paragraphs[0]
    fp.text = ""
    cn(fp.add_run("合成演示数据·非真实投标文件　　第 "), "宋体", 8)
    _field(fp, "PAGE")
    cn(fp.add_run(" 页 共 "), "宋体", 8)
    _field(fp, "NUMPAGES")
    cn(fp.add_run(" 页"), "宋体", 8)
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER


# ---------------------------------------------------------------- 价格文件
def build_price(b, rows):
    doc = Document()
    doc.styles["Normal"].font.name = "宋体"
    doc.styles["Normal"].font.size = Pt(10.5)
    add_header(doc, b, "价格文件")
    cover(doc, b, "价格文件",
          ["分标编号：%s" % SECTION,
           "包    号：包1（HB100）／包2（HB200）",
           "招标人：%s" % BUYER],
          "本册按招标文件第六章「投标文件格式」价格文件部分编制；"
          "投标函、已标价货物清单行报价暨投标报价汇总表、货物清单单价分析表同源同数。")

    exc_total, inc_total = totals(rows)

    h1(doc, "目  录")
    for i, t in enumerate(["一、投标函", "二、投标函附录", "三、已标价货物清单行报价暨投标报价汇总表",
                           "四、开标一览表", "五、货物清单单价分析表", "六、价格文件签署页"], 1):
        para(doc, t, 10.5, False, first_indent=False, space_after=2)
    doc.add_page_break()

    # 一、投标函
    h1(doc, "一、投标函")
    para(doc, "致：%s" % BUYER, first_indent=False)
    para(doc, "1. 我方已仔细研究 %s 招标文件（招标编号：%s，分标编号：%s）的全部内容，"
              "包括澄清与修改文件，愿意按照招标文件的约定承担本分标的供货、安装指导、"
              "调试配合、技术服务及质保期服务。"
              % (TENDER_NO, BATCH, SECTION))
    para(doc, "2. 我方投标总价为：人民币 %s（¥%s），其中未含税价人民币 %s 元，"
              "增值税税率 %d%%，税额人民币 %s 元。分项报价详见本册"
              "《已标价货物清单行报价暨投标报价汇总表》及随附《分项报价表》。"
              % (rmb_upper(inc_total), money(inc_total), money(exc_total), b["tax"],
                 money(round(inc_total - exc_total, 2))))
    para(doc, "3. 我方承诺投标有效期为自投标截止日起 %d 日历天，在此期间本投标文件始终对我方具有约束力。"
              % b["validity"])
    para(doc, "4. 我方已按招标文件要求提交全部投标文件，并承诺所提交的资料真实、准确、完整。"
              "如经查实存在虚假，愿承担相应法律责任，并接受招标人依据招标文件作出的处理。")
    para(doc, "5. 我方理解，贵方不承诺将合同授予最低报价的投标人，并保留招标文件规定的各项权利。")
    para(doc, "6. 我方理解并接受招标文件关于履约担保的约定，如获中标，将在规定期限内"
              "提交履约保证金并签订合同。", first_indent=True)
    para(doc, "7. 我方联系方式：联系人 %s，电话 %s，电子邮箱 %s。"
              % (b["agent_person"], b["tel"],
                 b["code"].lower()))
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run("投 标 人：%s（电子签章）" % b["seal_name"]), "宋体", 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run("法定代表人或其委托代理人：%s" % b["agent_person"]), "宋体", 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run(SIGN_DATE), "宋体", 10.5)
    doc.add_page_break()

    # 二、投标函附录
    h1(doc, "二、投标函附录")
    para(doc, "下表为我方对招标文件主要商务条款的响应，与投标函具有同等效力。", first_indent=False)
    app = [
        ("投标有效期", "自投标截止日起 %d 日历天" % b["validity"], "自投标截止日起 90 日",
         "满足" if b["validity"] >= VALIDITY_DAYS else "不满足"),
        ("投标保证金", "本项目免收投标保证金", "前附表 3.4.1：免收", "满足"),
        ("交货期（包1）",
         "2026-07-15" if b.get("deliver_first") else "2026-04-20 前完成首批交货",
         "货物清单：首批 2026-04-20", "满足" if not b.get("deliver_first") else "偏差"),
        ("交货期（包2）", "2026-06-29 前完成首批交货，2026-06-30 前完成末批",
         "货物清单：首批 2026-06-29、末批 2026-06-30", "满足"),
        ("交货地点与方式", DELIVERY_PLACE, "货物清单：湖北省武汉市江汉区，施工现场地面交货", "满足"),
        ("质保期", "系统投运后 %d 年" % WARRANTY_YEARS, "技术规范书 1.1.4：投运后 3 年", "满足"),
        ("增值税税率", "%d%%" % b["tax"], "按国家规定税率填报", "按实填报"),
        ("联合体投标", "不采用联合体，独立投标", "招标公告 3.2：不接受联合体", "满足"),
        ("备选投标方案", "未递交备选方案，仅一个报价", "前附表 3.6.1：不允许", "满足"),
        ("分包与外购", "不分包；外购件由我方承担质量责任", "前附表 1.10.1：不允许分包", "满足"),
        ("电子签章", "商务文件、技术文件整体电子签章已加盖", "前附表 3.7.3(A)(1)", "满足"),
        ("偏差情况", "技术偏差 %s 项，商务偏差 %s 项" % ("1" if b.get("deliver_first") else "0", "0"),
         "须在偏差表中列明", "已列明"),
    ]
    table(doc, ["条款名称", "我方响应", "招标文件要求", "响应结论"], app, size=8.5,
          aligns=[WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT,
                  WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER])
    doc.add_page_break()

    # 三、已标价货物清单行报价暨投标报价汇总表
    h1(doc, "三、已标价货物清单行报价暨投标报价汇总表")
    para(doc, "分标编号：%s　　投标人：%s" % (SECTION, b["name"]),
         first_indent=False, size=9)
    para(doc, "金额单位：人民币元。投标工具「已标价货物清单」按万元填报，"
              "本表按 1 万元 = 10000 元折算列示，两者数值一致。",
         first_indent=False, size=9)
    body = []
    for i, r in enumerate(rows, 1):
        body.append([i, r["no"], r["desc"], r["pkg"], r["unit"], r["qty"],
                     money(r["exc_unit"]), money(r["exc_amt"]), "%d%%" % r["rate"],
                     money(r["inc_unit"]), money(r["inc_amt"])])
    body.append(["合计", "—", "—", "—", "—", sum(r["qty"] for r in rows),
                 "—", money(exc_total), "%d%%" % b["tax"], "—", money(inc_total)])
    table(doc, ["序号", "网省采购申请号", "物料描述", "包号", "单位", "数量",
                "未含税单价", "未含税合价", "税率", "含税单价", "含税合价"],
          body, size=7.5)
    para(doc, "", first_indent=False, space_after=2)
    kv(doc, "投标总价（含税，小写）", "¥ %s 元" % money(inc_total))
    kv(doc, "投标总价（含税，大写）", rmb_upper(inc_total))
    kv(doc, "其中：未含税价", "¥ %s 元" % money(exc_total))
    kv(doc, "　　　增值税税额", "¥ %s 元（税率 %d%%）" % (money(round(inc_total - exc_total, 2)), b["tax"]))
    kv(doc, "最高限价（含税合计）", "¥ %s 元" % money(CAP_SUM))
    over = [r["no"] for r in rows if r["inc_amt"] > r["cap"] * r["qty"]]
    kv(doc, "超最高限价的行项目", "、".join(over) if over else "无")
    doc.add_page_break()

    # 四、开标一览表
    h1(doc, "四、开标一览表")
    para(doc, "注：本表含税合价即开标唱标价，与投标函报价、已标价货物清单三者一致。",
         first_indent=False, size=9)
    ol = [[i, r["pkg"], r["desc"], r["unit"], r["qty"],
           money(r["exc_unit"]), money(r["exc_amt"]), "%d%%" % r["rate"],
           money(r["inc_unit"]), money(r["inc_amt"])]
          for i, r in enumerate(rows, 1)]
    table(doc, ["序号", "包号", "货物（功能规格）描述", "单位", "数量",
                "未含税单价", "未含税合价", "税率(%)", "含税单价", "含税合价"],
          ol, size=7.5)
    para(doc, "合计人民币（小写）：%s 元　　　合计人民币（大写）：%s"
         % (money(inc_total), rmb_upper(inc_total)), first_indent=False, size=9)
    para(doc, "投标保证金：本项目免收。", first_indent=False, size=9)
    doc.add_page_break()

    # 五、货物清单单价分析表
    h1(doc, "五、货物清单单价分析表")
    para(doc, "以行项目 100034915900360（含税报价 %s 元／套）为例列示成本构成，"
              "其余行项目按同类产品结构分列，从略。"
         % money(rows[0]["inc_unit"]), first_indent=False)
    base = rows[0]["exc_unit"]
    cm = cost_mix(b["code"])
    mix, acc = [], 0.0
    for i, (name, r) in enumerate(cm, 1):
        amt = round(base - acc, 2) if i == len(cm) else round(base * r, 2)
        acc = round(acc + amt, 2)
        mix.append([i, name, "%.2f%%" % (r * 100), money(amt)])
    mix.append(["合计", "未含税单价", "100.00%", money(base)])
    table(doc, ["序号", "成本构成项", "占未含税单价比例", "金额（元/套）"], mix, size=8.5)
    para(doc, "说明：上述单价为运至交货地点并完成安装指导、调试配合、技术服务及"
              "5 年通信费用分摊后的综合单价，不含增值税。", first_indent=False, size=9)
    doc.add_page_break()

    # 六、签署页
    h1(doc, "六、价格文件签署页")
    para(doc, "我方已逐页核对本册，确认投标函、开标一览表与已标价货物清单行报价"
              "暨投标报价汇总表三处金额一致。", first_indent=False)
    para(doc, "我方承诺：本册所报价格为一次性报价，不存在两个及以上报价，未递交备选方案。",
         first_indent=False)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run("投 标 人：%s（电子签章）" % b["seal_name"]), "宋体", 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run("签章验证：%s" % ("验证通过" if b["seal_ok"] else "验证通过（签章主体与投标人不一致）")),
       "宋体", 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run(SIGN_DATE), "宋体", 10.5)

    path = os.path.join(OUT, "投标文件_%s_%s_价格文件.docx" % (b["short"], SECTION))
    doc.save(path)
    return path


# ---------------------------------------------------------------- 商务文件
def build_biz(b, rows):
    doc = Document()
    doc.styles["Normal"].font.name = "宋体"
    doc.styles["Normal"].font.size = Pt(10.5)
    add_header(doc, b, "商务文件")
    cover(doc, b, "商务文件",
          ["分标编号：%s" % SECTION, "包    号：包1（HB100）／包2（HB200）"],
          "本册内容包括：商务偏差表、投标人基本情况表、营业执照与资质、"
          "法定代表人身份证明与授权委托书、财务状况（2022—2024）、"
          "类似项目业绩、诉讼仲裁情况、声明与承诺。")

    h1(doc, "目  录")
    for t in ["一、商务偏差表", "二、投标人基本情况表", "三、营业执照及资质证书信息",
              "四、法定代表人（单位负责人）身份证明", "五、法定代表人授权委托书",
              "六、近年财务状况表（2022—2024）", "七、近年完成的类似项目情况表",
              "八、正在供货和新承接的项目情况表", "九、近年发生的诉讼及仲裁情况",
              "十、投标保证金说明", "十一、资格审查资料清单", "十二、资格与信用声明",
              "十三、廉洁承诺书", "十四、商务文件签署页"]:
        para(doc, t, 10.5, False, first_indent=False, space_after=2)
    doc.add_page_break()

    h1(doc, "一、商务偏差表")
    dev = []
    if b.get("deliver_first"):
        dev.append(["1", "交货期（包1）", "首批交货 2026-04-20",
                    "首批交货 2026-07-15",
                    "受产线排产周期影响，包1 首批交货较要求晚 86 天，其余条款无偏差"])
    if dev:
        table(doc, ["序号", "偏差事项", "招标文件要求", "投标文件响应", "偏差说明"], dev, size=8.5,
              aligns=[WD_ALIGN_PARAGRAPH.CENTER] + [WD_ALIGN_PARAGRAPH.LEFT] * 4)
        para(doc, "除上表列明的偏差外，我方对招标文件商务条款无其他偏差。", first_indent=False)
    else:
        para(doc, "经逐条核对招标文件商务条款，我方投标文件与招标文件要求无偏差，"
                  "本表为空表。我方确认：未在本表列明的偏离，视为我方未提出偏离。",
             first_indent=False)
    doc.add_page_break()

    h1(doc, "二、投标人基本情况表")
    info = [
        ("投标人名称", b["name"]),
        ("统一社会信用代码", b["uscc"]),
        ("纳税人识别号", b["uscc"]),
        ("法定代表人（单位负责人）", b["legal"]),
        ("注册地址", b["addr"]),
        ("成立时间", b["found"]),
        ("注册资本", b["capital"]),
        ("企业类型", "有限责任公司（自然人投资或控股）"),
        ("员工总数", "%d 人（其中技术人员 %d 人，社保参保人数 %d 人）"
                     % (b["staff"], b["tech_staff"], b["staff"] - 3)),
        ("营业范围", "电力监测设备、输变电设备、自动化装置的研发、制造、销售及技术服务；"
                     "计算机系统集成；软件开发与销售"),
        ("资质等级", "电力工程施工总承包叁级；电子与智能化工程专业承包贰级"),
        ("质量管理体系", "ISO 9001:2015（证书编号 CN-ISO-%05d）"
                         % (sd(b["code"], "iso") % 90000 + 10000)),
        ("环境/职业健康体系", "ISO 14001:2015 ／ ISO 45001:2018"),
        ("开户银行", b["bank"]),
        ("银行账号", b["acct"]),
        ("联系人／电话", "%s　%s" % (b["agent_person"], b["tel"])),
        ("电子邮箱", b["email"]),
        ("所投标段", "%s（包1、包2）" % SECTION),
        ("是否联合体", "否（招标公告 3.2 不接受联合体）"),
        ("是否代理商", "否，制造商直接投标"),
    ]
    table(doc, ["项目", "内容"], [[k, v] for k, v in info], size=9,
          aligns=[WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT])
    doc.add_page_break()

    h1(doc, "三、营业执照及资质证书信息")
    para(doc, "以下为原件扫描件的信息摘要，扫描件见商务文件附件（ECP2.0「补充文件」端口）。",
         first_indent=False, size=9)
    table(doc, ["证书名称", "编号", "发证机关", "有效期"], [
        ["营业执照", b["uscc"], AUTHORITY[b["short"]], "长期"],
        ["质量管理体系认证证书", "CN-ISO-%05d" % (sd(b["code"], "iso") % 90000 + 10000),
         CERT_BODY, "2027-06-30"],
        ["环境管理体系认证证书", "CN-EMS-%05d" % (sd(b["code"], "ems") % 90000 + 10000),
         CERT_BODY, "2027-06-30"],
        ["职业健康安全管理体系证书", "CN-OHS-%05d" % (sd(b["code"], "ohs") % 80000 + 20000),
         CERT_BODY, "2027-06-30"],
        ["型式试验报告（电缆隧道在线监测系统）",
         "XD-%d" % (20240000 + sd(b["code"], "test") % 99999),
         "电力工业电气设备质量检验测试中心", "2029-03-31"],
    ], size=8.5, aligns=[WD_ALIGN_PARAGRAPH.LEFT] * 4)
    doc.add_page_break()

    h1(doc, "四、法定代表人（单位负责人）身份证明")
    para(doc, "投标人名称：%s" % b["name"], first_indent=False)
    para(doc, "单位性质：有限责任公司　　地址：%s" % b["addr"], first_indent=False)
    para(doc, "成立时间：%s　　经营期限：长期" % b["found"], first_indent=False)
    para(doc, "姓名：%s　　性别：男　　年龄：%d　　职务：董事长兼总经理"
         % (b["legal"], age_of(b["legal_birth"])), first_indent=False)
    para(doc, "公民身份号码：%s" % b["legal_id"], first_indent=False)
    para(doc, "系 %s 的法定代表人（单位负责人）。" % b["name"], first_indent=False)
    para(doc, "特此证明。", first_indent=False)
    para(doc, "附：法定代表人身份证复印件（正反面）、营业执照复印件。", first_indent=False, size=9)
    doc.add_page_break()

    h1(doc, "五、法定代表人授权委托书")
    para(doc, "本授权委托书声明：我 %s 系 %s 的法定代表人，现授权委托 %s 为我方代理人，"
              "以我方名义参加 %s（分标编号 %s）的投标活动，代理人在开标、评标、澄清、"
              "签约过程中所签署的一切文件和处理与之有关的一切事务，我方均予承认。"
         % (b["legal"], b["name"], b["agent_person"], TENDER_NO, SECTION))
    para(doc, "代理人无转委托权。本授权委托书自签署之日起生效，有效期与投标有效期一致。", first_indent=False)
    table(doc, ["项目", "内容"], [
        ["代理人姓名", b["agent_person"]],
        ["公民身份号码", b["agent_id"]],
        ["职务", b["agent_title"]],
        ["联系电话", b["tel"]],
        ["电子邮箱", b["email"]],
    ], size=9, aligns=[WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT])
    para(doc, "", first_indent=False, space_after=2)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run("法定代表人：%s（签字）" % b["legal"]), "宋体", 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run("投标人：%s（电子签章）" % b["seal_name"]), "宋体", 10.5)
    doc.add_page_break()

    h1(doc, "六、近年财务状况表（2022—2024 年）")
    # 以人均产值定营收规模（制造业 22~30 万元/人），三年稳步增长；
    # 负债 = 资产 × 负债率，保证「负债÷资产」与表列负债率可勾稽。
    per_cap = 58.0 + (sd(b["code"], "pc") % 420) / 10.0     # 58~100 万元/人
    base_rev = round(b["staff"] * per_cap, 2)
    # 各家杠杆水平不同（±2 个百分点），逐年小幅降杠杆；六家取同一组数会露同源痕迹
    j = (sd(b["code"], "dr") % 40 - 20) / 1000.0
    dr = (0.512 + j, 0.534 + j, 0.551 + j)   # 对应 2024、2023、2022
    fin, dsum, asum = [], 0.0, 0.0
    for i, y in enumerate(("2024", "2023", "2022")):
        rev = round(base_rev / (1.0 - 0.0) ** 0, 2) if i == 0 else None
        rev = round(base_rev * (1 - i * 0.108), 2)
        asset = round(rev * (1.24 + (sd(b["code"], y) % 24) / 100.0), 2)
        debt = round(asset * dr[i], 2)
        net = round(rev * (0.071 + (sd(b["code"], "np") % 26) / 1000.0), 2)
        dsum += debt
        asum += asset
        fin.append([y, money(rev), money(net), money(asset), money(debt),
                    "%.1f%%" % (debt / asset * 100)])
    fin.append(["三年合计 / 平均资产负债率",
                money(round(base_rev * (1 + 0.892 + 0.784), 2)),
                "—", "—", "—", "%.1f%%" % (dsum / asum * 100)])
    table(doc, ["年份", "营业收入（万元）", "净利润（万元）", "资产总额（万元）",
                "负债总额（万元）", "资产负债率"], fin, size=8.5)
    para(doc, "以上数据摘自 %s 出具的 2022、2023、2024 年度审计报告"
              "（均为标准无保留意见），审计报告及财务报表附注复印件见附件。"
         % b["auditor"], first_indent=False, size=9)
    doc.add_page_break()

    h1(doc, "七、近年完成的类似项目情况表")
    projs = [[str(i), nm, "国网湖北省电力有限公司" + org, amt, dt, "已投运",
              REF_NOTE[(i - 1) % len(REF_NOTE)]]
             for i, (nm, org, amt, dt) in enumerate(REFS[b["code"]], 1)]
    table(doc, ["序号", "产品型式", "工程名称/项目单位", "数量或金额", "投运时间", "状态", "备注"],
          projs, size=8)
    para(doc, "以上业绩均附中标通知书、合同协议书及设备进场验收证书复印件；"
              "业绩时间均在投标截止日前三年内，满足招标公告专用资格要求。", first_indent=False, size=9)
    doc.add_page_break()

    h1(doc, "八、正在供货和新承接的项目情况表")
    table(doc, ["序号", "项目名称", "项目单位", "数量或金额", "约定交货", "履约状态"],
          [[str(i), nm, "国网湖北省电力有限公司" + org, amt, dt, "生产中，进度正常"]
           for i, (nm, org, amt, dt) in enumerate(ONGOING[b["code"]], 1)], size=8.5)
    para(doc, "上述在建项目不影响本分标的供货能力，我方现有产能与排产可满足本分标交货期要求"
              if not b.get("deliver_first") else
              "上述在建项目与本分标排产存在部分重叠，是我方申请延后包1 交货期的原因之一。",
         first_indent=False)
    doc.add_page_break()

    h1(doc, "九、近年发生的诉讼及仲裁情况")
    para(doc, "投标截止日前三年内，我方无因设备买卖合同纠纷败诉的情形，"
              "无被人民法院或仲裁机构作出的败诉判决、裁决。", first_indent=False)
    para(doc, "本表为空表。", first_indent=False)
    doc.add_page_break()

    h1(doc, "十、投标保证金说明")
    para(doc, "根据招标文件投标人须知前附表第 3.4.1 条，本批项目免收投标保证金，"
              "招标文件中保证金的相关要求均不适用。我方无需递交投标保证金及其证明文件。",
         first_indent=False)
    doc.add_page_break()

    h1(doc, "十一、资格审查资料清单")
    para(doc, "按招标文件 3.5 及 ECP2.0「补充文件」端口要求，逐项对照如下。",
         first_indent=False, size=9)
    table(doc, ["招标文件条款", "要求提供的资料", "本册对应位置", "提供情况"], [
        ["3.5.1", "投标人基本情况表 + 营业执照副本复印件", "第二部分、第三部分", "已提供"],
        ["3.5.1", "资质证书副本、检验或认证材料复印件", "第三部分", "已提供"],
        ["3.5.2", "经审计的财务会计报表（2022—2024 年）", "第六部分", "已提供（含审计报告）"],
        ["3.5.3", "近年完成的类似项目情况表 + 中标通知书/合同/验收证书",
         "第七部分", "已提供 3 个项目"],
        ["3.5.4", "正在供货和新承接的项目情况表 + 合同复印件", "第八部分", "已提供 1 个项目"],
        ["3.5.5", "近年发生的诉讼及仲裁情况 + 法律文书复印件", "第九部分", "空表（无此情形）"],
        ["前附表 3.5", "不接受资质业绩凭证单，须提供对应支持证明材料", "全文附件", "已按编制说明提供"],
        ["公告 3.5(8)", "国家企业信用信息公示系统查询结果（含营业执照信息、"
                       "严重违法失信名单、经营异常名录、行政处罚、清算信息）",
         "第十二部分及附件", "已提供（查询日期 2026-01-20）"],
        ["公告 3.5", "“信用中国”严重失信主体名单、失信被执行人查询截图",
         "第十二部分及附件", "已提供（查询日期 2026-01-20）"],
    ], size=8, aligns=[WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT,
                       WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.CENTER])
    doc.add_page_break()

    h1(doc, "十二、资格与信用声明")
    clauses = [
        "我方为中华人民共和国境内依法注册的法人，具有独立承担民事责任的能力，"
        "不属于招标人不具有独立法人资格的附属机构（单位）。",
        "我方未被市场监督管理机关在国家企业信用信息公示系统列入严重违法失信企业名单，"
        "未被列入经营异常名录；附查询截图（查询日期 2026-01-20）。",
        "我方未被最高人民法院在“信用中国”网站列入严重失信主体名单或失信被执行人；"
        "附查询截图（查询日期 2026-01-20）。",
        "我方及法定代表人投标截止日前三年内无行贿犯罪记录。",
        "我方投标截止日前三年内未发生重大质量问题，未因质量问题被行业主管部门行政处罚。",
        "我方未处于被责令停产停业、暂扣或吊销许可证执照、财产被接管或冻结的状态，"
        "未进入清算程序或被宣告破产。",
        "我方与本招标项目的招标人、监理人、代建人、招标代理机构不存在利害关系，"
        "不存在控股、参股关系，不存在同一法定代表人情形。",
        "我方未与其他投标人的法定代表人为同一人，与其他投标人不存在控股、管理关系。",
        "我方独立编制投标文件，未委托中介机构或中间人代行办理投标事宜。",
        "我方以制造商身份直接投标，非代理商，不存在制造商授权冲突情形。",
    ]
    for i, c in enumerate(clauses, 1):
        para(doc, "%d. %s" % (i, c))
    doc.add_page_break()

    h1(doc, "十三、廉洁承诺书")
    para(doc, "我方郑重承诺：在本项目投标及后续合同履行过程中，不向招标人、招标代理机构、"
              "评标委员会成员及其他相关工作人员提供、给予任何有价物或好处，"
              "不进行商业贿赂、不相互串通投标、不弄虚作假骗取中标。", first_indent=False)
    para(doc, "如有违反，我方接受招标人依据《国家电网有限公司供应商关系管理办法》"
              "作出的处理，并承担相应法律责任。", first_indent=False)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run("投标人：%s（电子签章）" % b["seal_name"]), "宋体", 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run(SIGN_DATE), "宋体", 10.5)
    doc.add_page_break()

    h1(doc, "十四、商务文件签署页")
    para(doc, "本册商务文件（含附件）共 %d 页，我方确认所附证书、报表、业绩、"
              "声明均真实有效。" % (28 + len(rows)), first_indent=False)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run("投 标 人：%s（电子签章）" % b["seal_name"]), "宋体", 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    if b["seal_ok"]:
        cn(p.add_run("电子签章验证：通过，签章主体与投标人一致"), "宋体", 10.5)
    else:
        cn(p.add_run("电子签章验证：签章已加盖，签章主体为「%s」，与投标人「%s」不一致"
                     % (b["seal_name"], b["name"])), "宋体", 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run(SIGN_DATE), "宋体", 10.5)

    path = os.path.join(OUT, "投标文件_%s_%s_商务文件.docx" % (b["short"], SECTION))
    doc.save(path)
    return path


# ---------------------------------------------------------------- 技术文件
def build_tech(b, rows):
    doc = Document()
    doc.styles["Normal"].font.name = "宋体"
    doc.styles["Normal"].font.size = Pt(10.5)
    add_header(doc, b, "技术文件")
    cover(doc, b, "技术文件",
          ["分标编号：%s" % SECTION, "货物名称：线路在线监测装置,电缆隧道在线监测系统"],
          "本册按招标文件第六章技术文件格式编制：技术偏差表、技术特性参数表（逐项填具体数值，"
          "不以“满足/响应”代替）、货物组件材料配置表、质保与服务承诺、生产与检测能力、"
          "认证与试验报告、项目人员、业绩文件。")

    h1(doc, "目  录")
    for t in ["一、技术偏差表", "二、技术特性参数响应表", "三、货物组件材料配置表",
              "四、系统技术方案", "五、施工组织与进度计划", "六、质量保证与风险管理",
              "七、质保期与售后服务承诺", "八、生产场地、装备与检测能力",
              "九、认证证书与型式试验报告", "十、项目人员配置", "十一、技术文件签署页"]:
        para(doc, t, 10.5, False, first_indent=False, space_after=2)
    doc.add_page_break()

    h1(doc, "一、技术偏差表")
    tdev = []
    if b.get("deliver_first"):
        tdev.append(["1", "交货期（包1 首批）", "2026-04-20", "2026-07-15", "延后 86 天，已如实列明"])
    tdev.append(["%d" % (len(tdev) + 1), "技术参数", "技术规范书带 * 的重要参数",
                 "全部满足或优于要求", "优于项已在参数表标注，无负偏差"])
    table(doc, ["序号", "偏差事项", "招标文件要求", "投标文件响应", "偏差说明"], tdev, size=8.5,
          aligns=[WD_ALIGN_PARAGRAPH.CENTER] + [WD_ALIGN_PARAGRAPH.LEFT] * 4)
    para(doc, "除上表列明者外，我方对技术规范书全部条款无偏差。"
              "按招标文件 1.11.2，参数表已填写具体数值，未使用“响应”“完全响应”“满足”等笼统表述替代。",
         first_indent=False)
    doc.add_page_break()

    h1(doc, "二、技术特性参数响应表")
    para(doc, "带 * 者为技术规范书规定的重要技术参数（招标文件 1.1.17），必须满足。",
         first_indent=False, size=9)
    # 真实技术响应表是「要求 / 响应 / 偏差」三列逐条对照，偏差列统一填「无」
    tp = [[x[0], x[1], x[2], x[3], "无偏差"] for x in tech_rows(b)]
    table(doc, ["条目", "技术参数名称", "招标人要求值", "我方响应值", "偏差"], tp, size=8)
    doc.add_page_break()

    h1(doc, "三、货物组件材料配置表")
    comp = [
        ["1", "DTS 分布式光纤测温主机", "DTS-%d/12CH" % (8000 + sd(b["code"], "dts") % 900), "1 台", "12 通道，定位精度 ±0.8m"],
        ["2", "测温光缆", "62.5/125μm 多模", "按隧道长度配置", "含接线盒、余缆盘"],
        ["3", "区域控制器 ACU", "ACU-%d" % (3000 + sd(b["code"], "acu") % 400), "按监控分区配置", "集成环网交换机与数据采集模块"],
        ["4", "工业以太网交换机", "IES-%d 千兆环网" % (2400 + sd(b["code"], "ies") % 200), "按分区配置", "支持冗余环网，自愈 <20ms"],
        ["5", "网络高清摄像机", "IPC-%d 万像素" % (400 + sd(b["code"], "ipc") % 100), "按隧道长度配置", "红外 80m，支持区域入侵检测"],
        ["6", "应急通话主机及分机", "ETC-200", "按分区配置", "支持调度台直呼"],
        ["7", "电缆护层接地电流监测装置", "CBM-100", "按接地箱数量配置", "精度 ±1%"],
        ["8", "监控子站平台软件", "TMS-V%d.%d" % (4 + sd(b["code"], "tms") % 2, sd(b["code"], "tms2") % 5), "1 套", "含组态、告警、报表、接口"],
        ["9", "通信模块（5G/4G 全网通）", "CM-5G", "按子站配置", "含 5 年通信费用"],
    ]
    table(doc, ["序号", "组件/材料名称", "型号规格", "数量", "技术说明"], comp, size=8,
          aligns=[WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT,
                  WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT])
    doc.add_page_break()

    h1(doc, "四、系统技术方案")
    h2(doc, "4.1 总体架构")
    para(doc, "按技术规范书 4.1.2，系统采用监控中心—监控子站—监控子系统三层架构。"
              "监控子站设于电缆线路始、末端，配置区域控制器 ACU（内含光纤环网交换机、"
              "模拟量采集模块与检测诊断服务器），就地完成数据采集、预处理与告警判断；"
              "监控中心完成集中展示、跨子系统联动、历史数据存储与向上级平台推送。")
    para(doc, "本工程按包1（先锋 220kV 输变电工程）与包2（巡鲇一回、关康、黄家湖二期）"
              "分别组网，两包共用同一套监控中心平台软件，子站按监控分区独立配置，"
              "互不影响运行。")
    h2(doc, "4.2 各子系统分述")
    sub = [
        ["1", "光纤测温子系统", "DTS-8000/12CH 主机 + 62.5/125μm 多模测温光缆，"
                           "监测范围 ≥32km，定位精度 ±0.8m，导体温度计算精度 ≤±1.5℃",
         "电缆导体温度、载流量动态评估、瓶颈点跟踪（≥32 个）"],
        ["2", "视频监控子系统", "400 万像素网络摄像机 + 16 盘位 NVR，可接入 72 路 1080P，"
                           "红外 80m，支持区域入侵与滞留检测",
         "隧道出入口、接头井、防火分区实况与入侵告警"],
        ["3", "应急通话子系统", "ETC-200 通话主机 + 分区通话分机，支持调度台直呼与录音",
         "隧道内人员应急处置通话"],
        ["4", "护层接地电流监测子系统", "CBM-100 接地电流采集单元，精度 ±1%",
         "电缆护层接地电流、环流异常判断"],
        ["5", "环境与安防子系统", "温湿度、水位、烟雾、门禁采集单元，接入 ACU",
         "隧道环境越限与非法进入告警"],
        ["6", "通信子系统", "5G/4G 全网通 + 光纤双通道热备，含 5 年通信费用",
         "子站至监控中心、监控中心至运检平台的数据通道"],
    ]
    table(doc, ["序号", "子系统", "主要配置", "监测/实现内容"], sub, size=8,
          aligns=[WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT,
                  WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT])
    h2(doc, "4.3 接口、协议与数据流")
    for t in [
        "1. 按技术规范书 1.2.2、1.2.3 开放软硬件数据协议接口，提供 IEC 61850、"
        "Modbus TCP、OPC UA 及 RESTful 四类接口，支持第三方设备无缝接入与二次开发。",
        "2. 数据流：现场采集单元 → ACU（就地处理、告警判断）→ 监控中心（存储、展示、联动）"
        "→ 武汉输电智能化运检平台（按上级平台要求的报文格式推送）。",
        "3. 时钟统一：全部子站与中心采用 NTP 对时，时标误差 ≤100ms，"
        "保证告警与视频检索时序一致。",
        "4. 信息安全：按国家电网公司电力监控系统安全防护要求，纵向加密认证、"
        "横向隔离，子站侧部署安全接入网关。",
    ]:
        para(doc, t)
    h2(doc, "4.4 电磁兼容与安装要求")
    for t in [
        "1. 按技术规范书 1.2.1，信号电缆与电源电缆分槽敷设，不共用同一根保护管，"
        "交叉处采用金属隔板屏蔽。",
        "2. 设备通过 GB/T 17626 系列电磁兼容试验（静电放电、辐射抗扰、快速瞬变脉冲群、"
        "浪涌），试验报告随技术文件附件提交。",
        "3. 我方负责现场安装、调试、系统集成、试运行、培训与验收；外购件质量由我方负责"
        "（技术规范书 1.1.3、1.1.14），不因分包或外购转移质量责任。",
    ]:
        para(doc, t)
    doc.add_page_break()

    h1(doc, "五、施工组织与进度计划")
    para(doc, "合同生效后按下表组织供货与实施。包1 与包2 并行排产，包1 优先。",
         first_indent=False)
    sched = [
        ["1", "合同签订与技术协议确认", "2026-02-10 前", "10 日", "技术协议、排产计划"],
        ["2", "系统设计与图纸确认", "2026-02-25 前", "15 日", "系统图、屏柜布置图、接口协议"],
        ["3", "设备生产与元器件采购", "2026-03-25 前", "30 日", "整机、屏柜、光缆"],
        ["4", "工厂联调与出厂检验", "2026-04-05 前", "10 日", "出厂检验报告、联调记录"],
        ["5", "包装运输至交货地点（包1）", "2026-04-18 前", "5 日", "到货签收单"],
        ["6", "包装运输至交货地点（包2）", "2026-06-25 前", "5 日", "到货签收单"],
        ["7", "现场安装指导与调试", "到货后 20 日内", "20 日", "调试记录、试运行报告"],
        ["8", "培训与验收", "调试完成后 10 日内", "10 日", "培训签到表、验收证书"],
    ]
    table(doc, ["序号", "阶段", "计划完成时间", "工期", "交付物"], sched, size=8,
          aligns=[WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT,
                  WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.CENTER,
                  WD_ALIGN_PARAGRAPH.LEFT])
    if b.get("deliver_first"):
        para(doc, "特别说明：受现有产线排产与关键元器件（DTS 主机激光模块）到货周期影响，"
                  "我方包1 首批交货最早可安排至 2026-07-15，较货物清单要求的 2026-04-20 延后 86 天；"
                  "包2 交货期不受影响。该偏差已在商务偏差表与技术偏差表中如实列明。",
             first_indent=False)
    else:
        para(doc, "排产说明：现有产线剩余产能可覆盖本分标全部数量，关键元器件已备安全库存，"
                  "包1 首批交货可提前至 2026-04-15，早于要求的 2026-04-20。", first_indent=False)
    doc.add_page_break()

    h1(doc, "六、质量保证与风险管理")
    h2(doc, "6.1 质量控制点")
    table(doc, ["阶段", "控制点", "控制方式", "记录"], [
        ["入厂", "元器件与光缆进厂检验", "抽检 + 供方合格证核验", "进厂检验记录"],
        ["生产", "SMT 贴装、整机装配、光纤熔接", "首件检验 + 巡检", "工序检验卡"],
        ["老化", "整机 72 小时高温老化", "100% 全检", "老化记录"],
        ["出厂", "功能、精度、绝缘、耐压", "100% 全检", "出厂检验报告"],
        ["现场", "安装工艺、光缆熔接损耗、联调", "监理见证 + 自检", "调试与试运行记录"],
    ], size=8.5, aligns=[WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT,
                        WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT])
    h2(doc, "6.2 主要风险与应对")
    table(doc, ["风险", "影响", "应对措施"], [
        ["关键元器件到货延迟", "影响交期", "提前锁定安全库存；双供方备份；周报预警"],
        ["隧道现场条件与图纸不符", "影响安装进度", "到货前完成现场踏勘复核，预留 20% 辅材余量"],
        ["光缆熔接损耗超标", "影响测温精度", "熔接后逐点 OTDR 测试，超标即返工"],
        ["与既有系统接口不兼容", "影响数据接入", "合同签订后 15 日内完成接口联调预演"],
        ["季节性施工窗口受限", "影响验收节奏", "优先安排送电前窗口期，必要时增加班组"],
    ], size=8.5, aligns=[WD_ALIGN_PARAGRAPH.LEFT] * 3)
    doc.add_page_break()

    h1(doc, "七、质保期与售后服务承诺")
    para(doc, "1. 质保期：系统投运后 %d 年，与招标文件技术规范书 1.1.4 一致。"
              "质保期内因产品质量问题导致的故障，免费维修或更换。" % WARRANTY_YEARS, first_indent=False)
    para(doc, "2. 响应时限：接到故障通知后 2 小时内响应，24 小时内到达现场，"
              "48 小时内恢复系统主要功能。", first_indent=False)
    para(doc, "3. 备品备件：随货提供技术规范书表 2 规定的必备备品备件、专用工具与仪器仪表。",
         first_indent=False)
    para(doc, "4. 培训：免费提供不少于 2 期、每期不少于 5 人的现场培训，"
              "内容含系统操作、日常维护、故障处理。", first_indent=False)
    para(doc, "5. 软件升级：质保期内免费提供同版本功能升级与安全补丁。", first_indent=False)
    doc.add_page_break()

    h1(doc, "八、生产场地、装备与检测能力")
    table(doc, ["项目", "内容"], [
        ["生产场地", "%s 厂区，自有厂房 %d ㎡（其中洁净车间 %d ㎡）"
                     % (b["addr"], 4000 + b["staff"] * 22, 300 + b["staff"] * 3)],
        ["年产能", "电缆隧道在线监测系统 %d 套/年，剩余产能 %d 套/年"
                   % (120 + b["staff"], 40 + int(b["staff"] * 0.5))],
        ["主要生产设备", "SMT 贴片线 2 条、波峰焊 1 条、光纤熔接台 12 台、整机老化台 6 台、"
                         "三防涂覆线 1 条"],
        ["检测试验设备", "高低温交变湿热试验箱、电磁兼容测试系统、光谱分析仪、"
                         "光时域反射仪（OTDR）、绝缘电阻测试仪、耐压试验装置"],
        ["调试试验场所", "系统联调实验室 260 ㎡，具备 1:1 隧道模拟环境与 DTS 标定槽"],
        ["制造工艺", "关键工序为 SMT 贴装、整机装配、光纤熔接、老化筛选、系统联调、出厂检验，"
                     "各工序设质量控制点并留记录"],
    ], size=8.5, aligns=[WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT])
    doc.add_page_break()

    h1(doc, "九、认证证书与型式试验报告")
    table(doc, ["序号", "证书/报告名称", "编号", "出具机构", "有效期"], [
        ["1", "型式试验报告（电缆隧道在线监测系统）",
         "XD-%d" % (20240000 + sd(b["code"], "test") % 99999),
         "电力工业电气设备质量检验测试中心", "2029-03-31"],
        ["2", "电磁兼容试验报告", "EMC-%d" % (2024000 + sd(b["code"], "emc") % 9999),
         "国家电器产品质量检验检测中心", "2028-12-31"],
        ["3", "软件产品登记证书", "鄂 DGY-%d" % (20240000 + sd(b["code"], "soft") % 9999),
         "湖北省工业和信息化厅", "2029-05-31"],
        ["4", "ISO 9001 质量管理体系证书",
         "CN-ISO-%05d" % (sd(b["code"], "iso") % 90000 + 10000),
         CERT_BODY, "2027-06-30"],
    ], size=8.5, aligns=[WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT,
                        WD_ALIGN_PARAGRAPH.LEFT, WD_ALIGN_PARAGRAPH.LEFT,
                        WD_ALIGN_PARAGRAPH.CENTER])
    doc.add_page_break()

    h1(doc, "十、项目人员配置")
    p0 = sd(b["code"], "ppl") % 25
    ppl = [(NAMES[p0], "电气工程 / 高级工程师", "14 年", "总体协调、进度与质量管理"),
           (NAMES[p0 + 1], "通信与信息系统 / 高级工程师", "11 年", "系统方案、接口与联调"),
           (NAMES[p0 + 2], "自动化 / 工程师", "7 年", "现场安装指导与调试"),
           (NAMES[p0 + 3], "软件工程 / 工程师", "6 年", "平台组态、数据接口开发"),
           (NAMES[p0 + 4], "质量管理 / 工程师", "9 年", "入厂检验与出厂验收")]
    table(doc, ["序号", "岗位", "姓名", "专业/职务", "工作年限", "本项目职责"], [
        [str(i), post, nm, spec, yr, dut]
        for i, (post, (nm, spec, yr, dut)) in enumerate(
            zip(["项目经理", "技术负责人", "现场调试工程师", "软件工程师", "质量工程师"], ppl), 1)
    ], size=8.5, aligns=[WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT,
                        WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT,
                        WD_ALIGN_PARAGRAPH.CENTER, WD_ALIGN_PARAGRAPH.LEFT])
    para(doc, "上述人员社保缴纳证明、职称证书、劳动合同复印件见附件。", first_indent=False, size=9)
    doc.add_page_break()

    h1(doc, "十一、技术文件签署页")
    para(doc, "本册技术文件（含附件）共 %d 页，我方确认技术参数响应值真实可核查，"
              "所附试验报告与认证证书均在有效期内。" % (24 + len(TECH_PARAMS)),
         first_indent=False)
    doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run("投 标 人：%s（电子签章）" % b["seal_name"]), "宋体", 10.5)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    cn(p.add_run(SIGN_DATE), "宋体", 10.5)

    path = os.path.join(OUT, "投标文件_%s_%s_技术文件.docx" % (b["short"], SECTION))
    doc.save(path)
    return path


# ---------------------------------------------------------------- 分项报价表 xlsx
def build_xlsx(b, rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "分项报价表"
    thin = Side(style="thin", color="B0B0B0")
    bd = Border(left=thin, right=thin, top=thin, bottom=thin)
    exc_total, inc_total = totals(rows)

    ws["A1"] = "分项报价表"
    ws["A1"].font = Font(size=14, bold=True)
    ws.merge_cells("A1:K1")
    ws["A1"].alignment = Alignment(horizontal="center")

    ws["A2"] = "招标编号：%s    分标编号：%s    投标人：%s" % (BATCH, SECTION, b["name"])
    ws.merge_cells("A2:K2")
    ws["A3"] = "投标总价（含税）：人民币 %s 元（%s）" % (money(inc_total), rmb_upper(inc_total))
    ws.merge_cells("A3:K3")

    heads = ["序号", "网省采购申请号", "物料描述", "项目名称", "单位", "数量",
             "未含税单价（元）", "未含税合价（元）", "税率", "含税单价（元）", "含税合价（元）"]
    for j, hd in enumerate(heads, 1):
        c = ws.cell(row=4, column=j, value=hd)
        c.font = Font(bold=True, size=9)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        c.border = bd

    for i, r in enumerate(rows, 5):
        vals = [i - 4, r["no"], r["desc"], r["project"], r["unit"], r["qty"],
                money(r["exc_unit"]), money(r["exc_amt"]), "%d%%" % r["rate"],
                money(r["inc_unit"]), money(r["inc_amt"])]
        for j, v in enumerate(vals, 1):
            c = ws.cell(row=i, column=j, value=v)
            c.border = bd
            c.font = Font(size=9)
            if j in (1, 5, 6, 9):
                c.alignment = Alignment(horizontal="center", vertical="center")
            elif j in (7, 8, 10, 11):
                c.alignment = Alignment(horizontal="right", vertical="center")
            else:
                c.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)

    tr = 5 + len(rows)
    tot = ["合计", "—", "—", "—", "—", sum(r["qty"] for r in rows),
           "—", money(exc_total), "%d%%" % b["tax"], "—", money(inc_total)]
    for j, v in enumerate(tot, 1):
        c = ws.cell(row=tr, column=j, value=v)
        c.border = bd
        c.font = Font(bold=True, size=9)
        c.fill = PatternFill("solid", fgColor="F2F2F2")
        c.alignment = Alignment(horizontal="center" if j not in (8, 11) else "right")

    ws.cell(row=tr + 2, column=1, value="注：1. 最高限价为含税总价，本表含税合价即与限价比较的口径。")
    ws.cell(row=tr + 3, column=1, value="　　2. 未含税价 = 含税价 ÷ (1 + 税率)；三处金额（投标函/开标一览表/本表）一致。")
    ws.cell(row=tr + 4, column=1, value="　　3. 投标保证金：本项目免收（前附表 3.4.1）。")
    ws.cell(row=tr + 5, column=1, value="　　4. 金额单位为元；ECP2.0 投标工具按万元填报，1 万元 = 10000 元，数值一致。")
    ws.cell(row=tr + 6, column=1, value="投标人（电子签章）：" + b["seal_name"])
    ws.cell(row=tr + 7, column=1, value="注：本表为【合成演示数据 · 非真实投标文件】，仅用于系统验证。")
    ws.cell(row=tr + 7, column=1).font = Font(size=9, color="C00000", bold=True)

    for col, w in (("A", 6), ("B", 20), ("C", 30), ("D", 40), ("E", 6), ("F", 6),
                   ("G", 16), ("H", 16), ("I", 7), ("J", 16), ("K", 16)):
        ws.column_dimensions[col].width = w

    ws2 = wb.create_sheet("编制说明")
    lines = [
        ("本文件为合成演示数据", True),
        ("不含任何真实投标人信息；物料、网省采购申请号、项目名称、数量、交货日期、最高限价均取自", False),
        ("国网湖北电力 152507 批次 152507-1102002-4004 标包的真实招标文件与货物清单。", False),
        ("", False),
        ("本表为投标文件价格册附件，随价格文件一并递交。", False),
        ("填报口径：", True),
        ("1. 最高限价、行项目、数量、交货日期均取自招标文件货物清单与附表一。", False),
        ("2. 未含税单价 = 含税单价 ÷ (1 + 增值税税率)，保留两位小数。", False),
        ("3. 含税合价 = 含税单价 × 数量；分项合计即投标函所报投标总价。", False),
        ("4. 报价为运至交货地点并完成安装指导、调试配合、技术服务后的综合单价，含 5 年通信费用。", False),
        ("5. 金额单位为人民币元。", False),
        ("", False),
        ("限价合计（含税）：%s 元" % money(CAP_SUM), False),
        ("投标报价（含税）：%s 元" % money(inc_total), False),
    ]
    for i, (t, bold) in enumerate(lines, 1):
        c = ws2.cell(row=i, column=1, value=t)
        c.font = Font(size=10, bold=bold)
    ws2.column_dimensions["A"].width = 110

    path = os.path.join(OUT, "分项报价表_%s_%s.xlsx" % (b["short"], SECTION))
    wb.save(path)
    return path


# ---------------------------------------------------------------- 主流程
def main():
    os.makedirs(OUT, exist_ok=True)
    truth = {
        "meta": {
            "title": "152507-1102002-4004 受控合成投标包 v2（三册制·6 家）",
            "version": "v3",
            "batch": BATCH,
            "section_no": SECTION,
            "tender_name": TENDER_NO,
            "buyer": BUYER,
            "deadline": "2026-01-28 09:00",
            "sign_date": "2026-01-26",
            "required_validity_days": VALIDITY_DAYS,
            "required_warranty_years": WARRANTY_YEARS,
            "bond": "本项目免收投标保证金（前附表 3.4.1）",
            "consortium": "不接受联合体（招标公告 3.2）",
            "alternative": "不允许备选投标方案（前附表 3.6.1）",
            "subcontract": "不允许分包（前附表 1.10.1）",
            "financial_years": ["2022", "2023", "2024"],
            "cap_basis": "含税总价（前附表之附表一）",
            "cap_items": [{"item_no": i["no"], "pkg": i["pkg"], "project": i["project"],
                           "qty": i["qty"], "unit": i["unit"], "cap_yuan": i["cap"],
                           "first_delivery": i["deliver"]} for i in ITEMS],
            "cap_sum_yuan": CAP_SUM,
            "legal_tax_rates": [0.13, 0.09, 0.06, 0.03, 0.01, 0.0],
            "nature": "合成演示数据；物料/行项目号/项目名/数量/交货期/限价取自 152507 真实招标文件；"
                      "投标人、报价、签章名、有效期、税率、交货承诺为剧本设定",
            "v1_to_v2_fixes": [
                "限价口径：v1 用未含税金额比含税限价 → v2 统一按含税比含税限价",
                "签章日期：v1 2026-10-18（晚于投标截止 2026-01-28）→ v2 2026-01-26",
                "交货期：v1 承诺 2026-05-10（晚于包1 要求 2026-04-20）→ v2 按包1/包2 分别承诺",
                "文件形态：v1 单册 8 节 → v2 价格/商务/技术三册，按招标文件 3.1.1 与 ECP2.0 端口组织",
            ],
        },
        "bidders": [],
    }

    for b in BIDDERS:
        rows = price_rows(b)
        exc_total, inc_total = totals(rows)
        p1 = build_price(b, rows)
        p2 = build_biz(b, rows)
        p3 = build_tech(b, rows)
        p4 = build_xlsx(b, rows)

        over_items = [r["no"] for r in rows if r["inc_amt"] > r["cap"] * r["qty"]]
        truth["bidders"].append({
            "code": b["code"],
            "short": b["short"],
            "bidder_name": b["name"],
            "files": [os.path.basename(p1), os.path.basename(p2),
                      os.path.basename(p3), os.path.basename(p4)],
            "expect": b["expect"],
            "defect_rule": b["defect"],
            "defect_note": b["note"],
            "ground_truth": {
                "bid.bidder_name": b["name"],
                "bid.seal_name": b["seal_name"],
                "bid.seal_valid": True,
                "bid.seal_owner_matches_bidder": b["seal_ok"],
                "bid.legal_rep_name": b["legal"],
                "bid.agent_name": b["agent_person"],
                "bid.validity_days": b["validity"],
                "bid.tax_rate": b["tax"] / 100.0,
                "bid.price_total_inc_tax": inc_total,
                "bid.price_total_ex_tax": exc_total,
                "bid.price_cap_sum_inc_tax": CAP_SUM,
                "bid.total_over_cap": inc_total > CAP_SUM,
                "bid.over_cap_items": over_items,
                "bid.bond_applicable": False,
                "bid.is_consortium": False,
                "bid.warranty_years": WARRANTY_YEARS,
                "bid.committed_delivery": {
                    i["no"]: (b["deliver_first"] if (b.get("deliver_first")
                                                     and i["deliver"] == "2026-04-20")
                              else i["deliver"])
                    for i in ITEMS},
                "bid.required_delivery": {i["no"]: i["deliver"] for i in ITEMS},
                "bid.delivery_meets_requirement": not b.get("deliver_first"),
                "bid.delivery_delay_days_pkg1": 86 if b.get("deliver_first") else 0,
                "bid.price_items": [
                    {"item_no": r["no"], "qty": r["qty"],
                     "unit_price_ex_tax": r["exc_unit"], "amount_ex_tax": r["exc_amt"],
                     "unit_price_inc_tax": r["inc_unit"], "amount_inc_tax": r["inc_amt"],
                     "tax_rate": r["rate"], "cap_inc_tax": r["cap"] * r["qty"],
                     "over_cap": r["inc_amt"] > r["cap"] * r["qty"]}
                    for r in rows],
                "tech.params_responded": len(TECH_PARAMS),
                "tech.deviations": 1 if b.get("deliver_first") else 0,
                "biz.deviations": 1 if b.get("deliver_first") else 0,
            },
            "derived": {
                "over_cap_items": over_items,
                "total_over_cap": inc_total > CAP_SUM,
                "expect_verdict": "否决" if b["defect"] else "通过初步评审",
            },
        })
        print("%-4s %-22s 含税=%-14s 未含税=%-14s 折扣=%.2f  %s"
              % (b["short"], b["name"], money(inc_total), money(exc_total),
                 b["ratio"], b["defect"] or "无缺陷"))

    with open(os.path.join(OUT, "_ground_truth_v3.json"), "w", encoding="utf-8") as f:
        json.dump(truth, f, ensure_ascii=False, indent=1)

    print("\n限价合计（含税）= %s 元" % money(CAP_SUM))
    print("产出目录：%s（每家 4 个文件，共 %d 个）" % (OUT, len(BIDDERS) * 4))


if __name__ == "__main__":
    main()
