# -*- coding: utf-8 -*-
"""国网招标样本 L1 验证：建知识库 / 建 Agent / 建会话，落盘 state.json。"""
import json, time, os
import ape_api as a

STATE = r"C:\Users\linkz\WorkBuddy\PC办公\sgcc_run_state.json"

PROMPT = """你是「国网物资招标文件审查辅助助手」，服务物资采购招标文件标前体检。

【合规红线 · 最高优先级】
- 你只做「提示判断依据」，不做终局判定。不得输出「该条款违规」「应否决投标」「应废标」「评分多少」等结论。
- 涉及排斥限制竞争、指定品牌型号、歧视性条款时，只能表述为「候选待核条款 / 疑似风险点」，并逐条标注「需人工判定是否违规」。
- 不得替代招标人、评标委员会或评标专家的判断，不改变法定责任。

【证据纪律】
- 只依据知识库原文作答。每条结论标注来源（文件名 + 章节/条款号/表行）；引用须能回读原文。
- 库内没有就明确写「知识库中未找到」，并列出已检索的文件范围与关键词；说明为何库中不应有该类文件时必须给出依据。禁止编造条款号、数字、分数、日期、分值。
- 跨文件比对时逐份列出各自条款位置，输出「差异清单 / 冲突表」，不得只复述单份文件，也不得把不同批次、不同标包混为同一份。
- 同名文件来自不同标包时必须区分标包（看文件名前缀的批次与品类标识），不得合并成一份。
- 遇到「资格预审 / 资格后审」两版并列，只陈述版本差异，不预断哪一版有效或是否属于错误。
- 冲突、缺失、证据不足必须显式标注；不足时明确说「证据不足，不能判断」，不用「建议进一步确认」这类套话。

【输出结构】中文，结构固定：结论 → 差异/依据清单（逐条带文件+条款）→ 待澄清 → 需人工判定项。
"""


def main():
    a.login()
    st = {}
    if os.path.exists(STATE):
        st = json.load(open(STATE, encoding="utf-8"))

    if not st.get("collection_id"):
        r = a.create_collection(
            title="国网湖北电力招标文件包·真实样本 L1（1525K1+152507）",
            description="国网湖北电力 2025 年两个批次 18 个标包全部原始文件（未脱敏）。用于 F11/F13/F34/F52 L1 技术验证，非验收。",
            enable_graph=True,
        )
        if not r:
            raise SystemExit("create_collection failed")
        cid = r.get("id") or r.get("collection_id") or (r.get("collection") or {}).get("id")
        print("COLLECTION", cid, flush=True)
        st["collection_id"] = cid
        st["collection_created_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    else:
        cid = st["collection_id"]
        print("COLLECTION reuse", cid, flush=True)

    if not st.get("bot_id"):
        body = {
            "title": "国网招标文件审查辅助助手 L1",
            "description": "标前体检辅助：依据原文给差异清单与候选条款，缺失即说未找到，不下违规/否决/赋分终局结论。",
            "type": "agent",
            "access": {
                "collections": {"mode": "allowlist", "ids": [cid]},
                "agents": {"mode": "listed", "include_self": False, "ids": []},
            },
            "config": {
                "agent": {
                    "completion": {"model_id": "mdl5b1236141ec14513", "temperature": 0.1},
                    "system_prompt_template": PROMPT,
                    "language": "zh-CN",
                    "runtime": {"max_tool_calls": 60, "deadline_s": 600},
                }
            },
        }
        r = a.S.post(f"{a.BASE}/api/v2/bots", params=a.ws(), json=body, timeout=60)
        print("BOT", r.status_code, r.text[:500], flush=True)
        if r.status_code >= 300:
            raise SystemExit("create bot failed")
        bid = r.json().get("id")
        st["bot_id"] = bid
    else:
        bid = st["bot_id"]
        print("BOT reuse", bid, flush=True)

    if not st.get("chat_id"):
        r = a.S.post(f"{a.BASE}/api/v2/bots/{bid}/chats", params=a.ws(),
                     json={"title": "国网真实样本 L1 验证 V1-V7"}, timeout=60)
        print("CHAT", r.status_code, r.text[:300], flush=True)
        if r.status_code >= 300:
            raise SystemExit("create chat failed")
        st["chat_id"] = r.json().get("id")

    json.dump(st, open(STATE, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("STATE", json.dumps(st, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
