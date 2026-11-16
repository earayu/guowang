"""国网 Demo · 待澄清事项表生成（纯结构化转换，不做任何合规判定）。

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
