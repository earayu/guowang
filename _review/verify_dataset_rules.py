# -*- coding: utf-8 -*-
"""验证「用平台 dataset 承载评审规则库」的三个前提是否成立。

背景：`_review/评审规则库_管理方案_2026-11-16.md` 第三节提出用 dataset 存规则台账，
但有三个前提没实测过，不能写进对客承诺：

  T1  metadata 能否原样吃下 check 的深层嵌套表达式（and/or 套 per_item_within_cap）
  T2  单数据集条目上限、版本数上限的具体数字
  T3  dataset version diff 的粒度：条目级还是字段级（字段级才能当「升版改动清单」）

用法：
  python verify_dataset_rules.py            # 全跑
  python verify_dataset_rules.py --keep     # 跑完保留验证数据集，便于人工看一眼

结论会打印成 PASS / FAIL / UNKNOWN 三段，FAIL 时给出原始返回。
本脚本只创建一个「验证用」数据集（名字带 VERIFY 前缀），不碰任何既有数据集。
"""
import argparse
import json
import subprocess
import sys
import time

CLI = "./apemind-cli/apemind.exe"
DS_NAME = "SGCC-规则库-VERIFY-勿用于生产"
RULES_SRC = "国网Demo_专家评审规则库_V1.json"
DISPATCH_SRC = "国网Demo_规则可执行化_46条分派表_V2.json"

STAMP = time.strftime("%H%M%S")
RETRY = 4
RETRY_WAIT = 5


def cli(args, timeout=120):
    """跑一条 CLI 命令，返回解析后的 dict。网络抖动时重试。"""
    last = None
    for i in range(RETRY):
        p = subprocess.run([CLI] + args, capture_output=True, timeout=timeout)
        raw = (p.stdout or b"").decode("utf-8", "replace").strip()
        if not raw:
            raw = (p.stderr or b"").decode("utf-8", "replace").strip()
        try:
            d = json.loads(raw)
        except Exception:
            last = "无法解析输出: %s" % raw[:200]
            time.sleep(RETRY_WAIT)
            continue
        if isinstance(d, dict) and d.get("error"):
            code = (d.get("error") or {}).get("code")
            # 业务错误（参数/权限/冲突）不重试，网络错误才重试
            if code in ("network_unavailable", "timeout"):
                last = d["error"].get("message")
                time.sleep(RETRY_WAIT)
                continue
            return d
        return d
    return {"error": {"code": "exhausted", "message": last or "重试耗尽"}}


def data_of(d):
    return d.get("data") if isinstance(d, dict) else None


def load_rules_for_verify():
    """挑一条最能暴露 metadata 结构问题的规则，用来测 T1。

    优先选含「非标准算子 + 附加参数」的（per_item_within_cap 带 fallback_total /
    amount_basis_why，group_dup_le / eval_threshold 带跨投标人语义）——
    这类算子除了嵌套还有额外键，比单纯嵌套深更容易被存储层压平或丢掉。
    没有这类规则时退回按嵌套深度选。
    """
    with open(DISPATCH_SRC, encoding="utf-8") as f:
        dd = json.load(f)

    RARE = ("per_item_within_cap", "per_item_amount_check", "group_dup_le",
            "group_no_overlap", "eval_threshold", "all_within_tolerance")

    def ops(node, acc=None):
        acc = acc if acc is not None else set()
        if isinstance(node, dict):
            op = node.get("op")
            if isinstance(op, str):
                acc.add(op)
            for v in node.values():
                ops(v, acc)
        elif isinstance(node, list):
            for x in node:
                ops(x, acc)
        return acc

    def depth(node):
        if not isinstance(node, dict):
            return 0
        inner = 0
        for v in node.values():
            if isinstance(v, dict):
                inner = max(inner, depth(v))
            elif isinstance(v, list):
                for x in v:
                    if isinstance(x, dict):
                        inner = max(inner, depth(x))
        return 1 + inner

    def extra_keys(node, acc=None):
        """统计算子节点上的「非标准键」数量。

        op / lhs / rhs / args 之外，判定式还挂着 fallback_total、key、amount_basis、
        tolerance_yuan、tolerance_why 这类口径参数（见行 10、行 11）。
        存储层最容易压平的正是这些键——它们是裸字段，不像 args 那样有固定形状。
        """
        acc = acc if acc is not None else 0
        STANDARD = {"op", "lhs", "rhs", "args"}
        if isinstance(node, dict):
            acc += len([k for k in node if k not in STANDARD])
            for v in node.values():
                extra_keys(v, acc)
        elif isinstance(node, list):
            for x in node:
                extra_keys(x, acc)
        return acc

    cand = [r for r in dd["rules"] if r.get("check")]

    def rare_hits(r):
        return len(ops(r["check"]) & set(RARE))

    # 测两条：稀有算子最多的（跨行语义）、附加参数键最多的（口径参数）。
    # 两者是不同的失效模式——前者怕算子被改写，后者怕裸字段被压平。
    a = max(cand, key=lambda r: (rare_hits(r), extra_keys(r["check"]), depth(r["check"])))
    b = max(cand, key=lambda r: (extra_keys(r["check"]), rare_hits(r), depth(r["check"])))
    picked = [a] if a["rule_id"] == b["rule_id"] else [a, b]
    return picked, [depth(r["check"]) for r in picked]


def merge_ledger(rule_id):
    """把 L1 台账字段与 L3 分派表字段按 rule_id 合并成一条 item。"""
    led = None
    try:
        with open(RULES_SRC, encoding="utf-8") as f:
            for r in json.load(f)["rules"]:
                if r.get("rule_id") == rule_id:
                    led = r
                    break
    except FileNotFoundError:
        pass
    with open(DISPATCH_SRC, encoding="utf-8") as f:
        for r in json.load(f)["rules"]:
            if r.get("rule_id") == rule_id:
                disp = r
                break
    meta = dict(disp)
    if led:
        # 台账字段先铺，分派表字段覆盖同名项（分派表是权威可执行口径）
        for k, v in led.items():
            meta.setdefault(k, v)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="跑完保留验证数据集")
    ap.add_argument("--fresh", action="store_true",
                    help="新建一个带时间戳的验证数据集再跑（规避 publish 的乐观锁 conflict）")
    args = ap.parse_args()

    report = []

    # ---- 前置：登录态与连通性
    st = cli(["auth", "status", "--json"])
    if (st.get("error") or {}).get("code"):
        print("网络或授权不可用，先修网络再跑：", st["error"].get("message"))
        return 2
    print("[前置] 已连通，account =", (data_of(st).get("account") or {}).get("name"))

    # ---- 建验证数据集（--fresh 强制新建；否则同名复用）
    ds_id = None
    if args.fresh:
        DS_NAME_LOCAL = "%s-%s" % (DS_NAME, time.strftime("%H%M%S"))
    else:
        DS_NAME_LOCAL = DS_NAME
    lst = data_of(cli(["dataset", "list", "--json"])) or {}
    for it in (lst.get("items") or []):
        if it.get("name") == DS_NAME_LOCAL:
            ds_id = it.get("id")
            print("[准备] 复用已有验证数据集", ds_id)
            break
    if not ds_id:
        r = cli(["dataset", "create", "--name", DS_NAME_LOCAL,
                 "--description", "验证 metadata 嵌套/容量/diff 粒度，不承载真实规则", "--json"])
        d = data_of(r) or {}
        ds_id = d.get("id")
        if not ds_id:
            print("[失败] 建数据集失败：", json.dumps(r.get("error"), ensure_ascii=False))
            return 2
        print("[准备] 新建验证数据集", ds_id)

    # 已有条目按 external_id 记账，重跑时走读取比对，不重复写入（幂等）
    existing = {}
    il = data_of(cli(["dataset", "item", "list", ds_id, "--json"])) or {}
    for it in (il.get("items") or []):
        if it.get("external_id"):
            existing[it["external_id"]] = it.get("item_id")

    # ---- T1：深层嵌套 check 与附加参数键能否原样存取（测两条，覆盖两种失效模式）
    rules, deps = load_rules_for_verify()
    t1_detail = []
    item_ids = []
    ok_all = True
    for rule, dep in zip(rules, deps):
        rid = rule["rule_id"]
        meta = merge_ledger(rid)
        print("[T1] 测 %s（check 嵌套深度 %d，附加参数键见 check）" % (rid, dep))

        if rid in existing:
            iid = existing[rid]
            print("[T1]   已存在 %s，改为读取比对" % iid)
            item_ids.append(iid)
            got = data_of(cli(["dataset", "item", "get", ds_id, iid, "--json"])) or {}
            gm = got.get("metadata") or (got.get("item") or {}).get("metadata") or {}
            same_all = json.dumps(gm, sort_keys=True, ensure_ascii=False) == \
                json.dumps(meta, sort_keys=True, ensure_ascii=False)
            same_check = json.dumps(gm.get("check"), sort_keys=True, ensure_ascii=False) == \
                json.dumps(meta.get("check"), sort_keys=True, ensure_ascii=False)
            lost = sorted(set(meta) - set(gm))
            # 判定只看两件事：check 整棵子树一致、没有丢键。
            # 「全等」会被 T3 写入过的字段影响，重跑时必然不等，不能当失败条件。
            if not same_check or lost:
                ok_all = False
            t1_detail.append("%s 全等=%s check=%s 丢键=%s item=%s"
                             % (rid, same_all, same_check, lost or "无", iid))
            continue

        payload = {
            "external_id": rid,
            "question": rule.get("rule_text", "")[:2000],
            "tags": [rule.get("category", ""), rule.get("subcategory", ""),
                     rule.get("exec_path", ""), "VERIFY"],
            "metadata": meta,
        }
        fn = "_verify_item_%s.json" % rid
        with open(fn, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False)

        add = cli(["dataset", "item", "add", ds_id, "--input", fn, "--json"])
        err = (add.get("error") or {}).get("code")
        if err:
            ok_all = False
            t1_detail.append("%s 写入失败(%s)" % (rid, json.dumps(add.get("error"), ensure_ascii=False)[:120]))
            continue

        ad = data_of(add) or {}
        iid = ad.get("item_id") or ad.get("id") or (ad.get("item") or {}).get("item_id")
        if not iid:
            ok_all = False
            t1_detail.append("%s 建出但取不到 id" % rid)
            continue
        item_ids.append(iid)

        got = data_of(cli(["dataset", "item", "get", ds_id, iid, "--json"])) or {}
        gm = got.get("metadata") or (got.get("item") or {}).get("metadata") or {}
        # 整棵 metadata 逐键比对：任何一个键被压平/丢键都会让 dumps 不等
        same_all = json.dumps(gm, sort_keys=True, ensure_ascii=False) == \
            json.dumps(meta, sort_keys=True, ensure_ascii=False)
        same_check = json.dumps(gm.get("check"), sort_keys=True, ensure_ascii=False) == \
            json.dumps(meta.get("check"), sort_keys=True, ensure_ascii=False)
        lost = sorted(set(meta) - set(gm))
        if not (same_all and same_check):
            ok_all = False
        t1_detail.append("%s 全等=%s check=%s 丢键=%s item=%s"
                         % (rid, same_all, same_check, lost or "无", iid))

    report.append(("T1 metadata 原样存取", "PASS" if ok_all else "FAIL", "；".join(t1_detail)[:400]))
    item_id = item_ids[0] if item_ids else None

    # ---- T2：容量上限（dataset get 不带 limits，走 api 透传能力接口）
    caps = cli(["api", "/api/v2/datasets/capabilities", "--json"])
    cd = data_of(caps) or {}
    if cd:
        blob = json.dumps(cd, ensure_ascii=False)
        report.append(("T2 容量上限", "PASS", blob[:320]))
    else:
        report.append(("T2 容量上限", "UNKNOWN",
                       json.dumps(caps.get("error"), ensure_ascii=False)[:220]))

    # ---- T3：先发版，再改一条，看 version diff 能细到什么粒度
    # version diff 的语义是「已发布版本 vs 当前内容」，所以必须先 publish 出 v1。
    if item_id and item_ids:
        # publish 走乐观锁，必须带上当前 revision，否则报 conflict
        cur = data_of(cli(["dataset", "get", ds_id, "--json"])) or {}
        rev = cur.get("revision")
        pub = cli(["dataset", "version", "publish", ds_id,
                   "--note", "VERIFY 基线", "--revision", str(rev), "--json"])
        pubd = data_of(pub) or {}
        ver_id = pubd.get("version_id") or pubd.get("id") or \
            (pubd.get("version") or {}).get("id")

        if (pub.get("error") or {}).get("code") or not ver_id:
            hint = ""
            if "conflict" in json.dumps(pub.get("error") or {}, ensure_ascii=False):
                hint = "（该数据集已被改动过，加 --fresh 新建一个再跑）"
            report.append(("T3 version diff 粒度", "UNKNOWN",
                           "发版失败" + hint + "：" + json.dumps(pub.get("error") or pubd,
                                                              ensure_ascii=False)[:200]))
        else:
            print("[T3] 已发版 v1 =", ver_id)
            r0 = rules[0]
            upd_payload = {
                "external_id": r0["rule_id"],
                "question": r0.get("rule_text", "")[:2000],
                "tags": [r0.get("category", ""), r0.get("subcategory", ""),
                         r0.get("exec_path", ""), "VERIFY"],
                "metadata": dict(merge_ledger(r0["rule_id"])),
            }
            # 只改一个字段，制造最小 diff
            if "evidence_level" in upd_payload["metadata"]:
                upd_payload["metadata"]["evidence_level"] = (
                    "【A】业务方已对照原文核对（VERIFY 写入 %s）" % STAMP)
            else:
                upd_payload["metadata"]["status"] = "CONFIRMED@%s" % STAMP
            with open("_verify_item2.json", "w", encoding="utf-8") as f:
                json.dump(upd_payload, f, ensure_ascii=False)

            upd = cli(["dataset", "item", "update", ds_id, item_id,
                       "--input", "_verify_item2.json", "--json"])
            if (upd.get("error") or {}).get("code"):
                report.append(("T3 version diff 粒度", "FAIL",
                               json.dumps(upd.get("error"), ensure_ascii=False)[:300]))
            else:
                diff = cli(["dataset", "version", "diff", ds_id, str(ver_id), "--json"])
                dd = data_of(diff) or {}
                blob = json.dumps(dd, ensure_ascii=False)
                # 实测结论：diff 返回条目级 before/after 全量快照，不直接给 changed_fields。
                # 所以「字段级改动清单」要前端拿 before/after 自己比 —— 能用，但不是平台现成给的。
                has_before_after = "\"before\"" in blob and "\"after\"" in blob
                has_field_level = any(k in blob for k in ("changed_fields", "\"path\""))
                if has_field_level:
                    verdict, how = "PASS", "字段级"
                elif has_before_after:
                    verdict, how = "PASS(条目级)", "条目级 before/after，字段差异需前端自比"
                else:
                    verdict, how = "UNKNOWN", "既无字段级也无 before/after"
                report.append(("T3 version diff 粒度", verdict, how + "：" + blob[:260]))
    else:
        report.append(("T3 version diff 粒度", "UNKNOWN", "T1 未建出 item，跳过"))

    # ---- 汇总
    print("\n" + "=" * 68)
    print("验证结论")
    print("=" * 68)
    for name, verdict, note in report:
        print("%-26s %-8s %s" % (name, verdict, note))

    bad = [r for r in report if r[1] == "FAIL"]
    print("\nPASS %d / UNKNOWN %d / FAIL %d"
          % (sum(1 for r in report if r[1] == "PASS"),
             sum(1 for r in report if r[1] == "UNKNOWN"),
             len(bad)))

    if args.keep:
        print("\n验证数据集保留：", ds_id)
    else:
        print("\n验证数据集 id = %s（未自动删除，平台无 dataset 删除命令；"
              "如需清理请在控制台归档）" % ds_id)

    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
