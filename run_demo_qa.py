# -*- coding: utf-8 -*-
"""按演示脚本顺序跑问题，保存回答与证据。"""
import json, time, sys
import ape_api as a

CHAT = "chatd07f470a49f092b4"
OUT = "demo_run_results.json"

QUESTIONS = [
    ("Q1-预热温度",
     "AH36 高强度钢、板厚 22mm 的对接焊，预热温度和层间温度要求是多少？依据哪份文件的哪一条？"),
    ("Q2-涂装要求",
     "船东对压载舱涂装有哪些额外要求？和我们厂自己的标准比，有哪些地方必须改？"),
    ("Q3-故意缺失",
     "去年 3 号门机吊装方案里，吊索具是怎么选型的？"),
    ("Q4-变更影响",
     "V-SW-201 这个蝶阀如果要换成江苏神通的，会影响哪些船、哪些图纸、哪些合同条款？还有什么没落实的？"),
    ("Q5-跨文件推理",
     "W35 周报里 S-203 和 S-207 两个分段返修率偏高，从工艺角度分析可能的原因，并给出依据。"),
    ("Q6-交付物",
     "请按 ECN-2026-0087 出一份变更影响与待办清单，要求：列出已确认影响、待澄清事项、责任部门，并标注每条的依据来源。"),
]


def run_one(chat, q, name):
    r = a.S.post(f"{a.BASE}/api/v2/agent/chats/{chat}/turns",
                 params=a.ws(), json={"query": q}, timeout=60)
    if r.status_code >= 300:
        return {"name": name, "question": q, "error": r.text[:300]}
    t = r.json()["turn"]["turn_id"]
    print(f"  turn {t} 提交", flush=True)
    deadline = time.time() + 420
    while time.time() < deadline:
        s = a.S.get(f"{a.BASE}/api/v2/agent/chats/{chat}/turns/{t}",
                    params=a.ws(), timeout=60).json()
        st = s.get("status")
        if st in ("COMPLETED", "FAILED", "CANCELLED"):
            break
        time.sleep(5)
    else:
        return {"name": name, "question": q, "error": "timeout"}

    parts = s.get("parts") or []
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    tools = [p.get("type", "").replace("tool-apemind__", "") for p in parts
             if str(p.get("type", "")).startswith("tool-")]
    cites = []
    for p in parts:
        if p.get("type") == "data-citation":
            d = p.get("data") or p.get("citation") or {}
            src = d.get("document_title") or d.get("title") or d.get("filename")
            if src and src not in cites:
                cites.append(src)
    excerpt = [p for p in parts if p.get("type") == "data-source-excerpt"]
    return {"name": name, "question": q, "status": st, "turn_id": t,
            "answer": text, "tools": tools, "tool_calls": len(tools),
            "citations": cites, "excerpts": len(excerpt)}


if __name__ == "__main__":
    a.login()
    results = []
    for name, q in QUESTIONS:
        print(f"== {name}", flush=True)
        res = run_one(CHAT, q, name)
        print(f"   status={res.get('status')} tools={res.get('tool_calls')} "
              f"cites={len(res.get('citations') or [])} ans_len={len(res.get('answer') or '')}",
              flush=True)
        results.append(res)
    json.dump(results, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("SAVED", OUT)
