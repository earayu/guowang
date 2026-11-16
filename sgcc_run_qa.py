# -*- coding: utf-8 -*-
"""国网真实样本 L1 题库 V1-V7 + 附测：逐题落盘工具轨迹、引用、耗时、回答全文。"""
import json, time, os, datetime, sys
import ape_api as a

ROOT = r"C:\Users\linkz\WorkBuddy\PC办公"
STATE = os.path.join(ROOT, "sgcc_run_state.json")
OUT = os.path.join(ROOT, "sgcc_l1_results.json")

QUESTIONS = [
    ("V1-双版差异",
     "1525K1 批次里同时提供了「资格预审」和「资格后审」两版采购文件。请比对这两版在对型式试验、检测报告、业绩、型号这四项上的要求差异，逐条给出两版各自的条款位置。注意：库里有多个标包含有同名文件，请说明你依据的是哪一份、并区分不同标包。"),
    ("V2-合规候选",
     "这批招标文件里，哪些条款可能构成排斥限制竞争或指定品牌型号？逐条给出条款原文位置与判断依据。请只列「候选待核条款」，并逐条标注「需人工判定是否违规」，不要下违规或否决的终局结论。"),
    ("V3-跨四类文件一致性",
     "投标保证金、履约保证金、最高限价、质保期、交货期这五项，在招标公告、采购文件、合同通用条款、专用合同里是否一致？列出不一致项，并分别标注各自条款位置与文件名。"),
    ("V4-跨包复用与跨批次差异",
     "152507 批次里，4004 电缆隧道在线监测系统的包1 与包2 货物清单是否相同？另外，152507 的 4006 与 1525K1 的 4033 都是输电线路故障监测系统，两者在技术要求上有哪些差异？请说明依据。"),
    ("V5-三级溯源",
     "请给出「否决投标」的全部适用情形，并逐条回读原文、标注文件名与条款号。"),
    ("V6-故意失败题",
     "本次评标的专家打分表在哪里？各投标人的技术得分分别是多少？"),
    ("V7-结构化交付物",
     "按 V1 的双版差异清单，出一份「待澄清事项表」，要求包含：差异项、责任方、依据来源（文件名+条款）、仍缺的文件。用表格输出。"),
    ("附测-doc老格式",
     "知识库中是否收录了名为「附件：线路在线监测装置 输电线路故障监测系统.doc」或「图像在线监测装置.doc」这类 .doc 老格式文件？如已收录，请引用其中任意一段原文并标注文件名；如未收录或无法读取，请明确说明。"),
]


def all_docs(cid):
    page, out = 1, []
    while True:
        d = a.S.get(f"{a.BASE}/api/v2/collections/{cid}/documents",
                    params=a.ws({"page": page, "page_size": 100}), timeout=90).json()
        out.extend(d.get("items") or [])
        if not d.get("has_next"):
            return out
        page += 1


def summarize_tool(part, dmap):
    t = str(part.get("type", "")).replace("tool-apemind__", "")
    out = part.get("output") or {}
    info = {"tool": t}
    if isinstance(out, dict):
        if out.get("query"):
            info["query"] = out["query"]
        if out.get("modes_applied"):
            info["modes"] = out["modes_applied"]
        if isinstance(out.get("hits"), list):
            info["hits"] = len(out["hits"])
        if isinstance(out.get("results"), list):
            titles = []
            for r in out["results"][:8]:
                tt = r.get("title") or r.get("doc_title") or r.get("document_title")
                if tt and tt not in titles:
                    titles.append(tt)
            info["docs"] = titles
            info["hits"] = len(out["results"])
        if out.get("groups"):
            info["docs"] = [g.get("title") for g in out["groups"]]
            info["hits"] = sum(len(g.get("matches") or []) for g in out["groups"])
        if isinstance(out.get("items"), list):
            ids = []
            for it in out["items"]:
                rid = (it.get("requested_ref") or {}).get("document_id")
                if rid and rid not in ids:
                    ids.append(rid)
            info["docs"] = [dmap.get(i, i[:8]) for i in ids]
            info["hits"] = len(out["items"])
    return info


def run_one(chat, q, name, dmap):
    ts = time.time()
    r = a.S.post(f"{a.BASE}/api/v2/agent/chats/{chat}/turns",
                 params=a.ws(), json={"query": q}, timeout=90)
    if r.status_code >= 300:
        return {"name": name, "question": q, "error": f"HTTP {r.status_code}: {r.text[:300]}"}
    tid = r.json()["turn"]["turn_id"]
    print(f"  turn {tid} submitted", flush=True)
    deadline = time.time() + 660
    s = {}
    while time.time() < deadline:
        try:
            s = a.S.get(f"{a.BASE}/api/v2/agent/chats/{chat}/turns/{tid}",
                        params=a.ws(), timeout=90).json()
        except Exception as e:
            print("  poll err", str(e)[:100], flush=True)
            time.sleep(8)
            continue
        if s.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(6)
    parts = s.get("parts") or []
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    reason = "\n".join(p.get("text", "") for p in parts if p.get("type") == "reasoning")
    trace = [summarize_tool(p, dmap) for p in parts
             if str(p.get("type", "")).startswith("tool-")]
    cites, cite_docs = [], []
    for p in parts:
        if p.get("type") == "data-citation":
            d = p.get("data") or {}
            did = (d.get("location") or {}).get("document_id")
            nm = dmap.get(did)
            if nm and nm not in cite_docs:
                cite_docs.append(nm)
            st = d.get("cited_text") or ""
            if st:
                cites.append(st)
    touched = []
    for tr in trace:
        for nm in tr.get("docs") or []:
            if nm and nm not in touched:
                touched.append(nm)
    sec = None
    st0, fi = s.get("started_at"), s.get("finished_at")
    if st0 and fi:
        f = lambda x: datetime.datetime.fromisoformat(x.replace("Z", "+00:00"))
        sec = round((f(fi) - f(st0)).total_seconds(), 1)
    return {"name": name, "question": q, "status": s.get("status"), "turn_id": tid,
            "seconds": sec, "wall_seconds": round(time.time() - ts, 1),
            "answer": text, "reasoning": reason, "trace": trace,
            "tool_calls": len(trace), "touched_docs": touched,
            "cited_docs": cite_docs, "citations": len(cites),
            "citation_texts": cites[:40], "error_message": s.get("error_message")}


def main():
    st = json.load(open(STATE, encoding="utf-8"))
    a.login()
    dmap = {x["id"]: x["name"] for x in all_docs(st["collection_id"])}
    print("DOC MAP", len(dmap), flush=True)
    results = []
    if os.path.exists(OUT):
        results = json.load(open(OUT, encoding="utf-8")).get("results", [])
    done = {r["name"] for r in results if r.get("status") == "COMPLETED"}
    for name, q in QUESTIONS:
        if name in done:
            print(f"== {name} (already done, skip)", flush=True)
            continue
        print(f"== {name} {time.strftime('%H:%M:%S')}", flush=True)
        res = run_one(st["chat_id"], q, name, dmap)
        print(f"   {res.get('status')} {res.get('seconds')}s tools={res.get('tool_calls')} "
              f"docs={len(res.get('touched_docs') or [])} cites={res.get('citations')} "
              f"len={len(res.get('answer') or '')} err={str(res.get('error'))[:100]}", flush=True)
        results = [r for r in results if r["name"] != name] + [res]
        results.sort(key=lambda r: [x[0] for x in QUESTIONS].index(r["name"]))
        json.dump({"chat_id": st["chat_id"], "collection_id": st["collection_id"],
                   "results": results}, open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("SAVED", OUT, flush=True)


if __name__ == "__main__":
    main()
