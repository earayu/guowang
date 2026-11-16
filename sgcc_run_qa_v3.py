# -*- coding: utf-8 -*-
"""国网 L1 题库 V3：每题独立会话，绕开 409 active_turn 状态锁。

实测背景（2026-11-14 12:42）：同一 chat 连发 7 题全部 HTTP 409 CONFLICT
code=1005，details.active_turn_id=turn04315b093195ecc1 —— 前一个 Turn 未释放
active 状态时，该 chat 拒绝新提问。V1 事件流 finish 后约 9 分钟聚合接口才
COMPLETED（parts=76），因此每题用独立 chat + 事件流判完成，不等聚合落库。
"""
import json, time, os
import ape_api as a
from sgcc_run_qa import QUESTIONS, all_docs
from sgcc_run_qa_v2 import run_one

ROOT = r"C:\Users\linkz\WorkBuddy\PC办公"
STATE = os.path.join(ROOT, "sgcc_run_state.json")
OUT = os.path.join(ROOT, "sgcc_l1_results.json")
CHATLOG = os.path.join(ROOT, "sgcc_chat_map.json")


def create_chat(bot_id, title):
    r = a.S.post(f"{a.BASE}/api/v2/bots/{bot_id}/chats", params=a.ws(),
                 json={"title": title}, timeout=60)
    if r.status_code >= 300:
        raise RuntimeError(f"create chat {r.status_code}: {r.text[:300]}")
    return r.json().get("id")


def main():
    st = json.load(open(STATE, encoding="utf-8"))
    a.login()
    dmap = {x["id"]: x["name"] for x in all_docs(st["collection_id"])}
    print("DOC MAP", len(dmap), "| BOT", st["bot_id"], flush=True)

    results = []
    if os.path.exists(OUT):
        results = json.load(open(OUT, encoding="utf-8")).get("results", [])
    # 清掉上一轮 409 空结果，只保留有答案的条目
    results = [r for r in results if (r.get("answer") or "").strip()]
    done = {r["name"] for r in results if r.get("status") == "COMPLETED"}
    print("ALREADY DONE", sorted(done), flush=True)

    cmap = json.load(open(CHATLOG, encoding="utf-8")) if os.path.exists(CHATLOG) else {}
    for name, q in QUESTIONS:
        if name in done:
            print(f"== {name} (skip)", flush=True)
            continue
        print(f"== {name} {time.strftime('%H:%M:%S')}", flush=True)
        try:
            chat = create_chat(st["bot_id"], f"国网L1-{name}")
            cmap[name] = chat
            print("  chat", chat, flush=True)
        except Exception as e:
            print("  CREATE CHAT FAILED", str(e)[:200], flush=True)
            results = [r for r in results if r["name"] != name] + [
                {"name": name, "question": q, "status": "BLOCKED", "error": str(e)[:300]}]
            json.dump({"chat_id": st["chat_id"], "collection_id": st["collection_id"],
                       "results": results}, open(OUT, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            continue
        res = run_one(chat, q, name, dmap)
        res["chat_id"] = chat
        print(f"   {res.get('status')} src={res.get('completion_source')} "
              f"wall={res.get('wall_seconds')}s tools={res.get('tool_calls')} "
              f"cites={res.get('citations')} len={len(res.get('answer') or '')} "
              f"ev={bool(res.get('events'))} err={str(res.get('error'))[:140]}", flush=True)
        results = [r for r in results if r["name"] != name] + [res]
        results.sort(key=lambda r: [x[0] for x in QUESTIONS].index(r["name"]))
        json.dump({"chat_id": st["chat_id"], "collection_id": st["collection_id"],
                   "results": results}, open(OUT, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        json.dump(cmap, open(CHATLOG, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("SAVED", OUT, flush=True)


if __name__ == "__main__":
    main()
