# -*- coding: utf-8 -*-
"""国网 L1 题库 V2 跑法：以 SSE 事件流为完成判据（修复聚合接口 parts 滞后）。

背景：V1 实测事件流已 finish / 产出 5670 字符答案，但聚合 turns/{tid} 仍
status=RUNNING、parts=[]。旧脚本 sgcc_run_qa.py 会等到 660s 超时并丢弃答案。
本脚本：先查聚合，未终态时定期查事件流；一旦出现 finish 即判完成，
并把事件流解析出的完整答案、工具轨迹、原文摘录落盘；聚合读数并列保留。

断点续传：每完成一题写一次 sgcc_l1_results.json；已 COMPLETED 的题跳过。
"""
import json, time, os, datetime
import ape_api as a
from sgcc_run_qa import QUESTIONS, all_docs, summarize_tool
from sgcc_events import fetch_events, parse_events, summarize_for_report

ROOT = r"C:\Users\linkz\WorkBuddy\PC办公"
STATE = os.path.join(ROOT, "sgcc_run_state.json")
OUT = os.path.join(ROOT, "sgcc_l1_results.json")


def excerpt_text(e):
    d = e.get("data") or e
    for k in ("citedText", "cited_text", "text", "excerpt", "content", "snippet"):
        v = d.get(k)
        if isinstance(v, str) and v.strip():
            return v
    return ""


def tool_summary_from_events(p, dmap):
    out = []
    for e in p["tool_events"]:
        if e.get("type") != "tool-input-available":
            continue
        name = str(e.get("toolName") or "?").replace("apemind__", "")
        inp = e.get("input") or {}
        rec = {"tool": name}
        for k in ("query", "pattern", "handles", "document_ids", "kb", "limit"):
            if isinstance(inp, dict) and inp.get(k) is not None:
                rec[k] = str(inp[k])[:200]
        out.append(rec)
    return out


def run_one(chat, q, name, dmap):
    ts = time.time()
    r = a.S.post(f"{a.BASE}/api/v2/agent/chats/{chat}/turns",
                 params=a.ws(), json={"query": q}, timeout=90)
    if r.status_code >= 300:
        return {"name": name, "question": q, "error": f"HTTP {r.status_code}: {r.text[:300]}"}
    tid = r.json()["turn"]["turn_id"]
    print(f"  turn {tid} submitted", flush=True)

    deadline = time.time() + 900
    agg, raw, events_done = {}, None, False
    last_ev = 0
    while time.time() < deadline:
        try:
            agg = a.S.get(f"{a.BASE}/api/v2/agent/chats/{chat}/turns/{tid}",
                          params=a.ws(), timeout=90).json()
        except Exception as e:
            print("  poll err", str(e)[:100], flush=True)
            time.sleep(8)
            continue
        if agg.get("status") in ("COMPLETED", "FAILED", "CANCELLED"):
            print("  aggregate terminal", agg.get("status"), flush=True)
            break
        # 聚合滞后 90s 后，开始用事件流辅助判完成
        if time.time() - ts > 90 and time.time() - last_ev > 90:
            try:
                code, raw = fetch_events(a.S, a.BASE, a.ws(), chat, tid, timeout=180)
                last_ev = time.time()
                if code == 200 and '"type":"finish"' in raw[-4000:]:
                    print("  events finish detected", flush=True)
                    events_done = True
                    break
            except Exception as e:
                print("  events check err", str(e)[:100], flush=True)
                last_ev = time.time()
        time.sleep(6)

    # 最终取一次完整事件流作为证据主源
    try:
        code, raw = fetch_events(a.S, a.BASE, a.ws(), chat, tid, timeout=240)
        p = parse_events(raw) if code == 200 else None
    except Exception as e:
        print("  final events err", str(e)[:120], flush=True)
        p = None

    parts = agg.get("parts") or []
    agg_text = "".join(x.get("text", "") for x in parts if x.get("type") == "text")
    agg_reason = "\n".join(x.get("text", "") for x in parts if x.get("type") == "reasoning")
    agg_trace = [summarize_tool(x, dmap) for x in parts
                 if str(x.get("type", "")).startswith("tool-")]
    agg_cites = [x.get("cited_text") for x in parts
                 if x.get("type") == "data-citation" and x.get("cited_text")]

    ev = p or {}
    text = agg_text if len(agg_text) > len(ev.get("answer") or "") else (ev.get("answer") or "")
    reason = agg_reason if len(agg_reason) > len(ev.get("reasoning") or "") else (ev.get("reasoning") or "")
    trace = agg_trace if agg_trace else tool_summary_from_events(ev, dmap) if ev else []
    cites = agg_cites if agg_cites else [x for x in (excerpt_text(e) for e in (ev.get("excerpts") or [])) if x]
    status = agg.get("status") if agg.get("status") in ("COMPLETED", "FAILED", "CANCELLED") \
        else ("COMPLETED" if (ev.get("status_from_events") == "COMPLETED" or events_done) else "TIMEOUT")

    sec = None
    st0, fi = agg.get("started_at"), agg.get("finished_at")
    if st0 and fi:
        f = lambda x: datetime.datetime.fromisoformat(x.replace("Z", "+00:00"))
        sec = round((f(fi) - f(st0)).total_seconds(), 1)
    return {
        "name": name, "question": q, "status": status, "turn_id": tid,
        "seconds": sec, "wall_seconds": round(time.time() - ts, 1),
        "completion_source": "aggregate" if agg_text else "events",
        "aggregate_status": agg.get("status"), "aggregate_parts": len(parts),
        "events": summarize_for_report(ev) if ev else None,
        "answer": text, "reasoning": reason, "trace": trace,
        "tool_calls": len(trace), "citations": len(cites),
        "citation_texts": cites[:40], "error_message": agg.get("error_message"),
    }


def main():
    st = json.load(open(STATE, encoding="utf-8"))
    a.login()
    dmap = {x["id"]: x["name"] for x in all_docs(st["collection_id"])}
    print("DOC MAP", len(dmap), flush=True)
    results = []
    if os.path.exists(OUT):
        results = json.load(open(OUT, encoding="utf-8")).get("results", [])
    done = {r["name"] for r in results if r.get("status") == "COMPLETED"}
    print("ALREADY DONE", sorted(done), flush=True)
    for name, q in QUESTIONS:
        if name in done:
            print(f"== {name} (skip, already COMPLETED)", flush=True)
            continue
        print(f"== {name} {time.strftime('%H:%M:%S')}", flush=True)
        res = run_one(st["chat_id"], q, name, dmap)
        print(f"   {res.get('status')} src={res.get('completion_source')} "
              f"wall={res.get('wall_seconds')}s tools={res.get('tool_calls')} "
              f"cites={res.get('citations')} len={len(res.get('answer') or '')} "
              f"ev={bool(res.get('events'))} err={str(res.get('error'))[:100]}", flush=True)
        results = [r for r in results if r["name"] != name] + [res]
        results.sort(key=lambda r: [x[0] for x in QUESTIONS].index(r["name"]))
        json.dump({"chat_id": st["chat_id"], "collection_id": st["collection_id"],
                   "results": results}, open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("SAVED", OUT, flush=True)


if __name__ == "__main__":
    main()
