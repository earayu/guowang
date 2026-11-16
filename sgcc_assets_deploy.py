# -*- coding: utf-8 -*-
"""C8 · 平台侧资产最小集真部署（Skill / Function / Dataset）
反假绿边界：
  - Dataset 只建「题目 + 标签」骨架，reference_answer 一律留空，禁止自动评分；
  - Skill 只核实状态，不挂载 Agent（挂载会改 Agent 行为，须单独做同 8 题 A/B 零回归）；
  - Function 纯结构化转换，不做判定、不下违规/否决结论，输出全部 CANDIDATE。
"""
import io
import json
import os
import subprocess
import time

B = 'c:/Users/linkz/WorkBuddy/PC办公/'
CLI = B + 'apemind-cli/apemind.exe'
OUT = B + 'sgcc_assets_deploy_result.json'
result = {'at': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'steps': []}


def run(args, timeout=180):
    p = subprocess.run([CLI] + args, cwd=B, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', timeout=timeout)
    raw = (p.stdout or '').strip()
    try:
        env = json.loads(raw)
    except Exception:
        env = {'raw': raw[:1500], 'stderr': (p.stderr or '')[-600:]}
    rec = {'cmd': ' '.join(args), 'exit': p.returncode, 'request_id': env.get('request_id') if isinstance(env, dict) else None}
    result['steps'].append(rec)
    print('CMD', rec['cmd'][:110], '-> exit', p.returncode, 'rid', rec['request_id'])
    return p.returncode, env


def dump():
    io.open(OUT, 'w', encoding='utf-8').write(json.dumps(result, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------- 1. Skill 状态核实（不挂载）
rc, env = run(['skill', 'list', '--json'])
items = (env.get('data') or {}).get('items') or []
skill = next((i for i in items if i.get('id') == 'skil3c96316cf7960d9a3ab5'), None)
result['skill'] = {'found': bool(skill), 'enabled': (skill or {}).get('enabled'),
                   'used_by_bots': (skill or {}).get('used_by_bots'),
                   'version': (skill or {}).get('version'), 'total_bytes': (skill or {}).get('total_bytes'),
                   'mounted_to_agent': False, 'note': '本轮不挂载 Agent'}
dump()

# ---------------------------------------------------------------- 2. Function：待澄清事项表（纯结构化）
FD = B + 'sgcc_fn_clarification'
os.makedirs(FD, exist_ok=True)
MAIN = '''"""国网 Demo · 待澄清事项表生成（纯结构化转换，不做任何合规判定）。

平台侧 Function 资产：输入差异清单条目，输出统一 CANDIDATE 的待澄清事项表。
195 号文辅助性定位：不自动否决 / 不赋分 / 不定标 / 不作违规终局判定。
"""
from typing import Any, Dict, List

from pydantic import BaseModel, Field

from apemind_fn import Context


class Input(BaseModel):
    batch_id: str = Field(description="批次编号，例如 1525K1")
    diff_items: List[Dict[str, Any]] = Field(default_factory=list, description="差异清单条目")


class Output(BaseModel):
    table: List[Dict[str, Any]]
    candidate_count: int
    executable: bool
    disclaimer: str


DISCLAIMER = ("本表为候选待核事项，不构成违规或有效性终局判定；"
              "依据 195 号文辅助性定位，判定权在招标人与评标委员会。")


def main(inp: Input, ctx: Context) -> Output:
    rows = []
    with ctx.step("生成待澄清事项表", detail={"batch_id": inp.batch_id, "items": len(inp.diff_items)}):
        for i, d in enumerate(inp.diff_items, 1):
            rows.append({
                "seq": i,
                "batch_id": inp.batch_id,
                "item": str(d.get("item", "")),
                "pre_review": str(d.get("pre_review", "")),
                "post_review": str(d.get("post_review", "")),
                "source": str(d.get("source", "")),
                "missing_files": str(d.get("missing_files", "")),
                "owner": "招标人（发澄清或修改）；评标委员会按澄清后版本执行",
                "status": "CANDIDATE",
                "needs_human": True,
            })
    return Output(table=rows, candidate_count=len(rows), executable=False, disclaimer=DISCLAIMER)
'''
io.open(FD + '/main.py', 'w', encoding='utf-8').write(MAIN)

sample_in = {"batch_id": "1525K1", "diff_items": [
    {"item": "资格审查方式", "pre_review": "预审合格", "post_review": "投标时提交资格审查资料",
     "source": "招标公告 3.6 / 附件 2.1 / 附件 2.2", "missing_files": "适用版本澄清"}]}
sample_out = {
    "table": [{
        "seq": 1, "batch_id": "1525K1", "item": "资格审查方式",
        "pre_review": "预审合格", "post_review": "投标时提交资格审查资料",
        "source": "招标公告 3.6 / 附件 2.1 / 附件 2.2",
        "missing_files": "适用版本澄清",
        "owner": "招标人（发澄清或修改）；评标委员会按澄清后版本执行",
        "status": "CANDIDATE", "needs_human": True}],
    "candidate_count": 1, "executable": False,
    "disclaimer": ("本表为候选待核事项，不构成违规或有效性终局判定；"
                   "依据 195 号文辅助性定位，判定权在招标人与评标委员会。"),
}
MANIFEST = {
    "slug": "sgcc-clarification-table",
    "title": "国网 Demo · 待澄清事项表（CANDIDATE，不可执行判定）",
    "description": "输入双版差异清单，输出统一 CANDIDATE 的待澄清事项表；纯结构化转换，不下违规/否决/赋分/定标结论。195 号文辅助性定位。",
    "network": False, "secret_names": [],
    "permissions": {"functions": "none", "knowledge_base": "view"},
    "examples": [{"input": sample_in, "expected_output": sample_out}],
}
io.open(FD + '/function.json', 'w', encoding='utf-8').write(json.dumps(MANIFEST, ensure_ascii=False, indent=2))

rc, env = run(['function', 'diff', 'sgcc_fn_clarification', '--json'])
result['function_diff'] = {'exit': rc, 'data': (env.get('data') if isinstance(env, dict) else None)}
dump()

rc, env = run(['function', 'apply', 'sgcc_fn_clarification', '--dry-run', '--json'])
result['function_apply_dryrun'] = {'exit': rc, 'request_id': env.get('request_id') if isinstance(env, dict) else None}
dump()

rc, env = run(['function', 'apply', 'sgcc_fn_clarification', '--json'])
result['function_apply'] = {'exit': rc, 'data': (env.get('data') if isinstance(env, dict) else None)}
dump()

if result['function_apply']['exit'] == 0:
    rc, env = run(['function', 'describe', 'sgcc-clarification-table', '--json'])
    result['function_describe'] = {'exit': rc}
    inp_file = B + 'sgcc_fn_invoke_input.json'
    io.open(inp_file, 'w', encoding='utf-8').write(json.dumps(sample_in, ensure_ascii=False))
    rc, env = run(['function', 'invoke', 'sgcc-clarification-table', '--input', inp_file, '--json'])
    result['function_invoke'] = {'exit': rc, 'data': (env.get('data') if isinstance(env, dict) else None)}
    dump()

# ---------------------------------------------------------------- 3. Dataset：只建题目骨架，不填参考答案
DS_NAME = '国网Demo_L1题库_人工核对骨架_无参考答案'
rc, env = run(['dataset', 'list', '--json'])
existing = next((i for i in ((env.get('data') or {}).get('items') or []) if i.get('name') == DS_NAME), None)
if existing:
    ds_id = existing['id']
    result['dataset'] = {'reused': True, 'id': ds_id}
    print('DATASET reuse', ds_id)
else:
    rc, env = run(['dataset', 'create', '--name', DS_NAME,
                   '--description', 'L1 demo 8 题人工核对骨架：只有题目与标签，reference_answer 一律留空。业务方未核对前禁止用于自动评分/准确率。',
                   '--dry-run', '--json'])
    result['dataset_create_dryrun'] = {'exit': rc}
    rc, env = run(['dataset', 'create', '--name', DS_NAME,
                   '--description', 'L1 demo 8 题人工核对骨架：只有题目与标签，reference_answer 一律留空。业务方未核对前禁止用于自动评分/准确率。',
                   '--json'])
    ds_id = ((env.get('data') or {}).get('id')) if isinstance(env, dict) else None
    result['dataset'] = {'reused': False, 'id': ds_id, 'create_exit': rc}
    dump()

qa = json.load(io.open(B + 'sgcc_l1_results.json', encoding='utf-8'))['results']
if ds_id:
    added = 0
    for r in qa:
        item = {'question': r['question'], 'tags': ['L1-demo', '待业务方核对', r['name']],
                'metadata': {'turn_id': r.get('turn_id'), 'citations': r.get('citations'),
                             'reference_answer': None,
                             'note': '参考答案留空；业务方核对前不得自动评分'}}
        f = B + 'sgcc_ds_item.json'
        io.open(f, 'w', encoding='utf-8').write(json.dumps(item, ensure_ascii=False))
        rc, env = run(['dataset', 'item', 'add', ds_id, '--input', f, '--json'], timeout=90)
        if rc == 0:
            added += 1
    result['dataset']['items_added'] = added
    result['dataset']['items_total'] = len(qa)
    result['dataset']['reference_answer_filled'] = False
    rc, env = run(['dataset', 'get', ds_id, '--json'])
    result['dataset_get'] = {'exit': rc, 'data': (env.get('data') if isinstance(env, dict) else None)}
    dump()

result['boundaries'] = [
    'Dataset 不含参考答案，禁止 dataset eval / 准确率 / 8 题全过表述',
    'Skill 已启用但未挂 Agent，未改 Agent 行为，零效果实测',
    'Function 输出全部 CANDIDATE，executable=false，不作违规终局判定',
]
dump()
print('\nDONE ->', OUT)
