"""探针：一句话说明这个函数做什么、给谁用。"""

from pydantic import BaseModel, Field

from apemind_fn import Context


class Input(BaseModel):
    text: str = Field(description="要处理的文本")


class Output(BaseModel):
    result: str


def main(inp: Input, ctx: Context) -> Output:
    with ctx.step("处理", detail={"chars": len(inp.text)}):
        result = inp.text.strip()
    return Output(result=result)
