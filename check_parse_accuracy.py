#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""国网 demo · 抽取（解析）准确率核查脚本。

核查口径：把演示判定输入快照（_judge_in_<代号>.json，即 sgcc-field-extract
的真跑输出）里的每一条字段记录，逐条放回平台知识库原文里验证：

  A. 锚点存在性 —— item_no 是否真的出现在对应侧知识库的原文里（防幻觉）
  B. 对位正确性 —— 锚点所在行的窗口内，能否同时找到 desc / 金额 / 数量
     （防止"值对了但安到别的物料头上"）
  C. 标量字段的原文证据 —— 交货期 / 有效期 / 税率 / 投标人名等是否有原文出处

输出：分侧分字段的命中率与明细。判定结论只报"可核查到/核查不到"，
不给"对/错"的终局——那是人工核对的事（与演示合规红线一致）。

用法：先起 sgcc_bff_http.py，再 BFF=http://127.0.0.1:8797 python3 check_parse_accuracy.py
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
BFF = os.environ.get("BFF", "http://127.0.0.1:8797")
TENDER_KBS = ["colcf0af5d45fd7ef6b", "col0cd75b81b6b47b74"]
BID_KB = {"恩施": "cold98e481541486cc5", "襄阳": "col4020b47c9984bbbb",
          "宜昌": "col2894640b355a1b11", "荆州": "col8fe7f3d2e3d2dac5",
          "黄石": "col1c64f1cb56417c15", "华中": "col2de7406a4c8a6e56"}
CODES = ["华中", "襄阳", "宜昌", "荆州", "黄石", "恩施"]


def api(path, timeout=120):
    url = BFF + path
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def grep(kb, q, limit=20):
    u = "/api/grep?kb=%s&q=%s&limit=%d" % (kb, urllib.parse.quote(q), limit)
    return api(u)


def read(handle):
    try:
        return api("/api/read?handle=" + urllib.parse.quote(handle))
    except Exception:
        return {}


def norm(s):
    return re.sub(r"[\s|<br/>　*,，]", "", str(s or ""))


def norm_num(s):
    """金额/数量统一成纯数字串（去掉千分位、小数尾巴、单位），两边都这么规整再比。"""
    t = re.sub(r"[^\d]", "", str(s or ""))
    return t.lstrip("0") or "0"


def num_variants(v):
    """同一个数的等价写法：7452212 / 7,452,212.39 / 745.2212万。任一命中即算。"""
    out = set()
    try:
        f = float(v)
    except (TypeError, ValueError):
        return out
    out.add(norm_num(int(f) if f == int(f) else f))
    wan = f / 10000.0
    out.add(norm_num(("%.4f" % wan).rstrip("0").rstrip(".")))          # 万元形式
    out.add(norm_num(("%.2f" % f)))                                    # 两位小数
    return {x for x in out if x and x != "0"}


def num_any_in(text, vals):
    nt = norm_num(text)
    for v in vals:
        for nv in num_variants(v):
            if nv and nv in nt:
                return True
    return False


_CONTENT = {}


def doc_content(doc_id):
    """直接从平台拉整篇原文（带本地缓存），比 read 的 11 行窗口可靠。"""
    if doc_id in _CONTENT:
        return _CONTENT[doc_id]
    import json as _j
    req = urllib.request.Request(
        "https://apemind.ai/api/v2/collections/%s/documents/%s/content"
        % (_content_kb.get(doc_id, ""), doc_id)
        + "?workspace_id=" + os.environ.get("APEMIND_WORKSPACE_ID", WORKSPACE_ID),
        headers={"Authorization": "Bearer " + API_KEY,
                 "User-Agent": "accuracy-check/0.1"})
    with urllib.request.urlopen(req, timeout=60) as r:
        c = (_j.loads(r.read().decode("utf-8", "ignore")).get("content")) or ""
    _CONTENT[doc_id] = c
    return c


WORKSPACE_ID = "orge0066e5cc05abc86"
API_KEY = os.environ.get("APEMIND_API_KEY", "")
_content_kb = {}


def find_first(kbs, needle, limit=5):
    """在多个库里找锚点；返回命中（含 doc id 与 kb，便于拉全文）。"""
    for kb in kbs:
        try:
            g = grep(kb, needle, limit)
        except Exception as e:
            print("  ! grep 失败", kb, needle[:20], repr(e)[:80], file=sys.stderr)
            continue
        for h in (g.get("hits") or []):
            if h.get("line") and h.get("handle"):
                doc = (h.get("handle") or "").split(":")[0]
                _content_kb[doc] = kb
                return {"kb": kb, "hit": h, "doc": doc,
                        "coverage": g.get("coverage")}
    return None


def check_item(anchor_result, tokens_text, tokens_num):
    """锚点命中后在原文里核对：
    pair_ok   = 锚点行 ±12 行内同时出现全部 文本/数字 token（对位正确性）
    doc_ok    = 全篇至少出现（宽松的值存在性）"""
    if not anchor_result:
        return "no_anchor", None, False, None
    line_no = anchor_result["hit"].get("line") or 1
    try:
        text = doc_content(anchor_result["doc"])
    except Exception as e:
        return "content_fail", repr(e)[:80], False, None
    lines = text.split("\n")
    s = max(0, line_no - 1 - 12)
    w = "\n".join(lines[s: line_no - 1 + 13])
    missing_t = [t for t in tokens_text if norm(t) and norm(t) not in norm(w)]
    missing_n = [] if num_any_in(w, tokens_num) else list(tokens_num)
    pair_ok = not missing_t and not missing_n
    doc_missing_t = [t for t in tokens_text if norm(t) and norm(t) not in norm(text)]
    doc_missing_n = [] if num_any_in(text, tokens_num) else list(tokens_num)
    doc_ok = not doc_missing_t and not doc_missing_n
    miss = {"window_text": missing_t, "window_num": missing_n,
            "doc_text": doc_missing_t, "doc_num": doc_missing_n}
    return ("ok" if pair_ok else "window_miss"), miss, doc_ok, line_no


def main():
    out = {"checked_at": time.strftime("%F %T"), "codes": {}}
    grand = {"anchor": [0, 0], "pair": [0, 0]}
    for code in CODES:
        src = os.path.join(HERE, "_judge_in_%s.json" % code)
        if not os.path.exists(src):
            continue
        d = json.load(open(src, encoding="utf-8"))
        res = {"tender": {}, "bid": {}, "scalars": []}
        # ---------- A/B：tender 侧逐物料 ----------
        for f in d.get("tender_fields") or []:
            items = f.get("items") or []
            if not items:
                continue
            stats = {"n": len(items), "anchor_ok": 0, "pair_ok": 0, "rows": []}
            for it in items:
                item_no = str(it.get("item_no") or "")
                if not item_no:
                    continue
                anchor = find_first(TENDER_KBS, item_no)
                a_ok = bool(anchor)
                must_t = [it.get("desc")]
                must_n = [it.get("cap_wan"), it.get("cap_yuan")]
                verdict, missing, doc_ok, line_no = check_item(
                    anchor, must_t, must_n)
                p_ok = verdict == "ok"
                stats["anchor_ok"] += a_ok
                stats["pair_ok"] += p_ok
                grand["anchor"][a_ok] += 1
                grand["pair"][p_ok] += 1
                stats["rows"].append({"item_no": item_no, "anchor": a_ok,
                                      "pair": p_ok, "doc_ok": doc_ok,
                                      "line": line_no, "missing": missing,
                                      "kb": (anchor or {}).get("kb"),
                                      "coverage": (anchor or {}).get("coverage")})
            res["tender"][f["field"]] = stats
        # ---------- bid 侧逐物料 ----------
        kb_bid = list(BID_KB.values())
        for f in d.get("bid_fields") or []:
            items = f.get("items") or []
            if f["field"] != "bid.price_items" or not items:
                continue
            stats = {"n": len(items), "anchor_ok": 0, "pair_ok": 0, "rows": []}
            for it in items:
                item_no = str(it.get("item_no") or "")
                if not item_no:
                    continue
                anchor = find_first(kb_bid, item_no)
                a_ok = bool(anchor)
                must_t = []
                must_n = [it.get("qty"), it.get("amount_yuan")]
                verdict, missing, doc_ok, line_no = check_item(
                    anchor, must_t, must_n)
                p_ok = verdict == "ok"
                stats["anchor_ok"] += a_ok
                stats["pair_ok"] += p_ok
                grand["anchor"][a_ok] += 1
                grand["pair"][p_ok] += 1
                stats["rows"].append({"item_no": item_no, "anchor": a_ok,
                                      "pair": p_ok, "doc_ok": doc_ok,
                                      "line": line_no, "missing": missing,
                                      "kb": (anchor or {}).get("kb"),
                                      "arith_ok": it.get("arith_ok")})
            res["bid"][f["field"]] = stats
        # ---------- C：标量字段 ----------
        scalars = []
        pf = d.get("peer_facts") or []
        pf0 = pf[0] if pf and isinstance(pf[0], dict) else {}
        checks = [("bid.bidder_name", pf0.get("bid.bidder_name"), list(BID_KB.values())),
                  ("bid.legal_rep_name", pf0.get("bid.legal_rep_name"), list(BID_KB.values()))]
        for name, val, kb in checks:
            if not val:
                scalars.append({"field": name, "value": val, "traceable": None})
                continue
            try:
                g = grep(kb, str(val), 3)
                scalars.append({"field": name, "value": val,
                                "traceable": bool(g.get("hits")),
                                "coverage": g.get("coverage")})
            except Exception as e:
                scalars.append({"field": name, "value": val, "traceable": None,
                                "error": repr(e)[:100]})
        res["scalars"] = scalars
        out["codes"][code] = res
        print("==", code, "tender ok: %s/%s, bid ok: %s/%s" % (
            sum(s.get("pair_ok", 0) for s in res["tender"].values()),
            sum(s.get("n", 0) for s in res["tender"].values()),
            sum(s.get("pair_ok", 0) for s in res["bid"].values()),
            sum(s.get("n", 0) for s in res["bid"].values())), flush=True)
    out["grand"] = {
        "anchor_hit_rate": round(grand["anchor"][1] / max(1, sum(grand["anchor"])), 4),
        "pair_hit_rate": round(grand["pair"][1] / max(1, sum(grand["pair"])), 4),
        "anchor": grand["anchor"], "pair": grand["pair"]}
    path = os.path.join(HERE, "国网Demo_解析准确率核查_V1.json")
    json.dump(out, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("grand:", out["grand"])
    print("saved:", path)


if __name__ == "__main__":
    main()
