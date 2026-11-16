# -*- coding: utf-8 -*-
"""把「5 家共用一个受审库」拆成「每家一个库」。

为什么要拆：实测 5 家同库时，检索某家的字段，limit=20 里本家只占 1 条，
另外 19 条被别家的块挤满——问句再改、limit 再调都没用，因为本家的块根本
进不了 top N。逐字段调参只是在赌排序运气：一次跑 55 个字段，
总会有几个字段被挤掉，而且每次掉的还不是同一个（实测 seal_valid 在
调 limit 之后从「全过」变成「两家丢」）。

物理隔离到「家」这一层才是根因修复：单库只放 2 个文件、约 20 个块，
limit=20 就能覆盖全文，字段抽取不再依赖「这次排序对我有利」。

旧的汇总库保留不删（有审计价值），函数读的时候只用新的分家库。
"""
import io, json, subprocess, sys, time

CLI = "./apemind-cli/apemind.exe"
OLD_KB = "cold848aad8f57412ce"
GT = "bid_packs/_ground_truth.json"


def run(args, timeout=300):
    p = subprocess.run([CLI] + args, capture_output=True, text=True,
                       encoding="utf-8", timeout=timeout)
    return p.returncode, p.stdout, p.stderr


def jload(out):
    try:
        return json.loads(out)
    except Exception:
        return None


gt = json.load(io.open(GT, encoding="utf-8"))
result = {"old_kb": OLD_KB, "per_bidder": [], "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}

for b in gt["bidders"]:
    code, tag = b["code"], b["bidder_name"]
    cfg = {
        "title": "P152507-受审库-%s-%s" % (code, tag),
        "description": (
            "152507-1102002-4004 标段，投标人「%s」一家的受控合成投标包（docx 投标文件 + xlsx 分项报价表）。"
            "按投标人单独建库：5 家同库时检索会被别家的块挤占 top N，"
            "本家文件排不进来，导致字段抽取随机失败。全部为合成演示数据。" % tag),
        "type": "document",
        "config": {"chunk_block_aware_splitter_enabled": True},
    }
    io.open("_kb_one.json", "w", encoding="utf-8").write(
        json.dumps(cfg, ensure_ascii=False, indent=1))
    code_, out, err = run(["knowledge", "create", "--input", "_kb_one.json", "--json"])
    d = jload(out) or {}
    kb = (d.get("data") or {}).get("id") or (d.get("data") or {}).get("knowledge_base_id")
    if not kb:
        print("!! 建库失败", tag, out[-300:], err[-200:])
        sys.exit(1)
    print("建库 %-24s → %s" % (tag, kb))

    ups = []
    for f in b["files"]:
        c2, o2, e2 = run(["document", "upload", "--file", "bid_packs/" + f,
                          "--kb", kb, "--wait", "--json"], timeout=600)
        d2 = jload(o2) or {}
        ok = (d2.get("data") or {}).get("status") in (None, "COMPLETE", "complete") and c2 == 0
        ups.append({"file": f, "ok": bool(ok), "status": (d2.get("data") or {}).get("status")})
        print("   上传 %-44s %s" % (f, "OK" if ok else "FAIL " + o2[-160:]))

    result["per_bidder"].append({"code": code, "bidder_name": tag, "kb": kb, "uploads": ups})

io.open("国网Demo_受审库分家清单_V1.json", "w", encoding="utf-8").write(
    json.dumps(result, ensure_ascii=False, indent=1))
print("\n清单已写：国网Demo_受审库分家清单_V1.json")
