# -*- coding: utf-8 -*-
"""多跳（multi-hop）实测：新建独立会话，逐题记录 耗时 / 工具轨迹 / 触及文件 / 引用。

轨迹里最关键的是每一步检索的 query —— 现场演示时就是靠它讲解“第 N 跳在查什么”。
"""
import json, time, datetime, sys
import ape_api as a

BOT = "bot89c72786c1cb2b80"
OUT = "multihop_results.json"

QUESTIONS = [
    ("H1-两跳_归因",
     "W35 周报里 W-203-012 这条焊缝不合格。查一下是谁焊的、他的资质能不能覆盖这条焊缝，"
     "以及当时预热是否达标。"),
    ("H2-三跳_逐条判定",
     "W35 周报里三条不合格焊缝，逐条判断根因是工艺问题、焊工资质问题，还是两者都有。"
     "每条都要给出焊工资质的覆盖情况和预热实测值。"),
    ("H3-四跳_变更可否执行",
     "ECN-2026-0087 的阀门变更，现在能不能下单和装船？把这条链上的卡点全部列出来，"
     "并判断船东口头同意是否足够。"),
    ("H4-四跳_质量追溯",
     "BT-3P 这个压载舱涂层判不合格，根因是什么？只补涂一遍能不能过？对交船文件有什么影响？"),
    ("H5-三跳_计划推演",
     "阀门交期延到 11 月 20 日，会影响哪个计划节点、影响多少天、会不会碰到交船日？"),
    ("H6-四跳_反向完整性",
     "如果下周船东来做进度审查，按我们现在文件里的记录，最可能被挑出的三个问题是什么？"
     "每个问题要指到具体文件条款和记录。"),
    ("H7-两跳_防编造",
     "W-207-002 这条焊缝的焊工，有没有做过 AH36 横焊的资格考试记录？考试日期是哪天？"),
]


def doc_map():
    d = a.list_docs("colfd38d9aef32dc78a")
    return {x["id"]: x["name"] for x in d["items"]}


def summarize_tool(part, dmap):
    """把一条工具调用压缩成可读的一行。"""
    t = str(part.get("type", "")).replace("tool-apemind__", "")
    out = part.get("output") or {}
    info = {"tool": t}
    if isinstance(out, dict):
        if out.get("query"):
            info["query"] = out["query"]
        if out.get("modes_applied"):
            info["modes"] = out["modes_applied"]
        if out.get("hits") and isinstance(out["hits"], list):
            info["hits"] = len(out["hits"])
        if out.get("results") and isinstance(out["results"], list):
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
        if out.get("items"):
            ids = []
            for it in out["items"]:
                rid = ((it.get("requested_ref") or {}).get("document_id"))
                if rid and rid not in ids:
                    ids.append(rid)
            info["docs"] = [dmap.get(i, i[:8]) for i in ids]
            info["hits"] = len(out["items"])
    return info


def run_one(chat, q, name, dmap):
    r = a.S.post(f"{a.BASE}/api/v2/agent/chats/{chat}/turns",
                 params=a.ws(), json={"query": q}, timeout=60)
    if r.status_code >= 300:
        return {"name": name, "question": q, "error": r.text[:300]}
    t = r.json()["turn"]["turn_id"]
    print(f"  turn {t}", flush=True)
    deadline = time.time() + 600
    s = {}
    while time.time() < deadline:
        s = a.S.get(f"{a.BASE}/api/v2/agent/chats/{chat}/turns/{t}",
                    params=a.ws(), timeout=60).json()
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
    return {"name": name, "question": q, "status": s.get("status"), "turn_id": t,
            "seconds": sec, "answer": text, "reasoning": reason,
            "trace": trace, "tool_calls": len(trace),
            "touched_docs": touched, "cited_docs": cite_docs,
            "citations": len(cites), "citation_texts": cites[:40],
            "error_message": s.get("error_message")}


if __name__ == "__main__":
    a.login()
    dmap = doc_map()
    # 新建独立会话，避免与 Q1-Q6 混杂
    r = a.S.post(f"{a.BASE}/api/v2/bots/{BOT}/chats", params=a.ws(),
                 json={"title": "多跳实测 H1-H7"}, timeout=60)
    if r.status_code >= 300:
        print("CREATE CHAT FAIL", r.status_code, r.text[:300]); sys.exit(1)
    chat = r.json()["id"]
    print("CHAT", chat, flush=True)
    results = []
    for name, q in QUESTIONS:
        print(f"== {name}", flush=True)
        res = run_one(chat, q, name, dmap)
        print(f"   {res.get('status')} {res.get('seconds')}s tools={res.get('tool_calls')} "
              f"docs={len(res.get('touched_docs') or [])} cites={res.get('citations')} "
              f"len={len(res.get('answer') or '')}", flush=True)
        results.append(res)
        json.dump({"chat_id": chat, "results": results},
                  open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("SAVED", OUT, "chat", chat)
