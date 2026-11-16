---
name: sgcc-rule-judge-invoke
description: 调用 46 条否决情形判定引擎（函数 sgcc-rule-judge）的调用路径、输入契约与结论解读纪律。涉及「这家投标人有没有触发否决情形 / 有几条判否 / 哪些待澄清 / 为什么判不了」时使用。含已在沙箱验证的 CLI 调用命令（本函数不经原生工具暴露，须走 run_command）。本技能规定怎么喂输入、怎么读四种结论状态、怎么对客表述，引擎结论不得由模型改写。
---

# 判定引擎调用纪律（sgcc-rule-judge）

## 它是什么、不是什么

- 是**确定性判定器**：46 条否决情形的判定式写成受限 DSL，算子白名单穷举，不用 eval/exec。
  同一份输入永远算出同一份结论，可回读每条规则用到哪几个字段、值是多少。
- **不是**裁决器：所有结论上限 `CANDIDATE`（候选）。是否构成否决，法定权力在评标委员会，
  引擎只给「合规条件成立 / 不成立 / 证不足 / 只能人判」。

遇到这类问题时，**先问有没有引擎结果**。有就直接引用，不要自己推理一遍再讲——
两条链路给出两套说法，是对客最危险的错误。

## 怎么调：唯一可行路径（已实测）

本函数**不会作为原生工具暴露**给你。你手上的工具只有
`load_capability / run_command / read_file / write_file / list_directory / persistent_storage`。
所以调用方式固定为：**用 `run_command` 执行平台 CLI**。

沙箱里已经装好 CLI（`/usr/local/bin/apemind`，v2.12.5），并且注入了 Agent 自己的身份凭证
（`APEMIND_SERVER_SOCKET`、`APEMIND_HARNESS_API_KEY`、`APEMIND_AGENT_ID`、`APEMIND_WORKSPACE`）。
它走本地 socket 通道，**不需要出网**——实测沙箱 `network.status=off`、`connections=0` 时
仍能正常返回，整条命令 338ms。所以「沙箱不能联网」不构成调不了的理由。

已实测通过的命令（照抄，只改值）：

```
apemind function invoke sgcc-rule-judge \
  --field 'bidder=宜昌三峡输变电设备有限公司' \
  --field 'facts={"bid.seal_present":true,"bid.seal_valid":true,"bid.seal_name":"宜昌三峡输变电设备有限公司","bid.bidder_name":"宜昌三峡输变电设备有限公司"}' \
  --field 'rule_ids=["GW-HB-FJ-004"]' \
  --json
```

- `--field` 的值按 JSON 解析；对象/数组类入参（`facts`、`rule_ids`、`*_fields`）就按上面的写法传整段 JSON。
- 入参长的时候改用文件更稳：`--input /workspace/facts.json`（`--input -` 读 stdin）。
- **出参在 `output` 里**，不在顶层：`{"data":{...,"output":{"rows":[...],"counts":{...},"rule_set":"V2","rule_set_sha":"..."}}}`。
  `data.elapsed_ms` 是函数内耗时，`data.status` 为 `succeeded` 才算跑通。

两种失败要分清，别混为一谈：

| 现象 | 含义 | 该怎么做 |
|---|---|---|
| `run_command was not run: no decision arrived in time` | 审批卡片没人点（助手开了写确认，无人值守场景必然超时） | **不是命令写错，不要重试同一条**。直接说明「执行审批未获批准，引擎未运行」，不要编结论 |
| `exit_code != 0` 且有 stderr | 命令本身错了（参数名、JSON 格式、规则号非法） | 贴 stderr 原文，按报错改 |

**绝不允许**在引擎没真正跑通的情况下，用历史结果、缓存或自己的推理顶上，
再把 `state` / `reason` / `sha` 写出来——那是编造。

## 输入契约

```
section_no      标包号，仅回填留痕（如 152507-1102002-4004）
bidder          受审投标人名称
tender_fields   基准侧抽取输出（sgcc-field-extract 的 fields 数组，原样传）
bid_fields      受审侧抽取输出（同上）
facts           已翻译好的扁平字段（键形如 bid.seal_name），与 *_fields 二选一
peer_facts      同标包其他投标人的事实，行32/39 必须给
rule_ids        只跑这些；空=全部 46 条
```

三条硬约束：

1. **`peer_facts` 不给，行 32（代理商重复）与行 39（法定代表人重复）必然转待澄清。**
   这不是 bug，是设计：组里只有自己时"组内无重复"永远成立，那是假绿。
2. **`rule_ids` 传错会直接报错，不会返回空结果。** 报错文案会列出未知的规则号与规则集版本。
   早先的行为是 `succeeded` + `total: 0`，那是最难发现的假绿——看着像"这家没有否决情形"。
3. **`rules` 与实际条数无关时不要想当然**：一次调用跑 1 条和跑 46 条耗时几乎相同
   （平台侧实测均约 245ms），因为那 245ms 是平台固定开销，不是逐条计算。
   所以**不要为了"省时间"裁规则**，要么全跑，要么按明确的业务范围裁。

## 四种结论状态，含义完全不同

| 状态 | 含义 | 对客怎么说 |
|---|---|---|
| `RESPONDED` | 合规条件成立，本条未触发 | 「未触发」 |
| `NOT_RESPONDED` | 合规条件不成立，本条情形成立 | 「触发（候选），需人工确认」 |
| `UNCERTAIN` | 缺字段 / 基准未结构化，证不足 | 「证不足，转待澄清」+ 缺什么、该谁补 |
| `NEED_HUMAN` | 结构上机器不能判（澄清、串标、外部信用、认定权） | 「只能人判」+ 证据出处 |

实测分布（6 家 × 46 条一致）：`RESPONDED 9 / NOT_RESPONDED 1 / UNCERTAIN 16 / NEED_HUMAN 21`。
**21 条 NEED_HUMAN 是法定边界，不是系统缺陷**，不要试图用模型补判；
**16 条 UNCERTAIN 才是可收口的部分**，其中约一半缺招标侧字段、一半缺投标侧字段。

## 读 `blocked_by`：待澄清不是一堆行号

`uncertain_rows` 只给行号（如 `[1,2,3,5,12,21,...]`），逐条列出来像 16 个互不相干的问题。
真正的结构在 `blocked_by`：

```json
{"field": "tender.avg_price_threshold_rule", "side": "tender", "rows": [46],
 "hint": "招标文件未给出该参数…只能人工对照原文补录"}
```

`side` 四档决定"该谁补"：

- `bid` 投标侧 —— 抽取未命中，可重抽或人工核对投标文件对应页
- `tender` 招标侧 —— 招标文件本身没给这个参数，只能人工补录
- `legal` 法规 / 名单 —— 库内通常没有，按外部渠道核验
- `platform` 库外数据 —— 递交日志、同包全量投标人等，系统内取不到

对客表述要落到这个粒度：「16 条待澄清里有 8 条缺招标侧参数（补不上就只能人工），
8 条缺投标侧字段（重抽可解决）」，比「大部分待澄清」有用得多。

## `warnings` 要读，但不用念给客户

三种输入降级会被显式记下：未传基准侧、未传 `peer_facts`、`bid_fields` 与 `facts` 同时传
（同名字段会被 `bid_fields` 覆盖）。前两种意味着结论覆盖不完整，
汇报时要说明"本次未传 X，所以 Y 类规则未判"，不能只报结论不提输入残缺。

## 引用引擎结论时的固定格式

每条结论带三样：`rule_id` + 行号 + 规则集版本与 sha（`rule_set` / `rule_set_sha`）。
少了 sha，事后无法回答"这个结论是哪版规则出的"。

对客话术模板：

> 第 10 行（最高限价）：触发（候选）。逐物料对位：物料 100035912200010 含税报价
> 4,600,000 元，限价 4,533,100 元，超 66,900 元。需评标委员会确认。
> 〔规则集 V2 · sha e80fd7b2〕

## 禁止事项

- 不得用模型推理改写引擎结论，也不得把 `UNCERTAIN` 说成「未见响应」。
- 不得在引擎没覆盖的问题上借用引擎的名义（引擎只覆盖这 46 条）。
- 不得把 `CANDIDATE` 表述成「已认定否决」。
- 不得省略 `rule_set_sha`；不得用缓存结果冒充本次运行（注意 `_source: snapshot` 的含义，
  它表示"输入指纹未变，复用上次结果"，不是重新算过）。
