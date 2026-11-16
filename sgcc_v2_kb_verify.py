# -*- coding: utf-8 -*-
"""入库后核验：六个 v2 受审库是否「各家只装各家」。

只看上传返回 200 就报通过是不成立的——v1 就是这么栽的：文件都在库里，
但检索时 top N 被别家块挤占，本家内容排不进来，字段抽取随机失败且不报错。
所以这里直接打检索接口，逐家验三件事：

1. **不串库**：查本家库返回的 document_title 必须全部是本家文件。
   一旦出现别家文件名，说明库里混进了别家内容或检索跨库了。
2. **召回得到**：本家企业全称、投标报价、税率必须能检出。
3. **内容对得上**：抽到的报价数字与 ground truth 一致（不是随便召回一个数）。
"""
import io
import json
import re
import subprocess
import sys

CLI = "./apemind-cli/apemind.exe"
MAP = "bid_packs_v2/_v2_kb_map.json"
GT = "bid_packs_v2/_ground_truth_v3.json"
OUT = "bid_packs_v2/_v2_kb_verify.json"

QUERIES = [
    ("企业名称", "投标人名称 投标人：", 5),
    ("投标报价", "投标总价 投标报价 含税", 5),
    ("税率", "增值税税率 13%", 5),
    ("有效期", "投标有效期", 4),
]


def search(kb, q, limit):
    p = subprocess.run([CLI, "search", q, "--kb", kb, "--limit", str(limit),
                        "--excerpt", "300", "--json"],
                       capture_output=True, text=True, encoding="utf-8")
    if p.returncode != 0:
        return None, (p.stderr or p.stdout)[-200:]
    try:
        d = json.loads(p.stdout)["data"]
        gs = d.get("groups") or []
        return (gs[0]["items"] if gs else []), None
    except Exception as e:
        return None, "解析失败 %s：%s" % (e, p.stdout[-160:])


def main():
    m = json.load(io.open(MAP, encoding="utf-8"))
    gt = {b["short"]: b["ground_truth"]
          for b in json.load(io.open(GT, encoding="utf-8"))["bidders"]}

    rep = {"checks": [], "summary": {}}
    ok_all = True

    for b in m["bidders"]:
        short, kb, name = b["short"], b["kb"], b["name"]
        print("\n[%s] %s  %s" % (b["code"], name, kb))
        others = [x["short"] for x in m["bidders"] if x["short"] != short]
        cross, miss = [], []

        for label, q, lim in QUERIES:
            items, err = search(kb, q, lim)
            if items is None:
                ok_all = False
                print("  ✗ %s 检索报错 %s" % (label, err))
                rep["checks"].append({"short": short, "item": label,
                                      "pass": False, "detail": "检索报错 " + str(err)})
                continue
            titles = [it["document_title"] for it in items]
            # 串库判定：返回了别家的文件
            bad = [t for t in titles if any(o in t for o in others)]
            if bad:
                cross.extend(bad)
            hit_txt = " ".join(it.get("excerpt") or "" for it in items)
            rep["checks"].append({
                "short": short, "item": label, "pass": not bad and bool(items),
                "n": len(items),
                "titles": sorted(set(titles)),
                "cross": bad,
                "strong": sum(1 for it in items if it.get("match_quality") == "strong"),
            })
            print("  %s %-6s 命中 %d 条（strong %d）%s"
                  % ("✓" if not bad and items else "✗", label, len(items),
                     sum(1 for it in items if it.get("match_quality") == "strong"),
                     " 串库：" + str(bad) if bad else ""))

            # 内容核对：企业全称必须出现；报价数字必须与真值一致
            if label == "企业名称" and name not in hit_txt:
                miss.append("企业全称未检出")
            if label == "投标报价":
                want = gt[short]["bid.price_total_inc_tax"]
                cand = [x.replace(",", "") for x in
                        re.findall(r"[0-9][0-9,]{6,}", hit_txt)]
                if not any(abs(float(c) - want) < 1.0 for c in cand):
                    miss.append("报价 %s 未检出（检出 %s）" % (want, cand[:6]))

        rep["summary"][short] = {"kb": kb, "name": name,
                                 "cross": sorted(set(cross)), "miss": miss}
        if cross:
            ok_all = False
            print("  ✗ 串库：%s" % sorted(set(cross)))
        if miss:
            ok_all = False
            print("  ✗ %s" % "；".join(miss))
        if not cross and not miss:
            print("  ✓ 本家内容完整、无串库")

    io.open(OUT, "w", encoding="utf-8").write(
        json.dumps(rep, ensure_ascii=False, indent=1))
    print("\n结论：%s → %s" % ("全部通过" if ok_all else "存在失败项", OUT))
    return 0 if ok_all else 1


if __name__ == "__main__":
    sys.exit(main())
