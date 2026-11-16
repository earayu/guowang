# -*- coding: utf-8 -*-
"""ApeMind Turn SSE 事件流解析器（应对聚合接口 parts 延迟/为空）。

实测背景：2026-11-14 V1 题事件流已含 finish/text-end/22 次工具调用并产出完整回答，
但 GET /agent/chats/{chat}/turns/{turn} 仍返回 status=RUNNING、parts=[]。
因此 L1 题库以事件流为完成判据与证据主源，聚合接口读数并列保留。
"""
import json
import re
import collections


def fetch_events(session, base, ws_params, chat_id, turn_id, timeout=180):
    p = f"{base}/api/v2/agent/chats/{chat_id}/turns/{turn_id}/events"
    r = session.get(p, params=ws_params, timeout=timeout)
    return r.status_code, r.text


def parse_events(raw):
    events = []
    for line in raw.splitlines():
        if line.startswith("data: "):
            try:
                events.append(json.loads(line[6:]))
            except Exception:
                pass
    types = collections.Counter(e.get("type") for e in events)

    answer_parts, reasoning_parts = [], []
    tools, excerpts, errors = [], [], []
    for e in events:
        t = e.get("type")
        if t == "text-delta":
            answer_parts.append(e.get("delta") or "")
        elif t == "reasoning-delta":
            reasoning_parts.append(e.get("delta") or "")
        elif t in ("tool-input-start", "tool-input-available",
                   "tool-output-available", "tool-output-error"):
            tools.append(e)
        elif t == "data-source-excerpt":
            excerpts.append(e)
        elif t == "error" or (isinstance(e.get("data"), dict)
                              and e["data"].get("intent") == "error"):
            errors.append(e)

    answer = "".join(answer_parts)
    reasoning = "".join(reasoning_parts)
    tool_names = collections.Counter(
        str(e.get("toolName") or e.get("tool_name") or
            (e.get("input") or {}).get("toolName") or "?")
        for e in tools if e.get("type") == "tool-input-available")

    finish_n = types.get("finish", 0)
    completed = finish_n > 0 and types.get("text-end", 0) > 0
    return {
        "event_bytes": len(raw),
        "event_count": len(events),
        "event_types": dict(types),
        "status_from_events": "COMPLETED" if completed else "RUNNING",
        "finish_events": finish_n,
        "answer": answer,
        "answer_chars": len(answer),
        "reasoning": reasoning,
        "reasoning_chars": len(reasoning),
        "tool_events": tools,
        "tool_names": dict(tool_names),
        "tool_calls": len([e for e in tools if e.get("type") == "tool-input-available"]),
        "tool_output_errors": len([e for e in tools if e.get("type") == "tool-output-error"]),
        "excerpts": excerpts,
        "excerpt_count": len(excerpts),
        "errors": errors[:5],
    }


def summarize_for_report(p):
    return {
        "status_from_events": p["status_from_events"],
        "event_bytes": p["event_bytes"],
        "event_count": p["event_count"],
        "finish_events": p["finish_events"],
        "answer_chars": p["answer_chars"],
        "tool_calls": p["tool_calls"],
        "tool_names": p["tool_names"],
        "tool_output_errors": p["tool_output_errors"],
        "excerpt_count": p["excerpt_count"],
        "event_types": p["event_types"],
    }


if __name__ == "__main__":
    import ape_api as a
    import os
    ROOT = r"C:\Users\linkz\WorkBuddy\PC办公"
    st = json.load(open(os.path.join(ROOT, "sgcc_run_state.json"), encoding="utf-8"))
    a.login()
    code, raw = fetch_events(a.S, a.BASE, a.ws(), st["chat_id"],
                             "turn6be04656b60885de")
    p = parse_events(raw)
    print("HTTP", code, "SUMMARY", json.dumps(summarize_for_report(p), ensure_ascii=False))
    print("--- ANSWER head 2200 ---")
    print(p["answer"][:2200])
    json.dump({"turn_id": "turn6be04656b60885de", "summary": summarize_for_report(p),
               "answer": p["answer"], "tool_events": p["tool_events"],
               "excerpts": p["excerpts"]},
              open(os.path.join(ROOT, "sgcc_v1_events_parsed.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
