# -*- coding: utf-8 -*-
"""把 v2 合成投标包（六家三册制）摄入一组新建的受审库。

两条硬约束，都是踩过的：

1. **一家一库**。c 家同库时 ctx.search 的 top N 会被别家的块挤占，本家文件
   排不进来，表现为字段随机丢失（limit=8 丢保证金，提到 20 保证金回来但
   另两家 seal_valid 又丢）。加大 limit 解决不了，只能物理分库。

2. **与招标文件库物理隔离**。招标侧在 colcf0af5d45fd7ef6b / col0cd75b81b6b47b74，
   投标侧只进本脚本建的库。两侧混在一个库，召回会把招标文件块当投标人答复，
   实测出现过「查投标人名称返回某份技术规范书」。

幂等：库按标题复用，文档按名称跳过，重复跑不会产生重复数据。
"""
import io
import json
import os
import subprocess
import sys

CLI = "./apemind-cli/apemind.exe"
DIR = "bid_packs_v2"
OUT = "bid_packs_v2/_v2_kb_map.json"

SECTION = "152507-1102002-4004"

# code → (简称, 投标人全称)；简称用于拼文件名，全称用于建库与抽取侧比对
BIDDERS = [
    ("HZ", "华中", "华中电力监测技术（湖北）有限公司"),
    ("XY", "襄阳", "襄阳汉江开关设备有限公司"),
    ("YC", "宜昌", "宜昌三峡输变电设备有限公司"),
    ("JZ", "荆州", "荆州楚元智能装备有限公司"),
    ("HS", "黄石", "黄石磁湖电力科技有限公司"),
    ("ES", "恩施", "恩施清江自动化设备有限公司"),
]

DESC = ("%s 标段投标人「%s」一家的 v2 受控合成投标包（三册制：价格文件／商务文件／"
        "技术文件 + 分项报价表）。与招标文件库物理隔离：投标侧文件只进本库，"
        "避免受审侧与基准侧互相污染检索结果。按投标人单独建库——多家同库时"
        "top N 会被别家的块挤占，本家文件排不进来，字段抽取会随机失败。"
        "全部为合成演示数据，不含真实投标人信息。")


def run(args, timeout=600):
    p = subprocess.run([CLI] + args, capture_output=True, text=True,
                       encoding="utf-8", timeout=timeout)
    return p.returncode, (p.stdout or ""), (p.stderr or "")


def kbs():
    """返回 {标题: id}"""
    rc, out, err = run(["knowledge", "list", "--json"])
    if rc != 0:
        raise SystemExit("列库失败：%s" % (err or out)[-300:])
    items = json.loads(out)["data"]["items"]
    return {x["name"]: x["id"] for x in items}


def ensure_kb(title, desc):
    m = kbs()
    if title in m:
        print("  库已存在，复用 %s" % m[title])
        return m[title]
    rc, out, err = run(["knowledge", "create", "--title", title,
                        "--description", desc, "--json"])
    if rc != 0:
        raise SystemExit("建库失败 %s：%s" % (title, (err or out)[-400:]))
    m = kbs()
    if title not in m:
        raise SystemExit("建库后仍查不到 %s" % title)
    print("  新建库 %s" % m[title])
    return m[title]


def doc_names(kb):
    rc, out, _ = run(["document", "list", "--kb", kb, "--json"])
    if rc != 0:
        return set()
    try:
        d = json.loads(out)["data"]
        items = d if isinstance(d, list) else d.get("items", [])
        return {x.get("name") for x in items}
    except Exception:
        return set()


def upload(kb, path):
    rc, out, err = run(["document", "upload", "--file", path,
                        "--kb", kb, "--wait", "--json"])
    if rc != 0:
        return None, (err or out)[-300:]
    try:
        return json.loads(out)["data"], None
    except Exception as e:
        return None, "解析失败 %s：%s" % (e, out[-200:])


def files_of(short):
    fs = ["投标文件_%s_%s_%s.docx" % (short, SECTION, v)
          for v in ("价格文件", "商务文件", "技术文件")]
    fs.append("分项报价表_%s_%s.xlsx" % (short, SECTION))
    return fs


def main():
    res = {"section": SECTION, "generated_at": None,
           "note": "v2 合成投标包受审库组；与招标文件库物理隔离", "bidders": []}
    total_up = total_skip = total_fail = 0

    for code, short, name in BIDDERS:
        print("\n[%s] %s" % (code, name))
        title = "P152507-受审库v2-%s-%s" % (code, name)
        kb = ensure_kb(title, DESC % (SECTION, name))
        have = doc_names(kb)
        rec = {"code": code, "short": short, "name": name, "kb": kb,
               "title": title, "docs": [], "skipped": [], "failed": []}

        for f in files_of(short):
            path = os.path.join(DIR, f)
            if not os.path.exists(path):
                rec["failed"].append({"file": f, "error": "本地文件不存在"})
                total_fail += 1
                print("   ✗ 缺失 %s" % f)
                continue
            if f in have:
                rec["skipped"].append(f)
                total_skip += 1
                print("   - 跳过（已存在）%s" % f)
                continue
            d, err = upload(kb, path)
            if d is None:
                rec["failed"].append({"file": f, "error": err})
                total_fail += 1
                print("   ✗ 失败 %s :: %s" % (f, err))
                continue
            rec["docs"].append({"file": f, "doc_id": d.get("id"),
                                "status": d.get("status"),
                                "vector": d.get("vector_index_status"),
                                "fulltext": d.get("fulltext_index_status"),
                                "windows": d.get("total_windows")})
            total_up += 1
            print("   ✓ %s  doc=%s vec=%s ft=%s win=%s"
                  % (f, d.get("id"), d.get("vector_index_status"),
                     d.get("fulltext_index_status"), d.get("total_windows")))
        res["bidders"].append(rec)

    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps(res, ensure_ascii=False, indent=1))
    print("\n上传 %d 份，跳过 %d 份，失败 %d 份 → %s"
          % (total_up, total_skip, total_fail, OUT))
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
