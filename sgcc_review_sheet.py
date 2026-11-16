# -*- coding: utf-8 -*-
"""C8 · 逐题人工核对与引用回填工作表（AI 只建表，不判对错、不写标准答案）"""
import io
import json
import re

B = 'c:/Users/linkz/WorkBuddy/PC办公/'
d = json.load(io.open(B + 'sgcc_l1_results.json', encoding='utf-8'))
gt_raw = io.open(B + 'sgcc_ground_truth.json', encoding='utf-8').read()
qa = d['results']

lines = []
A = lines.append
A('# 国网 Demo · 逐题人工核对与引用回填工作表 V1')
A('')
A('> **性质**：业务方核对用的**空判定表**，不是标准答案、不是评测集、不是验收结论。')
A('> **红线**：`判定` / `依据页码` / `回填引用` / `核对人` / `日期` 五列**全部留空**，由国网物资部门业务人员对照原文填写。')
A('> **不得**：AI 代判「答得对」、写参考答案、算准确率、把 8 题表述为「全过」；G3 仍 1/3（缺业务方手写 5 问 + 能判对错对接人）。')
A('> **来源**：`sgcc_l1_results.json`（8 题真跑答案 / 引用 / 工具轨迹）、`sgcc_ground_truth.json`（本地客观基准）。')
A('')
A('---')
A('')
A('## 1. 核对总表（8 题，判定列留空）')
A('')
A('| 题号 | 问题（原文） | 完成判据 | 耗时 | 摘录数 | 工具调用 | 答案字数 | 业务方判定 | 依据页码 | 回填引用 | 核对人 | 日期 |')
A('|---|---|---|---:|---:|---:|---:|---|---|---|---|---|')
for r in qa:
    q = re.sub(r'\s+', ' ', r['question'])[:120]
    A('| %s | %s | %s | %s | %s | %s | %s |  |  |  |  |  |' % (
        r['name'], q.replace('|', '／'), r.get('completion_source'),
        r.get('wall_seconds'), r.get('citations'), r.get('tool_calls'),
        len(r.get('answer') or '')))
A('')
A('> 判定列建议取值：`正确` / `部分正确` / `错误` / `无法判定（缺原文）`；**无法判定不算通过**。')
A('')
A('## 2. 逐题引用回填清单（摘录原文，供逐条回读）')
A('')
for r in qa:
    A('### %s　`%s`' % (r['name'], r.get('turn_id')))
    A('')
    A('- 问题：%s' % re.sub(r'\s+', ' ', r['question'])[:400])
    A('- AI 答案字数 %d｜摘录 %s 条｜工具 %s 次｜完成判据 `%s`｜事件 finish %s 次' % (
        len(r.get('answer') or ''), r.get('citations'), r.get('tool_calls'),
        r.get('completion_source'), (r.get('events') or {}).get('finish_events')))
    cites = r.get('citation_texts') or []
    A('- 摘录原文（%d 条，逐条回读并勾选）：' % len(cites))
    A('')
    A('| # | 摘录原文（截断 300 字） | 对应文件/条款 | 是否与答案一致 | 回填引用 ID |')
    A('|---|---|---|---|---|')
    for i, c in enumerate(cites, 1):
        t = re.sub(r'\s+', ' ', str(c)).replace('|', '／')[:300]
        A('| %d | %s |  |  |  |' % (i, t))
    A('')
    A('- 答案全文：`sgcc_l1_results.json` → `results[%d].answer`；工具轨迹 `trace`（%d 条）同文件。' % (
        qa.index(r), len(r.get('trace') or [])))
    A('')
A('## 3. 必须单独标注的冲突与未验证项')
A('')
A('| 项 | 现状 | 业务方需做什么 |')
A('|---|---|---|')
A('| V3 引用密度低 | 170.8 s / **仅 4 条摘录** / 4,965 字符 | 回读 4 条摘录是否足以支撑答案全部断言 |')
A('| V7 引用密度低 | 139.7 s / **仅 5 条摘录** / 3,623 字符 / 9 项待澄清 | 逐项核对 9 项是否各有原文依据 |')
A('| V4 与本地 sha1 基准张力 | AI 结论与本地「字节完全相同」基准存在张力 | 对照两份原文回读，判 AI 对错；**不改读数** |')
A('| V6 故意失败题 | 20.0 s / 30 摘录 / 890 字符，答「未找到打分表与实际技术得分」 | 确认库内确无打分表；确认「评分标准说明 ≠ 打分记录」的区分成立 |')
A('| 图谱增强效果 | 索引 155 全绿，但 8 题答案产出在收敛前、A5 对照轮未跑 | 不判图谱效果；后续补 A5 对照轮 |')
A('| 8 题答案性质 | 全部为 AI 自述，聚合/事件流两种完成判据并列 | 未经业务方核对，不写「答得对 / 准确率」 |')
A('')
A('## 4. 本地客观基准（只做对照，不等于参考答案）')
A('')
A('`sgcc_ground_truth.json` 内为文件清单、标包归属、同名文件、字节基准等**可核事实**；')
A('它不是标准答案，AI 结论与它冲突时须由业务方回读原文判定，不得由 AI 自行改成一致。')
A('')
A('## 5. 回填后怎么变成评测集（本轮**不做**）')
A('')
A('1. 业务方补齐 G3 剩余 2/3（手写 5 问 + 能判对错对接人）；')
A('2. 本表 8 题逐条回填判定与依据页码，冲突项闭环；')
A('3. **之后**才允许把已核对的条目写入 Dataset 的 `reference_answer` 并发布不可变版本；')
A('4. 在此之前，平台侧 Dataset `国网Demo_L1题库_人工核对骨架_无参考答案` **只有题目与标签**，`dataset eval` 一律不跑。')
A('')
A('---')
A('')
A('> 本表由 `sgcc_review_sheet.py` 从真跑结果机械生成，无任何人工编造条款或分数。')

out = B + '国网Demo_逐题人工核对与引用回填工作表_V1.md'
io.open(out, 'w', encoding='utf-8').write('\n'.join(lines) + '\n')

# 机器可读版（判定列留空）
sheet = []
for r in qa:
    sheet.append({
        'name': r['name'], 'turn_id': r.get('turn_id'), 'question': r['question'],
        'completion_source': r.get('completion_source'), 'wall_seconds': r.get('wall_seconds'),
        'citations': r.get('citations'), 'tool_calls': r.get('tool_calls'),
        'answer_chars': len(r.get('answer') or ''),
        'citation_texts': r.get('citation_texts') or [],
        'business_verdict': None, 'evidence_page': None, 'citation_ref_backfill': None,
        'reviewer': None, 'reviewed_at': None,
        'reference_answer': None,
    })
io.open(B + '国网Demo_逐题人工核对与引用回填_V1.json', 'w', encoding='utf-8').write(
    json.dumps({'meta': {'generated_at': '2026-11-14', 'source': 'sgcc_l1_results.json',
                         'verdict_filled_by_ai': False, 'reference_answer_filled': False,
                         'g3': '1/3'}, 'items': sheet}, ensure_ascii=False, indent=2))
print('OK', out, len(lines), 'lines,', sum(len(r.get('citation_texts') or []) for r in qa), 'citation rows')
